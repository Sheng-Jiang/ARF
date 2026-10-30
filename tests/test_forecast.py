from datetime import date

import pandas as pd
import pytest

from arf.db import (
    init_db,
    query_forecasts,
    query_latest_forecasts,
    upsert_snapshot,
)
from arf.forecast import (
    calibrate_eps_surprise_probability,
    compute_fair_value_distribution,
    compute_regime_breakout,
    compute_revision_velocity,
    compute_supply_chain_growth,
    generate_forecast_for_ticker,
    generate_forecasts_for_universe,
    seed_default_supply_chain_links,
)


@pytest.fixture
def conn(tmp_path):
    db_path = tmp_path / "test_forecast.db"
    c = init_db(db_path)
    yield c
    c.close()


def test_compute_supply_chain_growth_empty():
    empty_df = pd.DataFrame(columns=["supplier_ticker", "customer_ticker", "revenue_share_pct"])
    growth = compute_supply_chain_growth("NVDA", empty_df, {}, organic_growth=0.20)
    assert growth == 0.20

    # Bottleneck clamp
    growth_clamped = compute_supply_chain_growth(
        "NVDA", empty_df, {}, organic_growth=0.35, bottleneck_clamp=0.25
    )
    assert growth_clamped == 0.25


def test_compute_supply_chain_growth_weighted():
    links_df = pd.DataFrame([
        {"supplier_ticker": "300308.SZ", "customer_ticker": "NVDA", "revenue_share_pct": 40.0},
        {"supplier_ticker": "300308.SZ", "customer_ticker": "GOOGL", "revenue_share_pct": 20.0},
    ])
    # NVDA grows at 50%, GOOGL at 30%, remaining 40% unmapped grows at organic 10%
    cust_map = {"NVDA": 0.50, "GOOGL": 0.30}
    # Expected: 0.40 * 0.50 + 0.20 * 0.30 + 0.40 * 0.10 = 0.20 + 0.06 + 0.04 = 0.30
    growth = compute_supply_chain_growth(
        "300308.SZ", links_df, cust_map, organic_growth=0.10
    )
    assert pytest.approx(growth, abs=1e-4) == 0.30

    # Test bottleneck clamp capping the growth
    clamped = compute_supply_chain_growth(
        "300308.SZ", links_df, cust_map, organic_growth=0.10, bottleneck_clamp=0.22
    )
    assert pytest.approx(clamped, abs=1e-4) == 0.22


def test_calibrate_eps_surprise_probability():
    # Prior / baseline
    p_base = calibrate_eps_surprise_probability(expected_beat_pct=0.0, revision_velocity_14d=0.0)
    assert pytest.approx(p_base, abs=0.01) == 0.50

    # Positive expected beat boosts probability
    p_high = calibrate_eps_surprise_probability(expected_beat_pct=0.15, revision_velocity_14d=0.05)
    assert p_high > 0.80

    # Severe negative revision drops probability
    p_low = calibrate_eps_surprise_probability(expected_beat_pct=-0.20, revision_velocity_14d=-0.10)
    assert p_low < 0.20

    # Clamping limits [0.05, 0.95]
    p_extreme_high = calibrate_eps_surprise_probability(expected_beat_pct=5.0)
    assert p_extreme_high <= 0.95
    p_extreme_low = calibrate_eps_surprise_probability(expected_beat_pct=-5.0)
    assert p_extreme_low >= 0.05


def test_compute_fair_value_distribution():
    price = 100.0
    fcf0 = 5_000_000_000.0
    market_cap = 100_000_000_000.0
    pred_g = 0.25

    p10, p50, p90, exp_ret = compute_fair_value_distribution(
        price=price,
        fcf0=fcf0,
        market_cap=market_cap,
        predicted_growth=pred_g,
        wacc=0.10,
        leg="US",
    )

    assert p10 is not None and p50 is not None and p90 is not None and exp_ret is not None
    # Hierarchy check: P10 <= P50 <= P90
    assert p10 <= p50 <= p90
    # Expected return matches formula
    assert pytest.approx(exp_ret, abs=1e-3) == (p50 - price) / price

    # Negative or invalid price/market_cap returns None
    assert compute_fair_value_distribution(0.0, fcf0, market_cap, pred_g) == (None, None, None, None)
    assert compute_fair_value_distribution(price, fcf0, -100.0, pred_g) == (None, None, None, None)

    # Missing/negative FCF fallback check
    p10_f, p50_f, p90_f, _ = compute_fair_value_distribution(
        price=price,
        fcf0=-100.0,
        market_cap=market_cap,
        predicted_growth=pred_g,
    )
    assert p10_f is not None and p50_f is not None and p90_f is not None
    assert p10_f <= p50_f <= p90_f


def test_compute_regime_breakout():
    price = 100.0
    # Tech row missing
    prob, conc = compute_regime_breakout(price, None)
    assert prob == 0.50
    assert conc is None

    # Strong bullish setup: chip_profit >= 0.80, tight chip_90_cost concentration, ma_bullish, expected_beat
    strong_tech = {
        "chip_profit_ratio": 0.85,
        "chip_avg_cost": 95.0,
        "chip_90_cost_min": 92.0,
        "chip_90_cost_max": 98.0,  # spread = 6.0 / 95.0 = 0.063 (< 0.10)
        "ma_bullish_alignment": True,
        "rsi": 62.0,
    }
    prob_bull, conc_bull = compute_regime_breakout(
        price, strong_tech, expected_beat_pct=0.12, froth_flag=False
    )
    assert prob_bull > 0.80
    assert conc_bull is not None
    assert conc_bull < 0.10

    # Froth penalty and high RSI penalty
    prob_froth, _ = compute_regime_breakout(
        price, strong_tech, expected_beat_pct=0.12, froth_flag=True
    )
    assert prob_froth < prob_bull


def test_compute_revision_velocity(conn):
    as_of = date(2026, 5, 20)
    # Insert dummy research reports into research_reports
    # report_date within last 7 days vs 14 days ago vs 30 days ago
    reports = [
        {"ticker": "NVDA", "report_date": "2026-04-20", "eps_forecast": 2.0, "target_price": 120.0},
        {"ticker": "NVDA", "report_date": "2026-05-06", "eps_forecast": 2.2, "target_price": 130.0},
        {"ticker": "NVDA", "report_date": "2026-05-18", "eps_forecast": 2.5, "target_price": 150.0},
    ]
    for r in reports:
        conn.execute(
            """
            INSERT INTO research_reports (ticker, as_of_date, report_date, institution, title, target_price, rating, eps_forecast)
            VALUES (?, ?, ?, 'Morgan Stanley', 'Report', ?, 'Overweight', ?)
            """,
            [r["ticker"], as_of, r["report_date"], r["target_price"], r["eps_forecast"]],
        )

    v14, v30 = compute_revision_velocity("NVDA", conn, as_of)
    assert v14 is not None
    assert v30 is not None
    # Latest is 2.5 vs 14d ago 2.2 -> positive
    assert v14 > 0.0
    # Latest is 2.5 vs 30d ago 2.0 -> positive
    assert v30 > 0.0


def test_generate_forecast_for_ticker_and_universe(conn):
    as_of = date(2026, 5, 20)

    # 1. Insert snapshot data for NVDA and 300308.SZ
    snap_data = pd.DataFrame([
        {
            "ticker": "NVDA",
            "name": "NVIDIA",
            "leg": "US",
            "layer": "L2",
            "as_of_date": as_of,
            "price": 125.0,
            "market_cap_usd": 3.0e12,
            "free_cash_flow": 6.0e10,
            "eps_2yr_cagr": 0.35,
            "revenue_yoy_growth": 0.55,
            "revenue_ntm": 1.4e11,
            "roe": 0.85,
            "froth_flag": False,
        },
        {
            "ticker": "300308.SZ",
            "name": "Innolight",
            "leg": "China",
            "layer": "L3",
            "as_of_date": as_of,
            "price": 180.0,
            "market_cap_usd": 3.0e10,
            "free_cash_flow": 8.0e8,
            "eps_2yr_cagr": 0.28,
            "revenue_yoy_growth": 0.40,
            "revenue_ntm": 4.0e9,
            "roe": 0.25,
            "froth_flag": False,
        },
    ])
    upsert_snapshot(conn, snap_data, as_of)

    # 2. Seed default supply chain links
    seed_default_supply_chain_links(conn)

    # 3. Generate forecast for 300308.SZ
    fc = generate_forecast_for_ticker("300308.SZ", as_of, conn)
    assert fc is not None
    assert fc.ticker == "300308.SZ"
    assert fc.predicted_rev_growth > 0.0
    assert fc.fair_value_p10 is not None
    assert fc.fair_value_p50 is not None
    assert fc.fair_value_p90 is not None
    assert fc.fair_value_p10 <= fc.fair_value_p50 <= fc.fair_value_p90

    # 4. Generate universe forecasts and verify persistence
    universe_df = generate_forecasts_for_universe(as_of, conn, persist=True)
    assert not universe_df.empty
    assert len(universe_df) >= 2

    # Query from db
    saved_fc = query_forecasts(conn, as_of_date=as_of)
    assert not saved_fc.empty
    assert "300308.SZ" in saved_fc["ticker"].values
    assert "NVDA" in saved_fc["ticker"].values

    latest_fc = query_latest_forecasts(conn)
    assert not latest_fc.empty
    assert "NVDA" in latest_fc["ticker"].values
