"""Unit tests for Autonomous CIO Workflow, Thesis Watchdog, and Decision Packet Engine."""

from datetime import date

import pandas as pd
import pytest

from arf.agent.cio_loop import (
    build_cio_decision_packet,
    default_kill_conditions_for_row,
    evaluate_cio_gates,
    evaluate_thesis_watchdog,
    scan_material_deltas,
    simulate_supply_chain_shock,
)
from arf.agent.schemas import (
    CIODecisionPacket,
    DecisionAction,
    GateVerdict,
    KillCondition,
)
from arf.db import (
    init_db,
    upsert_forecasts,
    upsert_snapshot,
    upsert_supply_chain_links,
)


@pytest.fixture
def cio_test_db(tmp_path):
    """Create an isolated test database with snapshot, forecast, and technical data."""
    db_path = tmp_path / "test_cio_loop.db"
    conn = init_db(db_path)

    as_of = date(2026, 6, 1)

    # 1. Snapshots
    sample_snapshots = pd.DataFrame([
        {
            "ticker": "NVDA", "as_of_date": as_of, "leg": "US", "layer": "L2",
            "name": "NVIDIA", "price": 120.0, "market_cap_usd": 3e12, "ev_usd": 3e12,
            "revenue_ttm": 1e11, "revenue_yoy_growth": 0.80, "gross_margin": 0.75,
            "roe": 0.90, "free_cash_flow": 5e10, "forward_pe": 28.0, "eps_2yr_cagr": 0.35,
            "revenue_3yr_cagr": 0.30, "ps_ratio": 22.0, "ev_sales": 23.0,
            "ev_sales_5yr_percentile": 55.0, "e_score": 90.0, "v_score": 48.0,
            "arf": 65.7, "decile": 4, "froth_flag": False, "implied_growth": 0.12,
            "implied_growth_gap": -0.05, "policy_premium": False, "data_source": "test",
            "currency": "USD", "fx_rate_usd": 1.0,
        },
        {
            "ticker": "GOOGL", "as_of_date": as_of, "leg": "US", "layer": "L3",
            "name": "Alphabet", "price": 180.0, "market_cap_usd": 2.2e12, "ev_usd": 2.1e12,
            "revenue_ttm": 3.5e11, "revenue_yoy_growth": 0.18, "gross_margin": 0.58,
            "roe": 0.30, "free_cash_flow": 7e10, "forward_pe": 22.0, "eps_2yr_cagr": 0.18,
            "revenue_3yr_cagr": 0.15, "ps_ratio": 6.5, "ev_sales": 6.2,
            "ev_sales_5yr_percentile": 45.0, "e_score": 85.0, "v_score": 40.0,
            "arf": 58.3, "decile": 5, "froth_flag": False, "implied_growth": 0.10,
            "implied_growth_gap": -0.08, "policy_premium": False, "data_source": "test",
            "currency": "USD", "fx_rate_usd": 1.0,
        },
        {
            "ticker": "300308.SZ", "as_of_date": as_of, "leg": "China", "layer": "L3",
            "name": "Innolight", "price": 140.0, "market_cap_usd": 1.5e10, "ev_usd": 1.4e10,
            "revenue_ttm": 2e9, "revenue_yoy_growth": 0.60, "gross_margin": 0.35,
            "roe": 0.28, "free_cash_flow": 5e8, "forward_pe": 25.0, "eps_2yr_cagr": 0.30,
            "revenue_3yr_cagr": 0.25, "ps_ratio": 7.5, "ev_sales": 7.0,
            "ev_sales_5yr_percentile": 60.0, "e_score": 88.0, "v_score": 52.0,
            "arf": 67.6, "decile": 4, "froth_flag": False, "implied_growth": 0.16,
            "implied_growth_gap": -0.04, "policy_premium": False, "data_source": "test",
            "currency": "CNY", "fx_rate_usd": 0.14,
        },
        {
            "ticker": "FROTH_CO", "as_of_date": as_of, "leg": "US", "layer": "L4",
            "name": "Froth Corp", "price": 50.0, "market_cap_usd": 2e10, "ev_usd": 2e10,
            "revenue_ttm": 1e8, "revenue_yoy_growth": 0.20, "gross_margin": 0.30,
            "roe": -0.05, "free_cash_flow": -1e7, "forward_pe": 150.0, "eps_2yr_cagr": 0.05,
            "revenue_3yr_cagr": 0.10, "ps_ratio": 45.0, "ev_sales": 46.0,
            "ev_sales_5yr_percentile": 99.0, "e_score": 92.0, "v_score": 95.0,
            "arf": 93.5, "decile": 1, "froth_flag": True, "implied_growth": 0.45,
            "implied_growth_gap": 0.35, "policy_premium": False, "data_source": "test",
            "currency": "USD", "fx_rate_usd": 1.0,
        },
        {
            "ticker": "HARVEST_CO", "as_of_date": as_of, "leg": "US", "layer": "L1",
            "name": "Harvest Energy", "price": 190.0, "market_cap_usd": 5e10, "ev_usd": 6e10,
            "revenue_ttm": 1e10, "revenue_yoy_growth": 0.08, "gross_margin": 0.25,
            "roe": 0.12, "free_cash_flow": 2e9, "forward_pe": 32.0, "eps_2yr_cagr": 0.06,
            "revenue_3yr_cagr": 0.05, "ps_ratio": 5.0, "ev_sales": 6.0,
            "ev_sales_5yr_percentile": 85.0, "e_score": 50.0, "v_score": 75.0,
            "arf": 61.2, "decile": 5, "froth_flag": False, "implied_growth": 0.14,
            "implied_growth_gap": 0.08, "policy_premium": False, "data_source": "test",
            "currency": "USD", "fx_rate_usd": 1.0,
        },
    ])
    upsert_snapshot(conn, sample_snapshots, as_of)

    # 2. Supply chain links
    links = [
        {
            "supplier_ticker": "300308.SZ",
            "customer_ticker": "NVDA",
            "revenue_share_pct": 40.0,
            "bom_component_pct": 5.0,
            "relationship_type": "optical",
            "verified_source": "test",
        },
        {
            "supplier_ticker": "300308.SZ",
            "customer_ticker": "GOOGL",
            "revenue_share_pct": 20.0,
            "bom_component_pct": 4.0,
            "relationship_type": "optical",
            "verified_source": "test",
        },
    ]
    upsert_supply_chain_links(conn, links)

    # 3. Technical metrics
    conn.execute("""
        INSERT INTO technical_metrics (
            ticker, as_of_date, technical_score, chip_profit_ratio,
            chip_avg_cost, ma_bullish_alignment, rsi
        ) VALUES 
        ('NVDA', '2026-06-01', 85.0, 0.90, 105.0, TRUE, 65.0),
        ('GOOGL', '2026-06-01', 70.0, 0.75, 160.0, TRUE, 55.0),
        ('300308.SZ', '2026-06-01', 80.0, 0.85, 120.0, TRUE, 60.0),
        ('FROTH_CO', '2026-06-01', 30.0, 0.10, 68.0, FALSE, 40.0),
        ('HARVEST_CO', '2026-06-01', 65.0, 0.60, 185.0, TRUE, 72.0)
    """)

    # 4. Forecasts
    sample_forecasts = [
        {
            "ticker": "NVDA", "as_of_date": as_of.isoformat(), "horizon_days": 90,
            "predicted_rev_growth": 0.45, "consensus_rev_growth": 0.35, "expected_beat_pct": 0.10,
            "eps_surprise_prob": 0.75, "revision_velocity_14d": 0.04, "revision_velocity_30d": 0.06,
            "fair_value_p10": 110.0, "fair_value_p50": 155.0, "fair_value_p90": 195.0,
            "expected_return_p50": 0.2917, "regime_breakout_prob": 0.72, "chip_concentration_ratio": 0.08,
            "model_version": "v1.0",
        },
        {
            "ticker": "GOOGL", "as_of_date": as_of.isoformat(), "horizon_days": 90,
            "predicted_rev_growth": 0.20, "consensus_rev_growth": 0.18, "expected_beat_pct": 0.02,
            "eps_surprise_prob": 0.55, "revision_velocity_14d": 0.01, "revision_velocity_30d": 0.02,
            "fair_value_p10": 160.0, "fair_value_p50": 205.0, "fair_value_p90": 240.0,
            "expected_return_p50": 0.1389, "regime_breakout_prob": 0.60, "chip_concentration_ratio": 0.12,
            "model_version": "v1.0",
        },
        {
            "ticker": "300308.SZ", "as_of_date": as_of.isoformat(), "horizon_days": 90,
            "predicted_rev_growth": 0.38, "consensus_rev_growth": 0.30, "expected_beat_pct": 0.08,
            "eps_surprise_prob": 0.70, "revision_velocity_14d": 0.03, "revision_velocity_30d": 0.05,
            "fair_value_p10": 120.0, "fair_value_p50": 175.0, "fair_value_p90": 220.0,
            "expected_return_p50": 0.2500, "regime_breakout_prob": 0.68, "chip_concentration_ratio": 0.09,
            "model_version": "v1.0",
        },
        {
            "ticker": "FROTH_CO", "as_of_date": as_of.isoformat(), "horizon_days": 90,
            "predicted_rev_growth": 0.12, "consensus_rev_growth": 0.05, "expected_beat_pct": 0.07,
            "eps_surprise_prob": 0.60, "revision_velocity_14d": -0.02, "revision_velocity_30d": -0.04,
            "fair_value_p10": 15.0, "fair_value_p50": 25.0, "fair_value_p90": 40.0,
            "expected_return_p50": -0.5000, "regime_breakout_prob": 0.30, "chip_concentration_ratio": 0.25,
            "model_version": "v1.0",
        },
        {
            "ticker": "HARVEST_CO", "as_of_date": as_of.isoformat(), "horizon_days": 90,
            "predicted_rev_growth": 0.06, "consensus_rev_growth": 0.06, "expected_beat_pct": 0.00,
            "eps_surprise_prob": 0.50, "revision_velocity_14d": 0.00, "revision_velocity_30d": 0.00,
            "fair_value_p10": 130.0, "fair_value_p50": 150.0, "fair_value_p90": 180.0,
            "expected_return_p50": -0.2105, "regime_breakout_prob": 0.45, "chip_concentration_ratio": 0.18,
            "model_version": "v1.0",
        },
    ]
    upsert_forecasts(conn, sample_forecasts)

    conn.commit()
    yield conn
    conn.close()


def test_kill_condition_evaluation():
    """Verify KillCondition evaluation across operators, types, and edge cases."""
    # 1. Less than (<)
    cond_lt = KillCondition(metric="expected_beat_pct", operator="<", threshold=-0.10, description="growth drop")
    # Triggered
    trig, msg = cond_lt.evaluate({"expected_beat_pct": -0.15})
    assert trig is True
    assert "breached < -0.1" in msg

    # Not triggered
    trig, msg = cond_lt.evaluate({"expected_beat_pct": 0.05})
    assert trig is False
    assert "holds" in msg

    # 2. Less than or equal (<=)
    cond_le = KillCondition(metric="roe", operator="<=", threshold=0.05)
    trig, _ = cond_le.evaluate({"roe": 0.05})
    assert trig is True
    trig, _ = cond_le.evaluate({"roe": 0.051})
    assert trig is False

    # 3. Greater than (>)
    cond_gt = KillCondition(metric="v_score", operator=">", threshold=60.0)
    trig, _ = cond_gt.evaluate({"v_score": 75.0})
    assert trig is True
    trig, _ = cond_gt.evaluate({"v_score": 50.0})
    assert trig is False

    # 4. Greater than or equal (>=)
    cond_ge = KillCondition(metric="v_score", operator=">=", threshold=60.0)
    trig, _ = cond_ge.evaluate({"v_score": 60.0})
    assert trig is True

    # 5. Equal (==) bool
    cond_eq_bool = KillCondition(metric="froth_flag", operator="==", threshold=True)
    trig, _ = cond_eq_bool.evaluate({"froth_flag": True})
    assert trig is True
    trig, _ = cond_eq_bool.evaluate({"froth_flag": False})
    assert trig is False

    # 6. Equal (==) numeric
    cond_eq_num = KillCondition(metric="decile", operator="==", threshold=1.0)
    trig, _ = cond_eq_num.evaluate({"decile": 1})
    assert trig is True
    trig, _ = cond_eq_num.evaluate({"decile": 2})
    assert trig is False

    # 7. Missing metric
    trig, msg = cond_lt.evaluate({})
    assert trig is False
    assert msg == "metric missing"

    # 8. NaN metric
    trig, msg = cond_lt.evaluate({"expected_beat_pct": float("nan")})
    assert trig is False
    assert msg == "metric missing"

    # 9. None metric
    trig, msg = cond_lt.evaluate({"expected_beat_pct": None})
    assert trig is False
    assert msg == "metric missing"

    # 10. Default kill conditions for row
    defaults = default_kill_conditions_for_row({})
    assert len(defaults) == 4
    metrics = {c.metric for c in defaults}
    assert metrics == {"froth_flag", "expected_beat_pct", "roe", "chip_profit_ratio"}


def test_scan_material_deltas(cio_test_db):
    """Verify Stage 1 delta scanning identifies high-conviction longs and froth hazards."""
    as_of = date(2026, 6, 1)
    deltas = scan_material_deltas(cio_test_db, as_of)
    assert "high_conviction_longs" in deltas
    assert "froth_hazards" in deltas
    assert "breakouts" in deltas

    froth_tickers = [d["ticker"] for d in deltas["froth_hazards"]]
    assert "FROTH_CO" in froth_tickers


def test_evaluate_cio_gates_froth_hurdle_and_g_star_divergence():
    """Verify deterministic G1–G4 outside-model risk gates."""
    # G1: Data Integrity
    v, msg = evaluate_cio_gates({"price": 0.0, "market_cap_usd": 1e9})
    assert v == GateVerdict.BLOCKED_INSUFFICIENT_CRITERIA
    assert "G1 Data Integrity" in msg

    v, msg = evaluate_cio_gates({"price": 100.0, "market_cap_usd": None})
    assert v == GateVerdict.BLOCKED_INSUFFICIENT_CRITERIA

    v, msg = evaluate_cio_gates({"price": float("nan"), "market_cap_usd": 1e9})
    assert v == GateVerdict.BLOCKED_INSUFFICIENT_CRITERIA

    # G3: Froth Circuit Breaker
    v, msg = evaluate_cio_gates({"price": 100.0, "market_cap_usd": 1e9, "froth_flag": True})
    assert v == GateVerdict.BLOCKED_FROTH
    assert "G3 Froth Flag triggered" in msg

    # G2: WACC Hurdle Gate (US WACC = 10%)
    v, msg = evaluate_cio_gates({
        "price": 100.0, "market_cap_usd": 1e9, "froth_flag": False,
        "leg": "US", "roe": 0.06, "v_score": 75.0,
    })
    assert v == GateVerdict.BLOCKED_HURDLE
    assert "G2 Hurdle failed" in msg

    # G2: China leg WACC = 12%
    v, msg = evaluate_cio_gates({
        "price": 100.0, "market_cap_usd": 1e9, "froth_flag": False,
        "leg": "China", "roe": 0.11, "v_score": 62.0,
    })
    assert v == GateVerdict.BLOCKED_HURDLE

    # G2: Low valuation stretch (V=50) does not block even if ROE < WACC
    v, _ = evaluate_cio_gates({
        "price": 100.0, "market_cap_usd": 1e9, "froth_flag": False,
        "leg": "US", "roe": 0.08, "v_score": 50.0,
    })
    assert v == GateVerdict.PASSED

    # G4: Cross-Node Reverse-DCF g* Consistency Gate
    # Supplier g* = 0.40 (> 0.25), Customer avg g* = 0.12 (0.40 > 2 * 0.12 = 0.24)
    v, msg = evaluate_cio_gates(
        {
            "price": 100.0, "market_cap_usd": 1e9, "froth_flag": False,
            "leg": "US", "roe": 0.20, "v_score": 50.0, "implied_growth": 0.40,
        },
        customer_implied_growths=[0.10, 0.14],
    )
    assert v == GateVerdict.BLOCKED_VALUATION_STRETCH
    assert "G4 Supply-chain g* divergence" in msg

    # G4: Passes if customer average g* is high enough (0.40 <= 2 * 0.25)
    v, _ = evaluate_cio_gates(
        {
            "price": 100.0, "market_cap_usd": 1e9, "froth_flag": False,
            "leg": "US", "roe": 0.20, "v_score": 50.0, "implied_growth": 0.40,
        },
        customer_implied_growths=[0.24, 0.26],
    )
    assert v == GateVerdict.PASSED

    # G1–G4 All Passed
    v, msg = evaluate_cio_gates({
        "price": 120.0, "market_cap_usd": 3e12, "froth_flag": False,
        "leg": "US", "roe": 0.90, "v_score": 48.0, "implied_growth": 0.12,
    })
    assert v == GateVerdict.PASSED
    assert "Passed G1-G4" in msg


def test_simulate_supply_chain_shock(cio_test_db):
    """Verify positive hyperscaler CapEx shock boosts supplier growth respecting bottleneck clamp."""
    as_of = date(2026, 6, 1)

    # Shock: NVDA +20%, GOOGL +10%
    shock_df = simulate_supply_chain_shock(
        conn=cio_test_db,
        as_of=as_of,
        customer_shocks={"NVDA": 0.20, "GOOGL": 0.10},
        bottleneck_clamp=0.80,
    )

    assert not shock_df.empty
    expected_cols = [
        "ticker", "name", "leg", "layer", "base_pred_growth", "shocked_pred_growth",
        "growth_delta", "expected_beat_pct", "eps_surprise_prob", "fair_value_p50",
        "expected_return_p50",
    ]
    for col in expected_cols:
        assert col in shock_df.columns

    # 300308.SZ is supplier to NVDA (40%) and GOOGL (20%)
    inno_row = shock_df[shock_df["ticker"] == "300308.SZ"].iloc[0]
    assert inno_row["growth_delta"] > 0
    assert inno_row["shocked_pred_growth"] > inno_row["base_pred_growth"]

    # Verify bottleneck clamp
    huge_shock_df = simulate_supply_chain_shock(
        conn=cio_test_db,
        as_of=as_of,
        customer_shocks={"NVDA": 2.00, "GOOGL": 1.50},
        bottleneck_clamp=0.75,
    )
    inno_clamped = huge_shock_df[huge_shock_df["ticker"] == "300308.SZ"].iloc[0]
    assert inno_clamped["shocked_pred_growth"] <= 0.75


def test_evaluate_thesis_watchdog(cio_test_db):
    """Verify WatchdogAlert generation on froth, kill condition breach, and harvest triggers."""
    as_of = date(2026, 6, 1)

    alerts = evaluate_thesis_watchdog(conn=cio_test_db, as_of=as_of)

    assert len(alerts) > 0
    # Alerts must be sorted by severity: CRITICAL first
    severities = [a.severity for a in alerts]
    assert "CRITICAL" in severities

    alert_tickers = {a.ticker for a in alerts}
    assert "FROTH_CO" in alert_tickers

    froth_alert = [a for a in alerts if a.ticker == "FROTH_CO" and a.alert_type == "FROTH_CIRCUIT_BREAKER"][0]
    assert froth_alert.severity == "CRITICAL"
    assert froth_alert.recommended_action == DecisionAction.AVOID_FROTH

    # Harvest trigger on HARVEST_CO (price=190 >= p90=180 or exp_ret <= -15%)
    harvest_alerts = [a for a in alerts if a.ticker == "HARVEST_CO" and a.alert_type == "HARVEST_TARGET_REACHED"]
    assert len(harvest_alerts) > 0
    assert harvest_alerts[0].recommended_action == DecisionAction.HARVEST


def test_build_cio_decision_packet_end_to_end(cio_test_db):
    """Verify end-to-end CIODecisionPacket generation, proposals, and Markdown briefing."""
    as_of = date(2026, 6, 1)

    packet = build_cio_decision_packet(
        conn=cio_test_db,
        as_of=as_of,
        held_tickers=["NVDA", "FROTH_CO"],
        customer_shocks={"NVDA": 0.15},
        max_proposals=6,
    )

    assert isinstance(packet, CIODecisionPacket)
    assert packet.packet_id.startswith("CIO-PKT-2026-06-01")
    assert packet.as_of_date == "2026-06-01"
    assert "NVIDIA" in packet.markdown_brief or "NVDA" in packet.markdown_brief
    assert len(packet.proposals) > 0

    # Held ticker FROTH_CO should have EXIT_INVALIDATED action
    froth_prop = [p for p in packet.proposals if p.ticker == "FROTH_CO"]
    assert len(froth_prop) > 0
    assert froth_prop[0].action == "EXIT_INVALIDATED"
    assert froth_prop[0].conviction < 0

    # NVDA is in held_tickers and passed gates with high return -> ADD_LONG
    nvda_prop = [p for p in packet.proposals if p.ticker == "NVDA"]
    assert len(nvda_prop) > 0
    assert nvda_prop[0].action == "ADD_LONG"
    assert nvda_prop[0].gate_verdict == GateVerdict.PASSED
    assert nvda_prop[0].conviction > 0
    assert len(nvda_prop[0].kill_conditions) > 0

    # Markdown brief validation
    brief = packet.markdown_brief
    assert "# 💼 AI-CIO 自主投资决策简报" in brief
    assert "1. 宏观与 AI 价值链全局状态" in brief
    assert "2. 下游需求冲击传导模拟" in brief
    assert "3. 活跃持仓哨兵与触发告警" in brief
    assert "4. 推荐执行交易提案与风控门禁" in brief
