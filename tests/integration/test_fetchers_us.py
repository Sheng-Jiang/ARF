"""Integration tests for the US fetcher — hit real yfinance and stockanalysis.com."""
import pytest

from arf.config import UniverseEntry
from arf.fetchers.us import fetch_us


@pytest.mark.integration
class TestFetchUS:
    def test_fetch_nvda_returns_required_fields(self, today):
        entry = UniverseEntry(
            ticker="NVDA", name="NVIDIA", leg="US", layer="L2",
            pure_play_pct=90, primary_exchange="NASDAQ", policy_premium=False,
        )
        result = fetch_us(entry, today)
        assert result.price is not None, "NVDA price should be non-null"
        assert result.market_cap_usd is not None, "NVDA market_cap_usd should be non-null"
        assert result.ps_ratio is not None, "NVDA ps_ratio should be non-null"
        assert result.roe is not None, "NVDA roe should be non-null"
        assert result.ticker == "NVDA"

    def test_fetch_handles_bad_ticker_gracefully(self, today):
        entry = UniverseEntry(
            ticker="ZZZZZZ_BAD", name="Bad Ticker", leg="US", layer="L2",
            pure_play_pct=0, primary_exchange="NASDAQ", policy_premium=False,
        )
        result = fetch_us(entry, today)
        # Must not raise; price should be None
        assert result is not None
        assert result.price is None

    def test_fetch_pltr_has_high_ps_ratio(self, today):
        entry = UniverseEntry(
            ticker="PLTR", name="Palantir", leg="US", layer="L5",
            pure_play_pct=80, primary_exchange="NYSE", policy_premium=False,
        )
        result = fetch_us(entry, today)
        if result.ps_ratio is not None:
            assert result.ps_ratio > 20, f"PLTR P/S={result.ps_ratio}, expected >20"

    def test_fetch_csco_has_reasonable_forward_pe(self, today):
        entry = UniverseEntry(
            ticker="CSCO", name="Cisco", leg="US", layer="L3",
            pure_play_pct=20, primary_exchange="NASDAQ", policy_premium=False,
        )
        result = fetch_us(entry, today)
        if result.forward_pe is not None:
            assert result.forward_pe < 50, f"CSCO fwd P/E={result.forward_pe}, expected <50"

    def test_fetch_returns_stock_data_with_ticker(self, today):
        entry = UniverseEntry(
            ticker="MSFT", name="Microsoft", leg="US", layer="L5",
            pure_play_pct=35, primary_exchange="NASDAQ", policy_premium=False,
        )
        result = fetch_us(entry, today)
        assert result.ticker == "MSFT"
        assert result.currency in ("USD", "")
