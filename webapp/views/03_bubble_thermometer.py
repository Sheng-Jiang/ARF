"""泡沫温度计 — 跨快照的泡沫数量与D1个股历史趋势。"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from webapp.data import load_snapshot, load_thermometer_series
from webapp.mobile import inject_mobile_css, show_plotly
from webapp.ui import render_research_synthesis, render_sidebar, tr

st.set_page_config(
    page_title=tr("ARF — 泡沫温度计", "ARF — Bubble Thermometer"),
    layout="wide",
)

inject_mobile_css()

# Legend below the plot so its wrapped rows never collide with the title/toolbar.
_LEGEND_BELOW = dict(orientation="h", yanchor="top", y=-0.25, xanchor="left", x=0, font=dict(size=11))

st.title(tr("泡沫温度计", "Bubble Thermometer"))
st.caption(
    tr(
        "AI估值泡沫的周度演变。多次运行数据管道后，趋势线将逐渐清晰。",
        "Weekly evolution of the AI valuation bubble. Trend lines will sharpen as the pipeline runs repeatedly.",
    )
)
st.caption(
    tr(
        "⚠️ 口径说明：2026-06-26 之前的快照为旧版小池（32只），之后为 73 只完整池——"
        "早期绝对泡沫计数与当前口径不可直接比较，趋势图跨过该日期时应谨慎解读。",
        "⚠️ Scope note: snapshots before 2026-06-26 use the old small pool (32 tickers); later snapshots "
        "use the full 73-ticker pool — early absolute froth counts are not directly comparable, so interpret "
        "trends across that date with caution.",
    )
)

as_of = render_sidebar()

thermo = load_thermometer_series()
us_thermo = thermo[thermo["leg"] == "US"].sort_values("as_of_date")
cn_thermo = thermo[thermo["leg"] == "China"].sort_values("as_of_date")

if thermo.empty:
    st.warning(
        tr(
            "暂无历史数据。请先至少运行一次数据管道。",
            "No historical data yet. Please run the data pipeline at least once.",
        )
    )
    st.stop()

# ── Chart 1: Froth Count Trend ────────────────────────────────────────────────
fig = go.Figure()

if not us_thermo.empty:
    # Absolute froth (no D1 restriction)
    fig.add_trace(go.Scatter(
        x=us_thermo["as_of_date"], y=us_thermo["count_absolute_froth"],
        name=tr("美股·绝对★", "US Leg · Absolute ★"), mode="lines+markers",
        line=dict(color="#d62728", width=3),
        marker=dict(size=8),
    ))
    # Relative froth (D1 restricted)
    fig.add_trace(go.Scatter(
        x=us_thermo["as_of_date"], y=us_thermo["count_froth"],
        name=tr("美股·相对(D1)", "US Leg · Relative (D1)"), mode="lines+markers",
        line=dict(color="#d62728", width=1.5, dash="dash"),
        marker=dict(size=6),
    ))
    # ARF >= 90 (D1 reference)
    fig.add_trace(go.Scatter(
        x=us_thermo["as_of_date"], y=us_thermo["count_arf_gte_90"],
        name=tr("美股·ARF≥90", "US Leg · ARF≥90"), mode="lines+markers",
        line=dict(color="#d62728", width=1, dash="dot"),
        marker=dict(size=4),
    ))

if not cn_thermo.empty:
    # Absolute froth (no D1 restriction)
    fig.add_trace(go.Scatter(
        x=cn_thermo["as_of_date"], y=cn_thermo["count_absolute_froth"],
        name=tr("中股·绝对★", "China Leg · Absolute ★"), mode="lines+markers",
        line=dict(color="#e6a817", width=3),
        marker=dict(size=8),
    ))
    # Relative froth (D1 restricted)
    fig.add_trace(go.Scatter(
        x=cn_thermo["as_of_date"], y=cn_thermo["count_froth"],
        name=tr("中股·相对(D1)", "China Leg · Relative (D1)"), mode="lines+markers",
        line=dict(color="#e6a817", width=1.5, dash="dash"),
        marker=dict(size=6),
    ))
    # ARF >= 90 (D1 reference)
    fig.add_trace(go.Scatter(
        x=cn_thermo["as_of_date"], y=cn_thermo["count_arf_gte_90"],
        name=tr("中股·ARF≥90", "China Leg · ARF≥90"), mode="lines+markers",
        line=dict(color="#e6a817", width=1, dash="dot"),
        marker=dict(size=4),
    ))

fig.update_layout(
    xaxis_title=tr("日期", "Date"),
    yaxis=dict(
        title=tr("股票数量", "Number of Stocks"),
        rangemode="tozero",
        dtick=1,
        tickformat="d",
    ),
    hovermode="x unified",
    height=440,
    margin=dict(t=10, r=10, b=110, l=10),
    legend=_LEGEND_BELOW,
)
st.subheader(tr("ARF 绝对与相对泡沫个股数量趋势", "Trend in Absolute and Relative Froth Counts"))
show_plotly(fig)

st.markdown(tr("""
**温度计图解读：**
- **绝对泡沫数（实线）**：满足 `ROE < WACC` 且 `P/S > 25` 的个股数量。这是一个**绝对估值泡沫指标**，不受样本数量限制，能够真实反映全板块炒作的累积与出清程度（可从 0 一直“气球般膨胀”到整个板块的 16）。
- **相对泡沫数（虚线）**：满足 D1（ARF ≥ 90）且 `ROE < WACC` 且 `P/S > 25` 的个股数量。受限于十分位定义，其最大值被锁死在板块覆盖数的 10%（即 2 只），作为相对拉伸的参考。
- **ARF ≥ 90（点线）**：每天固定为板块前 10% 的股票（即 2 只），作为基准参考线。
""", """
**Reading the thermometer:**
- **Absolute froth count (solid line)**: number of stocks satisfying `ROE < WACC` and `P/S > 25`. This is an **absolute valuation-froth gauge** that is not constrained by sample size and genuinely reflects the build-up and clearing of speculative excess across the whole leg (it can "balloon" from 0 all the way to 16 for the entire leg).
- **Relative froth count (dashed line)**: number of stocks satisfying D1 (ARF ≥ 90) AND `ROE < WACC` AND `P/S > 25`. Bounded by the decile definition, its maximum is locked at 10% of the leg's coverage (i.e. 2 stocks), serving as a relative stretch reference.
- **ARF ≥ 90 (dotted line)**: always the top 10% of the leg (i.e. 2 stocks) each day, as a baseline reference line.
"""))

st.divider()

# ── Chart 2: Valuation Stretch & Growth Gap ──────────────────────────────────
fig2 = make_subplots(specs=[[{"secondary_y": True}]])

for leg_code, leg_df, color in [("US", us_thermo, "#d62728"), ("China", cn_thermo, "#e6a817")]:
    if not leg_df.empty:
        leg_label = tr("美股", "US Leg") if leg_code == "US" else tr("中股", "China Leg")
        # EV/Sales 5yr percentile (primary y-axis)
        fig2.add_trace(go.Scatter(
            x=leg_df["as_of_date"], y=leg_df["median_ev_sales_pct"],
            name=tr(f"{leg_label}·EV/S分位", f"{leg_label}·EV/S Percentile"), mode="lines+markers",
            line=dict(color=color, width=2),
            marker=dict(size=6),
        ), secondary_y=False)

        # Implied growth gap (secondary y-axis)
        fig2.add_trace(go.Scatter(
            x=leg_df["as_of_date"], y=leg_df["median_growth_gap_pct"],
            name=tr(f"{leg_label}·增长差值", f"{leg_label}·Growth Gap"), mode="lines+markers",
            line=dict(color=color, width=1.5, dash="dash"),
            marker=dict(size=5, symbol="square"),
        ), secondary_y=True)

# Add baseline line for primary y-axis (50% percentile)
fig2.add_hline(y=50, line_dash="dot", line_color="gray", opacity=0.5,
               annotation_text=tr("估值历史中线 (50%)", "Valuation Historical Median (50%)"))

fig2.update_layout(
    xaxis_title=tr("日期", "Date"),
    hovermode="x unified",
    height=440,
    margin=dict(t=10, r=10, b=110, l=10),
    legend=_LEGEND_BELOW,
)

fig2.update_yaxes(
    title_text=tr("EV/S 5年分位 (%)", "EV/S 5Y Percentile (%)"),
    range=[0, 100],
    secondary_y=False,
)
fig2.update_yaxes(
    title_text=tr("增长差值 (%)", "Growth Gap (%)"),
    secondary_y=True,
)

st.subheader(tr("各板块估值热度与隐含增长差值走势", "Valuation Heat and Implied Growth Gap by Leg"))
show_plotly(fig2)

st.markdown(tr("""
**估值与增长差值解读：**
- **EV/Sales 5年历史分位数中位数（实线，左轴）**：反映整个板块相对于自身历史估值的“平均温度”。持续高于 50% 说明板块估值整体偏贵；快速逼近 100% 说明估值已处于 5 年来的极端高位。该指标替代了原先因百分位排序而恒等于 53 的 flat 线。
- **隐含增长率与共识差值中位数（虚线，右轴）**：反映市场交易价格中隐含的永续增长率（$g^*$）比分析师 3 年 consensus 预期高出多少。差值越高，说明市场定价越是“定价完美”（Priced for Perfection），对未来业绩增长的透支越严重，系统性回调风险上升。
""", """
**Reading valuation vs growth gap:**
- **Median 5-year EV/Sales percentile (solid line, left axis)**: the "average temperature" of the whole leg relative to its own historical valuation. Sustained readings above 50% mean the leg is broadly expensive; a rapid approach to 100% means valuations are at a 5-year extreme. This metric replaces the old flat line that was pinned at 53 by percentile ranking.
- **Median implied growth minus consensus (dashed line, right axis)**: how much the perpetual growth rate ($g^*$) embedded in market prices exceeds the 3-year analyst consensus. A higher gap means the market is more "priced for perfection", borrowing more heavily from future earnings growth and raising systemic correction risk.
"""))

st.divider()

# ── Week-over-Week Delta Table ───────────────────────────────────────────────
dates = sorted(thermo["as_of_date"].unique())
if len(dates) >= 2:
    latest_dt, prior_dt = dates[-1], dates[-2]
    latest = thermo[thermo["as_of_date"] == latest_dt]
    prior = thermo[thermo["as_of_date"] == prior_dt]

    st.subheader(tr(f"周度变化：{prior_dt} → {latest_dt}", f"Week-over-Week Change: {prior_dt} → {latest_dt}"))
    
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

    delta_cols = {
        "leg": tr("板块", "Leg"),
        "absolute": tr("绝对泡沫数", "Absolute Froth"),
        "absolute_delta": tr("绝对泡沫变化", "Absolute Froth Δ"),
        "relative": tr("相对泡沫数 (D1)", "Relative Froth (D1)"),
        "relative_delta": tr("相对泡沫变化", "Relative Froth Δ"),
        "ev_pct": tr("EV/Sales历史分位数中位数", "Median EV/Sales Percentile"),
        "ev_delta": tr("分位数变化", "Percentile Δ"),
        "gap": tr("隐含增长差值中位数", "Median Implied Growth Gap"),
        "gap_delta": tr("增长差值变化", "Growth Gap Δ"),
        "coverage": tr("覆盖股票数", "Covered Tickers"),
    }
    leg_labels = {
        "US": tr("🇺🇸 美股", "🇺🇸 US Leg"),
        "China": tr("🇨🇳 中股", "🇨🇳 China Leg"),
    }

    delta_rows = []
    for leg, leg_label in leg_labels.items():
        l_row = latest[latest["leg"] == leg]
        p_row = prior[prior["leg"] == leg]
        if l_row.empty:
            continue
        cur = l_row.iloc[0]
        prv = p_row.iloc[0] if not p_row.empty else None

        delta_rows.append({
            delta_cols["leg"]: leg_label,
            delta_cols["absolute"]: int(cur["count_absolute_froth"]),
            delta_cols["absolute_delta"]: _delta_int(cur, prv, "count_absolute_froth"),
            delta_cols["relative"]: int(cur["count_froth"]),
            delta_cols["relative_delta"]: _delta_int(cur, prv, "count_froth"),
            delta_cols["ev_pct"]: f"{cur['median_ev_sales_pct']:.1f}%",
            delta_cols["ev_delta"]: _delta_float(cur, prv, "median_ev_sales_pct"),
            delta_cols["gap"]: f"{cur['median_growth_gap_pct']:.2f}%",
            delta_cols["gap_delta"]: _delta_float(cur, prv, "median_growth_gap_pct"),
            delta_cols["coverage"]: int(cur["total"]),
        })

    if delta_rows:
        st.dataframe(pd.DataFrame(delta_rows), hide_index=True, use_container_width=True)
else:
    st.info(
        tr(
            "在第二个日期运行数据管道后，即可查看周度对比数据。",
            "Run the pipeline for a second date to view week-over-week comparisons.",
        )
    )

st.divider()

if as_of is not None:
    snapshot_df = load_snapshot(as_of)
    scored = snapshot_df[snapshot_df["leg"].isin(["US", "China"])]
    render_research_synthesis(scored, as_of)

