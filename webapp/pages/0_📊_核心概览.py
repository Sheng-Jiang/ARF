"""ARF 仪表盘 — 首页：所选快照日期的核心指标概览。"""
import streamlit as st

from arf.health import calibration_check, coverage_report
from webapp.data import load_snapshot
from webapp.mobile import inject_mobile_css, is_mobile
from webapp.ui import get_current_lang, render_ask_gemini, render_sidebar, tr

inject_mobile_css()

is_en = get_current_lang() == "en"

st.title("AI Relevance Factor (ARF) Dashboard" if is_en else "AI相关性因子（ARF）仪表盘")
st.caption(
    tr(
        "衡量AI叙事对股票估值的扭曲程度。D1 = 估值拉伸最大，D10 = 相对于AI敞口最为低估。",
        "Quantifying the degree to which equity valuations are stretched by the AI narrative. D1 = Peak Valuation Stretch, D10 = Most Undervalued Relative to AI Exposure.",
    )
)

with st.expander(tr("📖 如何解读ARF分数", "📖 How to Interpret ARF Factor Scores"), expanded=False):
    if is_en:
        st.markdown("""
**ARF (AI Relevance Factor)** quantifies the AI narrative bubble intensity per stock on a 0–100 scale, synthesized from two fundamental dimensions:

| Dimension | Description | Underlying Logic |
| :--- | :--- | :--- |
| **E-Score (AI Exposure)** | Stack layer position, pure-play AI revenue %, gross margin quality, forward AI revenue CAGR | Higher = Core direct beneficiary of AI CapEx |
| **V-Score (Valuation Stretch)** | Reverse-DCF implied perpetual growth hurdle ($g^*$), PEG ratio, EV/Sales 5-year percentile, adjusted for ROE | Higher = Valuation more decoupled from fundamentals |

**Formula:** $\\text{ARF} = \\sqrt{E\\text{-score} \\times V\\text{-score}}$, percentile-ranked within leg into 10 deciles (D1–D10).

**Decile Interpretation:**
- 🔴 **D1 (Highest 10%)**: Peak AI narrative froth — high exposure + extreme valuation stretch (Highest downside risk)
- 🟠 **D2–D3**: Substantial valuation premium with strong fundamental backing
- ⚪ **D4–D7**: Balanced neutral zone, valuation aligned with AI revenue realization
- 🟢 **D8–D10**: Attractive value relative to AI exposure

**★ Froth Circuit Breaker Warning**: Triggered when a stock simultaneously lands in **D1 + ROE < Cost of Equity + P/S > 25**.
""")
    else:
        st.markdown("""
**ARF（AI Relevance Factor，AI相关性因子）** 将每只股票的AI叙事泡沫程度量化为0–100分，由两个维度合成：

| 维度 | 含义 | 权重逻辑 |
|------|------|----------|
| **E分（AI曝光度）** | 公司在AI产业链中的位置、纯AI业务占比、毛利率水平、AI营收增速 | 越高 = AI核心受益标的 |
| **V分（估值拉伸）** | DCF反推隐含增长溢价、PEG类比、EV/Sales五年百分位，扣除ROE质量加成 | 越高 = 估值偏离基本面越严重 |

**合成公式：ARF = √(E分 × V分)**，在同一板块内做百分位排名，再分为10个十分位（D1–D10）。

**分数解读：**
- 🔴 **D1（最高分）**：AI叙事泡沫最集中 — 高AI曝光 + 高估值拉伸，风险最高
- 🟠 **D2–D3**：估值明显偏高，但尚有一定基本面支撑
- ⚪ **D4–D7**：中性区间，AI参与度与估值基本匹配
- 🟢 **D8–D10**：相对于AI敞口，估值处于合理或低估区间

**★ 泡沫预警**：同时满足 D1 + ROE < WACC + P/S > 25 三重条件，为极端高估的强烈信号。
""")

as_of = render_sidebar()
if as_of is None:
    st.stop()

# Re-read language after sidebar render in case toggled
is_en = get_current_lang() == "en"

df = load_snapshot(as_of)
us = df[df["leg"] == "US"]
china = df[df["leg"] == "China"]
scored_df = df[df["leg"].isin(["US", "China"])]

_cov = coverage_report(scored_df, as_of=as_of)
_cal = calibration_check(scored_df, as_of=as_of)
if _cov.warnings or _cal.n_fail:
    warn_title = (
        f"⚠️ Data Quality Notice — {len(_cov.warnings)} coverage warnings · Calibration: {_cal.n_fail} fail / {_cal.n_pass} pass"
        if is_en
        else f"⚠️ 数据质量提示 — {len(_cov.warnings)} 条覆盖告警 · 校准 {_cal.n_fail} 失败 / {_cal.n_pass} 通过"
    )
    with st.expander(warn_title, expanded=False):
        for w in _cov.warnings:
            st.warning(w)
        if _cal.n_fail:
            fails = [r for r in _cal.results if r.status == "fail"]
            lines = [
                f"- **{r.ticker}** actual D{r.decile}, expected D{r.expected_lo}–D{r.expected_hi}"
                if is_en
                else f"- **{r.ticker}** 实际 D{r.decile}，期望 D{r.expected_lo}–D{r.expected_hi}"
                for r in fails
            ]
            st.markdown(("Calibration failures:\n" if is_en else "校准未通过：\n") + "\n".join(lines))

d1_us = int((us["decile"] == 1).sum()) if len(us) else 0
d1_china = int((china["decile"] == 1).sum()) if len(china) else 0
froth_us = int((us["froth_flag"] == True).sum()) if len(us) else 0  # noqa: E712
froth_china = int((china["froth_flag"] == True).sum()) if len(china) else 0  # noqa: E712
total = len(scored_df)
scored = int(scored_df["arf"].notna().sum())

if is_en:
    _metrics = [
        ("🇺🇸 US D1 Count", d1_us, "Stocks with highest valuation stretch in US leg"),
        ("🇺🇸 US Froth Warnings ★", froth_us, "D1 + ROE < WACC + P/S > 25"),
        ("🇨🇳 China D1 Count", d1_china, "Stocks with highest valuation stretch in China leg"),
        ("🇨🇳 China Froth Warnings ★", froth_china, "D1 + ROE < WACC + P/S > 25"),
        ("Scored Tickers", f"{scored}/{total}", None),
    ]
else:
    _metrics = [
        ("🇺🇸 美股 D1 数量", d1_us, "美股中估值拉伸最大的股票数量"),
        ("🇺🇸 美股泡沫预警 ★", froth_us, "D1 + ROE < WACC + P/S > 25"),
        ("🇨🇳 中股 D1 数量", d1_china, "中股中估值拉伸最大的股票数量"),
        ("🇨🇳 中股泡沫预警 ★", froth_china, "D1 + ROE < WACC + P/S > 25"),
        ("已评分股票数", f"{scored}/{total}", None),
    ]

_per_row = 2 if is_mobile() else 5
for _i in range(0, len(_metrics), _per_row):
    _cols = st.columns(_per_row)
    for _col, (_label, _val, _help) in zip(_cols, _metrics[_i:_i + _per_row], strict=False):
        _col.metric(_label, _val, help=_help)

st.markdown(
    tr(
        f"**快照日期：** {as_of} — 使用左侧边栏切换日期，点击页面导航查看各板块详情。",
        f"**Snapshot Date:** {as_of} — Use the sidebar to toggle dates or language; navigate pages to explore sections.",
    )
)

st.divider()


def _top5(leg_df, title):
    st.subheader(title)
    if len(leg_df):
        top = leg_df.sort_values("arf", ascending=False).head(5)[
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


if is_mobile():
    _top5(us, "🇺🇸 US Leg — Top 5 Highest ARF" if is_en else "🇺🇸 美股 — ARF前5名")
    _top5(china, "🇨🇳 China Leg — Top 5 Highest ARF" if is_en else "🇨🇳 中股 — ARF前5名")
else:
    col_us, col_cn = st.columns(2)
    with col_us:
        _top5(us, "🇺🇸 US Leg — Top 5 Highest ARF" if is_en else "🇺🇸 美股 — ARF前5名")
    with col_cn:
        _top5(china, "🇨🇳 China Leg — Top 5 Highest ARF" if is_en else "🇨🇳 中股 — ARF前5名")

st.divider()
render_ask_gemini(
    scored_df,
    as_of,
    section_key="home",
    label_intro=(
        "Based on Top 5 US + Top 5 China names (10 tickers), synthesized by Gemini AI with live web search to connect narrative momentum with factor metrics."
        if is_en
        else "基于本快照中美股+中股各前5名（共10只），由 Gemini 2.5 Pro 联网检索最近两周新闻，解读叙事面与因子读数之间的关系。"
    ),
)
