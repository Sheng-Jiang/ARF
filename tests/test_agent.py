"""Unit tests for the ARF Autonomous Investment Agent."""
from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from arf.agent.radar import discover_supply_chain_candidates, scan_valuation_anomalies
from arf.agent.thesis import generate_opportunity_card
from arf.agent.tools import (
    get_stock_quant_profile,
    query_quant_database,
    search_value_chain_layer,
)
from arf.db import init_db, query_candidates, upsert_snapshot


@pytest.fixture
def agent_test_db(tmp_path):
    db_path = tmp_path / "test_agent_arf.db"
    conn = init_db(db_path)

    # Insert sample snapshot
    as_of = date(2026, 6, 1)
    sample_snapshot = pd.DataFrame([
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
    ])
    upsert_snapshot(conn, sample_snapshot, as_of)

    # Insert technical metrics
    conn.execute("""
        INSERT INTO technical_metrics (
            ticker, as_of_date, technical_score, chip_profit_ratio,
            chip_avg_cost, ma_bullish_alignment, rsi
        ) VALUES 
        ('NVDA', '2026-06-01', 82.0, 0.88, 105.0, TRUE, 62.0),
        ('FROTH_CO', '2026-06-01', 35.0, 0.15, 68.0, FALSE, 41.0)
    """)
    conn.commit()
    conn.close()
    return db_path


def test_get_stock_quant_profile(agent_test_db):
    profile = get_stock_quant_profile("NVDA", date(2026, 6, 1), db_path=agent_test_db)
    assert profile is not None
    assert profile["ticker"] == "NVDA"
    assert profile["decile"] == 4
    assert profile["roe"] == 0.90
    assert profile["technical_score"] == 82.0
    assert profile["chip_profit_ratio"] == 0.88
    assert profile["ma_bullish"] is True


def test_query_quant_database_security_guards(agent_test_db):
    # Valid query
    rows = query_quant_database("SELECT ticker, arf FROM snapshots ORDER BY arf DESC", db_path=agent_test_db)
    assert len(rows) == 2
    assert rows[0]["ticker"] == "FROTH_CO"

    # Block non-SELECT
    with pytest.raises(ValueError, match="Only SELECT queries are permitted"):
        query_quant_database("INSERT INTO snapshots (ticker) VALUES ('FAIL')", db_path=agent_test_db)

    with pytest.raises(ValueError, match="Disallowed DDL/DML keyword"):
        query_quant_database("SELECT * FROM snapshots; DROP TABLE snapshots;", db_path=agent_test_db)


def test_search_value_chain_layer(agent_test_db):
    l2_rows = search_value_chain_layer("L2", db_path=agent_test_db)
    assert len(l2_rows) == 1
    assert l2_rows[0]["ticker"] == "NVDA"

    l4_rows = search_value_chain_layer("L4", leg="US", db_path=agent_test_db)
    assert len(l4_rows) == 1
    assert l4_rows[0]["ticker"] == "FROTH_CO"


def test_scan_valuation_anomalies(agent_test_db):
    anomalies = scan_valuation_anomalies(date(2026, 6, 1), db_path=agent_test_db)
    
    # NVDA: E_score=90, V_score=48, decile=4, ROE=0.90 -> GARP Opportunity
    garp = anomalies["garp_opportunities"]
    assert len(garp) == 1
    assert garp[0]["ticker"] == "NVDA"

    # FROTH_CO: froth_flag=True -> Froth Warning
    froth = anomalies["froth_warnings"]
    assert len(froth) == 1
    assert froth[0]["ticker"] == "FROTH_CO"

    # NVDA: ma_bullish=True, chip_profit_ratio=0.88, technical_score=82 -> Technical Breakout
    breakouts = anomalies["technical_breakouts"]
    assert len(breakouts) == 1
    assert breakouts[0]["ticker"] == "NVDA"


def test_generate_opportunity_card_mock(agent_test_db):
    mock_response = MagicMock()
    mock_response.text = """
    {
      "thesis_type": "garp_value",
      "title": "NVIDIA: Blackwell Ramp and Superior Capital Returns",
      "bull_case": "Unmatched 90% ROE and software moat with CUDA ecosystem.",
      "bear_case": "ASIC alternatives and potential hyperscaler capex moderation.",
      "synthesis": "Compelling risk/reward in decile D4 with multiple de-rating.",
      "valuation_entry_zone": "Forward P/E < 30",
      "invalidation_criteria": "Gross margin compresses below 70%",
      "confidence_score": 88.0,
      "catalysts": ["Q2 Earnings Report", "Blackwell shipment inflection"]
    }
    """
    mock_response.candidates = []

    with patch("google.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = mock_response

        card = generate_opportunity_card(
            "NVDA",
            date(2026, 6, 1),
            api_key="fake_test_key",
            db_path=agent_test_db,
            persist=True,
        )

        assert card.ticker == "NVDA"
        assert card.thesis_type == "garp_value"
        assert card.confidence_score == 88.0
        assert card.quant_profile.roe == 0.90

        # Verify client called with model
        call_kwargs = mock_client.models.generate_content.call_args[1]
        assert "gemini" in call_kwargs["model"]


def test_discover_supply_chain_candidates_mock(agent_test_db):
    mock_response = MagicMock()
    mock_response.text = """
    {
      "theme": "liquid cooling",
      "candidates": [
        {
          "ticker": "VRT",
          "name": "Vertiv Holdings",
          "leg": "US",
          "layer": "L1",
          "pure_play_est": 45.0,
          "supply_role": "Liquid cooling cold plates and CDI units",
          "key_customers": ["NVIDIA", "Microsoft"],
          "notes": "Leading thermal provider for GB200 racks"
        }
      ]
    }
    """

    with patch("google.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = mock_response

        cands = discover_supply_chain_candidates(
            "liquid cooling",
            api_key="fake_key",
            db_path=agent_test_db,
            stage_to_db=True,
        )

        assert len(cands) == 1
        assert cands[0].ticker == "VRT"
        assert cands[0].layer == "L1"

        # Verify staged in candidate_pool
        conn = init_db(agent_test_db)
        staged_df = query_candidates(conn)
        conn.close()
        assert len(staged_df) == 1
        assert staged_df.iloc[0]["ticker"] == "VRT"
