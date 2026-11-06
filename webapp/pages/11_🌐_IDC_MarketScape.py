"""IDC Quanta™ AI Analyst Research Desk — MarketScape™, Spending Guide & Research Studio."""

import contextlib

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from arf.forecast import capex_to_customer_shocks
from arf.idc import (
    CAPABILITY_LEADER_THRESHOLD,
    STRATEGY_LEADER_THRESHOLD,
    compute_ai_spending_tracker,
    compute_idc_marketscape,
    generate_analyst_vendor_profile,
    generate_idc_executive_briefing,
)
from webapp import data
from webapp.mobile import inject_mobile_css, show_plotly
from webapp.ui import get_current_lang, render_sidebar, tr

is_en = get_current_lang() == "en"

st.set_page_config(
    page_title="IDC Quanta™ Analyst Research Desk — ARF MarketScape™" if is_en else "IDC Quanta™ 分析师工作台 — ARF MarketScape™",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="auto",
)
inject_mobile_css()


def _pct(value: object, decimals: int = 1, signed: bool = False) -> str:
    """Percentage for display, treating both NULL and NaN as missing."""
    if value is None or pd.isna(value):
        return "N/A"
    return f"{float(value):+.{decimals}%}" if signed else f"{float(value):.{decimals}%}"


def _num(value: object, decimals: int = 1) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{float(value):.{decimals}f}"


def _usd_b(value: object, decimals: int = 1) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"${float(value):.{decimals}f}B"


_CATEGORY_ZH = {
    "Leaders": "领军者",
    "Major Players": "主要厂商",
    "Contenders": "挑战者",
    "Participants": "参与者",
}

_LAYER_ZH = {
    "L1": "晶圆代工与封装",
    "L2": "算力芯片与硬件",
    "L3": "云巨头与电力",
    "L4": "基础大模型",
    "L5": "企业应用与智能体",
}

_LAYER_EN = {
    "L1": "Silicon & Foundry",
    "L2": "Compute Chips & Hardware",
    "L3": "Cloud & Power",
    "L4": "Foundation Models",
    "L5": "Enterprise Apps & Agents",
}


def _cat(category: object, is_en: bool) -> str:
    if is_en:
        return str(category)
    return _CATEGORY_ZH.get(str(category), str(category))


# ── Analyst Desk Header ──────────────────────────────────────────────────────
st.title(
    "🌐 IDC Quanta™ AI Analyst Research Desk (MarketScape™)"
    if is_en
    else "🌐 IDC Quanta™ AI 分析师研报工作台 (Research Desk)"
)
st.caption(
    tr(
        "IDC 官方标准 AI 产业链全景智库：集成 IDC MarketScape™ 厂商战略能力双轴评估、全球 AI 产业支出指南 (Worldwide AI Spending Guide)、"
        "供应链 Leontief 瓶颈压力沙盘与 1-Click 分析师快报起草台。",
        "IDC Official AI Ecosystem Intelligence: Integrating IDC MarketScape™ Dual-Axis Capabilities & Strategies Evaluation, "
        "Worldwide AI Spending Guide, Leontief Supply-Chain Bottleneck Sandbox, and 1-Click Analyst Briefing Studio.",
    )
)

as_of = render_sidebar()
if as_of is None:
    st.stop()

# Refresh is_en after render_sidebar in case language was toggled
is_en = get_current_lang() == "en"

complete_date = data.latest_complete_snapshot_date(as_of)
if complete_date is None:
    st.warning(
        tr(
            f"截至 {as_of} 尚无已完成评分的快照，请先运行数据管道评分。",
            f"No completed snapshot found as of {as_of}. Please run scoring pipeline first.",
        )
    )
    st.stop()
if complete_date != as_of:
    st.warning(
        tr(
            f"{as_of} 的快照尚未完成评分；已自动切换到最近一次完整评分的快照 **{complete_date}**。",
            f"Snapshot for {as_of} is incomplete; automatically rolled back to latest complete snapshot **{complete_date}**.",
        )
    )
    as_of = complete_date

# ── Load Snapshot, Forecast, and Supply Chain Links ──────────────────────────
snap_df = data.load_snapshot(as_of)
if snap_df.empty:
    st.warning(
        tr(
            f"未找到 {as_of} 的快照数据，请在侧边栏选择有效日期。",
            f"No snapshot data found for {as_of}. Please select a valid date in the sidebar.",
        )
    )
    st.stop()

fc_df = pd.DataFrame()
with contextlib.suppress(Exception), st.spinner(
    tr("加载前瞻预测（缺失时即时生成并写入 GCS）…", "Loading forward forecasts (generating on-demand if missing)…")
):
    fc_df = data.ensure_forecasts(as_of)

links_df = pd.DataFrame()
with contextlib.suppress(Exception):
    links_df = data.load_supply_chain_links()

# Compute IDC intelligence datasets
ms_df = compute_idc_marketscape(snap_df, fc_df)
spending = compute_ai_spending_tracker(snap_df, lang="en" if is_en else "zh")

if ms_df.empty:
    st.warning(
        tr(
            "该快照没有可用的评分数据，无法生成 MarketScape 分析。",
            "No scored vendor data available in this snapshot to generate MarketScape analysis.",
        )
    )
    st.stop()

if fc_df.empty:
    st.caption(
        tr(
            "ℹ️ 该快照日期无前瞻预测数据：Strategies 轴暂以营收增速替代，超预期与修正动能显示为 N/A。",
            "ℹ️ No forward forecasts for this snapshot date: Strategies axis falls back to historical revenue growth; beat margins show N/A.",
        )
    )

scored_count = int(ms_df["ticker"].nunique())

# ── Top-Level KPI Ribbon ─────────────────────────────────────────────────────
m_col1, m_col2, m_col3, m_col4 = st.columns(4)
with m_col1:
    st.metric(
        tr("🏛️ AI 核心纳管市值", "🏛️ AI Universe Market Cap"),
        f"${spending.get('total_universe_mcap_t', 0.0)}T",
        help=tr(
            "全部已评分标的的美元总市值（中美双轨合计）",
            "Aggregate equity market capitalization across covered global AI leaders (USD)",
        ),
    )
with m_col2:
    st.metric(
        tr("💰 实质 AI 纯度收入 (年化)", "💰 Real Economic AI Revenue (Ann.)"),
        f"${spending.get('total_ai_revenue_b', 0.0)}B",
        help=tr(
            "经 E-score 纯度加权折算",
            "Annualized pure-play revenue adjusted by quantitative AI exposure (E-score)",
        ),
    )
with m_col3:
    bubble_mult = spending.get("overall_bubble_multiple", 0.0)
    st.metric(
        tr("🫧 全局叙事泡沫倍数 (P/S_AI)", "🫧 Narrative Bubble Multiple (P/S_AI)"),
        f"{bubble_mult:.1f}x",
        help=tr(
            "资本市值 / 实质 AI 收入",
            "Equity Market Cap / Real Economic AI Revenue",
        ),
    )
with m_col4:
    froth_total = sum(item["froth_count"] for item in spending.get("layers", []))
    st.metric(
        tr("🚨 触碰泡沫熔断厂商", "🚨 Froth Circuit Breached"),
        f"{froth_total} " + tr("家", "Vendors"),
        help=tr(
            "D1泡沫 + 负/低ROE + P/S>25",
            "Decile 1 Froth + Low/Negative ROE + Price-to-Sales > 25",
        ),
    )

st.caption(
    tr(
        f"{as_of} 快照 · {scored_count} 家已评分标的 · 泡沫熔断 = ARF D1 且 ROE < 权益成本 且 P/S > 25",
        f"{as_of} Snapshot · {scored_count} Scored Vendors · Froth Circuit = ARF Decile 1 & ROE < Cost of Equity & P/S > 25",
    )
)

st.divider()

# ── 6 Core Tabs of the Analyst Research Desk ─────────────────────────────────
tab_marketscape, tab_deepdive, tab_sandbox, tab_spending, tab_press, tab_studio = st.tabs([
    tr("🎯 IDC MarketScape™ 厂商竞争矩阵", "🎯 IDC MarketScape™ Quadrant Matrix"),
    tr("🔬 厂商深度调研与对标台", "🔬 Vendor Deep-Dive & Peer Radar"),
    tr("🛠️ 供应链需求与瓶颈沙盘", "🛠️ Supply-Chain Shock Sandbox"),
    tr("📊 全球 AI 产业支出指南", "📊 Worldwide AI Spending Guide"),
    tr("📰 WSJ & NYT 金融舆情前沿", "📰 WSJ & NYT Financial Press Wire"),
    tr("📝 分析师快报与研报起草台", "📝 Analyst Briefing & Studio"),
])

# ── TAB 1: IDC MarketScape ───────────────────────────────────────────────────
with tab_marketscape:
    st.subheader(
        tr("🎯 IDC MarketScape: 全球 AI 价值链厂商定位", "🎯 IDC MarketScape: Global AI Value Chain Positioning")
    )
    if is_en:
        st.markdown(
            """
            > **Evaluation Framework**: The IDC MarketScape employs a quantitative dual-axis model:
            > - **Y-Axis Capabilities (Execution Quality & Margins)**: Assesses ROE, gross margins, supply-chain criticality, and valuation quality.
            > - **X-Axis Strategies (Forward Growth Trajectory)**: Assesses quantitative AI exposure (E-score), 12M forward revenue forecast, and consensus revision velocity.
            > - **Bubble Size**: Equity Market Capitalization (USD). **Bubble Color**: US Leg (Cyan) vs Greater China Leg (Rose).
            """
        )
    else:
        st.markdown(
            """
            > **评估体系**：IDC MarketScape 采用行业金标准双轴模型。
            > - **纵轴 Capabilities (当前交付与财务质量)**：评估 ROE 资产收益率、毛利率、AI 供应链关键度与估值质量；
            > - **横轴 Strategies (未来战略与增长动能)**：评估 AI 暴露度 (E-score)、前瞻 12 个月预测营收复合增速与一致预期修正动能；
            > - **气泡大小**：代表厂商当前美元总市值；**气泡颜色**：代表中美双轨价值链归属。
            """
        )

    ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([2, 2, 3])
    with ctrl_col1:
        leg_opts = (
            ["All (Global All)", "US Value Chain (US Leg)", "China Value Chain (China Leg)"]
            if is_en
            else ["全部 (Global All)", "美系价值链 (US Leg)", "中系价值链 (China Leg)"]
        )
        leg_filter = st.selectbox(
            tr("区域价值链筛选", "Regional Value Chain"),
            leg_opts,
            index=0,
            key="ms_leg_filter",
        )
    with ctrl_col2:
        layer_opts = (
            [
                "All Layers",
                "L1 Silicon & Foundries",
                "L2 Optical Interconnect & Hardware",
                "L3 Cloud Infrastructure & Hyperscalers",
                "L4 Foundation Models & Platforms",
                "L5 Enterprise AI Applications",
            ]
            if is_en
            else [
                "全部层级 (All Layers)",
                "L1 芯片设计与制造 (Foundry & Chips)",
                "L2 核心互联与硬件 (Optical & Hardware)",
                "L3 基础设施与云厂商 (Cloud & Infra)",
                "L4 基础大模型与平台 (Foundational Models)",
                "L5 垂直行业应用 (Enterprise Apps)",
            ]
        )
        layer_filter = st.selectbox(
            tr("产业链层级筛选", "Stack Layer Filter"),
            layer_opts,
            index=0,
            key="ms_layer_filter",
        )
    with ctrl_col3:
        search_query = st.text_input(
            tr("🔍 搜索厂商代码或名称 (如 NVDA, 寒武纪, 300308)", "🔍 Search Ticker or Vendor Name (e.g. NVDA, Innolight, 300308)"),
            value="",
            placeholder=tr("输入 Ticker 或名称...", "Enter ticker or company name..."),
            key="ms_search_input",
        )

    # Filter DataFrame
    plot_df = ms_df.copy()
    if "US" in leg_filter:
        plot_df = plot_df[plot_df["leg"] == "US"]
    elif "China" in leg_filter:
        plot_df = plot_df[plot_df["leg"] == "China"]

    if layer_filter not in ("All Layers", "全部层级 (All Layers)"):
        layer_code = layer_filter[:2]
        plot_df = plot_df[plot_df["layer"] == layer_code]

    if search_query.strip():
        q = search_query.strip().upper()
        plot_df = plot_df[
            plot_df["ticker"].str.upper().str.contains(q, regex=False)
            | plot_df["name"].str.upper().str.contains(q, regex=False)
        ]

    # Create Plotly MarketScape Quadrant
    if not plot_df.empty:
        fig = go.Figure()

        x_cut = STRATEGY_LEADER_THRESHOLD
        y_cut = CAPABILITY_LEADER_THRESHOLD
        fig.add_shape(
            type="rect",
            x0=x_cut, x1=100, y0=y_cut, y1=100,
            fillcolor="rgba(34, 197, 94, 0.08)",
            line=dict(color="rgba(34, 197, 94, 0.3)", width=1, dash="dot"),
        )
        fig.add_shape(
            type="rect",
            x0=x_cut, x1=100, y0=10, y1=y_cut,
            fillcolor="rgba(249, 115, 22, 0.08)",
            line=dict(color="rgba(249, 115, 22, 0.3)", width=1, dash="dot"),
        )
        fig.add_shape(
            type="rect",
            x0=10, x1=x_cut, y0=y_cut, y1=100,
            fillcolor="rgba(59, 130, 246, 0.08)",
            line=dict(color="rgba(59, 130, 246, 0.3)", width=1, dash="dot"),
        )
        fig.add_shape(
            type="rect",
            x0=10, x1=x_cut, y0=10, y1=y_cut,
            fillcolor="rgba(148, 163, 184, 0.05)",
            line=dict(color="rgba(148, 163, 184, 0.3)", width=1, dash="dot"),
        )

        # Quadrant Watermark Annotations
        fig.add_annotation(
            x=97, y=97,
            text="<b>🏆 LEADERS</b>" + ("" if is_en else " (领军者)"),
            showarrow=False, font=dict(size=14, color="#22c55e"), xanchor="right", yanchor="top",
        )
        fig.add_annotation(
            x=13, y=97,
            text="<b>🛡️ MAJOR PLAYERS</b>" + ("" if is_en else " (主要厂商)"),
            showarrow=False, font=dict(size=14, color="#3b82f6"), xanchor="left", yanchor="top",
        )
        fig.add_annotation(
            x=97, y=13,
            text="<b>⚡ CONTENDERS</b>" + ("" if is_en else " (高增长挑战者)"),
            showarrow=False, font=dict(size=14, color="#f97316"), xanchor="right", yanchor="bottom",
        )
        fig.add_annotation(
            x=13, y=13,
            text="<b>🔍 PARTICIPANTS</b>" + ("" if is_en else " (利基参与者)"),
            showarrow=False, font=dict(size=14, color="#94a3b8"), xanchor="left", yanchor="bottom",
        )

        sizes = np.clip(np.sqrt(plot_df["market_cap_b"].clip(lower=1.0)) * 2.2, 10.0, 52.0)
        colors = [
            "#38bdf8" if row["leg"] == "US" else "#f43f5e"
            for _, row in plot_df.iterrows()
        ]

        if is_en:
            hover_texts = [
                f"<b>{r['name']}</b> ({r['ticker']})<br>"
                f"Region: {r['leg']} | Layer: {r['layer']}<br>"
                f"Quadrant: <b>{_cat(r['marketscape_category'], True)}</b><br>"
                f"Capabilities Score: <b>{r['capabilities_score']:.1f}</b><br>"
                f"Strategies Score: <b>{r['strategies_score']:.1f}</b><br>"
                f"Market Cap: {_usd_b(r['market_cap_b'])} | Real AI Rev: {_usd_b(r['ai_revenue_est_b'])}<br>"
                f"ARF Score: {_num(r['arf'])} | Forecast Growth: {_pct(r['predicted_growth'], signed=True)}<br>"
                f"Froth Circuit: {'🔴 BREACHED' if r['froth_flag'] else '🟢 NORMAL'}"
                for _, r in plot_df.iterrows()
            ]
        else:
            hover_texts = [
                f"<b>{r['name']}</b> ({r['ticker']})<br>"
                f"区域: {r['leg']} | 层级: {r['layer']}<br>"
                f"阵营: <b>{_cat(r['marketscape_category'], False)}</b><br>"
                f"交付质量 (Capabilities): <b>{r['capabilities_score']:.1f}</b><br>"
                f"战略动能 (Strategies): <b>{r['strategies_score']:.1f}</b><br>"
                f"市值: {_usd_b(r['market_cap_b'])} | 实质AI收入: {_usd_b(r['ai_revenue_est_b'])}<br>"
                f"ARF得分: {_num(r['arf'])} | 预测增速: {_pct(r['predicted_growth'], signed=True)}<br>"
                f"泡沫熔断状态: {'🔴 触碰熔断' if r['froth_flag'] else '🟢 正常'}"
                for _, r in plot_df.iterrows()
            ]

        fig.add_trace(
            go.Scatter(
                x=plot_df["strategies_score"],
                y=plot_df["capabilities_score"],
                mode="markers+text",
                marker=dict(
                    size=sizes,
                    color=colors,
                    opacity=0.82,
                    line=dict(width=1.5, color="#ffffff"),
                ),
                text=plot_df["ticker"],
                textposition="top center",
                textfont=dict(size=10, color="#f1f5f9"),
                hovertext=hover_texts,
                hoverinfo="text",
                name="AI Vendors",
            )
        )

        fig.update_layout(
            title=dict(
                text=tr(
                    f"<b>IDC MarketScape：全球 AI 厂商评估 ({as_of})</b>",
                    f"<b>IDC MarketScape: Global AI Vendors Assessment ({as_of})</b>",
                ),
                font=dict(size=17, color="#0f172a"),
            ),
            xaxis=dict(
                title=tr("<b>STRATEGIES (未来战略与增长弹性 ➔)</b>", "<b>STRATEGIES (Forward Growth Momentum ➔)</b>"),
                range=[10, 102],
                zeroline=False,
                gridcolor="#334155",
            ),
            yaxis=dict(
                title=tr("<b>CAPABILITIES (当期交付质量与财务壁垒 ➔)</b>", "<b>CAPABILITIES (Execution Quality & Margins ➔)</b>"),
                range=[10, 102],
                zeroline=False,
                gridcolor="#334155",
            ),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(15, 23, 42, 0.6)",
            height=600,
            showlegend=False,
            margin=dict(l=40, r=40, t=50, b=40),
        )

        show_plotly(fig)
    else:
        st.info(tr("筛选条件下暂无厂商数据。", "No vendor records match current filter criteria."))

    # Vendor Detail Table
    st.markdown(
        tr("#### 📋 厂商全景明细表 (IDC MarketScape Vendor Scorecard)", "#### 📋 IDC MarketScape Vendor Scorecard")
    )
    display_cols = [
        "ticker", "name", "leg", "layer", "marketscape_category",
        "capabilities_score", "strategies_score", "market_cap_b",
        "ai_revenue_est_b", "predicted_growth", "arf", "froth_flag",
    ]
    formatted_df = plot_df[display_cols].copy()
    if is_en:
        formatted_df.columns = [
            "Ticker", "Vendor Name", "Region", "Layer", "Quadrant",
            "Capabilities", "Strategies", "Market Cap ($B)", "Real AI Rev ($B)",
            "Forecast Growth", "ARF", "Froth Circuit",
        ]
        formatted_df["Forecast Growth"] = formatted_df["Forecast Growth"].apply(lambda x: f"{x:+.1%}" if pd.notna(x) else "—")
        formatted_df["Market Cap ($B)"] = formatted_df["Market Cap ($B)"].apply(_num)
        formatted_df["Real AI Rev ($B)"] = formatted_df["Real AI Rev ($B)"].apply(lambda x: _num(x, 2))
        formatted_df["Froth Circuit"] = formatted_df["Froth Circuit"].apply(lambda x: "🔴 BREACHED" if x else "🟢 NORMAL")
    else:
        formatted_df.columns = [
            "标的代码", "厂商名称", "区域", "层级", "IDC阵营分类",
            "交付质量", "战略动能", "市值 ($B)", "实质AI收入 ($B)",
            "预测增速", "ARF", "泡沫熔断",
        ]
        formatted_df["预测增速"] = formatted_df["预测增速"].apply(lambda x: f"{x:+.1%}" if pd.notna(x) else "—")
        formatted_df["市值 ($B)"] = formatted_df["市值 ($B)"].apply(_num)
        formatted_df["实质AI收入 ($B)"] = formatted_df["实质AI收入 ($B)"].apply(lambda x: _num(x, 2))
        formatted_df["泡沫熔断"] = formatted_df["泡沫熔断"].apply(lambda x: "🔴 熔断" if x else "🟢 正常")

    st.dataframe(formatted_df, use_container_width=True, hide_index=True)

# ── TAB 2: Vendor Deep-Dive & Peer Radar ─────────────────────────────────────
with tab_deepdive:
    st.subheader(
        tr("🔬 厂商深度调研台与同业对标 (Vendor Deep-Dive)", "🔬 Vendor Deep-Dive & Peer Radar Benchmark")
    )
    st.caption(
        tr(
            "供 IDC 分析师针对指定标的展开全景画像穿透：透视财务质量、逆向 DCF 增长预期、客户供应链拓扑与同业对标。",
            "Authoritative deep-dive workspace for IDC analysts: financial viability, reverse-DCF implied growth, supply chain topology, and head-to-head peer benchmarking.",
        )
    )

    all_tickers = sorted(ms_df["ticker"].unique().tolist())
    default_ix = all_tickers.index("NVDA") if "NVDA" in all_tickers else 0

    sel_col1, sel_col2 = st.columns([3, 3])
    with sel_col1:
        chosen_ticker = st.selectbox(
            tr("🎯 选择主要调研厂商 (Primary Vendor)", "🎯 Select Primary Vendor"),
            all_tickers,
            index=default_ix,
        )
    with sel_col2:
        peer_options = [t for t in all_tickers if t != chosen_ticker]
        default_peer_ix = peer_options.index("300308.SZ") if "300308.SZ" in peer_options else 0
        peer_ticker = st.selectbox(
            tr("⚖️ 选择同业对标厂商 (Benchmark Peer)", "⚖️ Select Benchmark Peer"),
            peer_options,
            index=default_peer_ix,
        )

    v_primary = ms_df[ms_df["ticker"] == chosen_ticker].iloc[0].to_dict()
    v_peer = ms_df[ms_df["ticker"] == peer_ticker].iloc[0].to_dict()

    cat_badge = (
        ("🟢 Leader" if is_en else "🟢 领军者 (Leader)")
        if v_primary["marketscape_category"] == "Leaders"
        else ("🔵 Major Player" if is_en else "🔵 主要厂商 (Major Player)")
        if v_primary["marketscape_category"] == "Major Players"
        else ("🟠 Contender" if is_en else "🟠 挑战者 (Contender)")
        if v_primary["marketscape_category"] == "Contenders"
        else ("⚪ Participant" if is_en else "⚪ 参与者 (Participant)")
    )

    st.markdown(
        f"### 🏢 **{v_primary['name']} ({chosen_ticker})** — {cat_badge} "
        f"`[{v_primary['leg']} / {v_primary['layer']}]`"
    )

    card_c1, card_c2, card_c3, card_c4, card_c5 = st.columns(5)
    with card_c1:
        st.metric(
            tr("交付质量 (Capabilities)", "Capabilities Score"),
            f"{v_primary['capabilities_score']:.1f} / 100",
        )
    with card_c2:
        st.metric(
            tr("战略动能 (Strategies)", "Strategies Score"),
            f"{v_primary['strategies_score']:.1f} / 100",
        )
    with card_c3:
        st.metric(
            tr("ARF 泡沫估值指数", "ARF Bubble Score"),
            f"{v_primary['arf']:.1f}",
            help=tr("D1 泡沫阈值 ≥ 90", "Decile 1 bubble threshold ≥ 90"),
        )
    with card_c4:
        st.metric(
            tr("逆向 DCF 隐含增速", "Reverse-DCF Implied g*"),
            _pct(v_primary.get("implied_growth")),
            help=tr("市场定价所需永续增速", "Market-implied perpetual growth hurdle"),
        )
    with card_c5:
        st.metric(
            tr("12M 预期超一致差", "Forecast Beat vs Consensus"),
            _pct(v_primary.get("expected_beat_pct"), signed=True),
            help=tr("ARF模型前瞻弹性", "ARF forward model revision momentum"),
        )

    st.markdown(
        tr("#### ⚖️ 双雄深度指标对标 (Head-to-Head Benchmark)", "#### ⚖️ Head-to-Head Peer Benchmark")
    )
    dim_lbl = "Dimension" if is_en else "指标维度"
    peer_metrics_table = [
        {dim_lbl: tr("IDC MarketScape 阵营", "MarketScape Quadrant"), chosen_ticker: _cat(v_primary["marketscape_category"], is_en), peer_ticker: _cat(v_peer["marketscape_category"], is_en)},
        {dim_lbl: tr("Capabilities (交付与财务质量)", "Capabilities (Execution Quality)"), chosen_ticker: f"{v_primary['capabilities_score']:.1f}", peer_ticker: f"{v_peer['capabilities_score']:.1f}"},
        {dim_lbl: tr("Strategies (未来战略与增速)", "Strategies (Forward Momentum)"), chosen_ticker: f"{v_primary['strategies_score']:.1f}", peer_ticker: f"{v_peer['strategies_score']:.1f}"},
        {dim_lbl: tr("资本总市值 (USD)", "Equity Market Cap (USD)"), chosen_ticker: f"${v_primary['market_cap_b']:.1f}B", peer_ticker: f"${v_peer['market_cap_b']:.1f}B"},
        {dim_lbl: tr("实质 AI 年化收入估算", "Real Annualized AI Revenue"), chosen_ticker: _usd_b(v_primary.get("ai_revenue_est_b"), 2), peer_ticker: _usd_b(v_peer.get("ai_revenue_est_b"), 2)},
        {dim_lbl: tr("AI 暴露纯度 (E_score)", "AI Pure-Play Exposure (E-score)"), chosen_ticker: f"{v_primary.get('e_score', 0):.0f}", peer_ticker: f"{v_peer.get('e_score', 0):.0f}"},
        {dim_lbl: tr("估值张力指数 (V_score)", "Valuation Stretch (V-score)"), chosen_ticker: f"{v_primary.get('v_score', 0):.0f}", peer_ticker: f"{v_peer.get('v_score', 0):.0f}"},
        {dim_lbl: tr("ROE 净资产收益率", "Return on Equity (ROE)"), chosen_ticker: _pct(v_primary.get("roe")), peer_ticker: _pct(v_peer.get("roe"))},
        {dim_lbl: tr("市销率 (P/S Ratio)", "Price-to-Sales (P/S)"), chosen_ticker: f"{_num(v_primary.get('ps_ratio'))}x", peer_ticker: f"{_num(v_peer.get('ps_ratio'))}x"},
        {dim_lbl: tr("前瞻 12M 预测增速 (ARF ĝ)", "12M Forward Revenue Forecast"), chosen_ticker: _pct(v_primary.get("predicted_growth"), signed=True), peer_ticker: _pct(v_peer.get("predicted_growth"), signed=True)},
        {dim_lbl: tr("泡沫熔断状态 (Froth Circuit)", "Froth Circuit Breaker"), chosen_ticker: ("🔴 BREACHED" if is_en else "🔴 触碰熔断") if v_primary['froth_flag'] else ("🟢 NORMAL" if is_en else "🟢 正常"), peer_ticker: ("🔴 BREACHED" if is_en else "🔴 触碰熔断") if v_peer['froth_flag'] else ("🟢 NORMAL" if is_en else "🟢 正常")},
    ]
    st.dataframe(pd.DataFrame(peer_metrics_table), use_container_width=True, hide_index=True)

    st.markdown(
        tr("#### 🔗 产业链上下游传导拓扑 (Supply Chain Topology)", "#### 🔗 Supply Chain Ecosystem Topology")
    )
    topo_c1, topo_c2 = st.columns(2)
    with topo_c1:
        st.markdown(
            "**" + tr(f"下游核心客户 (Direct Customers of {chosen_ticker}):", f"Direct Customers of {chosen_ticker}:") + "**"
        )
        if not links_df.empty:
            cust_sub = links_df[links_df["supplier_ticker"].astype(str).str.upper() == chosen_ticker]
            if not cust_sub.empty:
                rename_map = (
                    {
                        "customer_ticker": "Customer Ticker",
                        "revenue_share_pct": "Rev Share Contribution (%)",
                        "relationship_type": "Relationship Type",
                        "verified_source": "Disclosure Source",
                    }
                    if is_en
                    else {
                        "customer_ticker": "客户代码",
                        "revenue_share_pct": "营收占比贡献 (%)",
                        "relationship_type": "供应链关系",
                        "verified_source": "披露来源",
                    }
                )
                st.dataframe(
                    cust_sub[["customer_ticker", "revenue_share_pct", "relationship_type", "verified_source"]].rename(
                        columns=rename_map
                    ),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info(tr("该标的未在数据库中申报下游直连客户，或处于应用消费终端。", "No direct downstream customer disclosures in database, or end-consumer facing."))
        else:
            st.info(tr("供应链拓扑数据库就绪中。", "Supply chain database initializing."))

    with topo_c2:
        st.markdown(
            "**" + tr(f"上游核心供应商 (Key Suppliers to {chosen_ticker}):", f"Key Upstream Suppliers to {chosen_ticker}:") + "**"
        )
        if not links_df.empty:
            supp_sub = links_df[links_df["customer_ticker"].astype(str).str.upper() == chosen_ticker]
            if not supp_sub.empty:
                rename_map = (
                    {
                        "supplier_ticker": "Supplier Ticker",
                        "bom_component_pct": "BOM Cost Share (%)",
                        "relationship_type": "Supplied Component",
                        "verified_source": "Disclosure Source",
                    }
                    if is_en
                    else {
                        "supplier_ticker": "供应商代码",
                        "bom_component_pct": "BOM成本占比 (%)",
                        "relationship_type": "供应元器件",
                        "verified_source": "披露来源",
                    }
                )
                st.dataframe(
                    supp_sub[["supplier_ticker", "bom_component_pct", "relationship_type", "verified_source"]].rename(
                        columns=rename_map
                    ),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info(tr("该标的未在数据库中申报上游依赖，或处于全栈垂直整合。", "No direct upstream supplier disclosures in database, or vertically integrated."))
        else:
            st.info(tr("供应链拓扑数据库就绪中。", "Supply chain database initializing."))

    st.markdown("---")
    st.markdown(
        tr(f"#### 📰 华尔街日报与纽时实时舆情速递 ({chosen_ticker} Media Wire)", f"#### 📰 Real-Time WSJ & NYT Press Coverage ({chosen_ticker})")
    )
    v_news_df = data.load_ticker_news_signals(
        chosen_ticker, days=30, limit=6, as_of=as_of
    )
    if not v_news_df.empty:
        st.caption(
            tr(
                f"收录近 30 天《华尔街日报》与《纽约时报》提及 {chosen_ticker} 的权威报道（共 {len(v_news_df)} 篇）：",
                f"Verified WSJ & NYT editorial coverage citing {chosen_ticker} ({len(v_news_df)} articles):",
            )
        )
        for _, art in v_news_df.iterrows():
            pub_str = art["published_at"].strftime("%Y-%m-%d") if hasattr(art["published_at"], "strftime") else str(art["published_at"])[:10]
            sent_badge = "🟢 " + tr("偏多", "Bullish") if art["sentiment_label"] == "Bullish" else ("🔴 " + tr("偏空", "Bearish") if art["sentiment_label"] == "Bearish" else "⚪ " + tr("中性", "Neutral"))
            source_tag = f"**{art['source']}**"
            st.markdown(f"- {source_tag} `[{pub_str}]` [{art['title']}]({art['url']}) · {sent_badge}")
            if art.get("summary"):
                st.caption(f"> {art['summary'][:160]}...")
    else:
        st.info(
            tr(
                f"近 30 天权威财经媒体（WSJ / NYT）暂无针对 {chosen_ticker} 的专属报道。",
                f"No targeted WSJ / NYT reports recorded for {chosen_ticker} in the past 30 days.",
            )
        )

# ── TAB 3: CapEx & Leontief Scenario Sandbox ─────────────────────────────────
with tab_sandbox:
    st.subheader(
        tr("🛠️ 供应链需求拉动与物理瓶颈测算沙盘 (Analyst Scenario Sandbox)", "🛠️ Leontief Supply-Chain Shock & Bottleneck Sandbox")
    )
    if is_en:
        st.markdown(
            """
            > **IDC Proprietary Leontief Shock Sandbox**: Empowers analysts to simulate enterprise-wide impacts:
            > When hyperscalers (Microsoft, Google, Meta) revise compute CapEx, demand signals propagate across midstream hardware, optical transceivers, and foundries,
            > subject to physical capacity clamps (CoWoS advanced packaging and high-voltage electrical grid capacity).
            """
        )
    else:
        st.markdown(
            """
            > **IDC 独创 Leontief 传导沙盒**：供分析师向企业客户或投资者推演：
            > 当下游云巨头 (Microsoft, Google, Meta) 调整 AI 算力资本开支时，需求拉动如何沿价值链逐级传导至中上游硬件制造、光模块与晶圆代工，
            > 并受制于 CoWoS 先进封装与高压电网的硬性产能瓶颈夹钳。
            """
        )

    sb_c1, sb_c2, sb_c3 = st.columns([2, 2, 2])
    with sb_c1:
        capex_input = st.slider(
            tr("☁️ 云巨头 (MSFT/GOOGL/META) CapEx 变动假设", "☁️ Hyperscaler (MSFT/GOOGL/META) CapEx Shock (%)"),
            min_value=-30,
            max_value=60,
            value=15,
            step=5,
            format="%+d%%",
            help=tr("调整云厂商年度算力资本支出假设", "Simulate Hyperscaler CapEx expansion or contraction"),
            key="idk_capex_slider",
        )
    with sb_c2:
        clamp_input = st.slider(
            tr("🏭 物理产能瓶颈夹钳 (CoWoS / 电网扩容上限)", "🏭 Physical Bottleneck Capacity Clamp (CoWoS / Grid Cap %)"),
            min_value=20,
            max_value=120,
            value=80,
            step=10,
            format="%d%%",
            help=tr("Leontief 瓶颈夹钳：上限硬性截断名义拉动，防止虚假高增长", "Leontief clamp: truncates unrealistic nominal demand pull at physical limits"),
            key="idk_clamp_slider",
        )
    with sb_c3:
        status_lbl = (
            tr("正向强拉动", "Strong Expansion Pull")
            if capex_input >= 20
            else (tr("温和扩张", "Moderate Growth") if capex_input > 0 else tr("缩减承压", "CapEx Contraction"))
        )
        st.metric(
            tr("📡 传导情景模拟状态", "📡 Transmission Scenario Status"),
            status_lbl,
            help=f"CapEx {capex_input:+d}% / Clamp {clamp_input}%",
        )

    try:
        from arf.agent.cio_loop import simulate_supply_chain_shock

        sim_shocks = capex_to_customer_shocks(fc_df, capex_input)

        sim_df = simulate_supply_chain_shock(
            conn=data.get_conn(),
            as_of=as_of,
            customer_shocks=sim_shocks,
            bottleneck_clamp=clamp_input / 100.0,
            snap_df=snap_df,
            fc_df=fc_df,
            links_df=links_df,
        )

        if not sim_df.empty:
            st.markdown(
                tr("#### ⚡ 供应链核心受冲击节点敏感性模拟 (Top 8 Impacted Nodes)", "#### ⚡ Top 8 Most Sensitive Supply Chain Nodes")
            )
            rename_map = (
                {
                    "ticker": "Ticker",
                    "name": "Company Name",
                    "leg": "Region",
                    "layer": "Layer",
                    "base_pred_growth": "Base Forecast",
                    "shocked_pred_growth": "Shocked Forecast",
                    "growth_delta": "Demand Elasticity (Δ)",
                    "expected_beat_pct": "Beat Margin",
                    "fair_value_p50": "P50 Fair Value ($)",
                }
                if is_en
                else {
                    "ticker": "标的代码",
                    "name": "公司名称",
                    "leg": "区域",
                    "layer": "层级",
                    "base_pred_growth": "基准预测增速",
                    "shocked_pred_growth": "冲击后增速",
                    "growth_delta": "需求弹性增量 (Δ)",
                    "expected_beat_pct": "超预期差",
                    "fair_value_p50": "P50 公允价值 ($)",
                }
            )
            st.dataframe(
                sim_df.head(8)[[
                    "ticker", "name", "leg", "layer", "base_pred_growth",
                    "shocked_pred_growth", "growth_delta", "expected_beat_pct", "fair_value_p50",
                ]].rename(columns=rename_map),
                use_container_width=True,
                hide_index=True,
            )
    except Exception as exc:
        st.info(f"Scenario simulation note: {exc}" if is_en else f"情景模拟沙盘运算提示: {exc}")

# ── TAB 4: Worldwide AI Spending Guide ────────────────────────────────────────
with tab_spending:
    st.subheader(
        tr("📊 全球 AI 产业支出与泡沫乘数分布 (Worldwide AI Spending Guide)", "📊 Worldwide AI Spending Guide & Bubble Multipliers")
    )
    if is_en:
        st.markdown(
            """
            > **IDC Macro Spending Intelligence**: Tracks the ratio of **Equity Market Cap** to **Annualized Economic AI Revenue** across the 5 stack layers.
            > A higher multiplier indicates that more speculative future narrative is embedded into current valuations.
            """
        )
    else:
        st.markdown(
            """
            > **IDC 宏观支出指南**：追踪 5 层 AI 架构中**资本市值 (Equity Market Cap)** 与**实质年化 AI 支出/收入 (Annualized AI Spending)** 的比值；
            > 倍数越高，表明当前估值中注入的「未来增长叙事资本」越多。当物理基础设施增速无法承接下游算力扩张时，泡沫溢价最先发生均值回归。
            """
        )

    layers_df = pd.DataFrame(spending.get("layers", []))
    if not layers_df.empty:
        col_chart1, col_chart2 = st.columns([3, 2])

        with col_chart1:
            fig_bar = go.Figure()
            fig_bar.add_trace(
                go.Bar(
                    x=layers_df["layer_code"],
                    y=layers_df["market_cap_b"],
                    name=tr("资本市值 ($B USD)", "Market Cap ($B USD)"),
                    marker_color="#38bdf8",
                )
            )
            fig_bar.add_trace(
                go.Bar(
                    x=layers_df["layer_code"],
                    y=layers_df["ai_revenue_est_b"],
                    name=tr("实质 AI 纯度收入 ($B USD)", "Real Economic AI Rev ($B USD)"),
                    marker_color="#22c55e",
                )
            )
            fig_bar.update_layout(
                title=tr("<b>各层级总市值 vs 实质年化 AI 收入 ($B USD)</b>", "<b>Stack Layer Equity Cap vs Real AI Revenue ($B USD)</b>"),
                barmode="group",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                height=380,
                xaxis=dict(gridcolor="#334155"),
                yaxis=dict(gridcolor="#334155", title=tr("十亿美元 ($B)", "Billion USD ($B)")),
            )
            show_plotly(fig_bar)

        with col_chart2:
            fig_mult = px.bar(
                layers_df,
                x="layer_code",
                y="bubble_multiple",
                color="bubble_multiple",
                color_continuous_scale="Reds",
                title=tr("<b>各层级叙事泡沫乘数 (Market Cap / AI Revenue)</b>", "<b>Narrative Bubble Multiplier by Layer (P/S_AI)</b>"),
                text="bubble_multiple",
                labels={
                    "bubble_multiple": tr("叙事泡沫乘数", "Bubble Multiplier"),
                    "layer_code": tr("产业链层级", "Stack Layer"),
                },
            )
            fig_mult.update_traces(texttemplate="%{text:.1f}x", textposition="outside")
            fig_mult.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=380,
                xaxis=dict(title=tr("产业链层级", "Stack Layer"), gridcolor="#334155"),
                yaxis=dict(title=tr("泡沫乘数 (倍)", "Bubble Multiplier (x)"), gridcolor="#334155"),
                coloraxis_showscale=False,
                showlegend=False,
            )
            show_plotly(fig_mult)

        st.markdown(
            tr("#### 📑 5 层价值链支出与估值透视表", "#### 📑 5-Layer Value Chain Spending & Valuation Ledger")
        )
        rename_map = (
            {
                "layer_code": "Layer",
                "layer_name": "Stack Layer Name",
                "vendor_count": "Covered Vendors",
                "market_cap_b": "Total Market Cap ($B)",
                "ai_revenue_est_b": "Real AI Revenue ($B)",
                "bubble_multiple": "Bubble Multiplier",
                "froth_count": "Froth Count",
                "top_vendors": "Representative Leaders",
            }
            if is_en
            else {
                "layer_code": "代码",
                "layer_name": "产业链层级",
                "vendor_count": "纳管厂商数",
                "market_cap_b": "资本总市值 ($B)",
                "ai_revenue_est_b": "实质AI收入 ($B)",
                "bubble_multiple": "叙事泡沫乘数",
                "froth_count": "熔断数",
                "top_vendors": "代表性头部厂商",
            }
        )
        st.dataframe(
            layers_df[[
                "layer_code", "layer_name", "vendor_count", "market_cap_b",
                "ai_revenue_est_b", "bubble_multiple", "froth_count", "top_vendors",
            ]].rename(columns=rename_map),
            use_container_width=True,
            hide_index=True,
        )

# ── TAB 5: WSJ & NYT Financial Press Wire ─────────────────────────────────────
with tab_press:
    st.subheader(
        tr("📰 华尔街日报与纽约时报金融舆情前沿 (WSJ & NYT Financial Press Wire)", "📰 WSJ & NYT Financial Press Wire & Narrative Velocity")
    )
    if is_en:
        st.markdown(
            """
            > **IDC Automated Financial Press Wire**: Continuously ingests and classifies live intelligence from **The Wall Street Journal** and **The New York Times** across Jensen Huang's 5-layer AI stack.
            > 
            > **Grounding in Institutional Research**:
            > - **US vs. China Equity Valuation Spread**: Reconciling valuation multiples with corporate capital allocation (share buybacks vs. equity dilution) and cost-of-equity hurdles (*Reference: China vs. US Equity Markets*).
            > - **CapEx Bottlenecks & Demand Transmission**: Corroborating hyperscaler data center investments with real-world physical constraints in power generation, cooling, and CoWoS advanced packaging (*Reference: China vs. US Asset Management*).
            """
        )
    else:
        st.markdown(
            """
            > **IDC 金融媒体智库前沿**：实时抓取并解析《华尔街日报》(WSJ) 与《纽约时报》(NYT) 权威报道，深度对齐黄仁勋 AI 产业链五层金字塔。
            > 
            > **学术与机构研报底座支撑**：
            > - **中美估值差与股东回报治理**：印证《China vs. US Equity Markets》研究结论，跟踪美股高估值背后的大规模股份回购与股本注销，对比中股在「新国九条」市值管理驱动下的分红与回购破冰。
            > - **资本开支与物理瓶颈传导**：结合《China vs. US Asset Management》，追踪云厂商 CapEx 动能与电网负荷、CoWoS 封装等硬物理约束的报道。
            """
        )

    # Action bar: sync on-demand & stats
    col_sync, col_stats = st.columns([1, 4])
    with col_sync:
        if st.button(tr("⟳ 抓取与同步媒体舆情", "⟳ Sync Press Wire Now"), key="sync_press_wire_btn"):
            with st.spinner(tr("正在从 WSJ、NYT 及聚合源拉取最新报道并完成分类...", "Fetching & classifying latest articles from WSJ & NYT feeds...")):
                from arf.news.sync import sync_financial_press

                # Write through the webapp's active connection (in GCS mode
                # that is the downloaded temp DB, not data/arf.db) and upload
                # it back so the rows survive the next cold start.
                synced_cnt = sync_financial_press(
                    conn=data.get_conn(), max_items_per_feed=25
                )
                data.persist_db_to_gcs()
                st.success(tr(f"同步完成！新增/更新 {synced_cnt} 篇金融报道。", f"Sync complete! Upserted {synced_cnt} news signals."))
                data.refresh_data()
                st.rerun()

    news_telemetry = data.load_news_stats(days=30)
    with col_stats:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(tr("已索引报道总数", "Total Articles"), f"{news_telemetry.get('total_articles', 0)}")
        c2.metric("WSJ / NYT", f"{news_telemetry.get('wsj_count', 0)} / {news_telemetry.get('nyt_count', 0)}")
        bull_c = news_telemetry.get("bullish_count", 0)
        bear_c = news_telemetry.get("bearish_count", 0)
        c3.metric(tr("多空舆情比 (Bull/Bear)", "Bull/Bear Split"), f"🟢 {bull_c} / 🔴 {bear_c}")
        avg_sent = news_telemetry.get("avg_sentiment", 0.0)
        c4.metric(
            tr("全市场叙事偏向", "Average Polarity"),
            f"{avg_sent:+.2f}",
            help=tr("-1.0 (极度悲观) ~ +1.0 (极度乐观)", "-1.0 (Very Bearish) to +1.0 (Very Bullish)"),
        )

    st.markdown("---")

    # Multi-dimensional Filters
    f_col1, f_col2, f_col3, f_col4 = st.columns([2, 2, 3, 2])
    with f_col1:
        outlet_choice = st.selectbox(
            tr("媒体信源", "News Outlet"),
            ["All", "WSJ", "NYT"],
            key="news_outlet_filter",
        )
    with f_col2:
        layer_opts = ["All", "L1", "L2", "L3", "L4", "L5"]
        layer_choice = st.selectbox(
            tr("产业链层级", "Stack Layer"),
            layer_opts,
            format_func=lambda x: (
                tr("全部层级", "All Layers")
                if x == "All"
                else f"{x}: {_LAYER_ZH.get(x, x) if not is_en else _LAYER_EN.get(x, x)}"
            ),
            key="news_layer_filter",
        )
    with f_col3:
        theme_opts = [
            "All",
            "CapEx_Infrastructure",
            "Export_Controls_Policy",
            "Buybacks_Capital_Allocation",
            "Valuation_Bubble_Froth",
            "Model_Breakthrough",
            "General_AI_Tech",
        ]
        _THEME_NAMES = {
            "All": tr("全部主题", "All Themes"),
            "CapEx_Infrastructure": tr("⚡ 算力基建与电力/封装瓶颈", "⚡ CapEx & Infrastructure"),
            "Export_Controls_Policy": tr("🛡️ 出口管制与国产替代", "🛡️ Export Controls & Policy"),
            "Buybacks_Capital_Allocation": tr("💰 股份回购与资本配置治理", "💰 Buybacks & Capital Allocation"),
            "Valuation_Bubble_Froth": tr("🌡️ 估值泡沫与业绩重估", "🌡️ Valuation & Froth"),
            "Model_Breakthrough": tr("🧠 前沿模型与推理突破", "🧠 Model Breakthrough"),
            "General_AI_Tech": tr("🌐 泛 AI 生态落地", "🌐 General AI Tech"),
        }
        theme_choice = st.selectbox(
            tr("核心研究主题", "Thematic Dimension"),
            theme_opts,
            format_func=lambda x: _THEME_NAMES.get(x, x),
            key="news_theme_filter",
        )
    with f_col4:
        ticker_search = st.text_input(
            tr("标的代码过滤", "Filter by Ticker"),
            placeholder="e.g. NVDA, 688256, BABA",
            key="news_ticker_filter",
        )

    # Query articles
    filtered_articles = data.load_news_signals(
        ticker=ticker_search if ticker_search.strip() else None,
        layer=layer_choice if layer_choice != "All" else None,
        theme=theme_choice if theme_choice != "All" else None,
        source=outlet_choice if outlet_choice != "All" else None,
        days=30,
        min_relevance=0.15,
        limit=60,
    )

    if filtered_articles.empty:
        st.info(tr("当前筛选条件下未检索到符合条件的财经新闻报道。可点击上方按钮抓取最新资讯。", "No articles match the current filter criteria. Click 'Sync Press Wire Now' above to pull recent stories."))
    else:
        st.caption(tr(f"共检索到 {len(filtered_articles)} 篇符合条件的权威报道（点击标题直达官方原文）：", f"Found {len(filtered_articles)} matching reports (click headline to open verified source):"))

        # Render each article in card style
        import json
        for _, art in filtered_articles.iterrows():
            pub_date = art["published_at"].strftime("%Y-%m-%d %H:%M") if hasattr(art["published_at"], "strftime") else str(art["published_at"])[:16]
            source_tag = "🔴 WSJ" if art["source"] == "WSJ" else ("⚫ NYT" if art["source"] == "NYT" else "🌐 Syndication")
            sent_label = art["sentiment_label"]
            sent_badge = f":green[🟢 {sent_label}]" if sent_label == "Bullish" else (f":red[🔴 {sent_label}]" if sent_label == "Bearish" else f":gray[⚪ {sent_label}]")

            # Tickers list
            try:
                t_list = json.loads(art["tickers"]) if isinstance(art["tickers"], str) else (art["tickers"] or [])
            except Exception:
                t_list = []
            t_badges = " ".join([f"`{t}`" for t in t_list[:5]]) if t_list else ""

            # Themes list
            try:
                th_list = json.loads(art["themes"]) if isinstance(art["themes"], str) else (art["themes"] or [])
            except Exception:
                th_list = []
            th_tags = " · ".join([_THEME_NAMES.get(th, th) for th in th_list[:2]])

            with st.container(border=True):
                st.markdown(f"### [{art['title']}]({art['url']})")
                meta_line = f"**{source_tag}** · `{pub_date} UTC` · {sent_badge}"
                if t_badges:
                    meta_line += f" · {tr('标的', 'Tickers')}: {t_badges}"
                if th_tags:
                    meta_line += f" · {tr('主题', 'Themes')}: *{th_tags}*"
                st.markdown(meta_line)
                if art.get("summary"):
                    st.markdown(f"> {art['summary']}")

# ── TAB 6: Analyst Drafting Studio ───────────────────────────────────────────
with tab_studio:
    st.subheader(
        tr("📝 IDC 分析师快报与研报起草台 (Analyst Drafting Studio)", "📝 IDC Analyst Drafting Studio & Research Notes")
    )
    st.caption(
        tr(
            "供 IDC 分析师一键生成官方格式的《IDC 厂商单页调研档案 (Vendor Profile)》或《IDC 全球宏观研究报告 (MarketScape Briefing)》。",
            "Instant 1-click generator for official-format IDC Research Notes: Single-Vendor Profiles and Global MarketScape Briefings.",
        )
    )

    # Point-in-time: a briefing for a historical snapshot must not cite
    # articles published after that snapshot date.
    recent_news_df = data.load_news_signals(days=30, limit=100, as_of=as_of)

    draft_opts = (
        ["🔬 Single-Vendor Deep Dive Profile (IDC Format)", "🌐 Global AI Industry Overview & MarketScape Briefing"]
        if is_en
        else ["🔬 指定厂商深度调研档案 (IDC Vendor Profile)", "🌐 IDC 全球 AI 竞争全景与支出宏观研报 (Global Briefing)"]
    )
    draft_mode = st.radio(
        tr("选择起草类型 (Drafting Template)", "Select Research Template"),
        draft_opts,
        horizontal=True,
    )

    curr_lang = get_current_lang()

    if ("指定厂商" in draft_mode) or ("Single-Vendor" in draft_mode):
        studio_ticker = st.selectbox(
            tr("选择起草标的", "Select Target Vendor"),
            all_tickers,
            index=default_ix,
            key="studio_ticker_select",
        )
        analyst_notes_input = st.text_area(
            tr("✍️ IDC 分析师独家洞察与买方采购指引 (可选自定义批注)", "✍️ IDC Analyst Custom Commentary & Buyer Guidance (Optional)"),
            placeholder=tr(
                "输入您对该厂商的实地调研结论、商业洽谈观察或核心护城河评估...",
                "Enter field notes, commercial buyer observations, or proprietary moat assessments...",
            ),
            height=100,
        )

        vendor_profile_md = generate_analyst_vendor_profile(
            ticker=studio_ticker,
            snap_df=snap_df,
            fc_df=fc_df,
            links_df=links_df,
            analyst_commentary=analyst_notes_input,
            news_df=recent_news_df,
            lang=curr_lang,
        )

        col_d1, col_d2 = st.columns([4, 2])
        with col_d1:
            st.download_button(
                label=tr(f"📥 导出 IDC 厂商档案: {studio_ticker} (Markdown)", f"📥 Download IDC Vendor Profile: {studio_ticker} (Markdown)"),
                data=vendor_profile_md,
                file_name=f"IDC_Vendor_Profile_{studio_ticker}_{as_of.isoformat()}.md",
                mime="text/markdown",
            )
        with st.expander(
            tr(f"🔍 预览 IDC 厂商调研快报: {studio_ticker}", f"🔍 Preview IDC Vendor Profile: {studio_ticker}"),
            expanded=True,
        ):
            st.markdown(vendor_profile_md)
    else:
        briefing_md = generate_idc_executive_briefing(
            as_of,
            snap_df,
            fc_df,
            news_df=recent_news_df,
            lang=curr_lang,
        )
        st.download_button(
            label=tr("📥 导出完整 IDC 行业全景研报 (Markdown)", "📥 Download Full IDC MarketScape Executive Briefing (Markdown)"),
            data=briefing_md,
            file_name=f"IDC_MarketScape_AI_Briefing_{as_of.isoformat()}.md",
            mime="text/markdown",
        )
        with st.expander(
            tr("🔍 预览完整 IDC 行业研报", "🔍 Preview Full IDC MarketScape Briefing"),
            expanded=True,
        ):
            st.markdown(briefing_md)
