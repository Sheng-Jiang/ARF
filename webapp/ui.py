"""Shared UI helpers: sidebar, table renderer, scatter plot."""
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from webapp.data import list_dates, refresh_data


def render_sidebar() -> date | None:
    """Render date selector + refresh button; return selected date."""
    dates = list_dates()
    if not dates:
        st.sidebar.warning("No snapshots found. Run the pipeline first.")
        return None
    date_strs = [str(d) for d in dates]
    sel = st.sidebar.selectbox("Snapshot date", date_strs, key="selected_date_str")
    if st.sidebar.button("Refresh data"):
        refresh_data()
        st.rerun()
    return date.fromisoformat(sel)


def _fmt_num(v: object, decimals: int = 1) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    try:
        return f"{float(v):.{decimals}f}"
    except (TypeError, ValueError):
        return "—"


def _fmt_pct(v: object) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    try:
        return f"{float(v) * 100:.1f}%"
    except (TypeError, ValueError):
        return "—"


def _build_display_df(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in df.sort_values("arf", ascending=False, na_position="last").iterrows():
        d = r.get("decile")
        rows.append({
            "Ticker": r.get("ticker", ""),
            "Name": r.get("name", ""),
            "Layer": r.get("layer", ""),
            "D": int(d) if pd.notna(d) else None,
            "ARF": _fmt_num(r.get("arf")),
            "E": _fmt_num(r.get("e_score")),
            "V": _fmt_num(r.get("v_score")),
            "★": "★" if r.get("froth_flag") else "",
            "Fwd P/E": _fmt_num(r.get("forward_pe")),
            "P/S": _fmt_num(r.get("ps_ratio")),
            "Rev YoY": _fmt_pct(r.get("revenue_yoy_growth")),
            "ROE": _fmt_pct(r.get("roe")),
            "_decile": d,
            "_froth": bool(r.get("froth_flag")),
        })
    return pd.DataFrame(rows)


def _row_style(row: pd.Series) -> list[str]:
    d = row.get("_decile")
    froth = bool(row.get("_froth", False))
    try:
        d = int(d) if d is not None and not pd.isna(d) else None
    except (TypeError, ValueError):
        d = None

    if d == 1:
        bg = "background-color: #ffcccc"
    elif d == 2:
        bg = "background-color: #ffe0b3"
    elif d is not None and d >= 8:
        bg = "background-color: #d4edda"
    else:
        bg = ""

    weight = "font-weight: bold" if froth else ""
    style = "; ".join(s for s in [bg, weight] if s)
    return [style] * len(row)


def render_table(df: pd.DataFrame) -> None:
    """Render a ranked leg table with decile row colouring."""
    display = _build_display_df(df)
    styled = display.style.apply(_row_style, axis=1).hide(["_decile", "_froth"], axis="columns")
    st.dataframe(styled, use_container_width=True, hide_index=True)


_DECILE_COLOR = {
    1: "#d62728", 2: "#ff7f0e", 3: "#e8b85d", 4: "#bcbd22",
    5: "#999999", 6: "#98df8a", 7: "#4caf50", 8: "#2ca02c",
    9: "#1a7a20", 10: "#0d5e14",
}


def scatter_plot(df: pd.DataFrame, leg_name: str) -> go.Figure:
    """E-score vs V-score scatter; bubbles sized by market cap, coloured by decile."""
    plot_df = df.dropna(subset=["e_score", "v_score"]).copy()
    if plot_df.empty:
        return go.Figure()

    mktcap = plot_df.get("market_cap_usd", pd.Series([1.0] * len(plot_df), index=plot_df.index))
    mktcap = mktcap.fillna(1.0).clip(lower=1.0)
    sizes = (mktcap / mktcap.max() * 55 + 8).tolist()

    colors = [
        _DECILE_COLOR.get(int(d), "#999999") if pd.notna(d) else "#999999"
        for d in plot_df.get("decile", pd.Series([None] * len(plot_df), index=plot_df.index))
    ]

    def _hover(row: pd.Series) -> str:
        d = int(row["decile"]) if pd.notna(row.get("decile")) else "?"
        ps = _fmt_num(row.get("ps_ratio"))
        roe = _fmt_pct(row.get("roe"))
        return (
            f"<b>{row['ticker']}</b> — {row.get('name', '')}<br>"
            f"ARF {_fmt_num(row.get('arf'))}  D{d}  {'★' if row.get('froth_flag') else ''}<br>"
            f"E {_fmt_num(row.get('e_score'))}  V {_fmt_num(row.get('v_score'))}<br>"
            f"P/S {ps}  ROE {roe}"
        )

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=plot_df["e_score"].tolist(),
        y=plot_df["v_score"].tolist(),
        mode="markers+text",
        marker=dict(
            size=sizes,
            color=colors,
            opacity=0.85,
            line=dict(width=1, color="#333"),
        ),
        text=plot_df["ticker"].tolist(),
        textposition="top center",
        hovertext=[_hover(row) for _, row in plot_df.iterrows()],
        hoverinfo="text",
    ))
    fig.add_hline(y=50, line_dash="dot", line_color="gray", opacity=0.4)
    fig.add_vline(x=50, line_dash="dot", line_color="gray", opacity=0.4)
    fig.update_layout(
        title=f"{leg_name} — AI Exposure (E) vs Valuation Stretch (V)",
        xaxis_title="E-score — AI Exposure →",
        yaxis_title="V-score — Valuation Stretch →",
        xaxis=dict(range=[-5, 105]),
        yaxis=dict(range=[-5, 105]),
        height=480,
        showlegend=False,
        margin=dict(t=50, b=40),
    )
    return fig
