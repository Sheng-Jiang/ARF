"""美股板块 — 完整排名表 + E-V散点图。"""
import streamlit as st

from webapp.data import load_snapshot
from webapp.mobile import inject_mobile_css, is_mobile, show_plotly
from webapp.ui import render_sidebar, render_table, scatter_plot

st.set_page_config(page_title="ARF — 美股板块", layout="wide")
inject_mobile_css()
st.title("🇺🇸 美股板块")
st.caption("按ARF分数排名。D1 = AI叙事估值拉伸最大。红色行 = D1，橙色 = D2，绿色 = D8–D10。★ = 泡沫预警。")

as_of = render_sidebar()
if as_of is None:
    st.stop()

df = load_snapshot(as_of)
us = df[df["leg"] == "US"]

if us.empty:
    st.warning("该快照日期暂无美股数据。")
    st.stop()

def _table_block():
    st.subheader(f"排名表 — {as_of}")
    render_table(us)


def _scatter_block():
    st.subheader("E分 vs V分 散点图")
    show_plotly(scatter_plot(us, "美股"))
    st.markdown("""
**散点图解读：**
横轴 E分 = AI曝光度，纵轴 V分 = 估值拉伸程度，均为板块内百分位排名（0–100）。
- 🔴 **右上角**（高E + 高V）：AI叙事泡沫核心区，ARF最高，风险最集中
- 🟢 **右下角**（高E + 低V）：AI核心受益股且估值合理，基本面支撑充分
- 🟡 **左上角**（低E + 高V）：非AI驱动的高估值，需关注其他风险因素
- ⚪ **左下角**（低E + 低V）：AI参与度低且估值合理，ARF最低
- 气泡大小 = 市值；颜色由红（D1，泡沫最重）渐变至深绿（D10，最理性）
""")


# Phones get a single stacked column (the side-by-side split squeezes the scatter
# into an unreadable sliver); desktop keeps the table | scatter layout.
if is_mobile():
    _table_block()
    _scatter_block()
else:
    col_table, col_scatter = st.columns([3, 2], gap="large")
    with col_table:
        _table_block()
    with col_scatter:
        _scatter_block()

with st.expander("评分指标定义"):
    st.markdown("""
- **E分（AI曝光度）**：在AI产业链中的层级位置（30%）+ 纯AI业务占比（40%）+ 毛利率（20%）+ AI营收增速（上限200%）（10%）
- **V分（估值拉伸）**：反向DCF隐含增长缺口 + PEG类比 + EV/Sales五年百分位，减去ROE质量加成（±20分）
- **ARF** = √(E × V)，在板块内百分位排名，再分为D1–D10十分位
- **泡沫预警 ★**：D1 且 ROE < WACC（美股10%） 且 P/S > 25
- 美股数据来源：yfinance（主）+ SEC EDGAR（分部营收）+ Macrotrends（历史EV/S）
""")
