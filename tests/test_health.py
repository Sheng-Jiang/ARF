"""Unit tests for arf.health — freshness, coverage, calibration."""
from datetime import date

import pandas as pd

from arf.health import (
    CALIBRATION_TARGETS,
    calibration_check,
    coverage_report,
    evaluate_health,
    freshness_status,
    next_monday_utc,
)

# ── Freshness ────────────────────────────────────────────────────────────────

class TestFreshness:
    def test_fresh_within_7_days(self):
        s = freshness_status(date(2026, 7, 6), today=date(2026, 7, 12))
        assert s.level == "fresh"
        assert s.age_days == 6

    def test_stale_after_7_days(self):
        # 9 days: past FRESH_DAYS(7), still within STALE_DAYS(10)
        s = freshness_status(date(2026, 7, 3), today=date(2026, 7, 12))
        assert s.level == "stale"
        assert s.age_days == 9

    def test_critical_after_10_days(self):
        s = freshness_status(date(2026, 6, 30), today=date(2026, 7, 12))
        assert s.level == "critical"
        assert s.age_days == 12

    def test_unknown_when_no_snapshot(self):
        s = freshness_status(None, today=date(2026, 7, 12))
        assert s.level == "unknown"
        assert s.age_days is None

    def test_future_date_treated_as_fresh(self):
        s = freshness_status(date(2026, 7, 20), today=date(2026, 7, 12))
        assert s.level == "fresh"


# ── Coverage ─────────────────────────────────────────────────────────────────

def _snap_row(
    ticker: str,
    leg: str = "US",
    **overrides: object,
) -> dict:
    base: dict = {
        "ticker": ticker,
        "leg": leg,
        "as_of_date": date(2026, 7, 6),
        "price": 100.0,
        "gross_margin": 0.5,
        "revenue_yoy_growth": 0.2,
        "free_cash_flow": 1e9,
        "market_cap_usd": 5e10,
        "forward_pe": 25.0,
        "eps_2yr_cagr": 0.15,
        "ev_sales_5yr_percentile": 80.0,
        "roe": 0.2,
        "ps_ratio": 10.0,
        "e_score": 50.0,
        "v_score": 50.0,
        "arf": 50.0,
        "decile": 5,
        "froth_flag": False,
    }
    base.update(overrides)
    return base


class TestCoverage:
    def test_full_us_coverage_no_warnings(self):
        df = pd.DataFrame([_snap_row(f"T{i}") for i in range(10)])
        report = coverage_report(df, as_of=date(2026, 7, 6))
        assert "US" in report.legs
        leg = report.legs["US"]
        assert leg.n_scored == 10
        assert leg.v_c1_usable == 10
        assert leg.v_c2_usable == 10
        assert leg.v_c3_usable == 10
        assert report.overall_ok

    def test_china_missing_fcf_triggers_warning(self):
        rows = [
            _snap_row(f"C{i}", leg="China", free_cash_flow=float("nan"))
            for i in range(10)
        ]
        report = coverage_report(pd.DataFrame(rows))
        leg = report.legs["China"]
        assert leg.v_c1_usable == 0
        assert any("逆向DCF" in w for w in report.warnings)

    def test_negative_fcf_not_usable_for_c1(self):
        df = pd.DataFrame([_snap_row("X", free_cash_flow=-1e6)])
        leg = coverage_report(df).legs["US"]
        assert leg.v_c1_usable == 0

    def test_missing_revenue_growth_warning(self):
        rows = [
            _snap_row(f"C{i}", leg="China", revenue_yoy_growth=float("nan"))
            for i in range(8)
        ]
        report = coverage_report(pd.DataFrame(rows))
        assert any("营收增速" in w for w in report.warnings)

    def test_empty_df(self):
        report = coverage_report(pd.DataFrame())
        assert not report.overall_ok
        assert report.legs == {}


# ── Calibration ──────────────────────────────────────────────────────────────

class TestCalibration:
    def test_pass_within_band(self):
        df = pd.DataFrame([
            _snap_row("NVDA", decile=4, arf=55.0, e_score=97.0, v_score=20.0),
            _snap_row("CSCO", decile=9, arf=10.0, e_score=15.0, v_score=50.0),
        ])
        # Only check these two so missing others don't fail overall_ok here
        report = calibration_check(
            df, targets={"NVDA": (2, 5), "CSCO": (6, 10)}
        )
        assert report.n_pass == 2
        assert report.overall_ok

    def test_fail_outside_band(self):
        df = pd.DataFrame([
            _snap_row("NVDA", decile=6, arf=44.0),  # PRD wants D2–D4/5
        ])
        report = calibration_check(df, targets={"NVDA": (2, 5)})
        assert report.n_fail == 1
        assert report.results[0].status == "fail"
        assert not report.overall_ok

    def test_missing_ticker(self):
        df = pd.DataFrame([_snap_row("AAPL", decile=5)])
        report = calibration_check(df, targets={"NVDA": (2, 5)})
        assert report.n_missing == 1
        assert report.results[0].status == "missing"

    def test_null_decile_counts_as_missing(self):
        df = pd.DataFrame([_snap_row("NVDA", decile=None, arf=float("nan"))])
        report = calibration_check(df, targets={"NVDA": (2, 5)})
        assert report.results[0].status == "missing"

    def test_default_targets_include_prd_names(self):
        for t in ("NVDA", "PLTR", "CSCO", "688256.SH", "0700.HK"):
            assert t in CALIBRATION_TARGETS


# ── Combined ─────────────────────────────────────────────────────────────────

class TestEvaluateHealth:
    def test_combines_all_sections(self):
        df = pd.DataFrame([
            _snap_row(
                t,
                decile=CALIBRATION_TARGETS[t][0],
                arf=90.0 - i,
            )
            for i, t in enumerate(CALIBRATION_TARGETS)
        ])
        snap = evaluate_health(df, latest_as_of=date(2026, 7, 6), today=date(2026, 7, 12))
        assert snap.freshness.level == "fresh"
        assert snap.coverage.legs["US"].n_tickers == len(CALIBRATION_TARGETS)
        assert snap.calibration.n_pass == len(CALIBRATION_TARGETS)
        assert snap.level == "fresh"

    def test_calibration_fail_softens_level(self):
        # All targets missing → calibration fails → level degrades from fresh
        df = pd.DataFrame([_snap_row("ZZZZ", decile=5)])
        snap = evaluate_health(df, latest_as_of=date(2026, 7, 6), today=date(2026, 7, 12))
        assert snap.freshness.level == "fresh"
        assert snap.calibration.n_missing > 0
        assert snap.level == "stale"


class TestNextMonday:
    def test_on_monday_returns_same_day(self):
        # 2026-07-06 is a Monday
        assert next_monday_utc(date(2026, 7, 6)) == date(2026, 7, 6)

    def test_on_sunday_returns_next_day(self):
        # 2026-07-12 is a Sunday → next Monday is 13th
        assert next_monday_utc(date(2026, 7, 12)) == date(2026, 7, 13)
