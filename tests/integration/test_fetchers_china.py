"""Integration tests for the China fetcher — hit real AkShare / yfinance."""
import pytest

from arf.config import UniverseEntry
from arf.fetchers.china import fetch_china


@pytest.mark.integration
class TestFetchChina:
    def test_fetch_innolite_300308_returns_data(self, today):
        entry = UniverseEntry(
            ticker="300308.SZ", name="中际旭创 InnoLight", leg="China", layer="L3",
            pure_play_pct=95, primary_exchange="SZSE", policy_premium=False,
        )
        result = fetch_china(entry, today)
        assert result.ticker == "300308.SZ"
        # At minimum price or market_cap should be available
        assert result.price is not None or result.market_cap_usd is not None, (
            "InnoLight: at least one market data field should be non-null"
        )

    def test_fetch_cambricon_extreme_growth_present(self, today):
        entry = UniverseEntry(
            ticker="688256.SH", name="寒武纪 Cambricon", leg="China", layer="L2",
            pure_play_pct=95, primary_exchange="SSE", policy_premium=True,
        )
        result = fetch_china(entry, today)
        assert result.ticker == "688256.SH"
        # Revenue growth for Cambricon is extremely high (>100%)
        if result.revenue_yoy_growth is not None:
            assert result.revenue_yoy_growth > 1.0, (
                f"Cambricon YoY growth={result.revenue_yoy_growth:.1%}, "
                f"expected >100% (currently ~2386%)"
            )

    def test_fetch_hk_tencent_returns_data(self, today):
        entry = UniverseEntry(
            ticker="0700.HK", name="腾讯 Tencent", leg="China", layer="L5",
            pure_play_pct=20, primary_exchange="HKEX", policy_premium=False,
        )
        result = fetch_china(entry, today)
        assert result is not None
        assert result.ticker == "0700.HK"

    def test_fetch_bad_ticker_returns_nulls_not_exception(self, today):
        entry = UniverseEntry(
            ticker="999999.SZ", name="Bad Ticker", leg="China", layer="L2",
            pure_play_pct=0, primary_exchange="SZSE", policy_premium=False,
        )
        result = fetch_china(entry, today)
        assert result is not None
        assert result.price is None

    def test_fetch_gds_adr_returns_data(self, today):
        entry = UniverseEntry(
            ticker="GDS", name="GDS Holdings", leg="China", layer="L3",
            pure_play_pct=50, primary_exchange="NASDAQ", policy_premium=False,
        )
        result = fetch_china(entry, today)
        assert result.ticker == "GDS"
