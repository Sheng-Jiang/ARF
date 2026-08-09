"""Offline tests for arf.run pipeline helpers."""
from pathlib import Path

from arf.config import load_universe
from arf.db import init_db, query_pool_membership
from arf.run import _archive_active_pools

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
