"""US Leg — full ranked table + E-vs-V scatter."""
import streamlit as st

from webapp.data import load_snapshot
from webapp.ui import render_sidebar, render_table, scatter_plot

st.set_page_config(page_title="ARF — US Leg", layout="wide")
st.title("🇺🇸 US Leg")
st.caption("Ranked by ARF score. D1 = most AI-narrative-stretched. Red rows = D1, orange = D2, green = D8–D10. ★ = froth flag.")

as_of = render_sidebar()
if as_of is None:
    st.stop()

df = load_snapshot(as_of)
us = df[df["leg"] == "US"]

if us.empty:
    st.warning("No US data for this snapshot.")
    st.stop()

col_table, col_scatter = st.columns([3, 2], gap="large")

with col_table:
    st.subheader(f"Ranked table — {as_of}")
    render_table(us)

with col_scatter:
    st.subheader("E vs V scatter")
    fig = scatter_plot(us, "US")
    st.plotly_chart(fig, use_container_width=True)

with st.expander("Score definitions"):
    st.markdown("""
- **E-score** — AI Exposure: layer in stack (30%), pure-play % (40%), gross margin (20%), capped revenue growth (10%)
- **V-score** — Valuation Stretch: reverse-DCF implied growth gap + PEG + EV/Sales 5yr percentile, minus ROE quality credit
- **ARF** = √(E × V), percentile-ranked within leg
- **Froth flag ★**: D1 AND ROE < WACC (10%) AND P/S > 25
""")
