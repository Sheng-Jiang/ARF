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


class TestFadeScore:
    """Volume fade compares the last 30 bars against the 60 bars before them."""

    @staticmethod
    def _fading(recent_vol: float, prior_vol: float) -> pd.DataFrame:
        dates = pd.date_range("2026-04-01", periods=90, freq="D").date
        return pd.DataFrame([
            {"ticker": "FADE", "date": d, "close": 50.0,
             "volume": prior_vol if i < 60 else recent_vol}
            for i, d in enumerate(dates)
        ])

    def test_halved_volume_scores_worse_than_missing_data(self):
        from arf.pool import NEUTRAL, _fade_score

        score = _fade_score(self._fading(recent_vol=500, prior_vol=1000), "FADE")
        # Windows must not overlap: a 90-bar "prior" containing the recent 30
        # yields ratio 0.6 → 40, which ranks a genuinely fading name as *less*
        # faded than one with no data at all.
        assert score == 50.0 * 1.0  # (1 - 0.5) * 100
        assert score > NEUTRAL - 1e-9

    def test_flat_volume_scores_zero_fade(self):
        from arf.pool import _fade_score

        assert _fade_score(self._fading(recent_vol=1000, prior_vol=1000), "FADE") == 0.0

    def test_row_order_does_not_change_the_score(self):
        """daily_prices has no ORDER BY guarantee, so windows must sort first."""
        from arf.pool import _fade_score

        prices = self._fading(recent_vol=500, prior_vol=1000)
        shuffled = prices.sample(frac=1.0, random_state=0).reset_index(drop=True)
        assert _fade_score(shuffled, "FADE") == _fade_score(prices, "FADE")


class TestTurnoverOrdering:
    def test_turnover_uses_the_latest_bars_regardless_of_row_order(self):
        from arf.pool import _turnover

        dates = pd.date_range("2026-01-01", periods=120, freq="D").date
        # Old bars are heavily traded, the recent 90 are thin.
        prices = pd.DataFrame([
            {"ticker": "T", "date": d, "close": 10.0,
             "volume": 1_000_000 if i < 30 else 1_000}
            for i, d in enumerate(dates)
        ])
        expected = 10.0 * 1_000
        shuffled = prices.sample(frac=1.0, random_state=1).reset_index(drop=True)
        assert _turnover(shuffled, "T") == expected
        assert _turnover(prices, "T") == expected


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

    def test_retained_members_move_to_the_new_pool_id(self, tmp_path):
        """The pool id names the whole roster, not just the swapped-in names.

        Leaving retained members on the old id splits one roster across two
        pool ids, so pool_membership for the new quarter would hold only the
        handful of entrants and the app would report a 1-name pool.
        """
        text = (
            "# ARF Seed Universe\n\n"
            "- ticker: KEEP1\n  name: Keep One\n  leg: US\n  cohort: core\n"
            "  pool: '2026Q3'\n  pure_play_pct: 20\n  primary_exchange: NASDAQ\n"
            "  policy_premium: false\n  listed_at: null\n  notes: ''\n"
            "- ticker: KEEP2\n  name: Keep Two\n  leg: China\n  cohort: newcomer\n"
            "  pool: '2026Q3'\n  pure_play_pct: 40\n  primary_exchange: SSE\n"
            "  policy_premium: false\n  listed_at: null\n  notes: ''\n"
            "- ticker: DROP\n  name: Drop Me\n  leg: US\n  cohort: core\n"
            "  pool: '2026Q3'\n  pure_play_pct: 20\n  primary_exchange: NASDAQ\n"
            "  policy_premium: false\n  listed_at: null\n  notes: ''\n"
            "- ticker: ADD\n  name: Add Me\n  leg: US\n  cohort: watch\n  pool: null\n"
            "  pure_play_pct: 30\n  primary_exchange: NYSE\n  policy_premium: false\n"
            "  listed_at: '2024-04-02'\n  notes: ''\n"
            "- ticker: BENCH\n  name: Stay Out\n  leg: US\n  cohort: watch\n  pool: null\n"
            "  pure_play_pct: 10\n  primary_exchange: NYSE\n  policy_premium: false\n"
            "  listed_at: null\n  notes: ''\n"
        )
        path = tmp_path / "universe.yaml"
        path.write_text(text, encoding="utf-8")

        plan = {"US": {"out": ["DROP"], "in": ["ADD"]}}
        entrants = pd.DataFrame([
            {"ticker": "ADD", "leg": "US", "cohort": "core", "entrant_score": 90},
        ])
        changed = apply_rotation(path, plan, "2026Q4", entrants)

        import yaml

        by = {e["ticker"]: e for e in yaml.safe_load(path.read_text())}
        assert by["KEEP1"]["pool"] == "2026Q4"
        assert by["KEEP2"]["pool"] == "2026Q4"
        assert by["ADD"]["pool"] == "2026Q4"
        assert by["DROP"]["pool"] is None
        assert by["BENCH"]["pool"] is None  # never in the pool, stays out
        # Retention is not a rotation event.
        assert {c["ticker"] for c in changed} == {"DROP", "ADD"}
        # Cohorts are untouched by the re-stamp.
        assert by["KEEP2"]["cohort"] == "newcomer"


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
