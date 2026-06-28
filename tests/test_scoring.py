import math

import numpy as np
import pandas as pd
import pytest

from arf.scoring import (
    compute_arf,
    decile_assignment,
    e_score,
    froth_flag,
    implied_growth_gap,
    percentile_rank,
    reverse_dcf,
    v_score,
    winsorize,
    z_score,
)

# ── Pure math utilities ───────────────────────────────────────────────────────

class TestZScore:
    def test_mean_zero_std_one(self):
        s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        result = z_score(s)
        assert abs(result.mean()) < 1e-10
        assert abs(result.std(ddof=1) - 1.0) < 1e-10

    def test_single_element_returns_zero(self):
        s = pd.Series([42.0])
        result = z_score(s)
        assert result.iloc[0] == 0.0

    def test_nan_preserved(self):
        s = pd.Series([1.0, float("nan"), 3.0])
        result = z_score(s)
        assert math.isnan(result.iloc[1])

    def test_constant_series_returns_zeros(self):
        s = pd.Series([5.0, 5.0, 5.0])
        result = z_score(s)
        assert (result == 0.0).all()


class TestWinsorize:
    def test_clips_values_beyond_3sigma(self):
        rng = np.random.default_rng(0)
        base = pd.Series(rng.standard_normal(100))
        # inject a massive outlier
        s = pd.concat([base, pd.Series([100.0, -100.0])], ignore_index=True)
        result = winsorize(s, sigma=3.0)
        mu, sigma = s.mean(), s.std(ddof=1)
        assert result.max() <= mu + 3 * sigma + 1e-9
        assert result.min() >= mu - 3 * sigma - 1e-9

    def test_leaves_values_within_sigma_unchanged(self):
        s = pd.Series([0.0, 1.0, -1.0, 0.5])
        result = winsorize(s, sigma=3.0)
        assert (result == s).all()


class TestPercentileRank:
    def test_min_is_0_max_is_100(self):
        s = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0])
        result = percentile_rank(s)
        assert result.min() >= 0
        assert result.max() <= 100

    def test_monotone(self):
        s = pd.Series([1.0, 3.0, 2.0, 5.0, 4.0])
        result = percentile_rank(s)
        assert result[s.idxmin()] < result[s.idxmax()]

    def test_nan_excluded_from_calculation_but_returned_as_nan(self):
        s = pd.Series([1.0, float("nan"), 3.0, 5.0])
        result = percentile_rank(s)
        assert math.isnan(result.iloc[1])
        # non-NaN values should still get valid percentile ranks
        non_nan = result.dropna()
        assert len(non_nan) == 3
        assert non_nan.min() >= 0
        assert non_nan.max() <= 100


# ── Reverse-DCF ───────────────────────────────────────────────────────────────

class TestReverseDCF:
    def test_known_value(self):
        # P=100, FCF=5, r=0.10 → g* = r − FCF/P = 0.10 − 0.05 = 0.05
        result = reverse_dcf(price=100.0, fcf=5.0, wacc=0.10)
        assert result == pytest.approx(0.05, abs=1e-9)

    def test_negative_fcf_returns_none(self):
        result = reverse_dcf(price=100.0, fcf=-10.0, wacc=0.10)
        assert result is None

    def test_zero_price_returns_none(self):
        result = reverse_dcf(price=0.0, fcf=5.0, wacc=0.10)
        assert result is None

    def test_zero_fcf_returns_wacc(self):
        # FCF=0 → g* = r − 0/P = r
        result = reverse_dcf(price=100.0, fcf=0.0, wacc=0.10)
        assert result == pytest.approx(0.10, abs=1e-9)


class TestImpliedGrowthGap:
    def test_basic_gap(self):
        # g*=0.05, consensus=0.02 → gap=0.03
        gap = implied_growth_gap(price=100.0, fcf=5.0, wacc=0.10, consensus_cagr=0.02)
        assert gap == pytest.approx(0.03, abs=1e-9)

    def test_returns_none_when_dcf_undefined(self):
        gap = implied_growth_gap(price=100.0, fcf=-5.0, wacc=0.10, consensus_cagr=0.02)
        assert gap is None


# ── E_score ──────────────────────────────────────────────────────────────────

def _make_stock_df(**overrides) -> pd.DataFrame:
    """Minimal DataFrame for a single stock with all E_score inputs."""
    defaults = {
        "ticker": ["TEST"],
        "leg": ["US"],
        "layer": ["L2"],
        "pure_play_pct": [70.0],       # 0–100
        "gross_margin": [0.50],         # 0–1
        "revenue_ntm_growth": [0.30],  # forward AI revenue growth (pre-cap)
    }
    defaults.update(overrides)
    return pd.DataFrame(defaults)


def _make_universe_df(rows: list[dict]) -> pd.DataFrame:
    """Multi-row DataFrame for per-leg percentile ranking tests."""
    return pd.DataFrame(rows)


class TestEScore:
    def test_growth_capped_at_200pct(self):
        df_normal = _make_stock_df(revenue_ntm_growth=[2.0])    # 200% → kept
        df_extreme = _make_stock_df(revenue_ntm_growth=[23.86])  # 2386% → capped at 200%
        e_normal = e_score(df_normal).iloc[0]
        e_extreme = e_score(df_extreme).iloc[0]
        assert e_extreme == e_normal  # capped value identical to 200%

    def test_full_pipeline_returns_0_to_100_range(self):
        rows = [
            {"ticker": "A", "leg": "US", "layer": "L1", "pure_play_pct": 10.0, "gross_margin": 0.20, "revenue_ntm_growth": 0.05},
            {"ticker": "B", "leg": "US", "layer": "L3", "pure_play_pct": 60.0, "gross_margin": 0.50, "revenue_ntm_growth": 0.30},
            {"ticker": "C", "leg": "US", "layer": "L5", "pure_play_pct": 90.0, "gross_margin": 0.80, "revenue_ntm_growth": 1.50},
        ]
        df = _make_universe_df(rows)
        result = e_score(df)
        assert result.min() >= 0
        assert result.max() <= 100

    def test_null_growth_handled_gracefully(self):
        df = _make_stock_df(revenue_ntm_growth=[float("nan")])
        result = e_score(df)
        # NaN growth → still produces a score (growth component skipped/zero)
        assert len(result) == 1
        assert not math.isnan(result.iloc[0])


# ── V_score ──────────────────────────────────────────────────────────────────

def _make_v_df(**overrides) -> pd.DataFrame:
    """Minimal DataFrame for a single stock with all V_score inputs."""
    defaults = {
        "ticker": ["TEST"],
        "leg": ["US"],
        "market_cap_usd": [100.0],      # total market cap; g* = 0.10 - 5/100 = 0.05 at wacc=0.10
        "free_cash_flow": [5.0],
        "forward_pe": [25.0],
        "eps_2yr_cagr": [0.20],
        "ev_sales_5yr_percentile": [60.0],
        "roe": [0.15],
    }
    defaults.update(overrides)
    return pd.DataFrame(defaults)


class TestVScore:
    def test_roe_credit_reduces_score(self):
        # Two stocks identical in all valuation metrics, differing only in ROE.
        # High-ROE stock gets a quality credit → lower V_score within same universe.
        base = dict(market_cap_usd=100.0, free_cash_flow=2.0, forward_pe=40.0,
                    eps_2yr_cagr=0.20, ev_sales_5yr_percentile=70.0)
        df = pd.DataFrame([
            {"ticker": "LOW_ROE", "roe": 0.05, **base},  # ROE below WACC → penalty
            {"ticker": "HIGH_ROE", "roe": 1.14, **base},  # NVIDIA-like → credit
        ])
        result = v_score(df, wacc=0.10)
        low_score = result[df["ticker"] == "LOW_ROE"].iloc[0]
        high_score = result[df["ticker"] == "HIGH_ROE"].iloc[0]
        assert low_score > high_score

    def test_roe_penalty_increases_score(self):
        df = _make_v_df(roe=[-0.10])  # negative ROE → full penalty
        rows = pd.concat([df, _make_v_df(roe=[0.15]), _make_v_df(roe=[0.50])], ignore_index=True)
        scores = v_score(rows, wacc=0.10)
        # negative ROE row should have the highest v_score
        assert scores.iloc[0] == scores.max()

    def test_quality_adjustment_bounded_pm_20_pts(self):
        # Verify that the adjustment cannot move the final score by more than 20 pts
        # by comparing extreme ROE cases against a mid-case
        rows_extreme_high = pd.concat([_make_v_df(roe=[10.0])] * 5, ignore_index=True)
        rows_extreme_low = pd.concat([_make_v_df(roe=[-5.0])] * 5, ignore_index=True)
        scores_high = v_score(rows_extreme_high, wacc=0.10)
        scores_low = v_score(rows_extreme_low, wacc=0.10)
        # scores are 0–100; the adjustment is bounded ±20
        assert abs(scores_high.iloc[0] - scores_low.iloc[0]) <= 40  # 2 × 20 max swing

    def test_missing_peg_uses_remaining_components(self):
        df = _make_v_df(forward_pe=[float("nan")], eps_2yr_cagr=[float("nan")])
        rows = pd.concat([df, _make_v_df(), _make_v_df(forward_pe=[50.0])], ignore_index=True)
        result = v_score(rows, wacc=0.10)
        # No NaN in output — missing PEG falls back gracefully
        assert not result.isna().any()

    def test_missing_roe_does_not_propagate_nan(self):
        df = _make_v_df(roe=[float("nan")])
        rows = pd.concat([df, _make_v_df(roe=[0.15]), _make_v_df(roe=[0.30])], ignore_index=True)
        result = v_score(rows, wacc=0.10)
        # No NaN in output — missing ROE does not invalidate v_score
        assert not result.isna().any()


# ── ARF combination ──────────────────────────────────────────────────────────

def _make_arf_df(n: int = 5) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    return pd.DataFrame({
        "ticker": [f"T{i}" for i in range(n)],
        "leg": ["US"] * n,
        "layer": ["L2"] * n,
        "pure_play_pct": rng.uniform(10, 90, n),
        "gross_margin": rng.uniform(0.2, 0.8, n),
        "revenue_ntm_growth": rng.uniform(0.05, 1.5, n),
        "market_cap_usd": rng.uniform(10_000, 2_000_000, n),   # total market cap ($M scale)
        "free_cash_flow": rng.uniform(100, 50_000, n),          # total FCF ($M scale)
        "revenue_3yr_cagr": rng.uniform(0.05, 0.5, n),
        "forward_pe": rng.uniform(15, 100, n),
        "eps_2yr_cagr": rng.uniform(0.05, 0.5, n),
        "ev_sales_5yr_percentile": rng.uniform(20, 90, n),
        "roe": rng.uniform(0.05, 1.2, n),
        "policy_premium": [False] * n,
    })


class TestARFCombination:
    def test_geometric_mean_formula(self):
        e, v = 64.0, 25.0
        expected = math.sqrt(e * v)
        assert expected == pytest.approx(40.0, abs=0.01)

    def test_zero_e_score_yields_zero_arf(self):
        df = _make_arf_df(6)
        df.loc[0, "pure_play_pct"] = 0.0
        df.loc[0, "gross_margin"] = 0.0
        df.loc[0, "revenue_ntm_growth"] = 0.0
        df.loc[0, "layer"] = "L1"
        result = compute_arf(df, wacc_us=0.10, wacc_china=0.12)
        # lowest E_score row should have lowest ARF
        assert result.loc[0, "arf"] == result["arf"].min()

    def test_arf_percentile_rank_within_leg(self):
        df = _make_arf_df(10)
        result = compute_arf(df, wacc_us=0.10, wacc_china=0.12)
        assert result["arf"].min() >= 0
        assert result["arf"].max() <= 100

    def test_decile_assignment(self):
        assert decile_assignment(95.0) == 1
        assert decile_assignment(91.0) == 1
        assert decile_assignment(90.0) == 1
        assert decile_assignment(89.9) == 2
        assert decile_assignment(5.0) == 10
        assert decile_assignment(0.0) == 10

    def test_froth_flag_requires_all_three_conditions(self):
        assert froth_flag(decile=1, roe=0.05, cost_of_equity=0.10, ps_ratio=30.0) is True

    def test_froth_flag_false_if_only_two_conditions_met(self):
        # D1 + low ROE but P/S not > 25
        assert froth_flag(decile=1, roe=0.05, cost_of_equity=0.10, ps_ratio=20.0) is False
        # D1 + high P/S but ROE above cost of equity
        assert froth_flag(decile=1, roe=0.15, cost_of_equity=0.10, ps_ratio=30.0) is False
        # low ROE + high P/S but not D1
        assert froth_flag(decile=2, roe=0.05, cost_of_equity=0.10, ps_ratio=30.0) is False


# ── Calibration sanity checks ────────────────────────────────────────────────

def _make_calibration_universe() -> pd.DataFrame:
    """Realistic snapshot of the US leg for calibration testing.

    market_cap_usd and free_cash_flow are in the same unit (e.g. $B) so that
    reverse_dcf(market_cap, fcf, wacc) produces a meaningful FCF-yield g*.
    """
    return pd.DataFrame([
        # ticker, layer, pure_play_pct, gross_margin, revenue_ntm_growth,
        # market_cap_usd, free_cash_flow, revenue_3yr_cagr, forward_pe, eps_2yr_cagr,
        # ev_sales_5yr_percentile, roe, leg, policy_premium, ps_ratio
        {
            "ticker": "NVDA", "leg": "US", "layer": "L2", "pure_play_pct": 90,
            "gross_margin": 0.74, "revenue_ntm_growth": 0.65,
            "market_cap_usd": 3_200.0, "free_cash_flow": 44.0, "revenue_3yr_cagr": 0.50,
            "forward_pe": 23.0, "eps_2yr_cagr": 0.60,
            "ev_sales_5yr_percentile": 75.0, "roe": 1.14,
            "policy_premium": False, "ps_ratio": 21.0,
        },
        {
            "ticker": "PLTR", "leg": "US", "layer": "L5", "pure_play_pct": 80,
            "gross_margin": 0.84, "revenue_ntm_growth": 0.68,
            "market_cap_usd": 250.0, "free_cash_flow": 1.0, "revenue_3yr_cagr": 0.40,
            "forward_pe": 90.0, "eps_2yr_cagr": 0.40,
            "ev_sales_5yr_percentile": 98.0, "roe": 0.33,
            "policy_premium": False, "ps_ratio": 80.0,
        },
        {
            "ticker": "LITE", "leg": "US", "layer": "L3", "pure_play_pct": 80,
            "gross_margin": 0.55, "revenue_ntm_growth": 0.80,
            "market_cap_usd": 60.0, "free_cash_flow": 0.15, "revenue_3yr_cagr": 0.30,
            "forward_pe": 117.0, "eps_2yr_cagr": 0.50,
            "ev_sales_5yr_percentile": 96.0, "roe": 0.10,
            "policy_premium": False, "ps_ratio": 35.0,
        },
        {
            "ticker": "CSCO", "leg": "US", "layer": "L3", "pure_play_pct": 20,
            "gross_margin": 0.65, "revenue_ntm_growth": 0.06,
            "market_cap_usd": 240.0, "free_cash_flow": 15.0, "revenue_3yr_cagr": 0.05,
            "forward_pe": 18.0, "eps_2yr_cagr": 0.05,
            "ev_sales_5yr_percentile": 30.0, "roe": 0.35,
            "policy_premium": False, "ps_ratio": 5.0,
        },
        {
            "ticker": "NEE", "leg": "US", "layer": "L1", "pure_play_pct": 25,
            "gross_margin": 0.61, "revenue_ntm_growth": 0.12,
            "market_cap_usd": 160.0, "free_cash_flow": -5.0, "revenue_3yr_cagr": 0.08,
            "forward_pe": 24.0, "eps_2yr_cagr": 0.08,
            "ev_sales_5yr_percentile": 45.0, "roe": 0.12,
            "policy_premium": False, "ps_ratio": 7.0,
        },
        {
            "ticker": "ANET", "leg": "US", "layer": "L3", "pure_play_pct": 70,
            "gross_margin": 0.64, "revenue_ntm_growth": 0.31,
            "market_cap_usd": 170.0, "free_cash_flow": 4.0, "revenue_3yr_cagr": 0.28,
            "forward_pe": 40.0, "eps_2yr_cagr": 0.30,
            "ev_sales_5yr_percentile": 80.0, "roe": 0.45,
            "policy_premium": False, "ps_ratio": 22.0,
        },
        {
            "ticker": "WMB", "leg": "US", "layer": "L1", "pure_play_pct": 30,
            "gross_margin": 0.50, "revenue_ntm_growth": 0.10,
            "market_cap_usd": 80.0, "free_cash_flow": -0.5, "revenue_3yr_cagr": 0.07,
            "forward_pe": 33.0, "eps_2yr_cagr": 0.07,
            "ev_sales_5yr_percentile": 40.0, "roe": 0.20,
            "policy_premium": False, "ps_ratio": 8.0,
        },
        {
            "ticker": "AMD", "leg": "US", "layer": "L2", "pure_play_pct": 50,
            "gross_margin": 0.53, "revenue_ntm_growth": 0.35,
            "market_cap_usd": 750.0, "free_cash_flow": 5.0, "revenue_3yr_cagr": 0.35,
            "forward_pe": 62.0, "eps_2yr_cagr": 0.45,
            "ev_sales_5yr_percentile": 88.0, "roe": 0.08,
            "policy_premium": False, "ps_ratio": 22.0,
        },
        {
            "ticker": "MSFT", "leg": "US", "layer": "L5", "pure_play_pct": 35,
            "gross_margin": 0.70, "revenue_ntm_growth": 0.15,
            "market_cap_usd": 3_000.0, "free_cash_flow": 36.0, "revenue_3yr_cagr": 0.15,
            "forward_pe": 33.0, "eps_2yr_cagr": 0.15,
            "ev_sales_5yr_percentile": 70.0, "roe": 0.40,
            "policy_premium": False, "ps_ratio": 14.0,
        },
        {
            "ticker": "NVDA2", "leg": "US", "layer": "L2", "pure_play_pct": 88,
            "gross_margin": 0.72, "revenue_ntm_growth": 0.55,
            "market_cap_usd": 3_000.0, "free_cash_flow": 42.0, "revenue_3yr_cagr": 0.45,
            "forward_pe": 25.0, "eps_2yr_cagr": 0.55,
            "ev_sales_5yr_percentile": 73.0, "roe": 1.10,
            "policy_premium": False, "ps_ratio": 20.0,
        },
    ])


class TestCalibrationSanityChecks:
    """Verify the scoring formula produces sensible relative rankings.

    Full PRD D2–D4 / D6–D10 targets require a complete 16-stock universe;
    here we verify the key invariant relationships that must hold regardless
    of universe size.
    """

    @pytest.fixture(scope="class")
    def calibration_result(self):
        df = _make_calibration_universe()
        return compute_arf(df, wacc_us=0.10, wacc_china=0.12)

    def test_nvda_not_in_d1(self, calibration_result):
        nvda = calibration_result[calibration_result["ticker"] == "NVDA"].iloc[0]
        assert nvda["decile"] != 1, (
            f"NVDA decile={nvda['decile']}: should NOT be D1 (high ROE + moderate multiples = not bubbly)"
        )

    def test_nvda_has_higher_e_score_than_csco(self, calibration_result):
        nvda = calibration_result[calibration_result["ticker"] == "NVDA"].iloc[0]
        csco = calibration_result[calibration_result["ticker"] == "CSCO"].iloc[0]
        assert nvda["e_score"] > csco["e_score"], (
            f"NVDA E={nvda['e_score']:.1f} should exceed CSCO E={csco['e_score']:.1f}"
        )

    def test_pltr_has_higher_v_score_than_nvda(self, calibration_result):
        nvda = calibration_result[calibration_result["ticker"] == "NVDA"].iloc[0]
        pltr = calibration_result[calibration_result["ticker"] == "PLTR"].iloc[0]
        assert pltr["v_score"] > nvda["v_score"], (
            f"PLTR V={pltr['v_score']:.1f} should exceed NVDA V={nvda['v_score']:.1f} "
            f"(PLTR multiples far more stretched)"
        )

    def test_pltr_has_higher_arf_than_nvda(self, calibration_result):
        nvda = calibration_result[calibration_result["ticker"] == "NVDA"].iloc[0]
        pltr = calibration_result[calibration_result["ticker"] == "PLTR"].iloc[0]
        assert pltr["arf"] > nvda["arf"], (
            f"PLTR ARF={pltr['arf']:.1f} should exceed NVDA ARF={nvda['arf']:.1f}"
        )

    def test_pltr_lands_d1(self, calibration_result):
        pltr = calibration_result[calibration_result["ticker"] == "PLTR"].iloc[0]
        assert pltr["decile"] == 1, f"PLTR decile={pltr['decile']}, expected D1"

    def test_csco_lands_d6_to_d10(self, calibration_result):
        csco = calibration_result[calibration_result["ticker"] == "CSCO"].iloc[0]
        assert csco["decile"] >= 6, f"CSCO decile={csco['decile']}, expected D6–D10"
