"""ARF Dashboard — home page: KPI overview for the selected snapshot date."""
import streamlit as st

from webapp.data import load_snapshot
from webapp.ui import render_sidebar

st.set_page_config(
    page_title="ARF Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("AI Relevance Factor Dashboard")
st.caption(
    "Measures how much AI narrative is bending each stock's valuation. "
    "D1 = most stretched, D10 = cheapest relative to AI exposure."
)

as_of = render_sidebar()
if as_of is None:
    st.stop()

df = load_snapshot(as_of)
us = df[df["leg"] == "US"]
china = df[df["leg"] == "China"]
scored_df = df[df["leg"].isin(["US", "China"])]

d1_us = int((us["decile"] == 1).sum()) if len(us) else 0
d1_china = int((china["decile"] == 1).sum()) if len(china) else 0
froth_us = int((us["froth_flag"] == True).sum()) if len(us) else 0  # noqa: E712
froth_china = int((china["froth_flag"] == True).sum()) if len(china) else 0  # noqa: E712
total = len(scored_df)
scored = int(scored_df["arf"].notna().sum())

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("🇺🇸 US D1 names", d1_us, help="Stocks with highest valuation stretch in the US leg")
c2.metric("🇺🇸 US froth flags ★", froth_us, help="D1 + ROE < WACC + P/S > 25")
c3.metric("🇨🇳 China D1 names", d1_china)
c4.metric("🇨🇳 China froth flags ★", froth_china)
c5.metric("Stocks scored", f"{scored}/{total}")

st.markdown(f"**Snapshot:** {as_of} — Navigate via the sidebar to explore each leg in detail.")

st.divider()

col_us, col_cn = st.columns(2)

with col_us:
    st.subheader("🇺🇸 US Leg — top 5")
    if len(us):
        top = us.sort_values("arf", ascending=False).head(5)[
            ["ticker", "name", "decile", "arf", "froth_flag"]
        ].copy()
        top["D"] = top["decile"].apply(lambda d: int(d) if d == d else "—")
        top["ARF"] = top["arf"].apply(lambda v: f"{v:.1f}" if v == v else "—")
        top["★"] = top["froth_flag"].apply(lambda f: "★" if f else "")
        st.dataframe(
            top[["ticker", "name", "D", "ARF", "★"]],
            hide_index=True,
            use_container_width=True,
        )

with col_cn:
    st.subheader("🇨🇳 China Leg — top 5")
    if len(china):
        top = china.sort_values("arf", ascending=False).head(5)[
            ["ticker", "name", "decile", "arf", "froth_flag"]
        ].copy()
        top["D"] = top["decile"].apply(lambda d: int(d) if d == d else "—")
        top["ARF"] = top["arf"].apply(lambda v: f"{v:.1f}" if v == v else "—")
        top["★"] = top["froth_flag"].apply(lambda f: "★" if f else "")
        st.dataframe(
            top[["ticker", "name", "D", "ARF", "★"]],
            hide_index=True,
            use_container_width=True,
        )
