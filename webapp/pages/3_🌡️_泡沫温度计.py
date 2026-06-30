"""泡沫温度计 — 跨快照的泡沫数量与D1个股历史趋势。"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from webapp.data import load_snapshot, load_thermometer_series
from webapp.mobile import show_plotly
from webapp.ui import render_research_synthesis, render_sidebar

st.set_page_config(page_title="ARF — 泡沫温度计", layout="wide")

# Mobile hardening: keep CJK headings from clipping, tighten gutters on phones.
st.markdown(
    "<style>"
    "h1,h2,h3{line-height:1.45!important;overflow:visible}"
    "@media (max-width:640px){.block-container{padding-left:.7rem;padding-right:.7rem}}"
    "</style>",
    unsafe_allow_html=True,
)

# Legend below the plot so its wrapped rows never collide with the title/toolbar.
_LEGEND_BELOW = dict(orientation="h", yanchor="top", y=-0.25, xanchor="left", x=0, font=dict(size=11))

st.title("泡沫温度计")
st.caption("AI估值泡沫的周度演变。多次运行数据管道后，趋势线将逐渐清晰。")

as_of = render_sidebar()

thermo = load_thermometer_series()
us_thermo = thermo[thermo["leg"] == "US"].sort_values("as_of_date")
cn_thermo = thermo[thermo["leg"] == "China"].sort_values("as_of_date")

if thermo.empty:
    st.warning("暂无历史数据。请先至少运行一次数据管道。")
    st.stop()

# ── Chart 1: Froth Count Trend ────────────────────────────────────────────────
fig = go.Figure()

if not us_thermo.empty:
    # Absolute froth (no D1 restriction)
    fig.add_trace(go.Scatter(
        x=us_thermo["as_of_date"], y=us_thermo["count_absolute_froth"],
        name="美股·绝对★", mode="lines+markers",
        line=dict(color="#d62728", width=3),
        marker=dict(size=8),
    ))
    # Relative froth (D1 restricted)
    fig.add_trace(go.Scatter(
        x=us_thermo["as_of_date"], y=us_thermo["count_froth"],
        name="美股·相对(D1)", mode="lines+markers",
        line=dict(color="#d62728", width=1.5, dash="dash"),
        marker=dict(size=6),
    ))
    # ARF >= 90 (D1 reference)
    fig.add_trace(go.Scatter(
        x=us_thermo["as_of_date"], y=us_thermo["count_arf_gte_90"],
        name="美股·ARF≥90", mode="lines+markers",
        line=dict(color="#d62728", width=1, dash="dot"),
        marker=dict(size=4),
    ))

if not cn_thermo.empty:
    # Absolute froth (no D1 restriction)
    fig.add_trace(go.Scatter(
        x=cn_thermo["as_of_date"], y=cn_thermo["count_absolute_froth"],
        name="中股·绝对★", mode="lines+markers",
        line=dict(color="#e6a817", width=3),
        marker=dict(size=8),
    ))
    # Relative froth (D1 restricted)
    fig.add_trace(go.Scatter(
        x=cn_thermo["as_of_date"], y=cn_thermo["count_froth"],
        name="中股·相对(D1)", mode="lines+markers",
        line=dict(color="#e6a817", width=1.5, dash="dash"),
        marker=dict(size=6),
    ))
    # ARF >= 90 (D1 reference)
    fig.add_trace(go.Scatter(
        x=cn_thermo["as_of_date"], y=cn_thermo["count_arf_gte_90"],
        name="中股·ARF≥90", mode="lines+markers",
        line=dict(color="#e6a817", width=1, dash="dot"),
        marker=dict(size=4),
    ))

fig.update_layout(
    xaxis_title="日期",
    yaxis=dict(title="股票数量", rangemode="tozero", dtick=1, tickformat="d"),
    hovermode="x unified",
    height=440,
    margin=dict(t=10, r=10, b=110, l=10),
    legend=_LEGEND_BELOW,
)
st.subheader("ARF 绝对与相对泡沫个股数量趋势")
show_plotly(fig)

st.markdown("""
**温度计图解读：**
- **绝对泡沫数（实线）**：满足 `ROE < WACC` 且 `P/S > 25` 的个股数量。这是一个**绝对估值泡沫指标**，不受样本数量限制，能够真实反映全板块炒作的累积与出清程度（可从 0 一直“气球般膨胀”到整个板块的 16）。
- **相对泡沫数（虚线）**：满足 D1（ARF ≥ 90）且 `ROE < WACC` 且 `P/S > 25` 的个股数量。受限于十分位定义，其最大值被锁死在板块覆盖数的 10%（即 2 只），作为相对拉伸的参考。
- **ARF ≥ 90（点线）**：每天固定为板块前 10% 的股票（即 2 只），作为基准参考线。
""")

st.divider()

# ── Chart 2: Valuation Stretch & Growth Gap ──────────────────────────────────
fig2 = make_subplots(specs=[[{"secondary_y": True}]])

for leg, leg_df, color in [("美股", us_thermo, "#d62728"), ("中股", cn_thermo, "#e6a817")]:
    if not leg_df.empty:
        # EV/Sales 5yr percentile (primary y-axis)
        fig2.add_trace(go.Scatter(
            x=leg_df["as_of_date"], y=leg_df["median_ev_sales_pct"],
            name=f"{leg}·EV/S分位", mode="lines+markers",
            line=dict(color=color, width=2),
            marker=dict(size=6),
        ), secondary_y=False)

        # Implied growth gap (secondary y-axis)
        fig2.add_trace(go.Scatter(
            x=leg_df["as_of_date"], y=leg_df["median_growth_gap_pct"],
            name=f"{leg}·增长差值", mode="lines+markers",
            line=dict(color=color, width=1.5, dash="dash"),
            marker=dict(size=5, symbol="square"),
        ), secondary_y=True)

# Add baseline line for primary y-axis (50% percentile)
fig2.add_hline(y=50, line_dash="dot", line_color="gray", opacity=0.5,
               annotation_text="估值历史中线 (50%)")

fig2.update_layout(
    xaxis_title="日期",
    hovermode="x unified",
    height=440,
    margin=dict(t=10, r=10, b=110, l=10),
    legend=_LEGEND_BELOW,
)

fig2.update_yaxes(title_text="EV/S 5年分位 (%)", range=[0, 100], secondary_y=False)
fig2.update_yaxes(title_text="增长差值 (%)", secondary_y=True)

st.subheader("各板块估值热度与隐含增长差值走势")
show_plotly(fig2)

st.markdown("""
**估值与增长差值解读：**
- **EV/Sales 5年历史分位数中位数（实线，左轴）**：反映整个板块相对于自身历史估值的“平均温度”。持续高于 50% 说明板块估值整体偏贵；快速逼近 100% 说明估值已处于 5 年来的极端高位。该指标替代了原先因百分位排序而恒等于 53 的 flat 线。
- **隐含增长率与共识差值中位数（虚线，右轴）**：反映市场交易价格中隐含的永续增长率（$g^*$）比分析师 3 年 consensus 预期高出多少。差值越高，说明市场定价越是“定价完美”（Priced for Perfection），对未来业绩增长的透支越严重，系统性回调风险上升。
""")

st.divider()

# ── Week-over-Week Delta Table ───────────────────────────────────────────────
dates = sorted(thermo["as_of_date"].unique())
if len(dates) >= 2:
    latest_dt, prior_dt = dates[-1], dates[-2]
    latest = thermo[thermo["as_of_date"] == latest_dt]
    prior = thermo[thermo["as_of_date"] == prior_dt]

    st.subheader(f"周度变化：{prior_dt} → {latest_dt}")
    
    def _delta_int(cur: pd.Series, prv: pd.Series | None, col: str) -> str:
        if prv is None or col not in prv or pd.isna(prv[col]) or pd.isna(cur[col]):
            return "—"
        diff = int(cur[col]) - int(prv[col])
        return f"+{diff}" if diff > 0 else str(diff)

    def _delta_float(cur: pd.Series, prv: pd.Series | None, col: str) -> str:
        if prv is None or col not in prv or pd.isna(prv[col]) or pd.isna(cur[col]):
            return "—"
        diff = float(cur[col]) - float(prv[col])
        return f"+{diff:.2f}%" if diff > 0 else f"{diff:.2f}%"

    delta_rows = []
    for leg, leg_label in [("US", "🇺🇸 美股"), ("China", "🇨🇳 中股")]:
        l_row = latest[latest["leg"] == leg]
        p_row = prior[prior["leg"] == leg]
        if l_row.empty:
            continue
        cur = l_row.iloc[0]
        prv = p_row.iloc[0] if not p_row.empty else None

        delta_rows.append({
            "板块": leg_label,
            "绝对泡沫数": int(cur["count_absolute_froth"]),
            "绝对泡沫变化": _delta_int(cur, prv, "count_absolute_froth"),
            "相对泡沫数 (D1)": int(cur["count_froth"]),
            "相对泡沫变化": _delta_int(cur, prv, "count_froth"),
            "EV/Sales历史分位数中位数": f"{cur['median_ev_sales_pct']:.1f}%",
            "分位数变化": _delta_float(cur, prv, "median_ev_sales_pct"),
            "隐含增长差值中位数": f"{cur['median_growth_gap_pct']:.2f}%",
            "增长差值变化": _delta_float(cur, prv, "median_growth_gap_pct"),
            "覆盖股票数": int(cur["total"]),
        })

    if delta_rows:
        st.dataframe(pd.DataFrame(delta_rows), hide_index=True, use_container_width=True)
else:
    st.info("在第二个日期运行数据管道后，即可查看周度对比数据。")

st.divider()

if as_of is not None:
    snapshot_df = load_snapshot(as_of)
    scored = snapshot_df[snapshot_df["leg"].isin(["US", "China"])]
    render_research_synthesis(scored, as_of)

