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
from webapp.ui import render_sidebar

st.set_page_config(
    page_title="IDC Quanta™ 分析师工作台 — ARF MarketScape™",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded",
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


# ── Analyst Desk Header ──────────────────────────────────────────────────────
st.title("🌐 IDC Quanta™ AI 分析师研报工作台 (Research Desk)")
st.caption(
    "IDC 官方标准 AI 产业链全景智库：集成 IDC MarketScape™ 厂商战略能力双轴评估、全球 AI 产业支出指南 (Worldwide AI Spending Guide)、"
    "供应链 Leontief 瓶颈压力沙盘与 1-Click 分析师快报起草台。"
)

as_of = render_sidebar()
if as_of is None:
    st.stop()

# A partially written snapshot has rows but NULL scores. Never present it as a
# finished analysis (the axes would have to be invented); roll back to the
# newest fully-scored snapshot and say so.
complete_date = data.latest_complete_snapshot_date(as_of)
if complete_date is None:
    st.warning(f"截至 {as_of} 尚无已完成评分的快照，请先运行数据管道评分。")
    st.stop()
if complete_date != as_of:
    st.warning(
        f"{as_of} 的快照尚未完成评分；已自动切换到最近一次完整评分的快照 **{complete_date}**。"
    )
    as_of = complete_date

# ── Load Snapshot, Forecast, and Supply Chain Links ──────────────────────────
snap_df = data.load_snapshot(as_of)
if snap_df.empty:
    st.warning(f"未找到 {as_of} 的快照数据，请在侧边栏选择有效日期。")
    st.stop()

# Forecasts are point-in-time: only rows for this exact date are used. If the
# date has none, generate them from this snapshot and upload the result to GCS
# so the next session does not have to generate (and show N/A) again.
fc_df = pd.DataFrame()
with contextlib.suppress(Exception), st.spinner("加载前瞻预测（缺失时即时生成并写入 GCS）…"):
    fc_df = data.ensure_forecasts(as_of)

links_df = pd.DataFrame()
with contextlib.suppress(Exception):
    links_df = data.load_supply_chain_links()

# Compute IDC intelligence datasets
ms_df = compute_idc_marketscape(snap_df, fc_df)
spending = compute_ai_spending_tracker(snap_df)

if ms_df.empty:
    st.warning("该快照没有可用的评分数据，无法生成 MarketScape 分析。")
    st.stop()

if fc_df.empty:
    st.caption("ℹ️ 该快照日期无前瞻预测数据：Strategies 轴暂以营收增速替代，超预期与修正动能显示为 N/A。")

scored_count = int(ms_df["ticker"].nunique())

# ── Top-Level KPI Ribbon ─────────────────────────────────────────────────────
m_col1, m_col2, m_col3, m_col4 = st.columns(4)
with m_col1:
    st.metric(
        "🏛️ AI 核心纳管市值",
        f"${spending.get('total_universe_mcap_t', 0.0)}T",
        f"{scored_count} 家已评分标的 ({as_of})",
    )
with m_col2:
    st.metric(
        "💰 实质 AI 纯度收入 (年化)",
        f"${spending.get('total_ai_revenue_b', 0.0)}B",
        "经 E-score 纯度加权折算",
    )
with m_col3:
    bubble_mult = spending.get("overall_bubble_multiple", 0.0)
    st.metric(
        "🫧 全局叙事泡沫倍数 (P/S_AI)",
        f"{bubble_mult:.1f}x",
        "资本市值 / 实质 AI 收入",
        delta_color="inverse",
    )
with m_col4:
    froth_total = sum(item["froth_count"] for item in spending.get("layers", []))
    st.metric(
        "🚨 触碰泡沫熔断厂商",
        f"{froth_total} 家",
        "D1泡沫 + 负/低ROE + P/S>25",
        delta_color="inverse",
    )

st.divider()

# ── 5 Core Tabs of the Analyst Research Desk ─────────────────────────────────
tab_marketscape, tab_deepdive, tab_sandbox, tab_spending, tab_studio = st.tabs([
    "🎯 IDC MarketScape™ 厂商竞争矩阵",
    "🔬 厂商深度调研与对标台",
    "🛠️ 供应链需求与瓶颈沙盘",
    "📊 全球 AI 产业支出指南",
    "📝 分析师快报与研报起草台",
])

# ── TAB 1: IDC MarketScape ───────────────────────────────────────────────────
with tab_marketscape:
    st.subheader("🎯 IDC MarketScape: 全球 AI 价值链厂商定位")
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
        leg_filter = st.selectbox(
            "区域价值链筛选",
            ["全部 (Global All)", "美系价值链 (US Leg)", "中系价值链 (China Leg)"],
            index=0,
            key="ms_leg_filter",
        )
    with ctrl_col2:
        layer_filter = st.selectbox(
            "产业链层级筛选",
            [
                "全部层级 (All Layers)",
                "L1 芯片设计与制造 (Foundry & Chips)",
                "L2 核心互联与硬件 (Optical & Hardware)",
                "L3 基础设施与云厂商 (Cloud & Infra)",
                "L4 基础大模型与平台 (Foundational Models)",
                "L5 垂直行业应用 (Enterprise Apps)",
            ],
            index=0,
            key="ms_layer_filter",
        )
    with ctrl_col3:
        search_query = st.text_input(
            "🔍 搜索厂商代码或名称 (如 NVDA, 寒武纪, 300308)",
            value="",
            placeholder="输入 Ticker 或名称...",
            key="ms_search_input",
        )

    # Filter DataFrame
    plot_df = ms_df.copy()
    if leg_filter == "美系价值链 (US Leg)":
        plot_df = plot_df[plot_df["leg"] == "US"]
    elif leg_filter == "中系价值链 (China Leg)":
        plot_df = plot_df[plot_df["leg"] == "China"]

    if layer_filter != "全部层级 (All Layers)":
        layer_code = layer_filter[:2]
        plot_df = plot_df[plot_df["layer"] == layer_code]

    if search_query.strip():
        q = search_query.strip().upper()
        # regex=False: a ticker/name search must not treat "(" as a pattern
        # (str.contains would otherwise raise re.error and kill the page).
        plot_df = plot_df[
            plot_df["ticker"].str.upper().str.contains(q, regex=False)
            | plot_df["name"].str.upper().str.contains(q, regex=False)
        ]

    # Create Plotly MarketScape Quadrant
    if not plot_df.empty:
        fig = go.Figure()

        # Add shaded quadrant backgrounds. The cuts come from the same
        # constants that drive marketscape_category, so the picture can never
        # disagree with the table or the generated reports.
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
            x=97, y=97, text="<b>🏆 LEADERS (领军者)</b>",
            showarrow=False, font=dict(size=14, color="#22c55e"), xanchor="right", yanchor="top"
        )
        fig.add_annotation(
            x=13, y=97, text="<b>🛡️ MAJOR PLAYERS (主要厂商)</b>",
            showarrow=False, font=dict(size=14, color="#3b82f6"), xanchor="left", yanchor="top"
        )
        fig.add_annotation(
            x=97, y=13, text="<b>⚡ CONTENDERS (高增长挑战者)</b>",
            showarrow=False, font=dict(size=14, color="#f97316"), xanchor="right", yanchor="bottom"
        )
        fig.add_annotation(
            x=13, y=13, text="<b>🔍 PARTICIPANTS (利基参与者)</b>",
            showarrow=False, font=dict(size=14, color="#94a3b8"), xanchor="left", yanchor="bottom"
        )

        # Bubble Scatter Points
        sizes = np.clip(np.sqrt(plot_df["market_cap_b"].clip(lower=1.0)) * 2.2, 10.0, 52.0)
        colors = [
            "#38bdf8" if row["leg"] == "US" else "#f43f5e"
            for _, row in plot_df.iterrows()
        ]

        hover_texts = [
            f"<b>{r['name']}</b> ({r['ticker']})<br>"
            f"区域: {r['leg']} | 层级: {r['layer']}<br>"
            f"阵营: <b>{r['marketscape_category']}</b><br>"
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
                text=f"<b>IDC MarketScape: Global AI Vendors Assessment ({as_of})</b>",
                font=dict(size=17, color="#f8fafc"),
            ),
            xaxis=dict(
                title="<b>STRATEGIES (未来战略与增长弹性 ➔)</b>",
                range=[10, 102],
                zeroline=False,
                gridcolor="#334155",
            ),
            yaxis=dict(
                title="<b>CAPABILITIES (当期交付质量与财务壁垒 ➔)</b>",
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
        st.info("筛选条件下暂无厂商数据。")

    # Vendor Detail Table
    st.markdown("#### 📋 厂商全景明细表 (IDC MarketScape Vendor Scorecard)")
    display_cols = [
        "ticker", "name", "leg", "layer", "marketscape_category",
        "capabilities_score", "strategies_score", "market_cap_b",
        "ai_revenue_est_b", "predicted_growth", "arf", "froth_flag",
    ]
    formatted_df = plot_df[display_cols].copy()
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
    st.subheader("🔬 厂商深度调研台与同业对标 (Vendor Deep-Dive)")
    st.caption("供 IDC 分析师针对指定标的展开全景画像穿透：透视财务质量、逆向 DCF 增长预期、客户供应链拓扑与同业对标。")

    all_tickers = sorted(ms_df["ticker"].unique().tolist())
    default_ix = all_tickers.index("NVDA") if "NVDA" in all_tickers else 0

    sel_col1, sel_col2 = st.columns([3, 3])
    with sel_col1:
        chosen_ticker = st.selectbox("🎯 选择主要调研厂商 (Primary Vendor)", all_tickers, index=default_ix)
    with sel_col2:
        peer_options = [t for t in all_tickers if t != chosen_ticker]
        default_peer_ix = peer_options.index("300308.SZ") if "300308.SZ" in peer_options else 0
        peer_ticker = st.selectbox("⚖️ 选择同业对标厂商 (Benchmark Peer)", peer_options, index=default_peer_ix)

    v_primary = ms_df[ms_df["ticker"] == chosen_ticker].iloc[0].to_dict()
    v_peer = ms_df[ms_df["ticker"] == peer_ticker].iloc[0].to_dict()

    # Vendor Profile Header
    cat_badge = (
        "🟢 领军者 (Leader)" if v_primary["marketscape_category"] == "Leaders"
        else "🔵 主要厂商 (Major Player)" if v_primary["marketscape_category"] == "Major Players"
        else "🟠 挑战者 (Contender)" if v_primary["marketscape_category"] == "Contenders"
        else "⚪ 参与者 (Participant)"
    )

    st.markdown(
        f"### 🏢 **{v_primary['name']} ({chosen_ticker})** — {cat_badge} "
        f"`[{v_primary['leg']} / {v_primary['layer']}]`"
    )

    card_c1, card_c2, card_c3, card_c4, card_c5 = st.columns(5)
    with card_c1:
        st.metric("交付质量 (Capabilities)", f"{v_primary['capabilities_score']:.1f} / 100")
    with card_c2:
        st.metric("战略动能 (Strategies)", f"{v_primary['strategies_score']:.1f} / 100")
    with card_c3:
        st.metric("ARF 泡沫估值指数", f"{v_primary['arf']:.1f}", "D1 泡沫阈值 ≥ 90")
    with card_c4:
        st.metric("逆向 DCF 隐含增速", _pct(v_primary.get("implied_growth")), "市场定价所需永续增速")
    with card_c5:
        st.metric(
            "12M 预期超一致差",
            _pct(v_primary.get("expected_beat_pct"), signed=True),
            "ARF模型前瞻弹性",
        )

    # Side-by-Side Peer Comparison Table
    st.markdown("#### ⚖️ 双雄深度指标对标 (Head-to-Head Benchmark)")
    peer_metrics_table = [
        {"指标维度": "IDC MarketScape 阵营", chosen_ticker: v_primary["marketscape_category"], peer_ticker: v_peer["marketscape_category"]},
        {"指标维度": "Capabilities (交付与财务质量)", chosen_ticker: f"{v_primary['capabilities_score']:.1f}", peer_ticker: f"{v_peer['capabilities_score']:.1f}"},
        {"指标维度": "Strategies (未来战略与增速)", chosen_ticker: f"{v_primary['strategies_score']:.1f}", peer_ticker: f"{v_peer['strategies_score']:.1f}"},
        {"指标维度": "资本总市值 (USD)", chosen_ticker: f"${v_primary['market_cap_b']:.1f}B", peer_ticker: f"${v_peer['market_cap_b']:.1f}B"},
        {"指标维度": "实质 AI 年化收入估算", chosen_ticker: _usd_b(v_primary.get("ai_revenue_est_b"), 2), peer_ticker: _usd_b(v_peer.get("ai_revenue_est_b"), 2)},
        {"指标维度": "AI 暴露纯度 (E_score)", chosen_ticker: f"{v_primary.get('e_score', 0):.0f}", peer_ticker: f"{v_peer.get('e_score', 0):.0f}"},
        {"指标维度": "估值张力指数 (V_score)", chosen_ticker: f"{v_primary.get('v_score', 0):.0f}", peer_ticker: f"{v_peer.get('v_score', 0):.0f}"},
        {"指标维度": "ROE 净资产收益率", chosen_ticker: _pct(v_primary.get("roe")), peer_ticker: _pct(v_peer.get("roe"))},
        {"指标维度": "市销率 (P/S Ratio)", chosen_ticker: f"{_num(v_primary.get('ps_ratio'))}x", peer_ticker: f"{_num(v_peer.get('ps_ratio'))}x"},
        {"指标维度": "前瞻 12M 预测增速 (ARF ĝ)", chosen_ticker: _pct(v_primary.get("predicted_growth"), signed=True), peer_ticker: _pct(v_peer.get("predicted_growth"), signed=True)},
        {"指标维度": "泡沫熔断状态 (Froth Circuit)", chosen_ticker: "🔴 触碰熔断" if v_primary['froth_flag'] else "🟢 正常", peer_ticker: "🔴 触碰熔断" if v_peer['froth_flag'] else "🟢 正常"},
    ]
    st.dataframe(pd.DataFrame(peer_metrics_table), use_container_width=True, hide_index=True)

    # Supply Chain Customer & Supplier Network
    st.markdown("#### 🔗 产业链上下游传导拓扑 (Supply Chain Topology)")
    topo_c1, topo_c2 = st.columns(2)
    with topo_c1:
        st.markdown(f"**下游核心客户 (Direct Customers of {chosen_ticker}):**")
        if not links_df.empty:
            cust_sub = links_df[links_df["supplier_ticker"].astype(str).str.upper() == chosen_ticker]
            if not cust_sub.empty:
                st.dataframe(
                    cust_sub[["customer_ticker", "revenue_share_pct", "relationship_type", "verified_source"]].rename(
                        columns={
                            "customer_ticker": "客户代码",
                            "revenue_share_pct": "营收占比贡献 (%)",
                            "relationship_type": "供应链关系",
                            "verified_source": "披露来源",
                        }
                    ),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("该标的未在数据库中申报下游直连客户，或处于应用消费终端。")
        else:
            st.info("供应链拓扑数据库就绪中。")

    with topo_c2:
        st.markdown(f"**上游核心供应商 (Key Suppliers to {chosen_ticker}):**")
        if not links_df.empty:
            supp_sub = links_df[links_df["customer_ticker"].astype(str).str.upper() == chosen_ticker]
            if not supp_sub.empty:
                st.dataframe(
                    supp_sub[["supplier_ticker", "bom_component_pct", "relationship_type", "verified_source"]].rename(
                        columns={
                            "supplier_ticker": "供应商代码",
                            "bom_component_pct": "BOM成本占比 (%)",
                            "relationship_type": "供应元器件",
                            "verified_source": "披露来源",
                        }
                    ),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("该标的未在数据库中申报上游依赖，或处于全栈垂直整合。")
        else:
            st.info("供应链拓扑数据库就绪中。")

# ── TAB 3: CapEx & Leontief Scenario Sandbox ─────────────────────────────────
with tab_sandbox:
    st.subheader("🛠️ 供应链需求拉动与物理瓶颈测算沙盘 (Analyst Scenario Sandbox)")
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
            "☁️ 云巨头 (MSFT/GOOGL/META) CapEx 变动假设",
            min_value=-30,
            max_value=60,
            value=15,
            step=5,
            format="%+d%%",
            help="调整云厂商年度算力资本支出假设",
            key="idk_capex_slider",
        )
    with sb_c2:
        clamp_input = st.slider(
            "🏭 物理产能瓶颈夹钳 (CoWoS / 电网扩容上限)",
            min_value=20,
            max_value=120,
            value=80,
            step=10,
            format="%d%%",
            help="Leontief 瓶颈夹钳：上限硬性截断名义拉动，防止虚假高增长",
            key="idk_clamp_slider",
        )
    with sb_c3:
        status_lbl = "正向强拉动" if capex_input >= 20 else ("温和扩张" if capex_input > 0 else "缩减承压")
        st.metric("📡 传导情景模拟状态", status_lbl, f"CapEx {capex_input:+d}% / 产能截断 {clamp_input}%")

    try:
        from arf.agent.cio_loop import simulate_supply_chain_shock

        # Same helper as the CIO cockpit, so one CapEx input yields one answer.
        sim_shocks = capex_to_customer_shocks(fc_df, capex_input)

        sim_df = simulate_supply_chain_shock(
            conn=data.get_conn(),
            as_of=as_of,
            customer_shocks=sim_shocks,
            bottleneck_clamp=clamp_input / 100.0,
            # Pass the frames already in memory. Leaving them None makes the
            # simulator re-query and, when a date has no forecasts, generate
            # and persist them — a DB write caused by merely viewing the tab.
            snap_df=snap_df,
            fc_df=fc_df,
            links_df=links_df,
        )

        if not sim_df.empty:
            st.markdown("#### ⚡ 供应链核心受冲击节点敏感性模拟 (Top 8 Impacted Nodes)")
            st.dataframe(
                sim_df.head(8)[[
                    "ticker", "name", "leg", "layer", "base_pred_growth",
                    "shocked_pred_growth", "growth_delta", "expected_beat_pct", "fair_value_p50",
                ]].rename(columns={
                    "ticker": "标的代码",
                    "name": "公司名称",
                    "leg": "区域",
                    "layer": "层级",
                    "base_pred_growth": "基准预测增速",
                    "shocked_pred_growth": "冲击后增速",
                    "growth_delta": "需求弹性增量 (Δ)",
                    "expected_beat_pct": "超预期差",
                    "fair_value_p50": "P50 公允价值 ($)",
                }),
                use_container_width=True,
                hide_index=True,
            )
    except Exception as exc:
        st.info(f"情景模拟沙盘运算提示: {exc}")

# ── TAB 4: Worldwide AI Spending Guide ────────────────────────────────────────
with tab_spending:
    st.subheader("📊 全球 AI 产业支出与泡沫乘数分布 (Worldwide AI Spending Guide)")
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
                    name="资本市值 ($B USD)",
                    marker_color="#38bdf8",
                )
            )
            fig_bar.add_trace(
                go.Bar(
                    x=layers_df["layer_code"],
                    y=layers_df["ai_revenue_est_b"],
                    name="实质 AI 纯度收入 ($B USD)",
                    marker_color="#22c55e",
                )
            )
            fig_bar.update_layout(
                title="<b>各层级总市值 vs 实质年化 AI 收入 ($B USD)</b>",
                barmode="group",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                height=380,
                xaxis=dict(gridcolor="#334155"),
                yaxis=dict(gridcolor="#334155", title="亿美元 ($B)"),
            )
            show_plotly(fig_bar)

        with col_chart2:
            fig_mult = px.bar(
                layers_df,
                x="layer_code",
                y="bubble_multiple",
                color="bubble_multiple",
                color_continuous_scale="Reds",
                title="<b>各层级叙事泡沫乘数 (Market Cap / AI Revenue)</b>",
                text="bubble_multiple",
            )
            fig_mult.update_traces(texttemplate="%{text:.1f}x", textposition="outside")
            fig_mult.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=380,
                xaxis=dict(title="产业链层级", gridcolor="#334155"),
                yaxis=dict(title="泡沫乘数 (倍)", gridcolor="#334155"),
                showlegend=False,
            )
            show_plotly(fig_mult)

        st.markdown("#### 📑 5 层价值链支出与估值透视表")
        st.dataframe(
            layers_df[[
                "layer_code", "layer_name", "vendor_count", "market_cap_b",
                "ai_revenue_est_b", "bubble_multiple", "froth_count", "top_vendors",
            ]].rename(columns={
                "layer_code": "代码",
                "layer_name": "产业链层级",
                "vendor_count": "纳管厂商数",
                "market_cap_b": "资本总市值 ($B)",
                "ai_revenue_est_b": "实质AI收入 ($B)",
                "bubble_multiple": "叙事泡沫乘数",
                "froth_count": "熔断数",
                "top_vendors": "代表性头部厂商",
            }),
            use_container_width=True,
            hide_index=True,
        )

# ── TAB 5: Analyst Drafting Studio ───────────────────────────────────────────
with tab_studio:
    st.subheader("📝 IDC 分析师快报与研报起草台 (Analyst Drafting Studio)")
    st.caption("供 IDC 分析师一键生成官方格式的《IDC 厂商单页调研档案 (Vendor Profile)》或《IDC 全球宏观研究报告 (MarketScape Briefing)》。")

    draft_mode = st.radio(
        "选择起草类型 (Drafting Template)",
        ["🔬 指定厂商深度调研档案 (IDC Vendor Profile)", "🌐 IDC 全球 AI 竞争全景与支出宏观研报 (Global Briefing)"],
        horizontal=True,
    )

    if "指定厂商" in draft_mode:
        studio_ticker = st.selectbox("选择起草标的", all_tickers, index=default_ix, key="studio_ticker_select")
        analyst_notes_input = st.text_area(
            "✍️ IDC 分析师独家洞察与买方采购指引 (可选自定义批注)",
            placeholder="输入您对该厂商的实地调研结论、商业洽谈观察或核心护城河评估...",
            height=100,
        )

        vendor_profile_md = generate_analyst_vendor_profile(
            ticker=studio_ticker,
            snap_df=snap_df,
            fc_df=fc_df,
            links_df=links_df,
            analyst_commentary=analyst_notes_input,
        )

        col_d1, col_d2 = st.columns([4, 2])
        with col_d1:
            st.download_button(
                label=f"📥 导出 IDC 厂商档案: {studio_ticker} (Markdown)",
                data=vendor_profile_md,
                file_name=f"IDC_Vendor_Profile_{studio_ticker}_{as_of.isoformat()}.md",
                mime="text/markdown",
            )
        with st.expander(f"🔍 预览 IDC 厂商调研快报: {studio_ticker}", expanded=True):
            st.markdown(vendor_profile_md)
    else:
        briefing_md = generate_idc_executive_briefing(as_of, snap_df, fc_df)
        st.download_button(
            label="📥 导出完整 IDC 行业全景研报 (Markdown)",
            data=briefing_md,
            file_name=f"IDC_MarketScape_AI_Briefing_{as_of.isoformat()}.md",
            mime="text/markdown",
        )
        with st.expander("🔍 预览完整 IDC 行业研报", expanded=True):
            st.markdown(briefing_md)
