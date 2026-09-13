"""Tests for the multi-stage reverse DCF.

The analytical anchor: a perpetuity growing at a single rate g, split into an
explicit N-year phase plus a terminal value at that same g, must equal the
Gordon value FCF0(1+g)/(w-g). So pricing a company at exactly the Gordon value
for some g must recover that same g. Every other test hangs off that identity.
"""

import pandas as pd
import pytest

from arf.implied import (
    DEFAULT_YEARS,
    froth_level,
    implied_growth,
    present_value,
    required_growth_gap,
)


def gordon(fcf0: float, g: float, w: float) -> float:
    return fcf0 * (1.0 + g) / (w - g)


class TestPresentValue:
    def test_matches_gordon_when_growth_equals_terminal(self):
        fcf0, g, w = 100.0, 0.03, 0.10
        pv = present_value(fcf0, g, w, years=DEFAULT_YEARS, terminal_growth=g)
        assert pv == pytest.approx(gordon(fcf0, g, w), rel=1e-9)

    def test_monotone_increasing_in_growth(self):
        vals = [present_value(100.0, g, 0.10, 10, 0.03)
                for g in (0.0, 0.05, 0.10, 0.20, 0.40)]
        assert vals == sorted(vals)

    def test_rejects_terminal_growth_above_wacc(self):
        with pytest.raises(ValueError):
            present_value(100.0, 0.05, 0.03, 10, 0.05)


class TestImpliedGrowth:
    def test_recovers_the_rate_it_was_priced_at(self):
        """Price at the Gordon value for g=terminal -> solver returns terminal."""
        fcf0, w, gt = 100.0, 0.10, 0.03
        ev = gordon(fcf0, gt, w)
        assert implied_growth(ev, fcf0, w, DEFAULT_YEARS, gt) == pytest.approx(gt, abs=1e-5)

    def test_round_trip_at_a_high_rate(self):
        fcf0, w, gt, g = 100.0, 0.10, 0.03, 0.35
        ev = present_value(fcf0, g, w, DEFAULT_YEARS, gt)
        assert implied_growth(ev, fcf0, w, DEFAULT_YEARS, gt) == pytest.approx(g, abs=1e-5)

    def test_higher_price_implies_higher_growth(self):
        base = implied_growth(5000.0, 100.0, 0.10, 10, 0.03)
        rich = implied_growth(9000.0, 100.0, 0.10, 10, 0.03)
        assert base is not None and rich is not None
        assert rich > base

    def test_higher_wacc_implies_higher_required_growth(self):
        """Same price, costlier capital -> the price demands more growth."""
        low = implied_growth(6000.0, 100.0, 0.10, 10, 0.03)
        high = implied_growth(6000.0, 100.0, 0.12, 10, 0.03)
        assert low is not None and high is not None
        assert high > low

    @pytest.mark.parametrize(
        "ev,fcf0,wacc,terminal",
        [
            (1000.0, 0.0, 0.10, 0.03),      # no FCF base to grow
            (1000.0, -50.0, 0.10, 0.03),    # negative FCF
            (0.0, 100.0, 0.10, 0.03),       # no EV
            (-100.0, 100.0, 0.10, 0.03),    # negative EV
            (1000.0, 100.0, 0.03, 0.05),    # terminal >= wacc
        ],
    )
    def test_undefined_inputs_return_none(self, ev, fcf0, wacc, terminal):
        assert implied_growth(ev, fcf0, wacc, 10, terminal) is None

    def test_nan_inputs_return_none(self):
        assert implied_growth(float("nan"), 100.0, 0.10) is None
        assert implied_growth(1000.0, float("nan"), 0.10) is None
        assert implied_growth(None, 100.0, 0.10) is None

    def test_price_beyond_solver_ceiling_returns_none(self):
        """A price no cash-flow growth explains is None, not a huge number."""
        assert implied_growth(1e18, 1.0, 0.10, 10, 0.03) is None

    def test_differs_from_single_stage_for_a_fast_grower(self):
        """The whole point: single-stage caps g* below wacc; this does not."""
        from arf.scoring import reverse_dcf
        ev, fcf0, w = 8000.0, 100.0, 0.10
        single = reverse_dcf(ev, fcf0, w)
        multi = implied_growth(ev, fcf0, w, 10, 0.03)
        assert single is not None and multi is not None
        assert single < w              # single-stage is bounded by construction
        assert multi > single          # multi-stage reads the real requirement


class TestRequiredGrowthGap:
    def test_positive_when_price_needs_more_than_forecast(self):
        ev = present_value(100.0, 0.35, 0.10, 10, 0.03)
        gap = required_growth_gap(ev, 100.0, 0.10, 0.20, 10, 0.03)
        assert gap is not None and gap == pytest.approx(0.15, abs=1e-4)

    def test_none_when_growth_undefined(self):
        assert required_growth_gap(1000.0, -1.0, 0.10, 0.20) is None

    def test_none_when_forecast_missing(self):
        ev = present_value(100.0, 0.35, 0.10, 10, 0.03)
        assert required_growth_gap(ev, 100.0, 0.10, float("nan"), 10, 0.03) is None


class TestFrothLevel:
    def _frame(self, values):
        return pd.DataFrame({"implied_growth_multistage": values})

    def test_reports_median_and_share_above_threshold(self):
        out = froth_level(self._frame([0.10, 0.20, 0.30, 0.40]), threshold=0.25)
        assert out["median"] == pytest.approx(0.25)
        assert out["share_above"] == pytest.approx(0.5)
        assert out["n"] == 4
        assert out["coverage"] == pytest.approx(1.0)

    def test_coverage_falls_with_nulls(self):
        out = froth_level(self._frame([0.10, None, None, 0.40]))
        assert out["n"] == 2
        assert out["coverage"] == pytest.approx(0.5)

    def test_empty_and_missing_column_are_safe(self):
        assert froth_level(pd.DataFrame())["median"] is None
        assert froth_level(pd.DataFrame({"other": [1]}))["n"] == 0
        assert froth_level(self._frame([None, None]))["median"] is None

    def test_level_actually_moves_between_snapshots(self):
        """The property ARF structurally cannot have."""
        cheap = froth_level(self._frame([0.05, 0.08, 0.10]))
        rich = froth_level(self._frame([0.35, 0.40, 0.55]))
        assert rich["median"] > cheap["median"]
