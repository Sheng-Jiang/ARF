"""泡沫温度计 — 跨快照的泡沫数量与D1个股历史趋势。"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from webapp.data import load_thermometer_series
from webapp.ui import render_sidebar

st.set_page_config(page_title="ARF — 泡沫温度计", layout="wide")
st.title("泡沫温度计")
st.caption("AI估值泡沫的周度演变。多次运行数据管道后，趋势线将逐渐清晰。")

render_sidebar()

thermo = load_thermometer_series()
us_thermo = thermo[thermo["leg"] == "US"].sort_values("as_of_date")
cn_thermo = thermo[thermo["leg"] == "China"].sort_values("as_of_date")

if thermo.empty:
    st.warning("暂无历史数据。请先至少运行一次数据管道。")
    st.stop()

fig = go.Figure()

if not us_thermo.empty:
    fig.add_trace(go.Scatter(
        x=us_thermo["as_of_date"], y=us_thermo["count_froth"],
        name="美股 — 泡沫预警 ★", mode="lines+markers",
        line=dict(color="#d62728", width=2),
        marker=dict(size=8),
    ))
    fig.add_trace(go.Scatter(
        x=us_thermo["as_of_date"], y=us_thermo["count_arf_gte_90"],
        name="美股 — ARF ≥ 90", mode="lines+markers",
        line=dict(color="#d62728", width=2, dash="dot"),
        marker=dict(size=6),
    ))

if not cn_thermo.empty:
    fig.add_trace(go.Scatter(
        x=cn_thermo["as_of_date"], y=cn_thermo["count_froth"],
        name="中股 — 泡沫预警 ★", mode="lines+markers",
        line=dict(color="#e6a817", width=2),
        marker=dict(size=8),
    ))
    fig.add_trace(go.Scatter(
        x=cn_thermo["as_of_date"], y=cn_thermo["count_arf_gte_90"],
        name="中股 — ARF ≥ 90", mode="lines+markers",
        line=dict(color="#e6a817", width=2, dash="dot"),
        marker=dict(size=6),
    ))

fig.update_layout(
    title="ARF泡沫温度计 — 泡沫预警个股数量趋势",
    xaxis_title="日期",
    yaxis_title="股票数量",
    hovermode="x unified",
    height=420,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
)
st.plotly_chart(fig, use_container_width=True)

st.markdown("""
**温度计图解读：**
- **泡沫预警数（实线）上升**：满足 D1 + ROE < WACC + P/S > 25 三重条件的个股增多，市场AI叙事情绪整体升温，需提高警惕
- **ARF ≥ 90 数（虚线）上升**：接近极端估值拉伸的个股增多，系统性回调风险上升
- **两线同步走高**：板块性泡沫信号，非个股行为
- **两线背离**（ARF≥90增但预警未触发）：部分高估个股ROE尚可支撑估值，风险相对可控
""")

st.divider()

# Median ARF trend
fig2 = go.Figure()
for leg, leg_df, color in [("美股", us_thermo, "#d62728"), ("中股", cn_thermo, "#e6a817")]:
    if not leg_df.empty:
        fig2.add_trace(go.Scatter(
            x=leg_df["as_of_date"], y=leg_df["median_arf"],
            name=f"{leg}中位ARF", mode="lines+markers",
            line=dict(color=color, width=2),
        ))

fig2.add_hline(y=50, line_dash="dot", line_color="gray", opacity=0.5,
               annotation_text="基准中线")
fig2.update_layout(
    title="各板块中位ARF走势",
    xaxis_title="日期",
    yaxis_title="中位ARF（0–100）",
    yaxis=dict(range=[0, 100]),
    hovermode="x unified",
    height=320,
)
st.plotly_chart(fig2, use_container_width=True)

st.markdown("""
**中位ARF解读：**
中位ARF反映的是整个板块的"平均温度"。
- **持续高于50**：板块整体被AI叙事显著抬高，个股选择需更加谨慎
- **快速上升**：新资金涌入 + 估值快速扩张，泡沫形成加速
- **从高位回落**：叙事降温或基本面业绩开始消化估值，泡沫出清
""")

st.divider()

# Week-over-week delta table
dates = sorted(thermo["as_of_date"].unique())
if len(dates) >= 2:
    latest_dt, prior_dt = dates[-1], dates[-2]
    latest = thermo[thermo["as_of_date"] == latest_dt]
    prior = thermo[thermo["as_of_date"] == prior_dt]

    st.subheader(f"周度变化：{prior_dt} → {latest_dt}")
    def _delta(cur: pd.Series, prv: pd.Series | None, col: str) -> str:
        if prv is None:
            return "—"
        diff = int(cur[col]) - int(prv[col])
        return f"+{diff}" if diff > 0 else str(diff)

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
            "泡沫预警数": int(cur["count_froth"]),
            "泡沫预警变化": _delta(cur, prv, "count_froth"),
            "ARF≥90数": int(cur["count_arf_gte_90"]),
            "ARF≥90变化": _delta(cur, prv, "count_arf_gte_90"),
            "中位ARF": f"{cur['median_arf']:.1f}",
            "覆盖股票数": int(cur["total"]),
        })

    if delta_rows:
        st.dataframe(pd.DataFrame(delta_rows), hide_index=True, use_container_width=True)
else:
    st.info("在第二个日期运行数据管道后，即可查看周度对比数据。")
