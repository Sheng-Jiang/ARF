"""Multi-stage reverse DCF — the absolute-level counterpart to ARF.

Why this module exists
----------------------
``arf.scoring.reverse_dcf`` solves single-stage Gordon Growth on trailing FCF:

    g* = wacc − FCF / price

That is a strictly monotone transform of FCF yield, so percentile-ranking it
(V_score component C1) produces exactly an inverted FCF-yield rank and carries
no information beyond FCF/P. It is also the wrong shape for the companies this
universe is built from: a name whose thesis is "compound hard for a decade,
then fade" is not described by a single perpetual growth rate starting today,
and the single-stage form compresses every such name into a narrow band just
below WACC.

More importantly, every score ARF currently produces is a *percentile rank
within leg*, which makes its cross-sectional distribution identical in every
snapshot (median ≈ 50 by construction, empirically 50.0–54.2 across all
snapshots to date). A relative ranking can say which name is most stretched
today; it cannot say whether the complex is more stretched than in May. The
functions here return an **absolute** quantity in real units, so a median
across the leg moves when the market moves — which is what a thermometer has
to do to be one.

The metric
----------
Solve for the free-cash-flow CAGR ``g`` over an explicit high-growth window of
``years``, fading to ``terminal_growth`` in perpetuity, that reproduces today's
enterprise value:

    EV = Σ(t=1..N) FCF₀(1+g)^t / (1+w)^t
         + FCF₀(1+g)^N (1+g_t) / [(w − g_t)(1+w)^N]

The output is a sentence rather than a score: *"at this price the market
requires 34% annual FCF growth for ten years, then 3% forever."* That is a
falsifiable statement about the world, which is the point.
"""
from __future__ import annotations

import math

import pandas as pd

# Solver bounds. Below the floor the answer is "the market expects collapse";
# above the ceiling it is "the price is not explicable by cash flows at all".
# Both are reported as None rather than a number pretending to precision.
_G_FLOOR = -0.90
_G_CEIL = 10.0
_TOL = 1e-7
_MAX_ITER = 200

# Default high-growth window. Ten years is long enough to cover a full capex
# cycle in this universe and short enough that the terminal assumption still
# carries most of the value — which is itself worth seeing.
DEFAULT_YEARS = 10

# Terminal growth by leg — nominal, roughly long-run nominal GDP. These are
# judgment parameters, not measurements; they belong in config once wired.
DEFAULT_TERMINAL_GROWTH = {"US": 0.03, "China": 0.04}


def present_value(
    fcf0: float,
    growth: float,
    wacc: float,
    years: int = DEFAULT_YEARS,
    terminal_growth: float = 0.03,
) -> float:
    """PV of an N-year growth phase at ``growth`` fading to ``terminal_growth``.

    Splitting a perpetuity at a single rate into an explicit phase plus a
    terminal value at that same rate reproduces the Gordon value exactly; that
    identity is what :func:`implied_growth` is inverted against, and what the
    unit tests pin.
    """
    if wacc <= terminal_growth:
        raise ValueError("wacc must exceed terminal_growth for a finite terminal value")

    pv = 0.0
    for t in range(1, years + 1):
        pv += fcf0 * (1.0 + growth) ** t / (1.0 + wacc) ** t

    fcf_terminal = fcf0 * (1.0 + growth) ** years * (1.0 + terminal_growth)
    tv = fcf_terminal / (wacc - terminal_growth)
    pv += tv / (1.0 + wacc) ** years
    return pv


def implied_growth(
    enterprise_value: float,
    fcf0: float,
    wacc: float,
    years: int = DEFAULT_YEARS,
    terminal_growth: float = 0.03,
) -> float | None:
    """Solve for the FCF CAGR the current price requires over ``years``.

    Returns the growth rate as a decimal (0.34 = 34% a year), or None when the
    inputs make the question meaningless: non-positive FCF (the model has no
    base to grow), non-positive EV, an un-discountable terminal assumption, or
    a solution outside [-90%, +1000%] — beyond which the price is not being set
    by discounted cash flows and pretending otherwise would be false precision.

    PV is strictly increasing in ``growth`` for positive ``fcf0``, so bisection
    is exact and needs no derivative.
    """
    if enterprise_value is None or fcf0 is None:
        return None
    if _isnan(enterprise_value) or _isnan(fcf0):
        return None
    if enterprise_value <= 0 or fcf0 <= 0:
        return None
    if wacc <= terminal_growth:
        return None

    lo, hi = _G_FLOOR, _G_CEIL
    pv_lo = present_value(fcf0, lo, wacc, years, terminal_growth)
    pv_hi = present_value(fcf0, hi, wacc, years, terminal_growth)
    if enterprise_value < pv_lo or enterprise_value > pv_hi:
        return None

    for _ in range(_MAX_ITER):
        mid = (lo + hi) / 2.0
        pv_mid = present_value(fcf0, mid, wacc, years, terminal_growth)
        if abs(pv_mid - enterprise_value) < _TOL * max(1.0, abs(enterprise_value)):
            return mid
        if pv_mid < enterprise_value:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def required_growth_gap(
    enterprise_value: float,
    fcf0: float,
    wacc: float,
    analyst_cagr: float,
    years: int = DEFAULT_YEARS,
    terminal_growth: float = 0.03,
) -> float | None:
    """``implied_growth`` minus a comparable analyst growth rate.

    Unlike ``scoring.implied_growth_gap``, both sides are multi-year growth
    rates over comparable horizons, so the difference means something. Positive
    = the price requires more than the forecast supports.
    """
    g = implied_growth(enterprise_value, fcf0, wacc, years, terminal_growth)
    if g is None or analyst_cagr is None or _isnan(analyst_cagr):
        return None
    return g - float(analyst_cagr)


# ── Aggregate level: the actual thermometer ──────────────────────────────────

def froth_level(
    df: pd.DataFrame,
    growth_col: str = "implied_growth_multistage",
    threshold: float = 0.25,
) -> dict[str, float | int | None]:
    """Absolute froth statistics for one leg-snapshot.

    Every field here can move between snapshots, which is the whole difference
    from ARF. ``share_above`` is the fraction of scored names whose price
    requires sustained growth above ``threshold`` — a rate very few companies
    have ever held for a decade, which is why it reads as froth rather than
    optimism.

    ``coverage`` is reported alongside deliberately: these statistics are only
    comparable across snapshots when a similar share of the universe resolved,
    and coverage in this pipeline has ranged widely.
    """
    if growth_col not in df.columns or df.empty:
        return {"median": None, "p75": None, "share_above": None,
                "n": 0, "coverage": 0.0}

    series = pd.to_numeric(df[growth_col], errors="coerce")
    valid = series.dropna()
    n_total = len(df)
    if valid.empty:
        return {"median": None, "p75": None, "share_above": None,
                "n": 0, "coverage": 0.0}

    return {
        "median": float(valid.median()),
        "p75": float(valid.quantile(0.75)),
        "share_above": float((valid > threshold).mean()),
        "n": int(len(valid)),
        "coverage": float(len(valid) / n_total) if n_total else 0.0,
    }


def _isnan(x: object) -> bool:
    try:
        return math.isnan(float(x))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return True
