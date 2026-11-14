"""Plotly Chart Generators for stock prices and backtesting results.

These used to return pyecharts objects rendered through ``streamlit-echarts``.
That package's 0.7.x releases register a file-backed component that Streamlit
1.58 refuses to load ("must be declared ... with asset_dir"), so the charts are
now native Plotly — the same library the rest of the dashboard uses.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# China market convention: red = up, green = down.
_UP_COLOR = "#ec0000"
_DOWN_COLOR = "#00da3c"
_MA_COLORS = {5: "#f6c343", 10: "#ff7f50", 20: "#87cefa", 30: "#b0c4de"}


def _column(df: pd.DataFrame, zh: str, en: str) -> str:
    return zh if zh in df.columns else en


def split_data(df: pd.DataFrame) -> tuple[list[str], list[list[float]], pd.Series, list[list[float]]]:
    """Split a price DataFrame into Plotly-friendly lists (ZH or EN headers)."""
    date_col = _column(df, "日期", "date")
    open_col = _column(df, "开盘", "open")
    close_col = _column(df, "收盘", "close")
    low_col = _column(df, "最低", "low")
    high_col = _column(df, "最高", "high")
    vol_col = _column(df, "成交量", "volume")

    df_temp = df.copy()
    df_temp[date_col] = pd.to_datetime(df_temp[date_col]).dt.strftime("%Y-%m-%d")

    x_data = df_temp[date_col].values.tolist()
    y_data = df_temp[[open_col, close_col, low_col, high_col]].values.tolist()
    df_close = df_temp[close_col]

    df_temp["index"] = df_temp.index
    df_temp["rise"] = df_temp[[open_col, close_col]].apply(
        lambda x: 1 if x.iloc[0] > x.iloc[1] else -1, axis=1
    )
    y_vol = df_temp[["index", vol_col, "rise"]].values.tolist()
    return x_data, y_data, df_close, y_vol


def calculate_ma(day_count: int, df_close: pd.Series) -> list[float | None]:
    """Moving average as a list of floats with ``None`` for the warm-up NaNs."""
    df_ma = df_close.rolling(day_count).mean().round(2)
    return [None if pd.isna(v) else float(v) for v in df_ma.values]


def draw_pro_kline(df: pd.DataFrame, static: bool = False, lang: str = "zh") -> go.Figure:
    """Candlestick chart with MA5/10/20/30 and a volume panel.

    ``static`` (used on phones) keeps only the most recent ~90 bars and turns
    off hover/zoom so the chart cannot hijack page scrolling.
    """
    if static:
        df = df.tail(90)

    date_col = _column(df, "日期", "date")
    open_col = _column(df, "开盘", "open")
    close_col = _column(df, "收盘", "close")
    low_col = _column(df, "最低", "low")
    high_col = _column(df, "最高", "high")
    vol_col = _column(df, "成交量", "volume")

    dates = pd.to_datetime(df[date_col]).dt.strftime("%Y-%m-%d").tolist()
    opens = df[open_col].tolist()
    closes = df[close_col].tolist()
    lows = df[low_col].tolist()
    highs = df[high_col].tolist()
    volumes = df[vol_col].tolist()

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.72, 0.28],
    )

    fig.add_trace(
        go.Candlestick(
            x=dates,
            open=opens,
            high=highs,
            low=lows,
            close=closes,
            name="Daily K" if (static or lang == "en") else "日K",
            increasing_line_color=_UP_COLOR,
            increasing_fillcolor=_UP_COLOR,
            decreasing_line_color=_DOWN_COLOR,
            decreasing_fillcolor=_DOWN_COLOR,
            showlegend=False,
        ),
        row=1,
        col=1,
    )

    for period, color in _MA_COLORS.items():
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=calculate_ma(period, df[close_col]),
                mode="lines",
                name=f"MA{period}",
                line=dict(width=1.5, color=color),
                hoverinfo="skip" if static else "all",
            ),
            row=1,
            col=1,
        )

    vol_colors = [
        _UP_COLOR if close >= open_ else _DOWN_COLOR
        for open_, close in zip(opens, closes, strict=False)
    ]
    fig.add_trace(
        go.Bar(
            x=dates,
            y=volumes,
            name="Volume",
            marker_color=vol_colors,
            showlegend=False,
            hoverinfo="skip" if static else "all",
        ),
        row=2,
        col=1,
    )

    fig.update_xaxes(type="category", nticks=12)
    fig.update_yaxes(side="right", row=1, col=1)
    fig.update_yaxes(side="right", showticklabels=not static, row=2, col=1)
    fig.update_layout(
        height=360 if static else 520,
        margin=dict(l=10, r=10, t=30, b=10),
        bargap=0.1,
        showlegend=not static,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode=False if static else "x unified",
        dragmode=False if static else "zoom",
        xaxis_rangeslider_visible=False,
    )
    return fig


def draw_result_bar(df: pd.DataFrame, n_scores: int = 3) -> go.Figure:
    """Grouped bar chart comparing backtest metrics across parameter combinations."""
    params_columns = list(df.columns[:-n_scores])
    scores_columns = list(df.columns[-n_scores:])

    x_data = (
        df[params_columns]
        .apply(
            lambda x: "<br>".join(
                f"{name}: {value}"
                for name, value in zip(params_columns, x, strict=False)
            ),
            axis=1,
        )
        .tolist()
    )

    fig = go.Figure()
    for col in scores_columns:
        fig.add_trace(go.Bar(x=x_data, y=df[col].tolist(), name=str(col)))

    fig.update_layout(
        barmode="group",
        height=450,
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified",
    )
    return fig
