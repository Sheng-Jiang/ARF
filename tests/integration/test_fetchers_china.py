"""Integration tests for the China fetcher — Baostock (A-shares) and yfinance (HK/ADR)."""
import pytest

from arf.config import UniverseEntry
from arf.fetchers.china import fetch_china


@pytest.mark.integration
class TestFetchChina:
    def test_fetch_innolite_returns_price_and_ratios(self, today):
        entry = UniverseEntry(
            ticker="300308.SZ", name="中际旭创 InnoLight", leg="China", layer="L3",
            pure_play_pct=95, primary_exchange="SZSE", policy_premium=False,
        )
        result = fetch_china(entry, today)
        assert result.ticker == "300308.SZ"
        assert result.price is not None, "InnoLight price should be non-null"
        assert result.market_cap_usd is not None, "InnoLight market_cap_usd should be non-null"
        assert result.data_source == "baostock"

    def test_fetch_innolite_fundamentals_populated(self, today):
        entry = UniverseEntry(
            ticker="300308.SZ", name="中际旭创 InnoLight", leg="China", layer="L3",
            pure_play_pct=95, primary_exchange="SZSE", policy_premium=False,
        )
        result = fetch_china(entry, today)
        assert result.gross_margin is not None, "gross_margin should be populated from baostock"
        assert 0 < result.gross_margin < 1, f"gross_margin={result.gross_margin} should be 0–1"
        assert result.roe is not None, "ROE should be populated from baostock"

    def test_fetch_innolite_ev_sales_percentile_populated(self, today):
        entry = UniverseEntry(
            ticker="300308.SZ", name="中际旭创 InnoLight", leg="China", layer="L3",
            pure_play_pct=95, primary_exchange="SZSE", policy_premium=False,
        )
        result = fetch_china(entry, today)
        assert result.ev_sales_5yr_percentile is not None, (
            "ev_sales_5yr_percentile should be computed from 5yr P/S history"
        )
        assert 0 <= result.ev_sales_5yr_percentile <= 100

    def test_fetch_cambricon_revenue_growth_extreme(self, today):
        entry = UniverseEntry(
            ticker="688256.SH", name="寒武纪 Cambricon", leg="China", layer="L2",
            pure_play_pct=95, primary_exchange="SSE", policy_premium=True,
        )
        result = fetch_china(entry, today)
        assert result.ticker == "688256.SH"
        assert result.price is not None, "Cambricon price should be non-null from baostock"
        if result.revenue_yoy_growth is not None:
            assert result.revenue_yoy_growth > 1.0, (
                f"Cambricon YoY growth={result.revenue_yoy_growth:.1%}, expected >100%"
            )

    def test_fetch_hk_tencent_returns_data(self, today):
        entry = UniverseEntry(
            ticker="0700.HK", name="腾讯 Tencent", leg="China", layer="L5",
            pure_play_pct=20, primary_exchange="HKEX", policy_premium=False,
        )
        result = fetch_china(entry, today)
        assert result.ticker == "0700.HK"
        assert result.price is not None, "Tencent HK price should be non-null"
        assert result.data_source == "yfinance"

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
        assert result.price is not None, "GDS ADR price should be non-null"
