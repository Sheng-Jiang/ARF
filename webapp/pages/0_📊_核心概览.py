"""ARF 仪表盘 — 首页：所选快照日期的核心指标概览。"""
import streamlit as st

from webapp.data import load_snapshot
from webapp.mobile import inject_mobile_css, is_mobile
from webapp.ui import render_ask_gemini, render_sidebar

inject_mobile_css()
st.title("AI相关性因子（ARF）仪表盘")
st.caption(
    "衡量AI叙事对股票估值的扭曲程度。D1 = 估值拉伸最大，D10 = 相对于AI敞口最为低估。"
)

with st.expander("📖 如何解读ARF分数", expanded=False):
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

> **注意**：ARF是相对排名指标，衡量的是板块内部的相对估值拉伸，而非绝对高估。D1股票不代表必然下跌，但意味着其定价中包含了最高比例 of AI叙事溢价。
""")

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

# 5 metrics in one row on desktop; 2-per-row on phones so they aren't squished.
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

st.markdown(f"**快照日期：** {as_of} — 使用左侧边栏切换日期，点击页面导航查看各板块详情。")

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


# Stack the two tables on phones; side-by-side on desktop.
if is_mobile():
    _top5(us, "🇺🇸 美股 — ARF前5名")
    _top5(china, "🇨🇳 中股 — ARF前5名")
else:
    col_us, col_cn = st.columns(2)
    with col_us:
        _top5(us, "🇺🇸 美股 — ARF前5名")
    with col_cn:
        _top5(china, "🇨🇳 中股 — ARF前5名")

st.divider()
render_ask_gemini(
    scored_df,
    as_of,
    section_key="home",
    label_intro="基于本快照中美股+中股各前5名（共10只），由 Gemini 2.5 Pro 联网检索最近两周新闻，"
                "解读叙事面与因子读数之间的关系。",
)
