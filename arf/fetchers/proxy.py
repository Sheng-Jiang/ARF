"""Proxy routing utilities for China leg financial data ingestion.

Mainland China financial data sources (AkShare, Eastmoney, Tencent, Sina)
frequently geo-block or rate-limit requests originating from non-mainland IP
addresses (e.g. GCP asia-east1 or overseas developer machines).

This module provides scoped proxy management to route China-specific data
fetches through the domestic Tencent Cloud Lighthouse node (82.156.75.194)
either via an authenticated proxy URL or a local SSH SOCKS5 tunnel.
"""
from __future__ import annotations

import contextlib
import logging
import os
import socket
from collections.abc import Iterator

log = logging.getLogger(__name__)

# Default port for local SSH SOCKS5 tunnel started via scripts/tunnel_china.sh
DEFAULT_LOCAL_SOCKS_PORT = 10808
_PROXY_ENV_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
)


def _is_local_port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.15) -> bool:
    """Quick probe to see if a local port has a listening socket."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, TimeoutError):
        return False


def get_china_proxy() -> str | None:
    """Determine the active proxy URL for China data ingestion.

    Checks in order:
    1. ``ARF_CHINA_PROXY`` environment variable
    2. ``CHINA_DATA_PROXY`` environment variable
    3. ``ALL_PROXY`` environment variable
    4. Auto-detects local SSH SOCKS5 tunnel on 127.0.0.1:10808 (via scripts/tunnel_china.sh)
    """
    for env_var in ("ARF_CHINA_PROXY", "CHINA_DATA_PROXY", "ALL_PROXY"):
        val = os.getenv(env_var)
        if val and val.strip():
            return val.strip()

    # Fallback: check if local developer SSH tunnel is active
    if _is_local_port_open(DEFAULT_LOCAL_SOCKS_PORT):
        proxy = f"socks5://127.0.0.1:{DEFAULT_LOCAL_SOCKS_PORT}"
        log.debug("Auto-detected active local China proxy tunnel on %s", proxy)
        return proxy

    return None


@contextlib.contextmanager
def use_china_proxy(proxy_url: str | None = None) -> Iterator[str | None]:
    """Context manager to route operations through a domestic China proxy.

    Temporarily sets HTTP_PROXY, HTTPS_PROXY, and ALL_PROXY for standard
    libraries (requests, urllib, httpx, akshare), restoring original
    environment variables upon exit.

    Example::

        with use_china_proxy():
            df = ak.stock_zh_a_hist_tx(symbol="sz300308", ...)
    """
    proxy = proxy_url or get_china_proxy()
    if not proxy:
        yield None
        return

    orig_env = {k: os.environ.get(k) for k in _PROXY_ENV_KEYS}
    for k in _PROXY_ENV_KEYS:
        os.environ[k] = proxy

    try:
        log.debug("Routing China financial data fetch through proxy: %s", proxy)
        yield proxy
    finally:
        for k, v in orig_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
