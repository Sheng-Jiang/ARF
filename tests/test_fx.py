"""Offline tests for arf.fetchers.fx — cache, fallback, and rate selection."""
from unittest.mock import patch

from arf.fetchers import fx


def _reset():
    fx.reset_fx_cache()


def test_fetch_fx_rates_uses_yfinance_values():
    _reset()
    with patch("arf.fetchers.fx._yf_rate", side_effect=[7.15, 7.80, 31.5]) as mock_rate:
        rates = fx.fetch_fx_rates()
        fetched = [c.args[0] for c in mock_rate.call_args_list]
        assert fetched == ["USDCNY=X", "USDHKD=X", "USDTWD=X"]
        assert rates["CNY"] == 7.15
        assert rates["HKD"] == 7.80
        assert rates["TWD"] == 31.5


def test_fetch_fx_rates_includes_usd_identity():
    """Callers look up any reporting currency; USD must not need special-casing."""
    _reset()
    with patch("arf.fetchers.fx._yf_rate", return_value=None):
        assert fx.fetch_fx_rates()["USD"] == 1.0


def test_fetch_fx_rates_falls_back_to_constants_on_failure():
    _reset()
    with patch("arf.fetchers.fx._yf_rate", side_effect=[None, None, None]):
        rates = fx.fetch_fx_rates()
        assert rates["CNY"] == fx.DEFAULT_CNY
        assert rates["HKD"] == fx.DEFAULT_HKD
        assert rates["TWD"] == fx.DEFAULT_TWD


def test_fetch_fx_rates_partial_fallback():
    _reset()
    with patch("arf.fetchers.fx._yf_rate", side_effect=[7.12, None, 31.5]):
        rates = fx.fetch_fx_rates()
        assert rates["CNY"] == 7.12
        assert rates["HKD"] == fx.DEFAULT_HKD
        assert rates["TWD"] == 31.5


def test_get_fx_rates_caches_single_fetch():
    _reset()
    with patch("arf.fetchers.fx._yf_rate", side_effect=[7.15, 7.80, 31.5]) as mock_rate:
        first = fx.get_fx_rates()
        second = fx.get_fx_rates()
        assert first is second  # same cached dict object
        assert mock_rate.call_count == 3  # one per currency, never re-fetched


def test_yf_rate_returns_none_on_network_error():
    _reset()
    # _yf_rate_once lets the error escape so tenacity can retry it; _yf_rate
    # converts the exhausted RetryError into None (→ fallback constant).
    with patch("yfinance.Ticker", side_effect=RuntimeError("network down")):
        assert fx._yf_rate("USDCNY=X") is None


def test_yf_rate_once_retries_then_succeeds():
    """The @retry decorator is only live if exceptions escape _yf_rate_once."""
    _reset()
    ok = type("T", (), {"info": {"regularMarketPrice": 7.11}, "fast_info": {}})()
    with patch("yfinance.Ticker", side_effect=[RuntimeError("flaky"), ok]) as mock_ticker:
        assert fx._yf_rate("USDCNY=X") == 7.11
        assert mock_ticker.call_count == 2


def test_yf_rate_returns_none_on_empty_info():
    _reset()
    with patch("yfinance.Ticker") as mock_ticker:
        mock_ticker.return_value.info = {}
        # fast_info must not return a MagicMock (its __float__ is 1.0).
        mock_ticker.return_value.fast_info = {"lastPrice": None}
        assert fx._yf_rate("USDCNY=X") is None
