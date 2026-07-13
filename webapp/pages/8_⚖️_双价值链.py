"""双价值链 — 美系 vs 中系 AI 价值链五层市值对比（静态参考数据）。

数据来源：《全球 AI 双价值链格局下的投资决策参考》（2026-06-07），
截至 2026-06-05 收盘（含当周纳指 −4.18% 大跌）。与快照管道无关，
更新数据时直接修改本文件的 LAYERS 表。
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from webapp.mobile import inject_mobile_css, show_plotly

st.set_page_config(page_title="ARF — 双价值链", layout="wide")
inject_mobile_css()

_LEGEND_BELOW = dict(orientation="h", yanchor="top", y=-0.25, xanchor="left", x=0, font=dict(size=11))

st.title("双价值链市值对比")
st.caption(
    "Line 1（美系）vs Line 2（中系，覆盖 A股 + 港股 + 美股中概 + 未上市估值），按五层架构逐层对比。"
    "数据截至 2026-06-05 收盘（纳指当日 −4.18%），单位：万亿美元。"
)

# ── 数据（直接取自原报告，为约数）──────────────────────────────────────────────
LAYERS = [
    {
        "layer": "L1 能源",
        "us": 0.60, "cn": 0.20, "gap": "3.0×",
        "us_names": "NextEra、Williams、GE Vernova、西门子能源、施耐德",
        "cn_names": "宁德时代（A+H）、中恒电气（A股）；国家电网未上市，不计",
    },
    {
        "layer": "L2 芯片与设备",
        "us": 9.7, "cn": 0.36, "gap": "27×",
        "us_names": "NVDA 4.97T、TSMC 1.95T、AVGO 1.83T、ASML 4,850亿、AMD 2,800亿、INTC 1,900亿",
        "cn_names": "华为 ~2,000亿（未上市估值）、中芯国际 850亿（A+H）、寒武纪 750亿（A股）；海光（A股）未计",
    },
    {
        "layer": "L3 基础设施",
        "us": 12.31, "cn": 0.90, "gap": "13.6×",
        "us_names": "GOOGL 4.63T、MSFT 3.11T、AMZN 2.87T、META 1.55T、EQIX+DLR ~1,500亿",
        "cn_names": "腾讯 5,475亿（港股）、阿里 3,030亿（美+港）、百度 ~370亿（美+港）、万国数据+世纪互联 ~130亿（美股中概）",
    },
    {
        "layer": "L4 基础模型",
        "us": 1.97, "cn": 0.18, "gap": "11×",
        "us_names": "Anthropic 9,000亿、OpenAI 8,520亿、xAI ~2,000亿、Mistral ~150亿（私募估值）",
        "cn_names": "智谱 ~800亿（港股）、MiniMax 338亿（港股）、DeepSeek ~450亿、月之暗面 ~180亿（未上市）",
    },
    {
        "layer": "L5 应用与物理 AI",
        "us": 5.2, "cn": 0.55, "gap": "9.5×",
        "us_names": "AAPL 4.53T、SAP ~3,300亿、Salesforce ~2,600亿、ABB+KUKA+UR ~700亿",
        "cn_names": "字节跳动 5,500亿（未上市估值）；美团（港股）、小鹏（美+港）、优必选（港股）、宇树未细列",
    },
]
TOTAL_US, TOTAL_CN, TOTAL_GAP = 29.78, 2.19, "13.6×"


def _fmt_t(v: float) -> str:
    return f"${v:.2f}T" if v < 1 else f"${v:.4g}T"


# ── 头部指标 ──────────────────────────────────────────────────────────────────
c1, c2, c3 = st.columns(3)
c1.metric("Line 1 美系合计", f"${TOTAL_US}T", delta="-6,000亿（本周）",
          help="经当周纳指 −4.18% 大跌后，整体缩水约 $6,000 亿，相对优势几乎未变")
c2.metric("Line 2 中系合计", f"${TOTAL_CN}T", help="约为 Line 1 的 1/13.6")
c3.metric("整体差距", TOTAL_GAP, help="分布不均：芯片层 27× ↔ 能源层 3×")

st.divider()

# ── 逐层市值对比 ──────────────────────────────────────────────────────────────
# 横向分组条形图：类别自下而上排列，倒序后 L1 显示在最上方。
rows = list(reversed(LAYERS))
y_labels = [r["layer"] for r in rows]

fig = go.Figure()
# 横向分组时后添加的 trace 显示在组内上方，故先加 Line 2，让 Line 1 居上；
# 图例用 reversed 保持 Line 1 在前。
fig.add_trace(go.Bar(
    y=y_labels, x=[r["cn"] for r in rows],
    name="Line 2 中系", orientation="h",
    marker=dict(color="#e6a817"),
    text=[_fmt_t(r["cn"]) for r in rows], textposition="outside", cliponaxis=False,
    customdata=[r["cn_names"] for r in rows],
    hovertemplate="<b>%{y} · Line 2</b><br>合计 %{text}<br>%{customdata}<extra></extra>",
))
fig.add_trace(go.Bar(
    y=y_labels, x=[r["us"] for r in rows],
    name="Line 1 美系", orientation="h",
    marker=dict(color="#d62728"),
    text=[_fmt_t(r["us"]) for r in rows], textposition="outside", cliponaxis=False,
    customdata=[r["us_names"] for r in rows],
    hovertemplate="<b>%{y} · Line 1</b><br>合计 %{text}<br>%{customdata}<extra></extra>",
))

# 右缘标注每层差距倍数（原报告口径）。
for r in rows:
    is_max = r["gap"] == "27×"
    fig.add_annotation(
        x=15.9, y=r["layer"], text=f"<b>{r['gap']}</b>" if is_max else r["gap"],
        showarrow=False, xanchor="right", font=dict(size=13 if is_max else 12),
    )
fig.add_annotation(x=15.9, y=1.06, yref="paper", text="倍数", showarrow=False,
                   xanchor="right", font=dict(size=11, color="gray"))

fig.update_layout(
    barmode="group",
    xaxis=dict(title="市值（万亿美元）", range=[0, 16]),
    height=460,
    margin=dict(t=30, r=10, b=90, l=10),
    legend=dict(traceorder="reversed", **_LEGEND_BELOW),
)
st.subheader("逐层市值对比")
show_plotly(fig)

st.markdown("""
**解读：** 全球 AI 经济已分裂为两条平行价值链，整体差距约 13.6 倍，且**分布高度不均**——
芯片层高达 27 倍、模型层 11 倍，而能源层只有 3 倍。当周大跌后芯片层倍数反而从 26× 略升至
27×（港股/A 股跟跌更深），说明两条链 β 高度同步，并非真正脱钩。
""")

st.divider()

# ── 成分与口径 ────────────────────────────────────────────────────────────────
st.subheader("成分与口径")
table = pd.DataFrame([
    {
        "层级": r["layer"],
        "Line 1 美系": _fmt_t(r["us"]),
        "成分（美系）": r["us_names"],
        "Line 2 中系": _fmt_t(r["cn"]),
        "成分（中系）": r["cn_names"],
        "倍数": r["gap"],
    }
    for r in LAYERS
] + [{
    "层级": "合计",
    "Line 1 美系": f"${TOTAL_US}T", "成分（美系）": "",
    "Line 2 中系": f"${TOTAL_CN}T", "成分（中系）": "",
    "倍数": TOTAL_GAP,
}])
# st.table 渲染为静态 HTML，桌面与手机行为一致（不劫持触摸滚动）。
st.table(table.set_index("层级"))

st.markdown("""
**口径与注意事项**
- 数据为 2026 年 6 月 5 日收盘（含当周纳指 −4.18% 大跌之后），全部换算为美元；数值与倍数直接取自原报告，为约数。
- Line 2 覆盖 A股 + 港股 + 美股中概：A股（寒武纪、中恒电气、海光），A+H 双重上市（中芯国际、宁德时代），港股（腾讯、美团、智谱、MiniMax、优必选），美股中概（世纪互联；阿里、百度、万国数据、小鹏为美+港双重上市）。
- 未上市公司按最近一轮融资或二级市场交易估值计入：华为、字节跳动、OpenAI、Anthropic、xAI、DeepSeek、月之暗面等；国家电网体量巨大但无市值可比，未计入 L1。
- L2 中系未计海光；L5 两条链均存在口径模糊（不存在纯 AI 应用企业），倍数仅供参考。

*来源：《全球 AI 双价值链格局下的投资决策参考》，2026-06-07（`Reference/` 目录）。*
""")
