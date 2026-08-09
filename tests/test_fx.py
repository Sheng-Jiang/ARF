"""Offline tests for arf.fetchers.fx — cache, fallback, and rate selection."""
from unittest.mock import patch

from arf.fetchers import fx


def _reset():
    fx.reset_fx_cache()


def test_fetch_fx_rates_uses_yfinance_values():
    _reset()
    with patch("arf.fetchers.fx._yf_rate", side_effect=[7.15, 7.80]) as mock_rate:
        rates = fx.fetch_fx_rates()
        assert mock_rate.call_args_list[0].args[0] == "USDCNY=X"
        assert mock_rate.call_args_list[1].args[0] == "USDHKD=X"
        assert rates["CNY"] == 7.15
        assert rates["HKD"] == 7.80


def test_fetch_fx_rates_falls_back_to_constants_on_failure():
    _reset()
    with patch("arf.fetchers.fx._yf_rate", side_effect=[None, None]):
        rates = fx.fetch_fx_rates()
        assert rates["CNY"] == fx.DEFAULT_CNY
        assert rates["HKD"] == fx.DEFAULT_HKD


def test_fetch_fx_rates_partial_fallback():
    _reset()
    with patch("arf.fetchers.fx._yf_rate", side_effect=[7.12, None]):
        rates = fx.fetch_fx_rates()
        assert rates["CNY"] == 7.12
        assert rates["HKD"] == fx.DEFAULT_HKD


def test_get_fx_rates_caches_single_fetch():
    _reset()
    with patch("arf.fetchers.fx._yf_rate", side_effect=[7.15, 7.80]) as mock_rate:
        first = fx.get_fx_rates()
        second = fx.get_fx_rates()
        assert first is second  # same cached dict object
        assert mock_rate.call_count == 2  # one per currency, never re-fetched


def test_yf_rate_returns_none_on_network_error():
    _reset()
    # _yf_rate imports yfinance lazily and catches Exception internally, so a
    # throwing Ticker must yield None (which fetch_fx_rates turns into constants).
    with patch("yfinance.Ticker", side_effect=RuntimeError("network down")):
        assert fx._yf_rate("USDCNY=X") is None


def test_yf_rate_returns_none_on_empty_info():
    _reset()
    with patch("yfinance.Ticker") as mock_ticker:
        mock_ticker.return_value.info = {}
        # fast_info must not return a MagicMock (its __float__ is 1.0).
        mock_ticker.return_value.fast_info = {"lastPrice": None}
        assert fx._yf_rate("USDCNY=X") is None
