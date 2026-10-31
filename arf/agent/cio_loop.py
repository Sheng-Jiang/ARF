"""Autonomous 5-Stage CIO Agent Workflow, Executable Thesis Watchdog, and Decision Packet Engine.

This module implements the autonomous buy-side Chief Investment Officer workflow:
1. Anomaly & Delta Triage: Scans forward forecasts, consensus revision momentum, and CYQ chips.
2. Causal Shock Propagation: Stress-tests supply-chain demand pull across customer nodes.
3. G1–G4 Risk & Valuation Consistency Gatekeeper: Enforces hard circuit breakers and $g^*$ consistency.
4. Active Thesis Watchdog: Evaluates machine-executable KillConditions and harvest triggers on positions.
5. Autonomous CIO Decision Packet: Synthesizes high-conviction ProposalTickets and an institutional Markdown briefing.
"""

from __future__ import annotations

import argparse
import logging
import math
import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from arf.agent.schemas import (
    CIODecisionPacket,
    DecisionAction,
    GateVerdict,
    KillCondition,
    ProposalTicket,
    WatchdogAlert,
)
from arf.db import (
    init_db,
    query_latest_forecasts,
    query_supply_chain_links,
)
from arf.forecast import (
    _num,
    calibrate_eps_surprise_probability,
    compute_fair_value_distribution,
    compute_revision_velocity,
    compute_supply_chain_growth,
    generate_forecasts_for_universe,
    seed_default_supply_chain_links,
)
from arf.scoring import _local_market_cap

log = logging.getLogger(__name__)

_ACTIVE_THESIS_STAGES = ("thesis_formulated", "committee_pending", "active_watch")


def _num_or(val: Any, default: float) -> float:
    """Coerce val via _num(), returning default only when None/NaN (preserving 0.0)."""
    n = _num(val)
    return n if n is not None else default


def _load_latest_snapshots(conn: Any, as_of: date) -> pd.DataFrame:
    """Load latest snapshot rows on or before as_of."""
    snap_df = conn.execute(
        """
        SELECT ticker, name, leg, layer, price, market_cap_usd, free_cash_flow,
               eps_2yr_cagr, revenue_yoy_growth, roe, froth_flag, decile, ps_ratio,
               financial_fx_usd, fx_rate_usd, implied_growth, v_score, e_score, arf
        FROM snapshots
        WHERE as_of_date = (SELECT MAX(as_of_date) FROM snapshots WHERE as_of_date <= ?)
        """,
        [as_of],
    ).fetchdf()

    if snap_df.empty:
        snap_df = (
            conn.execute(
                """
                SELECT ticker, name, leg, layer, price, market_cap_usd, free_cash_flow,
                       eps_2yr_cagr, revenue_yoy_growth, roe, froth_flag, decile, ps_ratio,
                       financial_fx_usd, fx_rate_usd, implied_growth, v_score, e_score, arf
                FROM snapshots
                WHERE as_of_date <= ?
                ORDER BY as_of_date DESC
                """,
                [as_of],
            )
            .fetchdf()
            .drop_duplicates("ticker")
        )
    return snap_df


def _ensure_and_load_forecasts(
    conn: Any,
    as_of: date,
    horizon_days: int = 90,
) -> pd.DataFrame:
    """Load deduplicated latest forecasts for horizon_days, generating on-demand if missing."""
    fc_df = query_latest_forecasts(conn, horizon_days=horizon_days, as_of_date=as_of)
    if not fc_df.empty:
        return fc_df

    try:
        generated = generate_forecasts_for_universe(
            as_of, conn, horizon_days=horizon_days, persist=True
        )
    except Exception:
        generated = generate_forecasts_for_universe(
            as_of, conn, horizon_days=horizon_days, persist=False
        )

    reloaded = query_latest_forecasts(conn, horizon_days=horizon_days, as_of_date=as_of)
    return reloaded if not reloaded.empty else generated


def _load_latest_technicals(conn: Any, as_of: date) -> pd.DataFrame:
    """Load latest technical_metrics rows on or before as_of."""
    try:
        return conn.execute(
            """
            SELECT ticker, technical_score, chip_profit_ratio, chip_avg_cost,
                   ma_bullish_alignment, rsi
            FROM technical_metrics
            WHERE as_of_date = (
                SELECT MAX(as_of_date) FROM technical_metrics WHERE as_of_date <= ?
            )
            """,
            [as_of],
        ).fetchdf()
    except Exception:
        return pd.DataFrame()


# ── Stage 3: Deterministic G1–G4 Outside-Model Risk Gates ────────────────────

def evaluate_cio_gates(
    row: dict[str, Any],
    customer_implied_growths: list[float] | None = None,
) -> tuple[GateVerdict, str]:
    """Evaluate deterministic outside-model G1-G4 risk gates for a company row.

    Gates:
        G1 (Data Integrity): price and market_cap_usd must be finite and > 0.
        G3 (Froth Circuit Breaker): froth_flag is True.
        G2 (WACC Hurdle Gate): ROE < WACC (10% US, 12% China) with stretched V-score >= 60, or ROE < 0.
        G4 (Supply-Chain Implied Growth Consistency Gate): Supplier g* > 0.25 and > 2x Customer avg g*.

    Returns:
        (GateVerdict, reason_detail)
    """
    # G1: Data Integrity
    price = _num(row.get("price"))
    market_cap = _num(row.get("market_cap_usd"))
    if (
        price is None
        or price <= 0
        or not math.isfinite(price)
        or market_cap is None
        or market_cap <= 0
        or not math.isfinite(market_cap)
    ):
        return (
            GateVerdict.BLOCKED_INSUFFICIENT_CRITERIA,
            f"G1 Data Integrity failed: price={price}, market_cap={market_cap}",
        )

    # G3: Froth Circuit Breaker
    if bool(row.get("froth_flag")):
        return (
            GateVerdict.BLOCKED_FROTH,
            "G3 Froth Flag triggered (D1 bubble + ROE < WACC + P/S > 25)",
        )

    # G2: WACC Hurdle Gate (negative ROE or below-WACC ROE with stretched multiples)
    leg = str(row.get("leg") or "US")
    wacc = 0.10 if leg == "US" else 0.12
    roe = _num(row.get("roe"))
    v_score = _num(row.get("v_score"))
    if roe is not None and (roe < 0.0 or (v_score is not None and roe < wacc and v_score >= 60.0)):
        return (
            GateVerdict.BLOCKED_HURDLE,
            f"G2 Hurdle failed: ROE {roe:.1%} < WACC {wacc:.0%}",
        )

    # G4: Cross-Node Reverse-DCF g* Consistency Gate
    implied_g = _num(row.get("implied_growth"))
    if implied_g is not None and implied_g > 0.25 and customer_implied_growths:
        valid_cust = [
            _num(cg)
            for cg in customer_implied_growths
            if _num(cg) is not None and math.isfinite(_num(cg))  # type: ignore[arg-type]
        ]
        if valid_cust:
            cust_g_mean = float(np.mean(valid_cust))
            if cust_g_mean > 0 and implied_g > 2.0 * cust_g_mean:
                return (
                    GateVerdict.BLOCKED_VALUATION_STRETCH,
                    f"G4 Supply-chain g* divergence: Supplier g*={implied_g:.1%} > 2x Customer avg g*={cust_g_mean:.1%}",
                )

    return GateVerdict.PASSED, "Passed G1-G4 deterministic CIO gates"


# ── Stage 4 Helper: Default Quantitative Kill Conditions ─────────────────────

def default_kill_conditions_for_row(row: dict[str, Any]) -> list[KillCondition]:
    """Return standard machine-executable KillCondition predicates for long exposure."""
    return [
        KillCondition(
            metric="froth_flag",
            operator="==",
            threshold=True,
            description="Froth bubble circuit breaker",
        ),
        KillCondition(
            metric="expected_beat_pct",
            operator="<",
            threshold=-0.10,
            description="Supply-chain growth falls >10% below consensus",
        ),
        KillCondition(
            metric="roe",
            operator="<",
            threshold=0.05,
            description="Return on equity collapses below 5%",
        ),
        KillCondition(
            metric="chip_profit_ratio",
            operator="<",
            threshold=0.15,
            description="Severe CYQ overhead supply trap (<15% profit ratio)",
        ),
    ]


# ── Stage 1: Anomaly & Delta Triage ──────────────────────────────────────────

def scan_material_deltas(
    conn: Any,
    as_of: date,
    snap_df: pd.DataFrame | None = None,
    fc_df: pd.DataFrame | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Scan forward forecasts and snapshots to identify high-conviction catalysts and hazards."""
    if snap_df is None:
        snap_df = _load_latest_snapshots(conn, as_of)
    if snap_df.empty:
        return {"high_conviction_longs": [], "froth_hazards": [], "breakouts": []}

    if fc_df is None:
        fc_df = _ensure_and_load_forecasts(conn, as_of, horizon_days=90)

    fc_map = (
        {str(r["ticker"]).strip().upper(): r.to_dict() for _, r in fc_df.iterrows()}
        if not fc_df.empty
        else {}
    )

    longs: list[dict[str, Any]] = []
    froth: list[dict[str, Any]] = []
    breakouts: list[dict[str, Any]] = []

    for _, r in snap_df.iterrows():
        s_dict = r.to_dict()
        t = str(s_dict.get("ticker", "")).strip().upper()
        if not t:
            continue
        f_dict = fc_map.get(t, {})
        d = {**s_dict, **f_dict, "ticker": t}

        beat = _num(d.get("expected_beat_pct"))
        ret_p50 = _num(d.get("expected_return_p50"))
        breakout = _num_or(d.get("regime_breakout_prob"), 0.5)

        has_positive_upside = ret_p50 is None or ret_p50 >= 0.0
        is_bullish = has_positive_upside and (
            (beat is not None and beat >= 0.05) or (ret_p50 is not None and ret_p50 >= 0.12)
        )

        if bool(d.get("froth_flag")):
            froth.append(d)
        elif is_bullish:
            longs.append(d)

        if breakout >= 0.65:
            breakouts.append(d)

    return {
        "high_conviction_longs": sorted(
            longs, key=lambda x: _num_or(x.get("expected_return_p50"), -999.0), reverse=True
        ),
        "froth_hazards": froth,
        "breakouts": sorted(
            breakouts, key=lambda x: _num_or(x.get("regime_breakout_prob"), 0.0), reverse=True
        ),
    }


# ── Stage 2: Programmatic Causal Supply-Chain Shock Propagation ──────────────

def simulate_supply_chain_shock(
    conn: Any,
    as_of: date,
    customer_shocks: dict[str, float],
    bottleneck_clamp: float | None = 0.80,
    snap_df: pd.DataFrame | None = None,
    fc_df: pd.DataFrame | None = None,
    links_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Propagate customer CapEx/growth shocks across supply chain edges.

    Args:
        conn: DuckDB connection.
        as_of: Snapshot date.
        customer_shocks: Mapping of customer ticker -> additive delta (e.g. {"MSFT": 0.20, "AAPL": -0.15}).
        bottleneck_clamp: Maximum annual revenue growth ceiling for mapped suppliers.
        snap_df: Optional pre-loaded snapshot DataFrame.
        fc_df: Optional pre-loaded forecast DataFrame.
        links_df: Optional pre-loaded supply chain links DataFrame.

    Returns:
        DataFrame sorted by abs(growth_delta) descending with columns:
        ticker, name, leg, layer, base_pred_growth, shocked_pred_growth, growth_delta,
        expected_beat_pct, eps_surprise_prob, fair_value_p50, expected_return_p50.
    """
    empty_cols = [
        "ticker", "name", "leg", "layer", "base_pred_growth", "shocked_pred_growth",
        "growth_delta", "expected_beat_pct", "eps_surprise_prob", "fair_value_p50",
        "expected_return_p50",
    ]
    if links_df is None:
        seed_default_supply_chain_links(conn)
        links_df = query_supply_chain_links(conn)

    if snap_df is None:
        snap_df = _load_latest_snapshots(conn, as_of)

    if snap_df.empty:
        return pd.DataFrame(columns=empty_cols)

    if fc_df is None:
        fc_df = _ensure_and_load_forecasts(conn, as_of, horizon_days=90)

    fc_map = (
        {str(r["ticker"]).strip().upper(): r.to_dict() for _, r in fc_df.iterrows()}
        if not fc_df.empty
        else {}
    )

    # Build customer growth map
    norm_shocks = {
        str(k).strip().upper(): float(v)
        for k, v in (customer_shocks or {}).items()
    }
    all_customers = (
        set(links_df["customer_ticker"].astype(str).str.upper().unique())
        if not links_df.empty
        else set()
    )
    all_customers.update(norm_shocks.keys())

    base_cust_growth_map: dict[str, float] = {}
    shocked_cust_growth_map: dict[str, float] = {}

    snap_lookup = {
        str(r["ticker"]).strip().upper(): r.to_dict()
        for _, r in snap_df.iterrows()
    }

    for cust in all_customers:
        s_row = snap_lookup.get(cust)
        base_g = 0.20
        if s_row:
            cg = _num(s_row.get("eps_2yr_cagr"))
            if cg is None:
                cg = _num(s_row.get("revenue_yoy_growth"))
            if cg is not None:
                base_g = cg
        base_cust_growth_map[cust] = base_g
        shocked_cust_growth_map[cust] = base_g + norm_shocks.get(cust, 0.0)

    # Multi-hop propagation (2 passes: e.g. Hyperscalers -> NVDA -> TSM/Innolight -> ASML)
    if not links_df.empty:
        for _ in range(2):
            for cust in list(all_customers):
                cust_links = links_df[links_df["supplier_ticker"].astype(str).str.upper() == cust]
                if cust_links.empty:
                    continue
                s_row = snap_lookup.get(cust, {})
                org = _num_or(s_row.get("revenue_yoy_growth"), 0.15)
                b_pred = compute_supply_chain_growth(
                    cust, cust_links, base_cust_growth_map, organic_growth=org, bottleneck_clamp=bottleneck_clamp
                )
                s_pred = compute_supply_chain_growth(
                    cust, cust_links, shocked_cust_growth_map, organic_growth=org, bottleneck_clamp=bottleneck_clamp
                )
                delta = (s_pred - b_pred) + norm_shocks.get(cust, 0.0)
                if abs(delta) > 1e-6:
                    shocked_cust_growth_map[cust] = base_cust_growth_map[cust] + delta

    rows = []
    for _, snap_row in snap_df.iterrows():
        row_dict = snap_row.to_dict()
        t = str(row_dict.get("ticker", "")).strip().upper()
        if not t:
            continue

        name = str(row_dict.get("name") or "")
        leg = str(row_dict.get("leg") or "US")
        layer = str(row_dict.get("layer") or "L2")
        price = _num_or(row_dict.get("price"), 0.0)
        market_cap_local = _num_or(_local_market_cap(row_dict), 0.0)
        fcf0 = _num(row_dict.get("free_cash_flow"))
        wacc = 0.10 if leg == "US" else 0.12

        organic = _num_or(row_dict.get("revenue_yoy_growth"), 0.15)
        consensus_g = _num_or(row_dict.get("eps_2yr_cagr"), 0.15)

        sub_links = (
            links_df[links_df["supplier_ticker"].astype(str).str.upper() == t]
            if not links_df.empty
            else pd.DataFrame()
        )

        if not sub_links.empty:
            base_pred = compute_supply_chain_growth(
                t,
                sub_links,
                base_cust_growth_map,
                organic_growth=organic,
                bottleneck_clamp=bottleneck_clamp,
            )
            shocked_pred = compute_supply_chain_growth(
                t,
                sub_links,
                shocked_cust_growth_map,
                organic_growth=organic,
                bottleneck_clamp=bottleneck_clamp,
            )
            if t in norm_shocks:
                shocked_pred = shocked_pred + norm_shocks[t]
                if bottleneck_clamp is not None:
                    shocked_pred = min(shocked_pred, bottleneck_clamp)
        else:
            base_pred = _num_or(fc_map.get(t, {}).get("predicted_rev_growth"), organic)
            shocked_pred = base_pred + norm_shocks.get(t, 0.0)

        growth_delta = shocked_pred - base_pred
        exp_beat = shocked_pred - consensus_g

        v14 = _num(fc_map.get(t, {}).get("revision_velocity_14d"))
        if v14 is None:
            v14, _ = compute_revision_velocity(t, conn, as_of)

        surprise_prob = calibrate_eps_surprise_probability(exp_beat, v14)

        _, p50, _, exp_ret = compute_fair_value_distribution(
            price=price,
            fcf0=fcf0,
            market_cap=market_cap_local,
            predicted_growth=shocked_pred,
            wacc=wacc,
            leg=leg,
        )

        rows.append({
            "ticker": t,
            "name": name,
            "leg": leg,
            "layer": layer,
            "base_pred_growth": round(base_pred, 4),
            "shocked_pred_growth": round(shocked_pred, 4),
            "growth_delta": round(growth_delta, 4),
            "expected_beat_pct": round(exp_beat, 4),
            "eps_surprise_prob": round(surprise_prob, 4),
            "fair_value_p50": p50,
            "expected_return_p50": exp_ret,
        })

    result_df = pd.DataFrame(rows)
    if not result_df.empty:
        result_df["abs_delta"] = result_df["growth_delta"].abs()
        result_df = (
            result_df.sort_values("abs_delta", ascending=False)
            .drop(columns=["abs_delta"])
            .reset_index(drop=True)
        )
    return result_df


# ── Stage 4: Executable Thesis Watchdog ───────────────────────────────────────

def evaluate_thesis_watchdog(
    conn: Any,
    as_of: date,
    held_tickers: list[str] | None = None,
    snap_df: pd.DataFrame | None = None,
    fc_df: pd.DataFrame | None = None,
    links_df: pd.DataFrame | None = None,
    tech_df: pd.DataFrame | None = None,
) -> list[WatchdogAlert]:
    """Audit positions against machine-executable kill conditions and circuit breakers."""
    if links_df is None:
        seed_default_supply_chain_links(conn)
        links_df = query_supply_chain_links(conn)

    if snap_df is None:
        snap_df = _load_latest_snapshots(conn, as_of)

    if snap_df.empty:
        return []

    snap_map = {
        str(r["ticker"]).strip().upper(): r.to_dict()
        for _, r in snap_df.iterrows()
    }

    if fc_df is None:
        fc_df = _ensure_and_load_forecasts(conn, as_of, horizon_days=90)
    fc_map = (
        {str(r["ticker"]).strip().upper(): r.to_dict() for _, r in fc_df.iterrows()}
        if not fc_df.empty
        else {}
    )

    if tech_df is None:
        tech_df = _load_latest_technicals(conn, as_of)
    tech_map = (
        {str(r["ticker"]).strip().upper(): r.to_dict() for _, r in tech_df.iterrows()}
        if not tech_df.empty
        else {}
    )

    norm_held = {str(h).strip().upper() for h in (held_tickers or []) if str(h).strip()}

    # Determine candidate tickers
    if norm_held:
        target_tickers = sorted(norm_held)
    else:
        # Check active IDRs/opportunity states only (exclude invalidated/harvested)
        active_db_tickers: set[str] = set()
        stage_placeholders = ", ".join(f"'{s}'" for s in _ACTIVE_THESIS_STAGES)
        try:
            opp_df = conn.execute(
                f"SELECT DISTINCT ticker FROM opportunity_states WHERE current_stage IN ({stage_placeholders})"
            ).fetchdf()
            active_db_tickers.update(opp_df["ticker"].astype(str).str.strip().str.upper())
        except Exception:
            pass
        try:
            idr_df = conn.execute(
                f"SELECT DISTINCT ticker FROM investment_decision_records WHERE stage IN ({stage_placeholders})"
            ).fetchdf()
            active_db_tickers.update(idr_df["ticker"].astype(str).str.strip().str.upper())
        except Exception:
            pass

        if not active_db_tickers:
            # Default to all scored universe tickers in snapshot
            target_tickers = list(snap_map.keys())
        else:
            # Check active IDR tickers plus any froth tickers from snapshot
            for t, r in snap_map.items():
                if bool(r.get("froth_flag")):
                    active_db_tickers.add(t)
            target_tickers = sorted(active_db_tickers)

    alerts: list[WatchdogAlert] = []

    for t in target_tickers:
        snap_row = snap_map.get(t)
        if not snap_row:
            continue

        f_row = fc_map.get(t, {})
        m_row = tech_map.get(t, {})

        # Combine all metrics
        metrics: dict[str, Any] = {**snap_row, **f_row, **m_row}
        name = str(metrics.get("name") or "")
        is_held = t in norm_held

        # 1. G3 Froth Circuit Breaker Alert
        is_froth = bool(metrics.get("froth_flag"))
        if is_froth:
            decile = metrics.get("decile")
            roe = _num(metrics.get("roe"))
            ps = _num(metrics.get("ps_ratio"))
            roe_str = f"{roe:.1%}" if roe is not None else "N/A"
            ps_str = f"{ps:.1f}" if ps is not None else "N/A"
            alerts.append(
                WatchdogAlert(
                    ticker=t,
                    name=name,
                    alert_type="FROTH_CIRCUIT_BREAKER",
                    severity="CRITICAL",
                    triggered_rule="G3 Froth Flag triggered (D1 bubble + ROE < WACC + P/S > 25)",
                    current_value=f"ARF D{decile}, ROE={roe_str}, P/S={ps_str}",
                    recommended_action=DecisionAction.INVALIDATE if is_held else DecisionAction.AVOID_FROTH,
                )
            )

        # 2. Machine-Executable Kill Conditions
        kill_conditions = default_kill_conditions_for_row(metrics)
        for cond in kill_conditions:
            if cond.metric == "froth_flag" and is_froth:
                # Already alerted under FROTH_CIRCUIT_BREAKER above
                continue
            triggered, detail = cond.evaluate(metrics)
            if triggered:
                val = metrics.get(cond.metric)
                alerts.append(
                    WatchdogAlert(
                        ticker=t,
                        name=name,
                        alert_type="THESIS_INVALIDATED",
                        severity="CRITICAL",
                        triggered_rule=detail,
                        current_value=f"{cond.metric}={val}",
                        recommended_action=DecisionAction.INVALIDATE,
                    )
                )

        # 3. G4 Cross-Node Reverse-DCF g* Divergence Check
        implied_g = _num(metrics.get("implied_growth"))
        if implied_g is not None and implied_g > 0.25 and not links_df.empty:
            sub_links = links_df[links_df["supplier_ticker"].astype(str).str.upper() == t]
            if not sub_links.empty:
                cust_ticks = sub_links["customer_ticker"].astype(str).str.upper().tolist()
                cust_growths = [
                    _num(snap_map.get(ct, {}).get("implied_growth"))
                    for ct in cust_ticks
                    if _num(snap_map.get(ct, {}).get("implied_growth")) is not None
                ]
                valid_cust = [cg for cg in cust_growths if cg is not None and math.isfinite(cg)]
                if valid_cust:
                    cust_g_mean = float(np.mean(valid_cust))
                    if cust_g_mean > 0 and implied_g > 2.0 * cust_g_mean:
                        alerts.append(
                            WatchdogAlert(
                                ticker=t,
                                name=name,
                                alert_type="G_STAR_DIVERGENCE",
                                severity="WARNING",
                                triggered_rule=(
                                    f"Supplier g* ({implied_g:.1%}) > 2x customer avg g* ({cust_g_mean:.1%})"
                                ),
                                current_value=f"g*={implied_g:.1%}, CustAvg={cust_g_mean:.1%}",
                                recommended_action=DecisionAction.MONITOR,
                            )
                        )

        # 4. Harvest Target Reached Check
        price = _num(metrics.get("price"))
        p90 = _num(metrics.get("fair_value_p90"))
        exp_ret = _num(metrics.get("expected_return_p50"))

        if price is not None and price > 0:
            harvest_triggered = False
            harvest_rule = ""
            if p90 is not None and price >= p90:
                harvest_triggered = True
                harvest_rule = f"Price {price:.2f} reached or exceeded P90 fair value target {p90:.2f}"
            elif exp_ret is not None and exp_ret <= -0.15:
                harvest_triggered = True
                harvest_rule = f"Expected 12M return {exp_ret:.1%} collapsed below -15% harvest hurdle"

            if harvest_triggered:
                exp_ret_str = f"{exp_ret:.1%}" if exp_ret is not None else "N/A"
                alerts.append(
                    WatchdogAlert(
                        ticker=t,
                        name=name,
                        alert_type="HARVEST_TARGET_REACHED",
                        severity="INFO",
                        triggered_rule=harvest_rule,
                        current_value=f"Price={price:.2f}, P90={p90}, ExpRet={exp_ret_str}",
                        recommended_action=DecisionAction.HARVEST,
                    )
                )

    severity_order = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}
    alerts.sort(key=lambda a: (severity_order.get(a.severity, 3), a.ticker))
    return alerts


# ── Stage 5: Push-First CIO Decision Packet & Briefing Engine ────────────────

def build_cio_decision_packet(
    conn: Any,
    as_of: date,
    held_tickers: list[str] | None = None,
    customer_shocks: dict[str, float] | None = None,
    max_proposals: int = 8,
    bottleneck_clamp: float | None = 0.80,
) -> CIODecisionPacket:
    """Build the autonomous 5-stage CIO Decision Packet end-to-end."""
    packet_id = f"CIO-PKT-{as_of.isoformat()}-{uuid.uuid4().hex[:6].upper()}"

    # Load supply chain links, snapshots, forecasts, and technicals once
    seed_default_supply_chain_links(conn)
    links_df = query_supply_chain_links(conn)
    snap_df = _load_latest_snapshots(conn, as_of)

    if snap_df.empty:
        return CIODecisionPacket(
            packet_id=packet_id,
            as_of_date=as_of.isoformat(),
            regime_summary="No snapshot data available on or before as-of date.",
            shock_scenario=customer_shocks or {},
            watchdog_alerts=[],
            proposals=[],
            markdown_brief="# 💼 AI-CIO Decision Packet\n\nNo snapshot data available.",
        )

    fc_df = _ensure_and_load_forecasts(conn, as_of, horizon_days=90)
    tech_df = _load_latest_technicals(conn, as_of)

    snap_map = {
        str(r["ticker"]).strip().upper(): r.to_dict()
        for _, r in snap_df.iterrows()
    }
    fc_map = (
        {str(r["ticker"]).strip().upper(): r.to_dict() for _, r in fc_df.iterrows()}
        if not fc_df.empty
        else {}
    )
    tech_map = (
        {str(r["ticker"]).strip().upper(): r.to_dict() for _, r in tech_df.iterrows()}
        if not tech_df.empty
        else {}
    )

    # Stage 2: Causal shock simulation if customer_shocks provided
    shock_df = pd.DataFrame()
    if customer_shocks:
        shock_df = simulate_supply_chain_shock(
            conn,
            as_of,
            customer_shocks,
            bottleneck_clamp=bottleneck_clamp,
            snap_df=snap_df,
            fc_df=fc_df,
            links_df=links_df,
        )
        if not shock_df.empty:
            for _, s_row in shock_df.iterrows():
                stk = str(s_row["ticker"]).strip().upper()
                if stk not in fc_map:
                    fc_map[stk] = {"ticker": stk}
                fc_map[stk]["predicted_rev_growth"] = s_row["shocked_pred_growth"]
                fc_map[stk]["expected_beat_pct"] = s_row["expected_beat_pct"]
                fc_map[stk]["eps_surprise_prob"] = s_row["eps_surprise_prob"]
                fc_map[stk]["fair_value_p50"] = s_row["fair_value_p50"]
                fc_map[stk]["expected_return_p50"] = s_row["expected_return_p50"]
            fc_df = pd.DataFrame(list(fc_map.values()))

    # Stage 1: Anomaly & Delta Triage (driven by post-shock forecast state)
    triage = scan_material_deltas(conn, as_of, snap_df=snap_df, fc_df=fc_df)
    bullish_tickers = {str(d["ticker"]).strip().upper() for d in triage["high_conviction_longs"]}
    froth_tickers = {str(d["ticker"]).strip().upper() for d in triage["froth_hazards"]}

    # Stage 4: Run Active Thesis Watchdog (reusing pre-loaded DataFrames)
    watchdog_alerts = evaluate_thesis_watchdog(
        conn,
        as_of,
        held_tickers=held_tickers,
        snap_df=snap_df,
        fc_df=fc_df,
        links_df=links_df,
        tech_df=tech_df,
    )

    invalidated_alerts_by_ticker: dict[str, list[WatchdogAlert]] = {}
    for alert in watchdog_alerts:
        if alert.alert_type == "THESIS_INVALIDATED":
            invalidated_alerts_by_ticker.setdefault(alert.ticker.strip().upper(), []).append(alert)

    # Stage 3 & 5: Evaluate G1-G4 gates & build Proposals
    proposals: list[ProposalTicket] = []
    norm_held = {str(t).strip().upper() for t in (held_tickers or []) if str(t).strip()}

    for t, snap_row in snap_map.items():
        f_row = fc_map.get(t, {})
        m_row = tech_map.get(t, {})
        combined_metrics: dict[str, Any] = {**snap_row, **f_row, **m_row}

        # Find customer implied growths
        cust_implied_growths: list[float] = []
        if not links_df.empty:
            sub_links = links_df[links_df["supplier_ticker"].astype(str).str.upper() == t]
            if not sub_links.empty:
                for ct in sub_links["customer_ticker"].astype(str).str.upper():
                    cg = _num(snap_map.get(ct, {}).get("implied_growth"))
                    if cg is not None:
                        cust_implied_growths.append(cg)

        gate_verdict, gate_details = evaluate_cio_gates(snap_row, cust_implied_growths)

        exp_beat = _num(f_row.get("expected_beat_pct"))
        exp_ret = _num(f_row.get("expected_return_p50"))
        surprise_prob = _num(f_row.get("eps_surprise_prob"))
        breakout_prob = _num(f_row.get("regime_breakout_prob"))
        is_held = t in norm_held
        is_froth = t in froth_tickers or bool(snap_row.get("froth_flag"))

        kill_conds = default_kill_conditions_for_row(snap_row)
        breached_reasons: list[str] = [
            a.triggered_rule for a in invalidated_alerts_by_ticker.get(t, [])
        ]
        if not breached_reasons:
            for cond in kill_conds:
                if cond.metric == "froth_flag":
                    continue
                trig, detail = cond.evaluate(combined_metrics)
                if trig:
                    breached_reasons.append(detail)

        if is_froth:
            action = "EXIT_INVALIDATED" if is_held else "SHORT_FROTH"
            conviction = -0.85
            decile = snap_row.get("decile")
            ps = _num(snap_row.get("ps_ratio"))
            roe = _num(snap_row.get("roe"))
            ps_str = f"{ps:.1f}" if ps is not None else "N/A"
            roe_str = f"{roe:.1%}" if roe is not None else "N/A"
            rationale = (
                f"G3 Froth breaker active: D{decile} bubble, P/S={ps_str}, "
                f"ROE={roe_str}"
            )
            proposals.append(
                ProposalTicket(
                    ticker=t,
                    name=str(snap_row.get("name") or ""),
                    leg=str(snap_row.get("leg") or "US"),
                    layer=str(snap_row.get("layer") or "L2"),
                    action=action,
                    conviction=conviction,
                    expected_beat_pct=exp_beat,
                    eps_surprise_prob=surprise_prob,
                    expected_return_p50=exp_ret,
                    regime_breakout_prob=breakout_prob,
                    gate_verdict=gate_verdict,
                    gate_details=gate_details,
                    rationale=rationale,
                    kill_conditions=kill_conds,
                )
            )
        elif is_held and breached_reasons:
            action = "EXIT_INVALIDATED"
            conviction = -0.80
            rationale = f"Held position breached kill condition(s): {'; '.join(breached_reasons)}"
            proposals.append(
                ProposalTicket(
                    ticker=t,
                    name=str(snap_row.get("name") or ""),
                    leg=str(snap_row.get("leg") or "US"),
                    layer=str(snap_row.get("layer") or "L2"),
                    action=action,
                    conviction=conviction,
                    expected_beat_pct=exp_beat,
                    eps_surprise_prob=surprise_prob,
                    expected_return_p50=exp_ret,
                    regime_breakout_prob=breakout_prob,
                    gate_verdict=gate_verdict,
                    gate_details=gate_details,
                    rationale=rationale,
                    kill_conditions=kill_conds,
                )
            )
        elif is_held and exp_ret is not None and exp_ret <= -0.15:
            action = "TRIM_HARVEST"
            conviction = 0.50
            rationale = (
                f"Held position reached harvest target: forward expected return {exp_ret:.1%} collapsed below -15%"
            )
            proposals.append(
                ProposalTicket(
                    ticker=t,
                    name=str(snap_row.get("name") or ""),
                    leg=str(snap_row.get("leg") or "US"),
                    layer=str(snap_row.get("layer") or "L2"),
                    action=action,
                    conviction=conviction,
                    expected_beat_pct=exp_beat,
                    eps_surprise_prob=surprise_prob,
                    expected_return_p50=exp_ret,
                    regime_breakout_prob=breakout_prob,
                    gate_verdict=gate_verdict,
                    gate_details=gate_details,
                    rationale=rationale,
                    kill_conditions=kill_conds,
                )
            )
        elif gate_verdict == GateVerdict.PASSED and not breached_reasons and t in bullish_tickers:
            action = "ADD_LONG" if is_held else "INITIATE_LONG"
            base_conv = 0.50
            if exp_beat is not None:
                base_conv += exp_beat * 1.5
            if exp_ret is not None and exp_ret > 0:
                base_conv += min(0.30, exp_ret * 0.5)
            conviction = round(float(np.clip(base_conv, 0.20, 0.95)), 2)

            beat_str = f"{exp_beat:+.1%}" if exp_beat is not None else "N/A"
            ret_str = f"{exp_ret:+.1%}" if exp_ret is not None else "N/A"
            win_str = f"{surprise_prob:.0%}" if surprise_prob is not None else "N/A"
            rationale = (
                f"Passed G1-G4 gates. Supply-chain beat: {beat_str}, "
                f"12M P50 return: {ret_str}, "
                f"beat win rate: {win_str}"
            )
            proposals.append(
                ProposalTicket(
                    ticker=t,
                    name=str(snap_row.get("name") or ""),
                    leg=str(snap_row.get("leg") or "US"),
                    layer=str(snap_row.get("layer") or "L2"),
                    action=action,
                    conviction=conviction,
                    expected_beat_pct=exp_beat,
                    eps_surprise_prob=surprise_prob,
                    expected_return_p50=exp_ret,
                    regime_breakout_prob=breakout_prob,
                    gate_verdict=gate_verdict,
                    gate_details=gate_details,
                    rationale=rationale,
                    kill_conditions=kill_conds,
                )
            )

    # Rank proposals
    action_priority = {
        "INITIATE_LONG": 0,
        "ADD_LONG": 0,
        "EXIT_INVALIDATED": 1,
        "SHORT_FROTH": 2,
        "TRIM_HARVEST": 3,
        "HOLD_MONITOR": 4,
    }
    proposals.sort(
        key=lambda p: (
            action_priority.get(p.action, 5),
            -abs(p.conviction),
            -_num_or(p.expected_return_p50, -999.0),
        )
    )
    proposals = proposals[:max_proposals]

    # Synthesize macro regime summary
    total_names = len(snap_map)
    froth_count = sum(1 for r in snap_map.values() if bool(r.get("froth_flag")))
    valid_arf = [_num(r.get("arf")) for r in snap_map.values() if _num(r.get("arf")) is not None]
    median_arf = float(np.median(valid_arf)) if valid_arf else 50.0

    valid_v = [_num(r.get("v_score")) for r in snap_map.values() if _num(r.get("v_score")) is not None]
    median_v = float(np.median(valid_v)) if valid_v else 50.0

    regime_summary = (
        f"As-of {as_of.isoformat()} ({total_names} tickers): Market Median ARF={median_arf:.1f}, "
        f"Median Valuation Stretch V={median_v:.1f}. Active Froth Bubbles={froth_count} names."
    )

    # Render Markdown briefing
    brief_lines = [
        "# 💼 AI-CIO 自主投资决策简报 (Autonomous Decision Packet)",
        f"**Packet ID:** `{packet_id}` | **As Of Date:** `{as_of.isoformat()}` | **Generated At:** `{datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}`",
        "",
        "---",
        "",
        "## 1. 宏观与 AI 价值链全局状态 (Macro & Value Chain Regime)",
        f"> {regime_summary}",
        "",
    ]

    if customer_shocks:
        brief_lines.extend([
            "## 2. 下游需求冲击传导模拟 (Causal Supply-Chain Shock Propagation)",
            f"**Hyperscaler Shocks:** {', '.join(f'`{k}: {v:+.1%}`' for k, v in customer_shocks.items())}",
            "",
        ])
        if not shock_df.empty:
            top_shocks = shock_df.head(6)
            brief_lines.append("| 标的代码 | 名称 | 区域 | 层级 | 基准预测 | 冲击后预测 | 弹性增量 (Δ) | P50 空间 |")
            brief_lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
            for _, sr in top_shocks.iterrows():
                ret_val = _num(sr.get("expected_return_p50"))
                ret_str = f"{ret_val:+.1%}" if ret_val is not None else "—"
                brief_lines.append(
                    f"| **{sr['ticker']}** | {sr['name']} | {sr['leg']} | {sr['layer']} | "
                    f"{sr['base_pred_growth']:+.1%} | {sr['shocked_pred_growth']:+.1%} | "
                    f"**{sr['growth_delta']:+.1%}** | {ret_str} |"
                )
            brief_lines.append("")

    brief_lines.extend([
        "## 3. 活跃持仓哨兵与触发告警 (Active Thesis Watchdog Alerts)",
    ])
    if watchdog_alerts:
        brief_lines.append("| 严重性 | 标的 | 告警类型 | 触发规则 | 当前指标值 | 建议动作 |")
        brief_lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
        for alert in watchdog_alerts:
            sev_badge = (
                "🔴 **CRITICAL**" if alert.severity == "CRITICAL"
                else "🟡 **WARNING**" if alert.severity == "WARNING"
                else "🔵 **INFO**"
            )
            brief_lines.append(
                f"| {sev_badge} | **{alert.ticker}** ({alert.name}) | `{alert.alert_type}` | "
                f"{alert.triggered_rule} | `{alert.current_value}` | **{alert.recommended_action}** |"
            )
        brief_lines.append("")
    else:
        brief_lines.append("✅ 哨兵监测正常：当前无持仓触及定量证伪 (Kill Conditions) 或估值泡沫熔断。\n")

    brief_lines.extend([
        "## 4. 推荐执行交易提案与风控门禁 (Actionable Proposal Tickets & Risk Gates)",
    ])
    if proposals:
        brief_lines.append("| 标的 | 动作 | 置信度 | 超额差 (Beat) | 12M P50空间 | 门禁裁决 | 论证逻辑与核心证伪条件 |")
        brief_lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        for p in proposals:
            act_badge = (
                f"🟢 **{p.action}**" if "LONG" in p.action
                else f"🔴 **{p.action}**" if "SHORT" in p.action or "EXIT" in p.action
                else f"🟠 **{p.action}**"
            )
            beat_val = _num(p.expected_beat_pct)
            p50_val = _num(p.expected_return_p50)
            beat_str = f"{beat_val:+.1%}" if beat_val is not None else "—"
            p50_str = f"{p50_val:+.1%}" if p50_val is not None else "—"
            gate_badge = f"`{p.gate_verdict}`"
            kills_summary = "; ".join(f"{kc.metric} {kc.operator} {kc.threshold}" for kc in p.kill_conditions[:2])
            brief_lines.append(
                f"| **{p.ticker}** ({p.name}) | {act_badge} | `{p.conviction:+.2f}` | {beat_str} | {p50_str} | "
                f"{gate_badge} | {p.rationale} *(Kill: {kills_summary})* |"
            )
        brief_lines.append("")
    else:
        brief_lines.append("当前无满足 G1–G4 准入标准的高置信度提案。\n")

    brief_lines.extend([
        "---",
        "*Report compiled autonomously by ARF AI-CIO Agent. Deterministic G1–G4 risk rules enforced with zero arithmetic hallucination.*",
    ])

    markdown_brief = "\n".join(brief_lines)

    return CIODecisionPacket(
        packet_id=packet_id,
        as_of_date=as_of.isoformat(),
        regime_summary=regime_summary,
        shock_scenario=customer_shocks or {},
        watchdog_alerts=watchdog_alerts,
        proposals=proposals,
        markdown_brief=markdown_brief,
    )


# ── CLI Entrypoint ───────────────────────────────────────────────────────────

def main() -> None:
    """CLI entrypoint for running the Autonomous CIO workflow and generating decision packets."""
    parser = argparse.ArgumentParser(description="ARF Autonomous CIO Decision Packet Generator")
    parser.add_argument(
        "--as-of",
        type=str,
        default=None,
        help="As of date (YYYY-MM-DD). Defaults to latest snapshot.",
    )
    parser.add_argument(
        "--db",
        type=str,
        default="data/arf.db",
        help="Path to DuckDB database file.",
    )
    parser.add_argument(
        "--shock",
        action="extend",
        nargs="+",
        default=[],
        help="Customer CapEx shock in format TICKER:DELTA (e.g. --shock MSFT:+0.15 META:+0.20)",
    )
    parser.add_argument(
        "--held",
        action="extend",
        nargs="+",
        default=[],
        help="Held portfolio tickers to monitor in thesis watchdog (e.g. --held NVDA TSM LITE)",
    )
    parser.add_argument(
        "--max-proposals",
        type=int,
        default=8,
        help="Maximum proposal tickets to return.",
    )

    args = parser.parse_args()
    conn = init_db(Path(args.db))

    # Resolve as_of date
    if args.as_of:
        as_of = date.fromisoformat(args.as_of)
    else:
        latest = conn.execute("SELECT MAX(as_of_date) FROM snapshots").fetchone()[0]
        as_of = latest if latest is not None else date.today()

    # Parse shocks (support both TICKER:DELTA and TICKER=DELTA)
    shocks: dict[str, float] = {}
    for s in args.shock:
        sep = ":" if ":" in s else ("=" if "=" in s else None)
        if sep:
            k, v = s.split(sep, 1)
            try:
                shocks[k.strip().upper()] = float(v)
            except ValueError:
                log.warning("Invalid shock specification: %s", s)

    held = [t.strip().upper() for t in args.held] if args.held else None

    packet = build_cio_decision_packet(
        conn=conn,
        as_of=as_of,
        held_tickers=held,
        customer_shocks=shocks if shocks else None,
        max_proposals=args.max_proposals,
    )

    print(packet.markdown_brief)


if __name__ == "__main__":
    main()
