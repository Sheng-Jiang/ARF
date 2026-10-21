"""Unit tests for China data proxy routing."""
import os
import threading
from unittest.mock import patch

import pytest
import requests

from arf.fetchers.proxy import get_china_proxy, use_china_proxy

PROXY = "socks5://127.0.0.1:10808"


def _fake_response(request: requests.PreparedRequest) -> requests.Response:
    resp = requests.Response()
    resp.status_code = 200
    resp.reason = "OK"
    resp.url = request.url
    resp.request = request
    resp.encoding = "utf-8"
    resp.headers["Content-Type"] = "application/json"
    resp._content = b"{}"
    return resp


def _send_via_requests(url: str) -> dict:
    """Issue a GET and return the proxies that would be used on the wire."""
    seen: dict = {}

    def fake_send(adapter, request, **kwargs):
        seen.update(kwargs.get("proxies") or {})
        return _fake_response(request)

    with patch("requests.adapters.HTTPAdapter.send", autospec=True, side_effect=fake_send):
        requests.get(url, timeout=1)
    return seen


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch):
    """No ambient proxy env and no real local tunnel during tests."""
    for key in ("ARF_CHINA_PROXY", "CHINA_DATA_PROXY", "ALL_PROXY", "HTTP_PROXY", "HTTPS_PROXY"):
        monkeypatch.delenv(key, raising=False)
        monkeypatch.delenv(key.lower(), raising=False)
    monkeypatch.setattr("arf.fetchers.proxy._is_local_port_open", lambda *a, **k: False)


class TestChinaProxy:
    def test_get_china_proxy_from_env(self, monkeypatch):
        assert get_china_proxy() is None

        # ARF_CHINA_PROXY takes priority
        monkeypatch.setenv("ARF_CHINA_PROXY", PROXY)
        assert get_china_proxy() == PROXY

        # CHINA_DATA_PROXY fallback
        monkeypatch.delenv("ARF_CHINA_PROXY")
        monkeypatch.setenv("CHINA_DATA_PROXY", "http://proxy.example.com:8080")
        assert get_china_proxy() == "http://proxy.example.com:8080"

    def test_get_china_proxy_ignores_general_all_proxy(self, monkeypatch):
        # A developer's global ALL_PROXY is usually an overseas VPN; it must
        # not be mistaken for the domestic China route.
        monkeypatch.setenv("ALL_PROXY", "socks5://127.0.0.1:7890")
        assert get_china_proxy() is None

    def test_get_china_proxy_auto_detect_socket(self):
        with patch("arf.fetchers.proxy._is_local_port_open", return_value=True):
            assert get_china_proxy() == PROXY

        with patch("arf.fetchers.proxy._is_local_port_open", return_value=False):
            assert get_china_proxy() is None

    def test_context_manager_routes_requests_without_touching_env(self, monkeypatch):
        monkeypatch.setenv("HTTP_PROXY", "http://original:8080")
        env_before = dict(os.environ)

        with use_china_proxy(PROXY) as active_proxy:
            assert active_proxy == PROXY
            routed = _send_via_requests("https://push2.eastmoney.com/api/qt/stock/kline/get")
            assert routed["http"] == PROXY
            assert routed["https"] == PROXY
            # Unrelated environment is untouched (no process-wide proxy window).
            assert os.environ["HTTP_PROXY"] == "http://original:8080"

        assert dict(os.environ) == env_before
        assert _current_proxy() is None

    def test_proxy_is_thread_scoped(self):
        """A concurrent US fetch must not inherit the China proxy."""
        started = threading.Event()
        release = threading.Event()
        us_proxies: dict = {}

        def us_fetch():
            started.set()
            release.wait(timeout=5)
            us_proxies.update(_send_via_requests("https://query1.finance.yahoo.com/v8/finance"))

        worker = threading.Thread(target=us_fetch)
        worker.start()
        try:
            with use_china_proxy(PROXY):
                started.wait(timeout=5)
                china = _send_via_requests("https://push2.eastmoney.com/api/qt")
                assert china["https"] == PROXY
                release.set()
                worker.join(timeout=5)
        finally:
            release.set()
            worker.join(timeout=5)

        assert us_proxies.get("https") != PROXY

    def test_no_proxy_configured_leaves_requests_alone(self):
        with use_china_proxy(None):
            assert _current_proxy() is None
            routed = _send_via_requests("https://push2.eastmoney.com/api/qt")
        assert PROXY not in routed.values()


def _current_proxy() -> str | None:
    from arf.fetchers.proxy import _current_thread_proxy

    return _current_thread_proxy()
