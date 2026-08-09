"""Offline tests for arf.pool — rotation scoring, planning, applying, reporting."""
from datetime import date

import pandas as pd

from arf.pool import (
    apply_rotation,
    build_rotation_plan,
    entrant_scores,
    generate_rotation_report,
    inactivity_scores,
    next_quarter_id,
)


def _snapshots() -> pd.DataFrame:
    """Two snapshot dates; rows carry the QUALITY_FIELDS plus cohort."""
    rows = []
    for as_of in (date(2026, 7, 19), date(2026, 7, 26)):
        for t in ("NVDA", "CSCO", "CRWV", "688256.SH"):
            rows.append({
                "ticker": t,
                "as_of_date": as_of,
                "leg": "US" if t != "688256.SH" else "China",
                "cohort": "newcomer" if t == "CRWV" else "core",
                "price": 100.0,
                "roe": 0.2,
                "ps_ratio": 10.0,
                "arf": 55.0 if t == "CSCO" else 80.0,
            })
    return pd.DataFrame(rows)


def _prices() -> pd.DataFrame:
    """90 days of prices; NVDA liquid, CSCO dead (tiny volume), CRWV no data."""
    dates = pd.date_range("2026-04-01", periods=90, freq="D").date
    rows = []
    for d in dates:
        for t, vol in (("NVDA", 1_000_000), ("CSCO", 1_000), ("688256.SH", 200_000)):
            rows.append({"ticker": t, "date": d, "close": 50.0, "volume": vol})
    return pd.DataFrame(rows)


class TestInactivityScores:
    def test_liquidity_axis_flags_dead_name(self):
        df = inactivity_scores(_snapshots(), _prices())
        by = df.set_index("ticker")
        # CSCO's tiny volume → poor liquidity → high inactivity score.
        assert by.loc["CSCO", "liquidity_score"] > by.loc["NVDA", "liquidity_score"]
        # CRWV has no price history → neutral liquidity.
        assert by.loc["CRWV", "liquidity_score"] == 50.0

    def test_composite_score_ranks_dead_name_highest(self):
        df = inactivity_scores(_snapshots(), _prices())
        by = df.set_index("ticker")
        assert by.loc["CSCO", "inactivity_score"] > by.loc["NVDA", "inactivity_score"]


class TestEntrantScores:
    class _E:
        def __init__(self, ticker, leg, cohort="watch", listed_at=None):
            self.ticker = ticker
            self.leg = leg
            self.cohort = cohort
            self.listed_at = listed_at

    def test_new_listing_is_auto_candidate(self):
        e = self._E("NEWCO", "US", listed_at=date(2026, 2, 1))
        df = entrant_scores([e], _prices(), as_of=date(2026, 8, 1))
        row = df.iloc[0]
        assert row["new_listing_score"] == 100.0
        assert row["cohort"] == "newcomer"

    def test_old_listing_not_newcomer(self):
        e = self._E("OLDCO", "US", listed_at=date(2019, 1, 1))
        df = entrant_scores([e], _prices(), as_of=date(2026, 8, 1))
        assert df.iloc[0]["new_listing_score"] == 0.0
        assert df.iloc[0]["cohort"] == "core"


class TestRotationPlan:
    def test_1to1_cohort_matching(self):
        inactive = pd.DataFrame([
            {"ticker": "CSCO", "leg": "US", "cohort": "core", "inactivity_score": 80},
            {"ticker": "CRWV", "leg": "US", "cohort": "newcomer", "inactivity_score": 70},
        ])
        entrants = pd.DataFrame([
            {"ticker": "GEV", "leg": "US", "cohort": "core", "entrant_score": 90},
            {"ticker": "NEWUP", "leg": "US", "cohort": "newcomer", "entrant_score": 95},
        ])
        plan = build_rotation_plan(inactive, entrants)
        assert plan["US"]["out"] == ["CSCO", "CRWV"]
        assert plan["US"]["in"] == ["GEV", "NEWUP"]
        assert len(plan["US"]["out"]) == len(plan["US"]["in"])

    def test_max_per_leg_caps_swaps(self):
        inactive = pd.DataFrame([
            {"ticker": f"T{i}", "leg": "US", "cohort": "core", "inactivity_score": 90 - i}
            for i in range(6)
        ])
        entrants = pd.DataFrame([
            {"ticker": f"C{i}", "leg": "US", "cohort": "core", "entrant_score": 90 - i}
            for i in range(6)
        ])
        plan = build_rotation_plan(inactive, entrants, max_per_leg=3)
        assert len(plan["US"]["out"]) == 3
        assert len(plan["US"]["in"]) == 3

    def test_insufficient_candidates_limits_swaps(self):
        inactive = pd.DataFrame([
            {"ticker": "A", "leg": "China", "cohort": "core", "inactivity_score": 90},
            {"ticker": "B", "leg": "China", "cohort": "core", "inactivity_score": 85},
        ])
        entrants = pd.DataFrame([
            {"ticker": "X", "leg": "China", "cohort": "core", "entrant_score": 90},
        ])
        plan = build_rotation_plan(inactive, entrants)
        assert len(plan["China"]["out"]) == 1
        assert len(plan["China"]["in"]) == 1


class TestApplyRotation:
    def test_updates_pool_fields_and_preserves_header(self, tmp_path):
        text = (
            "# ARF Seed Universe\n# header comment\n\n"
            "- ticker: CSCO\n  name: Cisco\n  leg: US\n  cohort: core\n  pool: '2026Q3'\n"
            "  pure_play_pct: 20\n  primary_exchange: NASDAQ\n  policy_premium: false\n"
            "  listed_at: null\n  notes: ''\n"
            "- ticker: GEV\n  name: GE Vernova\n  leg: US\n  cohort: watch\n  pool: null\n"
            "  pure_play_pct: 30\n  primary_exchange: NYSE\n  policy_premium: false\n"
            "  listed_at: '2024-04-02'\n  notes: ''\n"
        )
        path = tmp_path / "universe.yaml"
        path.write_text(text, encoding="utf-8")

        plan = {"US": {"out": ["CSCO"], "in": ["GEV"]}}
        entrants = pd.DataFrame([
            {"ticker": "GEV", "leg": "US", "cohort": "core", "entrant_score": 90},
        ])
        changed = apply_rotation(path, plan, "2026Q4", entrants)

        assert {"ticker": "CSCO", "leg": "US", "direction": "out"} in changed
        assert {"ticker": "GEV", "leg": "US", "direction": "in"} in changed

        import yaml

        data = yaml.safe_load(path.read_text())
        by = {e["ticker"]: e for e in data}
        assert by["CSCO"]["pool"] is None
        assert by["CSCO"]["cohort"] == "watch"
        assert by["GEV"]["pool"] == "2026Q4"
        assert by["GEV"]["cohort"] == "core"
        # Leading comments preserved.
        assert path.read_text().startswith("# ARF Seed Universe")


class TestRotationReport:
    def test_report_contains_swaps(self):
        plan = {"US": {"out": ["CSCO"], "in": ["GEV"]}, "China": {"out": [], "in": []}}
        inactive = pd.DataFrame([
            {"ticker": "CSCO", "leg": "US", "inactivity_score": 80.0,
             "liquidity_score": 95.0, "quality_score": 0.0,
             "fade_score": 100.0, "inertia_score": 50.0},
        ])
        entrants = pd.DataFrame([
            {"ticker": "GEV", "leg": "US", "entrant_score": 90.0,
             "new_listing_score": 0.0, "liquidity_score": 80.0, "heat_score": 50.0},
        ])
        report = generate_rotation_report(
            plan, inactive, entrants, as_of=date(2026, 10, 1), pool_id="2026Q4"
        )
        assert "2026Q4" in report
        assert "CSCO" in report
        assert "GEV" in report
        assert "换出" in report and "换入" in report


class TestQuarterId:
    def test_next_quarter(self):
        assert next_quarter_id(date(2026, 8, 9)) == "2026Q4"
        assert next_quarter_id(date(2026, 10, 1)) == "2027Q1"
        assert next_quarter_id(date(2026, 1, 5)) == "2026Q2"
