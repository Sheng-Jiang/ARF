"""Unit tests for China data proxy routing."""
import os
from unittest.mock import patch

from arf.fetchers.proxy import (
    _PROXY_ENV_KEYS,
    get_china_proxy,
    use_china_proxy,
)


class TestChinaProxy:
    def test_get_china_proxy_from_env(self, monkeypatch):
        # Clear existing env vars
        for k in _PROXY_ENV_KEYS:
            monkeypatch.delenv(k, raising=False)
        monkeypatch.delenv("ARF_CHINA_PROXY", raising=False)
        monkeypatch.delenv("CHINA_DATA_PROXY", raising=False)

        assert get_china_proxy() is None

        # ARF_CHINA_PROXY takes priority
        monkeypatch.setenv("ARF_CHINA_PROXY", "socks5://127.0.0.1:10808")
        assert get_china_proxy() == "socks5://127.0.0.1:10808"

        # CHINA_DATA_PROXY fallback
        monkeypatch.delenv("ARF_CHINA_PROXY")
        monkeypatch.setenv("CHINA_DATA_PROXY", "http://proxy.example.com:8080")
        assert get_china_proxy() == "http://proxy.example.com:8080"

    def test_get_china_proxy_auto_detect_socket(self, monkeypatch):
        for k in ("ARF_CHINA_PROXY", "CHINA_DATA_PROXY", "ALL_PROXY"):
            monkeypatch.delenv(k, raising=False)

        with patch("arf.fetchers.proxy._is_local_port_open", return_value=True):
            assert get_china_proxy() == "socks5://127.0.0.1:10808"

        with patch("arf.fetchers.proxy._is_local_port_open", return_value=False):
            assert get_china_proxy() is None

    def test_use_china_proxy_context_manager(self, monkeypatch):
        for k in _PROXY_ENV_KEYS:
            monkeypatch.delenv(k, raising=False)
        monkeypatch.setenv("HTTP_PROXY", "http://original:8080")

        # When no proxy is configured, env is untouched
        with use_china_proxy(None):
            assert os.environ.get("HTTP_PROXY") == "http://original:8080"
            assert os.environ.get("ALL_PROXY") is None

        # When proxy is passed, env is scoped
        target_proxy = "socks5://127.0.0.1:10808"
        with use_china_proxy(target_proxy) as active_proxy:
            assert active_proxy == target_proxy
            assert os.environ["HTTP_PROXY"] == target_proxy
            assert os.environ["HTTPS_PROXY"] == target_proxy
            assert os.environ["ALL_PROXY"] == target_proxy

        # Original environment restored cleanly
        assert os.environ.get("HTTP_PROXY") == "http://original:8080"
        assert "HTTPS_PROXY" not in os.environ
        assert "ALL_PROXY" not in os.environ
