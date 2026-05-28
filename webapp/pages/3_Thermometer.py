"""Bubble Thermometer — historical trend of froth and D1 counts across snapshots."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from webapp.data import load_thermometer_series
from webapp.ui import render_sidebar

st.set_page_config(page_title="ARF — Thermometer", layout="wide")
st.title("Bubble Thermometer")
st.caption("Week-over-week evolution of AI valuation froth. Add more pipeline runs to see the trend build.")

render_sidebar()

thermo = load_thermometer_series()
us_thermo = thermo[thermo["leg"] == "US"].sort_values("as_of_date")
cn_thermo = thermo[thermo["leg"] == "China"].sort_values("as_of_date")

if thermo.empty:
    st.warning("No historical data. Run the pipeline on at least one date first.")
    st.stop()

fig = go.Figure()

if not us_thermo.empty:
    fig.add_trace(go.Scatter(
        x=us_thermo["as_of_date"], y=us_thermo["count_froth"],
        name="US — froth ★", mode="lines+markers",
        line=dict(color="#d62728", width=2),
        marker=dict(size=8),
    ))
    fig.add_trace(go.Scatter(
        x=us_thermo["as_of_date"], y=us_thermo["count_arf_gte_90"],
        name="US — ARF ≥ 90", mode="lines+markers",
        line=dict(color="#d62728", width=2, dash="dot"),
        marker=dict(size=6),
    ))

if not cn_thermo.empty:
    fig.add_trace(go.Scatter(
        x=cn_thermo["as_of_date"], y=cn_thermo["count_froth"],
        name="China — froth ★", mode="lines+markers",
        line=dict(color="#e6a817", width=2),
        marker=dict(size=8),
    ))
    fig.add_trace(go.Scatter(
        x=cn_thermo["as_of_date"], y=cn_thermo["count_arf_gte_90"],
        name="China — ARF ≥ 90", mode="lines+markers",
        line=dict(color="#e6a817", width=2, dash="dot"),
        marker=dict(size=6),
    ))

fig.update_layout(
    title="ARF Bubble Thermometer — froth count over time",
    xaxis_title="Date",
    yaxis_title="Number of names",
    hovermode="x unified",
    height=420,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
)
st.plotly_chart(fig, use_container_width=True)

# Median ARF trend
fig2 = go.Figure()
for leg, leg_df, color in [("US", us_thermo, "#d62728"), ("China", cn_thermo, "#e6a817")]:
    if not leg_df.empty:
        fig2.add_trace(go.Scatter(
            x=leg_df["as_of_date"], y=leg_df["median_arf"],
            name=f"{leg} median ARF", mode="lines+markers",
            line=dict(color=color, width=2),
        ))

fig2.add_hline(y=50, line_dash="dot", line_color="gray", opacity=0.5,
               annotation_text="midpoint")
fig2.update_layout(
    title="Median ARF per leg over time",
    xaxis_title="Date",
    yaxis_title="Median ARF (0–100)",
    yaxis=dict(range=[0, 100]),
    hovermode="x unified",
    height=320,
)
st.plotly_chart(fig2, use_container_width=True)

# Week-over-week delta table
dates = sorted(thermo["as_of_date"].unique())
if len(dates) >= 2:
    latest_dt, prior_dt = dates[-1], dates[-2]
    latest = thermo[thermo["as_of_date"] == latest_dt]
    prior = thermo[thermo["as_of_date"] == prior_dt]

    st.subheader(f"Week-over-week: {prior_dt} → {latest_dt}")
    def _delta(cur: pd.Series, prv: pd.Series | None, col: str) -> str:
        if prv is None:
            return "—"
        diff = int(cur[col]) - int(prv[col])
        return f"+{diff}" if diff > 0 else str(diff)

    delta_rows = []
    for leg in ["US", "China"]:
        l_row = latest[latest["leg"] == leg]
        p_row = prior[prior["leg"] == leg]
        if l_row.empty:
            continue
        cur = l_row.iloc[0]
        prv = p_row.iloc[0] if not p_row.empty else None

        delta_rows.append({
            "Leg": leg,
            "Froth now": int(cur["count_froth"]),
            "Froth Δ": _delta(cur, prv, "count_froth"),
            "ARF≥90 now": int(cur["count_arf_gte_90"]),
            "ARF≥90 Δ": _delta(cur, prv, "count_arf_gte_90"),
            "Median ARF": f"{cur['median_arf']:.1f}",
            "Stocks": int(cur["total"]),
        })

    if delta_rows:
        st.dataframe(pd.DataFrame(delta_rows), hide_index=True, use_container_width=True)
else:
    st.info("Run the pipeline on a second date to see week-over-week deltas.")
