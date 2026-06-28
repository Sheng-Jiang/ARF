import math

import numpy as np
import pandas as pd

# Layer numeric values for E_score (higher = more AI-pure in this cycle)
_LAYER_VALUES: dict[str, float] = {
    "L5": 5.0,  # Apps
    "L4": 5.0,  # Models
    "L2": 4.0,  # Chips
    "L3": 3.0,  # Infra
    "L1": 2.0,  # Energy
}

_GROWTH_CAP = 2.0  # 200% — Cambricon guard


def z_score(s: pd.Series) -> pd.Series:
    """Compute z-score, treating NaN as missing. Constant series → all zeros."""
    std = s.std(ddof=1)
    if std == 0 or (math.isnan(std) and s.notna().sum() <= 1):
        return s.where(s.isna(), 0.0)
    return (s - s.mean()) / std


def winsorize(s: pd.Series, sigma: float = 3.0) -> pd.Series:
    """Clip values to [mean ± sigma * std]."""
    mu = s.mean()
    std = s.std(ddof=1)
    if std == 0 or math.isnan(std):
        return s.copy()
    return s.clip(lower=mu - sigma * std, upper=mu + sigma * std)


def percentile_rank(s: pd.Series) -> pd.Series:
    """Map values to 0–100 percentile ranks. NaN → NaN, excluded from calculation."""
    result = s.copy().astype(float)
    valid_mask = s.notna()
    if valid_mask.sum() == 0:
        return result
    valid = s[valid_mask]
    ranks = valid.rank(method="average", pct=True) * 100.0
    result[valid_mask] = ranks
    return result


def reverse_dcf(price: float, fcf: float, wacc: float) -> float | None:
    """Solve Gordon Growth for implied perpetual growth rate.

    g* = wacc − FCF / price  (derived from P = FCF / (wacc − g))
    Returns None when inputs make the calculation undefined.
    """
    if price <= 0 or fcf < 0:
        return None
    return wacc - fcf / price


def implied_growth_gap(
    price: float,
    fcf: float,
    wacc: float,
    consensus_cagr: float,
) -> float | None:
    """Return g* − consensus_cagr, or None if reverse_dcf is undefined."""
    g_star = reverse_dcf(price, fcf, wacc)
    if g_star is None:
        return None
    return g_star - consensus_cagr


# ── E_score ───────────────────────────────────────────────────────────────────

def e_score(df: pd.DataFrame) -> pd.Series:
    """Compute AI Exposure sub-score (0–100) via percentile rank within df.

    Required columns: ticker, layer, pure_play_pct, gross_margin,
                       revenue_ntm_growth
    """
    df = df.copy()

    # Layer component (30%)
    df["_layer_val"] = df["layer"].map(_LAYER_VALUES).fillna(2.0)
    layer_norm = df["_layer_val"] / 5.0 * 100.0  # 0–100

    # Pure-play % component (40%)
    pure_play = df["pure_play_pct"].clip(0, 100)

    # Supply-chain criticality proxy: gross_margin (20%)
    # gross_margin in [0,1] → scale to 0–100
    criticality = (df["gross_margin"].clip(0, 1) * 100.0).fillna(0.0)

    # Forward AI revenue growth component (10%) — cap at 200%
    growth_raw = df["revenue_ntm_growth"].fillna(0.0).clip(0, _GROWTH_CAP)
    growth_norm = (growth_raw / _GROWTH_CAP) * 100.0  # 0–100

    composite = (
        0.30 * layer_norm
        + 0.40 * pure_play
        + 0.20 * criticality
        + 0.10 * growth_norm
    )

    return percentile_rank(composite)


# ── V_score ───────────────────────────────────────────────────────────────────

def _peg_ratio(forward_pe: float | None, eps_2yr_cagr: float | None) -> float | None:
    """Compute PEG; return None if inputs are missing or zero growth."""
    if forward_pe is None or eps_2yr_cagr is None:
        return None
    if math.isnan(forward_pe) or math.isnan(eps_2yr_cagr):
        return None
    if eps_2yr_cagr <= 0:
        return None
    raw = forward_pe / (eps_2yr_cagr * 100.0)  # growth in %, e.g. 20% → 20
    return min(raw, 5.0)  # cap at 5


def v_score(df: pd.DataFrame, wacc: float = 0.10) -> pd.Series:
    """Compute Valuation Stretch sub-score (0–100) via percentile rank within df.

    Required columns: ticker, price, free_cash_flow,
                       forward_pe, eps_2yr_cagr, ev_sales_5yr_percentile, roe

    Component 1 uses the reverse-DCF implied perpetual growth rate (g*).
    Higher g* means market prices near-WACC perpetual growth = more stretched.
    """
    df = df.copy()

    # Component 1: Reverse-DCF implied g* (higher → closer to WACC → more stretched)
    # Uses market_cap_usd (total) with total FCF so units match in the Gordon Growth formula.
    gaps = pd.Series(index=df.index, dtype=float)
    for i, row in df.iterrows():
        mkt_cap = row.get("market_cap_usd")
        fcf = row.get("free_cash_flow")
        if any(pd.isna(x) or x is None for x in [mkt_cap, fcf]):
            gaps[i] = float("nan")
        else:
            g_star = reverse_dcf(float(mkt_cap), float(fcf), wacc)
            gaps[i] = g_star if g_star is not None else float("nan")

    # Component 2: PEG-like ratio (higher → more stretched)
    pegs = pd.Series(index=df.index, dtype=float)
    for i, row in df.iterrows():
        peg = _peg_ratio(
            row.get("forward_pe") if not _is_nan(row.get("forward_pe")) else None,
            row.get("eps_2yr_cagr") if not _is_nan(row.get("eps_2yr_cagr")) else None,
        )
        pegs[i] = peg if peg is not None else float("nan")

    # Component 3: EV/Sales 5-year percentile (already 0–100, higher → more stretched)
    ev_pct = df["ev_sales_5yr_percentile"].astype(float)

    # Rank each component within the group, then average available components
    c1 = percentile_rank(gaps)
    c2 = percentile_rank(pegs)
    c3 = percentile_rank(ev_pct)

    component_stack = pd.concat([c1, c2, c3], axis=1)
    component_stack.columns = ["c1", "c2", "c3"]
    raw_v = component_stack.mean(axis=1, skipna=True)

    # Fallback for pure story stocks with negative FCF, negative PE, and no 5yr history.
    # We rank them by their raw EV/Sales multiple so they still receive a v_score.
    ev_sales = df["ev_sales"].astype(float)
    c_fallback = percentile_rank(ev_sales)
    raw_v = raw_v.fillna(c_fallback)

    # Quality adjustment: subtract (ROE − wacc) normalized to ±20 points
    roe = df["roe"].astype(float)
    roe_adj_raw = (roe - wacc) / 1.0  # normalizer: 100% ROE swing = 100 pts
    roe_adj = roe_adj_raw.fillna(0.0).clip(-0.20, 0.20) * 100.0  # ±20 pts
    adjusted = (raw_v - roe_adj).clip(0, 100)

    return percentile_rank(adjusted)


def _is_nan(x: object) -> bool:
    try:
        return math.isnan(float(x))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return True


# ── ARF combination ───────────────────────────────────────────────────────────

def decile_assignment(arf_value: float) -> int:
    """Map ARF 0–100 to decile 1 (top) – 10 (bottom)."""
    if arf_value >= 90:
        return 1
    return 10 - int(arf_value // 10)


def froth_flag(
    decile: int,
    roe: float,
    cost_of_equity: float,
    ps_ratio: float,
) -> bool:
    """True iff D1 AND ROE < cost_of_equity AND P/S > 25."""
    return decile == 1 and roe < cost_of_equity and ps_ratio > 25


def compute_arf(
    df: pd.DataFrame,
    wacc_us: float = 0.10,
    wacc_china: float = 0.12,
) -> pd.DataFrame:
    """Compute E_score, V_score, ARF, decile, and froth_flag per row.

    Legs are scored separately (US and China). Europe-ref and Pre-IPO are
    passed through with null ARF.

    Required input columns: all columns needed by e_score() and v_score(),
    plus: leg, roe, ps_ratio (for froth flag).
    """
    df = df.copy()
    result_frames = []

    for leg_name, wacc in [("US", wacc_us), ("China", wacc_china)]:
        mask = df["leg"] == leg_name
        if mask.sum() == 0:
            continue
        leg_df = df[mask].copy()

        e = e_score(leg_df)
        v = v_score(leg_df, wacc=wacc)

        # Geometric mean → raw ARF
        arf_raw = np.sqrt(e * v)

        # Final percentile rank within leg
        arf_final = percentile_rank(arf_raw)

        leg_df["e_score"] = e.values
        leg_df["v_score"] = v.values
        leg_df["arf"] = arf_final.values
        leg_df["decile"] = leg_df["arf"].apply(
            lambda x: decile_assignment(x) if not math.isnan(x) else None
        )

        _wacc = wacc_us if leg_name == "US" else wacc_china
        def _froth(row: pd.Series, w: float = _wacc) -> bool:
            d = row.get("decile")
            if d is None or (isinstance(d, float) and math.isnan(d)):
                return False
            return froth_flag(
                int(d),
                float(row.get("roe") or 1.0),
                w,
                float(row.get("ps_ratio") or 0.0),
            )

        leg_df["froth_flag"] = leg_df.apply(_froth, axis=1)
        result_frames.append(leg_df)

    # Non-scored legs pass through
    other_mask = ~df["leg"].isin(["US", "China"])
    if other_mask.any():
        other_df = df[other_mask].copy()
        for col in ("e_score", "v_score", "arf", "decile", "froth_flag"):
            other_df[col] = None
        result_frames.append(other_df)

    if not result_frames:
        return df

    return pd.concat(result_frames, ignore_index=True)
