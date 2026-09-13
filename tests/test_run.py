"""Offline tests for arf.run pipeline helpers."""
from pathlib import Path

import pytest

from arf.config import load_universe
from arf.db import init_db, query_pool_membership
from arf.run import _archive_active_pools, _build_scoring_df

UNIVERSE_PATH = Path(__file__).parent.parent / "config" / "universe.yaml"


def test_archive_active_pools_writes_membership(tmp_path):
    conn = init_db(tmp_path / "t.db")
    universe = load_universe(UNIVERSE_PATH)
    _archive_active_pools(conn, universe)

    df = query_pool_membership(conn, "2026Q3")
    assert len(df) == 100  # US 50 + China 50
    assert len(df[df["cohort"] == "core"]) == 90
    assert len(df[df["cohort"] == "newcomer"]) == 10
    assert set(df["leg"].unique()) == {"US", "China"}
    conn.close()


def test_archive_active_pools_idempotent(tmp_path):
    conn = init_db(tmp_path / "t.db")
    universe = load_universe(UNIVERSE_PATH)
    _archive_active_pools(conn, universe)
    _archive_active_pools(conn, universe)
    assert len(query_pool_membership(conn, "2026Q3")) == 100
    conn.close()


def test_archive_excludes_watchlist_and_preipo(tmp_path):
    conn = init_db(tmp_path / "t.db")
    universe = load_universe(UNIVERSE_PATH)
    _archive_active_pools(conn, universe)
    members = query_pool_membership(conn, "2026Q3")
    tickers = set(members["ticker"])
    # Watchlist (GEV etc.) and Pre-IPO observation (SPACEX) must not be members.
    assert "GEV" not in tickers
    assert "SPACEX" not in tickers
    conn.close()


def test_scoring_df_carries_reporting_currency_into_reverse_dcf():
    """ADRs trade in USD but report in another currency (TSM: TWD). The fetcher
    records the reporting FX rate; if the pipeline drops it on the way to
    scoring, g* silently falls back to the trading rate and is off ~32x."""
    from datetime import date

    from arf.fetchers.base import StockData
    from arf.scoring import implied_growth_for_row

    sd = StockData(ticker="TSM", as_of_date=date(2026, 9, 13))
    sd.market_cap_usd = 1e9            # USD
    sd.free_cash_flow = 1.6e9          # TWD
    sd.currency, sd.fx_rate_usd = "USD", 1.0
    sd.financial_currency, sd.financial_fx_usd = "TWD", 32.0

    row = _build_scoring_df([sd], []).iloc[0]

    # Market cap in TWD = 32e9 → FCF yield 5% → g* = 10% − 5% = 5%.
    assert implied_growth_for_row(row, wacc=0.10) == pytest.approx(0.05)
