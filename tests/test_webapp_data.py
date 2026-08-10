"""Offline tests for webapp.data — quarterly pool loading and its config fallback."""
from datetime import date

import duckdb
import pytest

from arf.db import _SCHEMA_POOL_CHANGES, _SCHEMA_POOL_MEMBERSHIP, upsert_pool_membership
from webapp import data as webapp_data

UNIVERSE_YAML = """\
# test universe
- ticker: NVDA
  name: NVIDIA
  leg: US
  layer: L2
  pure_play_pct: 80
  primary_exchange: NASDAQ
  policy_premium: false
  cohort: core
  pool: '2026Q3'
  listed_at: '1999-01-22'
- ticker: CRWV
  name: CoreWeave
  leg: US
  layer: L3
  pure_play_pct: 95
  primary_exchange: NASDAQ
  policy_premium: false
  cohort: newcomer
  pool: '2026Q3'
  listed_at: '2025-03-28'
- ticker: GEV
  name: GE Vernova
  leg: US
  layer: L1
  pure_play_pct: 30
  primary_exchange: NYSE
  policy_premium: false
  cohort: watch
  pool: null
  listed_at: '2024-04-02'
"""


@pytest.fixture
def wired(tmp_path, monkeypatch):
    """webapp.data pointed at an empty in-memory DB and a small universe.yaml."""
    conn = duckdb.connect(":memory:")
    conn.execute(_SCHEMA_POOL_MEMBERSHIP)
    conn.execute(_SCHEMA_POOL_CHANGES)

    universe = tmp_path / "universe.yaml"
    universe.write_text(UNIVERSE_YAML, encoding="utf-8")

    monkeypatch.setattr(webapp_data, "_open_conn", lambda: conn)
    monkeypatch.setattr(webapp_data, "UNIVERSE_PATH", universe)
    yield conn
    conn.close()


class TestPoolConfigFallback:
    """pool_membership is only written by a full pipeline run.

    Until one happens the roster still exists in universe.yaml, so the page
    must serve that rather than showing an empty pool.
    """

    def test_list_pool_ids_includes_the_config_pool(self, wired):
        assert webapp_data.list_pool_ids() == ["2026Q3"]

    def test_membership_falls_back_to_universe_yaml(self, wired):
        members = webapp_data.load_pool_membership("2026Q3")
        assert set(members["ticker"]) == {"NVDA", "CRWV"}  # GEV is watchlist
        assert dict(zip(members["ticker"], members["cohort"], strict=True)) == {
            "NVDA": "core", "CRWV": "newcomer",
        }
        assert not webapp_data.pool_membership_is_archived("2026Q3")

    def test_fallback_matches_the_table_shape(self, wired):
        """The page reads these columns regardless of where the rows came from."""
        assert list(webapp_data.load_pool_membership("2026Q3").columns) == [
            "pool_id", "ticker", "leg", "cohort", "listed_at", "added_at", "reason",
        ]

    def test_archived_rows_win_over_config(self, wired):
        upsert_pool_membership(wired, "2026Q3", [
            {"ticker": "NVDA", "leg": "US", "cohort": "core",
             "listed_at": date(1999, 1, 22), "reason": "pipeline archive"},
        ])
        members = webapp_data.load_pool_membership("2026Q3")
        assert set(members["ticker"]) == {"NVDA"}
        assert members.iloc[0]["reason"] == "pipeline archive"
        assert webapp_data.pool_membership_is_archived("2026Q3")

    def test_default_pool_id_is_the_newest(self, wired):
        upsert_pool_membership(wired, "2026Q2", [
            {"ticker": "OLD", "leg": "US", "cohort": "core",
             "listed_at": None, "reason": "archive"},
        ])
        assert webapp_data.list_pool_ids() == ["2026Q3", "2026Q2"]
        # 2026Q3 has no archived rows, so the default resolves to the fallback.
        assert set(webapp_data.load_pool_membership()["ticker"]) == {"NVDA", "CRWV"}

    def test_missing_config_is_not_fatal(self, wired, tmp_path, monkeypatch):
        monkeypatch.setattr(webapp_data, "UNIVERSE_PATH", tmp_path / "nope.yaml")
        assert webapp_data.list_pool_ids() == []
        assert webapp_data.load_pool_membership().empty
