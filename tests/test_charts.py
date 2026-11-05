"""Tests for the Plotly chart helpers (webapp/charts.py)."""

import pandas as pd

from webapp.charts import draw_pro_kline, draw_result_bar


def _prices() -> pd.DataFrame:
    return pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=40, freq="D"),
        "open": [100 + i for i in range(40)],
        "close": [101 + i for i in range(40)],
        "low": [99 + i for i in range(40)],
        "high": [102 + i for i in range(40)],
        "volume": [1000 + i for i in range(40)],
    })


def test_kline_is_plotly_with_price_ma_and_volume():
    fig = draw_pro_kline(_prices())

    assert fig.data[0].type == "candlestick"
    assert sum(trace.type == "scatter" for trace in fig.data) == 4  # MA5/10/20/30
    assert fig.data[-1].type == "bar"  # volume panel


def test_kline_static_limits_bars_and_disables_hover():
    fig = draw_pro_kline(_prices(), static=True)

    assert len(fig.data[0].x) <= 90
    assert fig.layout.hovermode is False


def test_result_bar_has_one_trace_per_score():
    df = pd.DataFrame({
        "param": [1, 2],
        "return": [0.10, 0.20],
        "dd": [-0.10, -0.05],
        "sharpe": [1.0, 1.2],
    })

    fig = draw_result_bar(df)

    assert len(fig.data) == 3
    assert all(trace.type == "bar" for trace in fig.data)
