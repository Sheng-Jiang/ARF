"""Streamlit page: Autonomous AI Investment Opportunity Radar."""
from __future__ import annotations

import logging

import pandas as pd
import streamlit as st

from arf.agent.radar import discover_supply_chain_candidates, scan_valuation_anomalies
from arf.agent.thesis import generate_opportunity_card
from arf.db import init_db, query_candidates, query_theses
from webapp import data, gemini
from webapp.mobile import inject_mobile_css
from webapp.ui import render_sidebar

log = logging.getLogger(__name__)

st.set_page_config(
    page_title="ARF — AI 投资雷达",
    page_icon="🤖",
    layout="wide",
)
inject_mobile_css()

st.title("🤖 AI 投资机会与产业链雷达")
st.caption(
    "由 Gemini 3.7/3.8 Flash 驱动的自主投研 Agent：全天候扫描跨板块估值异动，主动探寻全球 AI 供应链未覆盖标的，生成结构化 Opportunity Card。"
)

as_of = render_sidebar()
if as_of is None:
    st.info("👈 请在左侧边栏选择快照日期。")
    st.stop()

db_path = data.get_db_path()

tab_radar, tab_discovery, tab_theses = st.tabs([
    "🎯 主动机会雷达 (Anomaly Scanner)",
    "🌐 全网产业链探针 (Open-World Discovery)",
    "📑 机会卡与研究池 (Opportunity Cards)",
])

# ── TAB 1: 主动机会雷达 ───────────────────────────────────────────────────────
with tab_radar:
    st.subheader(f"📊 快照 {as_of} 跨维度量化异动扫描")
    st.markdown(
        "Agent 自动扫描核心股票池，根据 **ARF 估值拉伸**、**AI 业务敞口**、**ROE 资本回报** 与 **CYQ 筹码微观结构**，自动聚类出三大异动池："
    )

    try:
        anomalies = scan_valuation_anomalies(as_of=as_of, db_path=db_path)
        garp_list = anomalies.get("garp_opportunities", [])
        breakouts = anomalies.get("technical_breakouts", [])
        froth_list = anomalies.get("froth_warnings", [])

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("💎 GARP 黄金标的", f"{len(garp_list)} 只", help="高 AI 敞口 + 优质 ROE + 估值合理未泡沫化 (D4-D7)")
        with col2:
            st.metric("🚀 筹码技术突破", f"{len(breakouts)} 只", help="均线多头 + 获利盘 > 70% + 技术强动量")
        with col3:
            st.metric("⚠️ 泡沫与高估值预警", f"{len(froth_list)} 只", help="D1 极度拉伸或 Froth Flag 触发")

        st.divider()

        # Section 1: GARP
        st.markdown("### 💎 1. GARP 优选机会 (Growth At a Reasonable Price)")
        st.caption("特征：AI 曝光度 (E分) ≥ 55，ROE ≥ 18%，且估值偏离度 (V分) ≤ 60，处于 D3–D7 安全区间。")
        if garp_list:
            garp_df = pd.DataFrame(garp_list)
            # Format display
            disp_cols = ["ticker", "name", "leg", "layer", "arf", "decile", "roe", "forward_pe", "ps_ratio", "chip_profit_ratio"]
            available_cols = [c for c in disp_cols if c in garp_df.columns]
            st.dataframe(garp_df[available_cols], use_container_width=True, hide_index=True)
        else:
            st.info("当前快照日期暂无符合 GARP 严格阈值的股票。")

        # Section 2: Technical & Chip Breakouts
        st.markdown("### 🚀 2. 筹码与技术面共振突破")
        st.caption("特征：均线多头排列，筹码获利盘 ≥ 70%，且综合技术评分 ≥ 65。")
        if breakouts:
            bk_df = pd.DataFrame(breakouts)
            disp_cols = ["ticker", "name", "leg", "layer", "arf", "technical_score", "chip_profit_ratio", "chip_avg_cost", "rsi"]
            available_cols = [c for c in disp_cols if c in bk_df.columns]
            st.dataframe(bk_df[available_cols], use_container_width=True, hide_index=True)
        else:
            st.info("当前快照日期暂无均线多头且获利盘 > 70% 的股票。")

        # Section 3: Froth Warnings
        st.markdown("### ⚠️ 3. 泡沫风险与估值过热预警")
        st.caption("特征：触发 Froth Flag 或处于 D1 估值极度透支且资本回报率低 (ROE < 10%)。")
        if froth_list:
            froth_df = pd.DataFrame(froth_list)
            disp_cols = ["ticker", "name", "leg", "layer", "arf", "v_score", "ps_ratio", "roe", "chip_profit_ratio"]
            available_cols = [c for c in disp_cols if c in froth_df.columns]
            st.dataframe(froth_df[available_cols], use_container_width=True, hide_index=True)
        else:
            st.success("当前快照日期未检测到显著的泡沫警报。")

        st.divider()

        # Deep Dive Agent Trigger
        st.subheader("⚡ 触发 Agent 深度研究研判")
        c_pick, c_btn = st.columns([3, 1])
        all_screened = list(dict.fromkeys(
            [r["ticker"] for r in garp_list] + [r["ticker"] for r in breakouts] + [r["ticker"] for r in froth_list]
        ))
        if not all_screened:
            all_screened = ["NVDA", "PLTR", "300308.SZ", "688256.SH"]

        with c_pick:
            target_ticker = st.selectbox("选择目标标的生成 Opportunity Card：", options=all_screened)
        with c_btn:
            st.write("")
            st.write("")
            trigger_thesis = st.button("🚀 生成 Opportunity Card", disabled=not gemini.is_enabled(), use_container_width=True)

        if trigger_thesis and target_ticker:
            with st.spinner("Agent 正在结合 Gemini 3.7/3.8 Flash 进行 Bull vs Bear 研判并检索全球最新动态..."):
                try:
                    card = generate_opportunity_card(
                        ticker=target_ticker,
                        as_of=as_of,
                        db_path=db_path,
                        persist=True,
                    )
                    st.success(f"✅ 已成功为 **{target_ticker}** 生成并存入 Opportunity Card！请前往第 3 个 Tab 查看完整研报。")
                except Exception as e:
                    st.error(f"研报生成失败: {e}")

    except Exception as e:
        log.exception("Error in anomaly scan")
        st.error(f"雷达异动扫描失败: {e}")

# ── TAB 2: 全网产业链探针 ───────────────────────────────────────────────────
with tab_discovery:
    st.subheader("🌐 全网 AI 产业链未覆盖标的探针 (Open-World Discovery)")
    st.markdown("""
    当前 ARF 核心评级池涵盖 73 只标的。你可通过输入任何 AI 供应链瓶颈或细分领域，由 **Agent 联网检索、穿透多层供应链**，发掘未覆盖标的并暂存至 `candidate_pool`。
    """)

    theme_input = st.text_input(
        "🔎 请输入想要探索的供应链主题或瓶颈技术：",
        value="AI数据中心液冷冷板与CDU分配单元供应商 (中美核心上市标的)",
        help="例如：800G/1.6T硅光光引擎与DSP芯片供应商，或核电SMR与高压直流电力设备",
    )

    c_disc, _ = st.columns([1, 4])
    with c_disc:
        run_discovery = st.button("🚀 启动供应链探针", disabled=not gemini.is_enabled(), use_container_width=True)

    if run_discovery and theme_input:
        with st.spinner("Agent 正在调用 Google Search 遍历产业上下游供应商与客户名录..."):
            try:
                candidates = discover_supply_chain_candidates(
                    theme=theme_input,
                    db_path=db_path,
                    stage_to_db=True,
                )
                st.success(f"🎯 成功识别并暂存 {len(candidates)} 只产业链标的！")
                c_data = [
                    {
                        "代码": c.ticker,
                        "公司名称": c.name,
                        "板块": c.leg,
                        "层级": c.layer,
                        "AI纯度预估": f"{c.pure_play_est}%" if c.pure_play_est else "—",
                        "核心角色与产品": c.supply_role,
                        "关键客户": ", ".join(c.key_customers),
                        "研究简注": c.notes,
                    }
                    for c in candidates
                ]
                st.dataframe(pd.DataFrame(c_data), use_container_width=True, hide_index=True)
            except Exception as e:
                st.error(f"探针检索失败: {e}")

    st.divider()
    st.subheader("📋 候选储备池 (Candidate Pool)")
    conn = init_db(db_path)
    cand_df = query_candidates(conn)
    conn.close()

    if not cand_df.empty:
        st.dataframe(cand_df, use_container_width=True, hide_index=True)
    else:
        st.info("当前候选储备池为空。可在上方输入主题启动探针。")

# ── TAB 3: 机会卡与研究池 ───────────────────────────────────────────────────
with tab_theses:
    st.subheader("📑 活跃 Opportunity Cards 库")
    st.caption("展示由 Agent 多维度推演生成的投资机会卡，包含定量画像、Bull/Bear 对决与失效准则。")

    conn = init_db(db_path)
    theses_df = query_theses(conn, limit=20)
    conn.close()

    if theses_df.empty:
        st.info("暂未生成 Opportunity Card。可在 Tab 1 中选择股票点击生成。")
    else:
        for _, row in theses_df.iterrows():
            t_type = row.get("thesis_type", "neutral_watch")
            tag_color = {
                "long_opportunity": "🟢 战略做多",
                "garp_value": "💎 GARP 优选",
                "froth_short": "🔴 泡沫预警 / 避险",
                "neutral_watch": "🟡 观望追踪",
            }.get(t_type, t_type)

            with st.expander(f"{tag_color} | **{row['ticker']}** — {row['title']} (信心分: {row.get('confidence_score', 50):.1f}分)", expanded=False):
                st.markdown(f"**快照日期**：`{row['as_of_date']}` | **生成模型**：`{row.get('model', 'gemini-3.7-flash')}`")
                
                col_bull, col_bear = st.columns(2)
                with col_bull:
                    st.markdown("#### 🐂 Bull Case (多头驱动)")
                    st.info(row.get("bull_case") or "暂无多头阐述")
                with col_bear:
                    st.markdown("#### 🐻 Bear Case (红队风险)")
                    st.warning(row.get("bear_case") or "暂无空头阐述")

                st.markdown("#### ⚖️ 综合多因子研判 (Synthesis)")
                st.write(row.get("synthesis") or "")

                col_entry, col_inv = st.columns(2)
                with col_entry:
                    st.markdown("🎯 **建议估值介入区间**")
                    st.code(row.get("valuation_entry_zone") or "暂无", language="text")
                with col_inv:
                    st.markdown("🚫 **逻辑证伪与失效触发条件 (Invalidation)**")
                    st.code(row.get("invalidation_criteria") or "暂无", language="text")

                catalysts = row.get("catalysts_json")
                if catalysts:
                    st.markdown("⏳ **关键催化剂与时间表**")
                    if isinstance(catalysts, str):
                        try:
                            import json
                            catalysts = json.loads(catalysts)
                        except Exception:
                            pass
                    if isinstance(catalysts, list):
                        for cat in catalysts:
                            st.markdown(f"- {cat}")
                    else:
                        st.write(catalysts)
