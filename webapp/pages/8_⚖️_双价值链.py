"""双价值链 — 美系 vs 中系 AI 价值链五层市值对比。

数据来源：weekly pipeline 的 value_chain 阶段（见 arf/value_chain.py + config/
value_chain.yaml），公开公司按当周收盘市值实时计算，未上市公司按人工维护的最近
估值静态计入。若数据库里还没有快照（例如全新本地环境、尚未跑过一次 pipeline），
回退展示《全球 AI 双价值链格局下的投资决策参考》（2026-06-07）截至 2026-06-05
收盘的静态参考数据。
"""
import json

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from webapp import data
from webapp.mobile import inject_mobile_css, show_plotly

st.set_page_config(page_title="ARF — 双价值链", layout="wide")
inject_mobile_css()

_LEGEND_BELOW = dict(orientation="h", yanchor="top", y=-0.25, xanchor="left", x=0, font=dict(size=11))

st.title("双价值链市值对比")

# ── 静态回退数据（2026-06-05 收盘，来自原始报告）─────────────────────────────
_FALLBACK_LAYERS = [
    {
        "layer": "L1 能源",
        "us": 0.60, "cn": 0.20,
        "us_names": "NextEra、Williams、GE Vernova、西门子能源、施耐德",
        "cn_names": "宁德时代（A+H）、中恒电气（A股）；国家电网未上市，不计",
    },
    {
        "layer": "L2 芯片与设备",
        "us": 9.7, "cn": 0.36,
        "us_names": "NVDA 4.97T、TSMC 1.95T、AVGO 1.83T、ASML 4,850亿、AMD 2,800亿、INTC 1,900亿",
        "cn_names": "华为 ~2,000亿（未上市估值）、中芯国际 850亿（A+H）、寒武纪 750亿（A股）；海光（A股）未计",
    },
    {
        "layer": "L3 基础设施",
        "us": 12.31, "cn": 0.90,
        "us_names": "GOOGL 4.63T、MSFT 3.11T、AMZN 2.87T、META 1.55T、EQIX+DLR ~1,500亿",
        "cn_names": "腾讯 5,475亿（港股）、阿里 3,030亿（美+港）、百度 ~370亿（美+港）、万国数据+世纪互联 ~130亿（美股中概）",
    },
    {
        "layer": "L4 基础模型",
        "us": 1.97, "cn": 0.18,
        "us_names": "Anthropic 9,000亿、OpenAI 8,520亿、xAI ~2,000亿、Mistral ~150亿（私募估值）",
        "cn_names": "智谱 ~800亿（港股）、MiniMax 338亿（港股）、DeepSeek ~450亿、月之暗面 ~180亿（未上市）",
    },
    {
        "layer": "L5 应用与物理 AI",
        "us": 5.2, "cn": 0.55,
        "us_names": "AAPL 4.53T、SAP ~3,300亿、Salesforce ~2,600亿、ABB+KUKA+UR ~700亿",
        "cn_names": "字节跳动 5,500亿（未上市估值）；美团（港股）、小鹏（美+港）、优必选（港股）、宇树未细列",
    },
]


def _fmt_t(v: float) -> str:
    return f"${v:.2f}T" if v < 1 else f"${v:.4g}T"


def _fmt_gap(us: float, cn: float) -> str:
    if not cn:
        return "—"
    return f"{us / cn:.1f}×"


def _names_from_constituents(constituents_json: str) -> str:
    try:
        items = json.loads(constituents_json) if constituents_json else []
    except (TypeError, ValueError):
        return ""
    return "、".join(f"{c['name']} {_fmt_t(c['market_cap_usd'] / 1e12)}" for c in items)


# ── 加载数据：优先用 DB 里 pipeline 算出的快照，没有则回退静态数据 ────────────
vc_df = data.load_value_chain()
using_live = not vc_df.empty

if using_live:
    as_of = pd.Timestamp(vc_df["as_of_date"].iloc[0]).date()
    us_rows = vc_df[vc_df["leg"] == "US"].set_index("layer")
    cn_rows = vc_df[vc_df["leg"] == "China"].set_index("layer")
    layers = []
    for layer_code in ["L1", "L2", "L3", "L4", "L5"]:
        u = us_rows.loc[layer_code] if layer_code in us_rows.index else None
        c = cn_rows.loc[layer_code] if layer_code in cn_rows.index else None
        us_cap = float(u["market_cap_usd"]) if u is not None else 0.0
        cn_cap = float(c["market_cap_usd"]) if c is not None else 0.0
        layer_name = (u["layer_name"] if u is not None else c["layer_name"]) if (u is not None or c is not None) else layer_code
        layers.append({
            "layer": layer_name,
            "us": us_cap / 1e12,
            "cn": cn_cap / 1e12,
            "us_names": _names_from_constituents(u["constituents_json"]) if u is not None else "",
            "cn_names": _names_from_constituents(c["constituents_json"]) if c is not None else "",
        })
    total_us = sum(r["us"] for r in layers)
    total_cn = sum(r["cn"] for r in layers)
    total_gap = _fmt_gap(total_us, total_cn)
    for r in layers:
        r["gap"] = _fmt_gap(r["us"], r["cn"])

    # 上一期快照，用于计算周环比
    all_dates = data.list_value_chain_dates(limit=2)
    delta_us = None
    if len(all_dates) == 2:
        prev_df = data.load_value_chain(as_of=all_dates[1])
        prev_us_total = prev_df[prev_df["leg"] == "US"]["market_cap_usd"].sum()
        if prev_us_total:
            delta_us = total_us - prev_us_total / 1e12

    caption = (
        f"Line 1（美系）vs Line 2（中系，覆盖 A股 + 港股 + 美股中概 + 未上市估值），按五层架构逐层对比。"
        f"数据截至 {as_of} 收盘，公开公司为当周实时市值，未上市公司为人工维护的最近估值，单位：万亿美元。"
    )
else:
    as_of = None
    layers = [dict(r, gap=_fmt_gap(r["us"], r["cn"])) for r in _FALLBACK_LAYERS]
    total_us = sum(r["us"] for r in layers)
    total_cn = sum(r["cn"] for r in layers)
    total_gap = _fmt_gap(total_us, total_cn)
    delta_us = None
    caption = (
        "Line 1（美系）vs Line 2（中系，覆盖 A股 + 港股 + 美股中概 + 未上市估值），按五层架构逐层对比。"
        "⚠ 数据库中暂无 pipeline 计算的快照，回退展示 2026-06-05 收盘的静态参考数据（截至下次 pipeline 运行后自动切换为实时计算）。"
    )

st.caption(caption)

# ── 头部指标 ──────────────────────────────────────────────────────────────────
c1, c2, c3 = st.columns(3)
delta_label = f"{delta_us:+.2f}T（周环比）" if delta_us is not None else None
c1.metric("Line 1 美系合计", f"${total_us:.2f}T", delta=delta_label,
          help="公开公司按当周收盘市值实时计算，未上市公司为静态估值")
c2.metric("Line 2 中系合计", f"${total_cn:.2f}T", help=f"约为 Line 1 的 1/{total_us / total_cn:.1f}" if total_cn else None)
c3.metric("整体差距", total_gap, help="分布不均：逐层差距倍数见下方图表")

st.divider()

# ── 逐层市值对比 ──────────────────────────────────────────────────────────────
rows = list(reversed(layers))
y_labels = [r["layer"] for r in rows]

fig = go.Figure()
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

axis_max = max(max(r["us"] for r in rows), 1.0) * 1.7
for r in rows:
    fig.add_annotation(
        x=axis_max * 0.995, y=r["layer"], text=f"<b>{r['gap']}</b>",
        showarrow=False, xanchor="right", font=dict(size=12),
    )
fig.add_annotation(x=axis_max * 0.995, y=1.06, yref="paper", text="倍数", showarrow=False,
                   xanchor="right", font=dict(size=11, color="gray"))

fig.update_layout(
    barmode="group",
    xaxis=dict(title="市值（万亿美元）", range=[0, axis_max]),
    height=460,
    margin=dict(t=30, r=10, b=90, l=10),
    legend=dict(traceorder="reversed", **_LEGEND_BELOW),
)
st.subheader("逐层市值对比")
show_plotly(fig)

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
    for r in layers
] + [{
    "层级": "合计",
    "Line 1 美系": f"${total_us:.2f}T", "成分（美系）": "",
    "Line 2 中系": f"${total_cn:.2f}T", "成分（中系）": "",
    "倍数": total_gap,
}])
st.table(table.set_index("层级"))

if using_live:
    st.markdown(f"""
**口径与注意事项**
- 数据截至 {as_of} 收盘，全部换算为美元；公开公司市值为当周实时抓取，未上市公司为
  `config/value_chain.yaml` 中人工维护的最近估值（有新一轮融资/二级市场成交时手动更新）。
- Line 2 覆盖 A股 + 港股 + 美股中概；A+H 双重上市（中芯国际）优先取 A 股口径，与 ARF 主
  评分口径一致。
- 部分名称原始报告无法干净估值，本页明确排除而非估算：国家电网、海光（未计入 L2 中系）、
  宇树（未列入 L5 中系）、KUKA/Universal Robots（已私有化/为集团子公司，未单独计入 L5 美系）。
- 层级划分为本页专用口径（按竞争关系分组，如云计算巨头计入 L3 基础设施），与 ARF 主评分
  的 layer 字段是两套独立体系。

*来源：`config/value_chain.yaml`（公开公司）+《全球 AI 双价值链格局下的投资决策参考》
（2026-06-07，`Reference/` 目录，作为未上市公司估值的原始出处）。*
""")
else:
    st.markdown("""
**口径与注意事项**
- 数据为 2026 年 6 月 5 日收盘（含当周纳指 −4.18% 大跌之后），全部换算为美元；数值与倍数直接取自原报告，为约数。
- Line 2 覆盖 A股 + 港股 + 美股中概：A股（寒武纪、中恒电气、海光），A+H 双重上市（中芯国际、宁德时代），港股（腾讯、美团、智谱、MiniMax、优必选），美股中概（世纪互联；阿里、百度、万国数据、小鹏为美+港双重上市）。
- 未上市公司按最近一轮融资或二级市场交易估值计入：华为、字节跳动、OpenAI、Anthropic、xAI、DeepSeek、月之暗面等；国家电网体量巨大但无市值可比，未计入 L1。
- L2 中系未计海光；L5 两条链均存在口径模糊（不存在纯 AI 应用企业），倍数仅供参考。

*来源：《全球 AI 双价值链格局下的投资决策参考》，2026-06-07（`Reference/` 目录）。*
""")
