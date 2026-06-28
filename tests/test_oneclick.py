from datetime import date
import pandas as pd
import pytest
from unittest.mock import MagicMock, patch

from arf.oneclick import (
    select_top_china_stocks,
    _compute_thermo_deltas,
    _backtest_summary_for_gemini,
    generate_report_html,
    ReportData,
    StockBacktestResult,
    ThermometerDelta,
)


def test_select_top_china_stocks():
    df = pd.DataFrame([
        {"ticker": "A", "leg": "China", "arf": 80.0},
        {"ticker": "B", "leg": "US", "arf": 90.0},
        {"ticker": "C", "leg": "China", "arf": 95.0},
        {"ticker": "D", "leg": "China", "arf": None},
        {"ticker": "E", "leg": "China", "arf": 70.0},
        {"ticker": "F", "leg": "China", "arf": 60.0},
        {"ticker": "G", "leg": "China", "arf": 50.0},
    ])
    top = select_top_china_stocks(df, n=3)
    assert len(top) == 3
    assert top.iloc[0]["ticker"] == "C"
    assert top.iloc[1]["ticker"] == "A"
    assert top.iloc[2]["ticker"] == "E"


def test_compute_thermo_deltas():
    # Empty or 1 row
    df_empty = pd.DataFrame(columns=["as_of_date", "leg", "count_absolute_froth", "count_froth", "median_ev_sales_pct", "median_growth_gap_pct", "total"])
    assert len(_compute_thermo_deltas(df_empty)) == 0

    df_one = pd.DataFrame([
        {"as_of_date": date(2026, 6, 26), "leg": "China", "count_absolute_froth": 1, "count_froth": 1, "median_ev_sales_pct": 50.0, "median_growth_gap_pct": 5.0, "total": 36}
    ])
    deltas = _compute_thermo_deltas(df_one)
    assert len(deltas) == 1
    assert deltas[0].absolute_froth_delta == "—"

    # Multi rows
    df_multi = pd.DataFrame([
        {"as_of_date": date(2026, 6, 19), "leg": "China", "count_absolute_froth": 1, "count_froth": 1, "median_ev_sales_pct": 50.0, "median_growth_gap_pct": 5.0, "total": 36},
        {"as_of_date": date(2026, 6, 26), "leg": "China", "count_absolute_froth": 3, "count_froth": 2, "median_ev_sales_pct": 55.0, "median_growth_gap_pct": 4.0, "total": 36},
        {"as_of_date": date(2026, 6, 19), "leg": "US", "count_absolute_froth": 2, "count_froth": 1, "median_ev_sales_pct": 70.0, "median_growth_gap_pct": 10.0, "total": 32},
        {"as_of_date": date(2026, 6, 26), "leg": "US", "count_absolute_froth": 1, "count_froth": 1, "median_ev_sales_pct": 65.0, "median_growth_gap_pct": 12.0, "total": 32},
    ])
    deltas = _compute_thermo_deltas(df_multi)
    assert len(deltas) == 2
    cn_delta = next(d for d in deltas if d.leg == "China")
    us_delta = next(d for d in deltas if d.leg == "US")
    assert cn_delta.absolute_froth_delta == "+2"
    assert cn_delta.ev_sales_delta == "+5.00%"
    assert cn_delta.growth_gap_delta == "-1.00%"
    assert us_delta.absolute_froth_delta == "-1"
    assert us_delta.ev_sales_delta == "-5.00%"
    assert us_delta.growth_gap_delta == "+2.00%"


def test_backtest_summary_for_gemini():
    strat_results = pd.DataFrame([
        {"sharpe": 1.5, "return": 15.0, "dd": 5.0, "maperiod": 20}
    ])
    stock_res = StockBacktestResult(
        ticker="688256.SH",
        name="寒武纪",
        tech_score=75.0,
        rsi=60.0,
        ma_bullish=True,
        chip_profit_ratio=0.85,
        chip_avg_cost=300.0,
        strategy_results={"MA 策略 (单均线)": strat_results},
        best_strategy="MA 策略 (单均线)",
        best_sharpe=1.5,
        best_return=15.0,
        best_max_dd=5.0,
    )
    summary = _backtest_summary_for_gemini([stock_res])
    assert "### 688256.SH (寒武纪)" in summary
    assert "技术评分: 75.0" in summary
    assert "均线多头: 是" in summary
    assert "最优策略: MA 策略 (单均线)" in summary
    assert "收益=15.0%" in summary


def test_generate_report_html():
    report = ReportData(as_of=date(2026, 6, 26))
    report.us_df = pd.DataFrame([{"ticker": "NVDA", "name": "NVIDIA", "leg": "US", "arf": 85.0, "decile": 2, "e_score": 90.0, "v_score": 80.0}])
    report.china_df = pd.DataFrame([{"ticker": "688256.SH", "name": "寒武纪", "leg": "China", "arf": 75.0, "decile": 3, "e_score": 94.0, "v_score": 56.0}])
    report.thermo_deltas = [
        ThermometerDelta(leg="US", absolute_froth=2, absolute_froth_delta="+1", relative_froth=1, relative_froth_delta="0", median_ev_sales_pct=50.0, ev_sales_delta="+2.00%", median_growth_gap=5.0, growth_gap_delta="+1.00%")
    ]
    report.thermo_chart_html = "<div>Thermo Chart</div>"
    report.valuation_chart_html = "<div>Valuation Chart</div>"
    
    html = generate_report_html(report)
    assert "AI Stack Bubble Monitor" in html
    assert "NVDA" in html
    assert "688256.SH" in html
    assert "Thermo Chart" in html
    assert "Valuation Chart" in html
