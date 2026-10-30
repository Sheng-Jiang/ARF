"""4-Layer Predictive Forecasting Engine for ARF / AI-CIO.

Shifts the system from lagging, diagnostic nowcasts (the thermometer) to forward-looking
predictive alpha (the barometer) across four distinct temporal horizons:

Layer 1 (Fundamental Forecast, 1–2 Quarters Ahead):
    Computes supply-chain demand pull across customer nodes (w_ij) and applies upstream
    physical bottleneck clamps (e.g. packaging/wafer limits) to forecast revenue growth
    ĝ_ARF and expected earnings beat margin vs. stale sell-side consensus.

Layer 2 (Revision Velocity Forecast, 2–6 Weeks Ahead):
    Measures the 1st and 2nd derivatives of sell-side consensus revisions (from research_reports)
    and predicts institutional herding and EPS surprise probabilities ahead of earnings releases.

Layer 3 (Forward FCF & Fair-Value Fan, 6–12 Months Ahead):
    Applies operating leverage to forward revenue projections and evaluates multi-stage DCF
    present values to output a bounded 12-month target price fan (P10 Bear, P50 Base, P90 Bull).

Layer 4 (Microstructure & Regime Breakout, 5–20 Days Ahead):
    Analyzes CYQ chip profit ratios and chip cost concentration (chip_90_cost) to predict
    breakout probabilities and optimal tactical entry windows.
"""

from __future__ import annotations

import logging
import math
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from arf.db import (
    query_supply_chain_links,
    upsert_forecasts,
    upsert_supply_chain_links,
)
from arf.implied import DEFAULT_TERMINAL_GROWTH, present_value

log = logging.getLogger(__name__)

FORECAST_MODEL_VERSION = "v1.0"

# Canonical seed supply chain edges (supplier -> customer) with estimated revenue share %
# and BoM % share. Can be enriched by the Supply Chain Traversal Agent.
CANONICAL_SUPPLY_CHAIN_LINKS = [
    # Optical Interconnect (L3 -> L2/L3)
    {
        "supplier_ticker": "300308.SZ",
        "customer_ticker": "NVDA",
        "revenue_share_pct": 38.0,
        "bom_component_pct": 5.0,
        "relationship_type": "optical",
        "verified_source": "10-K Customer Mention & Industry Checks",
        "notes": "800G / 1.6T optical transceivers for Blackwell DGX systems",
    },
    {
        "supplier_ticker": "300308.SZ",
        "customer_ticker": "GOOGL",
        "revenue_share_pct": 24.0,
        "bom_component_pct": 4.0,
        "relationship_type": "optical",
        "verified_source": "Industry Supply Chain Checks",
        "notes": "TPU v5p / v6 optical interconnect modules",
    },
    {
        "supplier_ticker": "300502.SZ",
        "customer_ticker": "NVDA",
        "revenue_share_pct": 32.0,
        "bom_component_pct": 4.0,
        "relationship_type": "optical",
        "verified_source": "Annual Report & Industry Checks",
        "notes": "800G optical modules for AI compute clusters",
    },
    {
        "supplier_ticker": "300502.SZ",
        "customer_ticker": "META",
        "revenue_share_pct": 22.0,
        "bom_component_pct": 4.5,
        "relationship_type": "optical",
        "verified_source": "Export Manifest & Broker Reports",
        "notes": "Data center fabric expansion",
    },
    # Foundry & Packaging (L2 -> L2)
    {
        "supplier_ticker": "TSM",
        "customer_ticker": "NVDA",
        "revenue_share_pct": 14.0,
        "bom_component_pct": 20.0,
        "relationship_type": "foundry",
        "verified_source": "SEC 10-K Customer Disclosure",
        "notes": "4N/3nm advanced nodes and CoWoS packaging allocation",
    },
    {
        "supplier_ticker": "TSM",
        "customer_ticker": "AAPL",
        "revenue_share_pct": 22.0,
        "bom_component_pct": 15.0,
        "relationship_type": "foundry",
        "verified_source": "SEC 10-K Customer Disclosure",
        "notes": "A18 / M4 leading edge capacity",
    },
    {
        "supplier_ticker": "TSM",
        "customer_ticker": "AMD",
        "revenue_share_pct": 6.0,
        "bom_component_pct": 22.0,
        "relationship_type": "foundry",
        "verified_source": "Company Filings",
        "notes": "MI300 / MI325 compute tiles",
    },
    # Lithography & Equipment (L2 -> L2)
    {
        "supplier_ticker": "ASML",
        "customer_ticker": "TSM",
        "revenue_share_pct": 35.0,
        "bom_component_pct": 25.0,
        "relationship_type": "equipment",
        "verified_source": "Annual Report",
        "notes": "High-NA and 0.33 NA EUV lithography systems",
    },
    # Chips to Cloud Hyperscalers (L2 -> L3)
    {
        "supplier_ticker": "NVDA",
        "customer_ticker": "MSFT",
        "revenue_share_pct": 19.0,
        "bom_component_pct": 32.0,
        "relationship_type": "direct_customer",
        "verified_source": "SEC 10-K Customer Footnotes",
        "notes": "Customer A - Azure AI infrastructure CapEx",
    },
    {
        "supplier_ticker": "NVDA",
        "customer_ticker": "META",
        "revenue_share_pct": 13.0,
        "bom_component_pct": 28.0,
        "relationship_type": "direct_customer",
        "verified_source": "SEC 10-K Customer Footnotes",
        "notes": "Llama 3/4 training and GenAI inference clusters",
    },
    {
        "supplier_ticker": "NVDA",
        "customer_ticker": "GOOGL",
        "revenue_share_pct": 9.0,
        "bom_component_pct": 14.0,
        "relationship_type": "direct_customer",
        "verified_source": "Industry Estimates",
        "notes": "Google Cloud external tenant GPU clusters",
    },
    # Power & Thermal Infrastructure (L1 -> L3/L2)
    {
        "supplier_ticker": "VRT",
        "customer_ticker": "MSFT",
        "revenue_share_pct": 15.0,
        "bom_component_pct": 6.0,
        "relationship_type": "power",
        "verified_source": "Broker Checks",
        "notes": "Liquid cooling CDUs and power distribution units",
    },
    {
        "supplier_ticker": "VRT",
        "customer_ticker": "NVDA",
        "revenue_share_pct": 12.0,
        "bom_component_pct": 4.0,
        "relationship_type": "power",
        "verified_source": "Partnership Announcement",
        "notes": "Co-designed liquid cooling architectures for GB200 NVL72",
    },
]


@dataclass
class ForecastResult:
    """Structured output of the 4-layer forecasting engine."""

    ticker: str
    as_of_date: date
    horizon_days: int
    predicted_rev_growth: float  # ĝ_ARF (e.g. 0.42 for +42%)
    consensus_rev_growth: float | None
    expected_beat_pct: float | None  # ĝ_ARF - consensus
    eps_surprise_prob: float  # 0.0 - 1.0 probability of beating consensus
    revision_velocity_14d: float | None  # 14-day revision momentum
    revision_velocity_30d: float | None  # 30-day revision momentum
    fair_value_p10: float | None  # Bear case target price
    fair_value_p50: float | None  # Base target price
    fair_value_p90: float | None  # Bull case target price
    expected_return_p50: float | None  # (P50 - price) / price
    regime_breakout_prob: float  # 0.0 - 1.0 technical/chip breakout probability
    chip_concentration_ratio: float | None
    model_version: str = FORECAST_MODEL_VERSION

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["as_of_date"] = self.as_of_date.isoformat()
        return d


def seed_default_supply_chain_links(conn: Any) -> None:
    """Seed the database with verified canonical supply chain links if empty."""
    existing = query_supply_chain_links(conn)
    if existing.empty:
        log.info("Seeding database with %d canonical supply chain links", len(CANONICAL_SUPPLY_CHAIN_LINKS))
        upsert_supply_chain_links(conn, CANONICAL_SUPPLY_CHAIN_LINKS)


# ── Layer 1: Supply Chain Demand Pull & Physical Bottleneck Clamp ──────────────

def compute_supply_chain_growth(
    supplier_ticker: str,
    links_df: pd.DataFrame,
    customer_growth_map: dict[str, float],
    organic_growth: float = 0.15,
    bottleneck_clamp: float | None = None,
) -> float:
    """Forecast revenue growth (ĝ_ARF) via customer demand pull and upstream clamps.

    Args:
        supplier_ticker: Ticker of the target supplier.
        links_df: DataFrame of supply chain links (columns: supplier_ticker, customer_ticker, revenue_share_pct).
        customer_growth_map: Mapping of customer ticker -> expected CapEx or revenue growth (e.g. 0.35 for +35%).
        organic_growth: Fallback growth rate for the unmapped share of revenue.
        bottleneck_clamp: Maximum physical growth limit (e.g. foundry capacity expansion).
    """
    clean_s = supplier_ticker.strip().upper()
    org_g = float(np.clip(organic_growth, -0.50, 2.00)) if not math.isnan(organic_growth) else 0.15
    subset = links_df[links_df["supplier_ticker"] == clean_s]
    if subset.empty:
        res = org_g if bottleneck_clamp is None else min(org_g, bottleneck_clamp)
        return float(np.clip(res, -0.50, 2.00))

    total_weight = 0.0
    weighted_growth = 0.0

    for _, row in subset.iterrows():
        cust = str(row["customer_ticker"]).strip().upper()
        weight = float(row.get("revenue_share_pct") or 0.0) / 100.0
        if weight <= 0.0:
            continue
        cust_g = float(customer_growth_map.get(cust, org_g))
        cust_g = float(np.clip(cust_g, -0.50, 2.00))
        weighted_growth += weight * cust_g
        total_weight += weight

    if total_weight < 1.0:
        remainder_weight = max(0.0, 1.0 - total_weight)
        weighted_growth += remainder_weight * org_g

    if bottleneck_clamp is not None and not math.isnan(bottleneck_clamp):
        weighted_growth = min(weighted_growth, bottleneck_clamp)
    return float(np.clip(weighted_growth, -0.50, 2.00))


# ── Layer 2: Revision Velocity & Consensus Herding ────────────────────────────

def compute_revision_velocity(
    ticker: str,
    conn: Any,
    as_of: date,
    lookback_14: int = 14,
    lookback_30: int = 30,
) -> tuple[float | None, float | None]:
    """Calculate the 14-day and 30-day percentage revision velocity of analyst forecasts."""
    clean_t = ticker.strip().upper()
    query = """
    SELECT report_date, eps_forecast, target_price
    FROM research_reports
    WHERE ticker = ? AND report_date <= ? AND report_date >= ?
    ORDER BY report_date ASC
    """
    earliest_cutoff = as_of - pd.Timedelta(days=lookback_30 + 15)
    df = conn.execute(query, [clean_t, as_of, earliest_cutoff]).fetchdf()
    if df.empty or len(df) < 2:
        return None, None

    as_of_ts = pd.Timestamp(as_of)
    df["report_date"] = pd.to_datetime(df["report_date"])

    # Measure average target price or EPS across intervals
    def _metric(sub: pd.DataFrame) -> float | None:
        valid_eps = pd.to_numeric(sub["eps_forecast"], errors="coerce").dropna()
        if not valid_eps.empty and valid_eps.mean() != 0:
            return float(valid_eps.mean())
        valid_tgt = pd.to_numeric(sub["target_price"], errors="coerce").dropna()
        if not valid_tgt.empty and valid_tgt.mean() != 0:
            return float(valid_tgt.mean())
        return None

    now_sub = df[df["report_date"] >= (as_of_ts - pd.Timedelta(days=7))]
    d14_sub = df[
        (df["report_date"] >= (as_of_ts - pd.Timedelta(days=lookback_14 + 7)))
        & (df["report_date"] < (as_of_ts - pd.Timedelta(days=7)))
    ]
    d30_sub = df[
        (df["report_date"] >= (as_of_ts - pd.Timedelta(days=lookback_30 + 7)))
        & (df["report_date"] < (as_of_ts - pd.Timedelta(days=lookback_14)))
    ]

    val_now = _metric(now_sub) or _metric(df.tail(3))
    val_14 = _metric(d14_sub)
    val_30 = _metric(d30_sub)

    v14 = (val_now - val_14) / abs(val_14) if (val_now and val_14 and val_14 != 0) else None
    v30 = (val_now - val_30) / abs(val_30) if (val_now and val_30 and val_30 != 0) else None
    return v14, v30


def calibrate_eps_surprise_probability(
    expected_beat_pct: float | None,
    revision_velocity_14d: float | None = None,
) -> float:
    """Calibrate the probability of beating the next consensus earnings report [0.05, 0.95]."""
    base_logits = 0.0  # prior 50% probability
    if expected_beat_pct is not None and not math.isnan(expected_beat_pct):
        # 10% expected beat adds ~1.0 logit
        base_logits += expected_beat_pct * 10.0

    if revision_velocity_14d is not None and not math.isnan(revision_velocity_14d):
        base_logits += revision_velocity_14d * 4.0

    # Logistic sigmoid with clipping
    prob = 1.0 / (1.0 + math.exp(-max(-3.0, min(3.0, base_logits))))
    return float(np.clip(prob, 0.05, 0.95))


# ── Layer 3: Forward FCF Distribution & Fair-Value Fan (P10, P50, P90) ────────

def compute_fair_value_distribution(
    price: float,
    fcf0: float | None,
    market_cap: float,
    predicted_growth: float,
    wacc: float = 0.10,
    leg: str = "US",
    terminal_growth: float | None = None,
) -> tuple[float | None, float | None, float | None, float | None]:
    """Evaluate forward fair-value price distribution (P10 Bear, P50 Base, P90 Bull).

    Returns:
        (fair_value_p10, fair_value_p50, fair_value_p90, expected_return_p50)
    """
    if price <= 0 or market_cap <= 0:
        return None, None, None, None

    term_g = terminal_growth or DEFAULT_TERMINAL_GROWTH.get(leg, 0.03)

    # If FCF is missing, negative, or tiny (<0.5% yield), fallback to a normalized 3.5% FCF yield proxy
    min_viable_fcf = market_cap * 0.005
    effective_fcf = (
        fcf0 if (fcf0 is not None and not math.isnan(fcf0) and fcf0 >= min_viable_fcf) else (market_cap * 0.035)
    )

    try:
        # Cap 10-year compound growth rate at 35% to prevent compounding explosion
        g_dcf_base = float(np.clip(predicted_growth, -0.30, 0.35))
        pv_base = present_value(effective_fcf, g_dcf_base, wacc, years=10, terminal_growth=term_g)
        raw_price_p50 = price * (pv_base / market_cap)

        # Bear Case (P10): Lower growth (-15%), higher cost of capital (+150 bps)
        g_bear = float(np.clip(g_dcf_base - 0.15, -0.35, 0.25))
        wacc_bear = wacc + 0.015
        pv_bear = present_value(effective_fcf, g_bear, wacc_bear, years=10, terminal_growth=term_g)
        raw_price_p10 = price * (pv_bear / market_cap)

        # Bull Case (P90): Higher growth (+10%), lower risk premium (-75 bps)
        g_bull = float(np.clip(g_dcf_base + 0.10, -0.20, 0.45))
        wacc_bull = max(term_g + 0.02, wacc - 0.0075)
        pv_bull = present_value(effective_fcf, g_bull, wacc_bull, years=10, terminal_growth=term_g)
        raw_price_p90 = price * (pv_bull / market_cap)

        # Institutional guardrails / bounded target price envelope [-75%, +250%]
        price_p50 = float(np.clip(raw_price_p50, price * 0.35, price * 3.00))
        price_p10 = float(np.clip(min(raw_price_p10, price_p50 * 0.85), price * 0.25, price_p50))
        price_p90 = float(np.clip(max(raw_price_p90, price_p50 * 1.15), price_p50, price * 4.00))
        exp_return_p50 = (price_p50 - price) / price

        return (
            round(price_p10, 2),
            round(price_p50, 2),
            round(price_p90, 2),
            round(exp_return_p50, 4),
        )
    except Exception as exc:
        log.warning("Fair value distribution computation failed for price=%.2f: %s", price, exc)
        return None, None, None, None


# ── Layer 4: CYQ Microstructure Regime Breakout Probability ───────────────────

def compute_regime_breakout(
    price: float,
    tech_row: dict[str, Any] | None,
    expected_beat_pct: float | None = None,
    froth_flag: bool = False,
) -> tuple[float, float | None]:
    """Calculate 20-day regime breakout probability and chip concentration ratio.

    Returns:
        (regime_breakout_prob, chip_concentration_ratio)
    """
    if not tech_row or price <= 0:
        return 0.50, None

    chip_profit = tech_row.get("chip_profit_ratio")
    avg_cost = tech_row.get("chip_avg_cost")
    c90_min = tech_row.get("chip_90_cost_min")
    c90_max = tech_row.get("chip_90_cost_max")
    ma_bullish = bool(tech_row.get("ma_bullish_alignment") or tech_row.get("ma_bullish"))
    rsi = tech_row.get("rsi")

    concentration_ratio = None
    if avg_cost and avg_cost > 0 and c90_min is not None and c90_max is not None:
        concentration_ratio = float((c90_max - c90_min) / avg_cost)

    # Base breakout score
    score = 0.50

    # 1. Profit ratio influence: High profit ratio means little overhead trapped supply
    if chip_profit is not None and not math.isnan(chip_profit):
        if chip_profit >= 0.80:
            score += 0.15
        elif chip_profit <= 0.35:
            score -= 0.15

    # 2. Tight chip concentration means supply is locked in, primed for expansion
    if concentration_ratio is not None and concentration_ratio < 0.10:
        score += 0.12

    # 3. Moving average alignment
    if ma_bullish:
        score += 0.08

    # 4. Fundamental expected beat bonus
    if expected_beat_pct is not None and expected_beat_pct > 0.05:
        score += 0.10

    # 5. Penalties for frothy overbought or bubble stocks
    if froth_flag:
        score -= 0.20
    if rsi is not None and rsi > 80:
        score -= 0.10

    breakout_prob = float(np.clip(score, 0.05, 0.95))
    return round(breakout_prob, 4), (round(concentration_ratio, 4) if concentration_ratio else None)


# ── Composite Forecaster Engine ───────────────────────────────────────────────

def generate_forecast_for_ticker(
    ticker: str,
    as_of: date,
    conn: Any,
    horizon_days: int = 90,
    model_version: str = FORECAST_MODEL_VERSION,
) -> ForecastResult | None:
    """Generate the full 4-layer predictive forecast for a single ticker."""
    clean_t = ticker.strip().upper()

    # 1. Fetch snapshot row
    snap = conn.execute(
        """
        SELECT ticker, name, leg, layer, price, market_cap_usd, free_cash_flow,
               eps_2yr_cagr, revenue_yoy_growth, revenue_ntm, roe, froth_flag,
               financial_fx_usd, fx_rate_usd
        FROM snapshots
        WHERE ticker = ? AND as_of_date = ?
        """,
        [clean_t, as_of],
    ).fetchdf()

    if snap.empty:
        # Fallback to latest available snapshot on or before as_of
        snap = conn.execute(
            """
            SELECT ticker, name, leg, layer, price, market_cap_usd, free_cash_flow,
                   eps_2yr_cagr, revenue_yoy_growth, revenue_ntm, roe, froth_flag,
                   financial_fx_usd, fx_rate_usd
            FROM snapshots
            WHERE ticker = ? AND as_of_date <= ?
            ORDER BY as_of_date DESC LIMIT 1
            """,
            [clean_t, as_of],
        ).fetchdf()
        if snap.empty:
            return None

    row = snap.iloc[0].to_dict()
    price = float(row.get("price") or 0.0)
    market_cap_usd = float(row.get("market_cap_usd") or 0.0)
    fin_fx = row.get("financial_fx_usd") or row.get("fx_rate_usd") or 1.0
    fin_fx_val = float(fin_fx) if not pd.isna(fin_fx) and float(fin_fx) > 0 else 1.0
    market_cap_local = market_cap_usd * fin_fx_val
    fcf = row.get("free_cash_flow")
    fcf0 = float(fcf) if (fcf is not None and not pd.isna(fcf)) else None
    leg = str(row.get("leg") or "US")
    froth = bool(row.get("froth_flag") or False)
    wacc = 0.10 if leg == "US" else 0.12

    # Consensus growth benchmark
    consensus_raw = row.get("eps_2yr_cagr")
    consensus_g = float(consensus_raw) if (consensus_raw is not None and not pd.isna(consensus_raw)) else 0.15

    # 2. Layer 1: Supply Chain Demand Pull
    links = query_supply_chain_links(conn, supplier_ticker=clean_t)
    # Estimate customer growth map from recent snapshot
    cust_tickers = links["customer_ticker"].tolist() if not links.empty else []
    cust_growth_map = {}
    if cust_tickers:
        placeholders = ", ".join("?" for _ in cust_tickers)
        c_df = conn.execute(
            f"SELECT ticker, eps_2yr_cagr, revenue_yoy_growth FROM snapshots WHERE ticker IN ({placeholders}) AND as_of_date <= ? ORDER BY as_of_date DESC",
            [*cust_tickers, as_of],
        ).fetchdf()
        for _, c_row in c_df.iterrows():
            c_tick = str(c_row["ticker"]).strip().upper()
            if c_tick not in cust_growth_map:
                cg = c_row.get("eps_2yr_cagr") or c_row.get("revenue_yoy_growth") or 0.20
                cust_growth_map[c_tick] = float(cg) if not pd.isna(cg) else 0.20

    pred_growth = compute_supply_chain_growth(
        clean_t,
        links,
        cust_growth_map,
        organic_growth=float(row.get("revenue_yoy_growth") or 0.15),
    )
    expected_beat = pred_growth - consensus_g

    # 3. Layer 2: Revision Velocity
    v14, v30 = compute_revision_velocity(clean_t, conn, as_of)
    surprise_prob = calibrate_eps_surprise_probability(expected_beat, v14)

    # 4. Layer 3: Fair Value Distribution Fan
    p10, p50, p90, exp_ret = compute_fair_value_distribution(
        price, fcf0, market_cap_local, pred_growth, wacc=wacc, leg=leg
    )

    # 5. Layer 4: CYQ Microstructure Regime Breakout
    tech_df = conn.execute(
        "SELECT * FROM technical_metrics WHERE ticker = ? AND as_of_date <= ? ORDER BY as_of_date DESC LIMIT 1",
        [clean_t, as_of],
    ).fetchdf()
    tech_row = tech_df.iloc[0].to_dict() if not tech_df.empty else None
    breakout_prob, conc_ratio = compute_regime_breakout(price, tech_row, expected_beat, froth_flag=froth)

    return ForecastResult(
        ticker=clean_t,
        as_of_date=as_of,
        horizon_days=horizon_days,
        predicted_rev_growth=round(pred_growth, 4),
        consensus_rev_growth=round(consensus_g, 4),
        expected_beat_pct=round(expected_beat, 4),
        eps_surprise_prob=round(surprise_prob, 4),
        revision_velocity_14d=round(v14, 4) if v14 is not None else None,
        revision_velocity_30d=round(v30, 4) if v30 is not None else None,
        fair_value_p10=p10,
        fair_value_p50=p50,
        fair_value_p90=p90,
        expected_return_p50=exp_ret,
        regime_breakout_prob=breakout_prob,
        chip_concentration_ratio=conc_ratio,
        model_version=model_version,
    )


def generate_forecasts_for_universe(
    as_of: date,
    conn: Any,
    horizon_days: int = 90,
    model_version: str = FORECAST_MODEL_VERSION,
    persist: bool = True,
) -> pd.DataFrame:
    """Generate forecasts for all scored universe tickers as of date."""
    seed_default_supply_chain_links(conn)

    tickers_df = conn.execute(
        "SELECT DISTINCT ticker FROM snapshots WHERE as_of_date = (SELECT MAX(as_of_date) FROM snapshots WHERE as_of_date <= ?)",
        [as_of],
    ).fetchdf()

    if tickers_df.empty:
        log.warning("No tickers found in snapshot on or before %s", as_of)
        return pd.DataFrame()

    results: list[ForecastResult] = []
    for ticker in tickers_df["ticker"]:
        try:
            fc = generate_forecast_for_ticker(ticker, as_of, conn, horizon_days, model_version)
            if fc is not None:
                results.append(fc)
        except Exception as exc:
            log.warning("Forecast generation failed for %s on %s: %s", ticker, as_of, exc)

    if not results:
        return pd.DataFrame()

    rows = [r.to_dict() for r in results]
    if persist:
        upsert_forecasts(conn, rows)

    return pd.DataFrame(rows)
