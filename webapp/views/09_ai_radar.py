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
from webapp.ui import get_current_lang, render_sidebar, tr

log = logging.getLogger(__name__)

is_en = get_current_lang() == "en"

_RADAR_COL_LABELS = {
    "ticker": tr("代码", "Ticker"),
    "name": tr("公司名称", "Company"),
    "leg": tr("板块", "Leg"),
    "layer": tr("层级", "Layer"),
    "arf": tr("ARF 评分", "ARF"),
    "decile": tr("ARF 十分位", "Decile"),
    "roe": "ROE",
    "forward_pe": tr("预期 P/E", "Fwd P/E"),
    "ps_ratio": tr("P/S 比例", "P/S"),
    "chip_profit_ratio": tr("筹码获利比例", "Chip Profit Ratio"),
    "technical_score": tr("技术评分", "Technical Score"),
    "chip_avg_cost": tr("平均持仓成本", "Avg Chip Cost"),
    "rsi": "RSI (14)",
    "v_score": tr("V分 (估值偏离)", "V-Score"),
}

inject_mobile_css()

st.title(tr("🤖 AI 投资机会与产业链雷达", "🤖 AI Opportunity & Supply-Chain Radar"))
st.caption(
    tr(
        "由 Gemini Flash 驱动的自主投研 Agent：全天候扫描跨板块估值异动，主动探寻全球 AI 供应链未覆盖标的，生成结构化 Opportunity Card。",
        "An autonomous research agent powered by Gemini Flash: continuously scans cross-leg valuation anomalies, "
        "proactively hunts uncovered targets across the global AI supply chain, and generates structured Opportunity Cards.",
    )
)

as_of = render_sidebar()
if as_of is None:
    st.info(tr("👈 请在左侧边栏选择快照日期。", "👈 Select a snapshot date in the left sidebar."))
    st.stop()

db_path = data.get_db_path()

tab_radar, tab_discovery, tab_theses = st.tabs([
    tr("🎯 主动机会雷达 (Anomaly Scanner)", "🎯 Opportunity Radar (Anomaly Scanner)"),
    tr("🌐 全网产业链探针 (Open-World Discovery)", "🌐 Open-World Supply-Chain Discovery"),
    tr("📑 机会卡与研究池 (Opportunity Cards)", "📑 Opportunity Cards & Research Pool"),
])

# ── TAB 1: 主动机会雷达 ───────────────────────────────────────────────────────
with tab_radar:
    st.subheader(tr(f"📊 快照 {as_of} 跨维度量化异动扫描", f"📊 Cross-Dimensional Anomaly Scan — Snapshot {as_of}"))
    st.markdown(tr(
        "Agent 自动扫描核心股票池，根据 **ARF 估值拉伸**、**AI 业务敞口**、**ROE 资本回报** 与 **CYQ 筹码微观结构**，自动聚类出三大异动池：",
        "The agent automatically scans the core universe and clusters it into three anomaly pools based on "
        "**ARF valuation stretch**, **AI business exposure**, **ROE capital returns** and **CYQ chip microstructure**:",
    ))

    try:
        anomalies = scan_valuation_anomalies(as_of=as_of, db_path=db_path)
        garp_list = anomalies.get("garp_opportunities", [])
        breakouts = anomalies.get("technical_breakouts", [])
        froth_list = anomalies.get("froth_warnings", [])

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(
                tr("💎 GARP 黄金标的", "💎 GARP Golden Picks"),
                tr(f"{len(garp_list)} 只", f"{len(garp_list)} tickers"),
                help=tr(
                    "高 AI 敞口 + 优质 ROE + 估值合理未泡沫化 (D4-D7)",
                    "High AI exposure + quality ROE + reasonable, non-bubbly valuation (D4-D7)",
                ),
            )
        with col2:
            st.metric(
                tr("🚀 筹码技术突破", "🚀 Technical Breakouts"),
                tr(f"{len(breakouts)} 只", f"{len(breakouts)} tickers"),
                help=tr(
                    "均线多头 + 获利盘 > 70% + 技术强动量",
                    "Bullish moving averages + profit ratio > 70% + strong technical momentum",
                ),
            )
        with col3:
            st.metric(
                tr("⚠️ 泡沫与高估值预警", "⚠️ Froth & Overvaluation Warnings"),
                tr(f"{len(froth_list)} 只", f"{len(froth_list)} tickers"),
                help=tr(
                    "D1 极度拉伸或 Froth Flag 触发",
                    "Extreme D1 stretch or Froth Flag triggered",
                ),
            )

        st.divider()

        # Section 1: GARP
        st.markdown(tr("### 💎 1. GARP 优选机会 (Growth At a Reasonable Price)", "### 💎 1. GARP Opportunities (Growth At a Reasonable Price)"))
        st.caption(tr(
            "特征：AI 曝光度 (E分) ≥ 55，ROE ≥ 18%，且估值偏离度 (V分) ≤ 60，处于 D3–D7 安全区间。",
            "Criteria: AI exposure (E-score) ≥ 55, ROE ≥ 18%, and valuation stretch (V-score) ≤ 60, within the safe D3–D7 band.",
        ))
        if garp_list:
            garp_df = pd.DataFrame(garp_list)
            # Format display
            disp_cols = ["ticker", "name", "leg", "layer", "arf", "decile", "roe", "forward_pe", "ps_ratio", "chip_profit_ratio"]
            available_cols = [c for c in disp_cols if c in garp_df.columns]
            st.dataframe(garp_df[available_cols].rename(columns=_RADAR_COL_LABELS), use_container_width=True, hide_index=True)
        else:
            st.info(tr("当前快照日期暂无符合 GARP 严格阈值的股票。", "No stocks meet the strict GARP thresholds in this snapshot."))

        # Section 2: Technical & Chip Breakouts
        st.markdown(tr("### 🚀 2. 筹码与技术面共振突破", "### 🚀 2. Chip & Technical Breakout Confluence"))
        st.caption(tr(
            "特征：均线多头排列，筹码获利盘 ≥ 70%，且综合技术评分 ≥ 65。",
            "Criteria: bullish moving-average alignment, chip profit ratio ≥ 70%, and overall technical score ≥ 65.",
        ))
        if breakouts:
            bk_df = pd.DataFrame(breakouts)
            disp_cols = ["ticker", "name", "leg", "layer", "arf", "technical_score", "chip_profit_ratio", "chip_avg_cost", "rsi"]
            available_cols = [c for c in disp_cols if c in bk_df.columns]
            st.dataframe(bk_df[available_cols].rename(columns=_RADAR_COL_LABELS), use_container_width=True, hide_index=True)
        else:
            st.info(tr("当前快照日期暂无均线多头且获利盘 > 70% 的股票。", "No stocks with bullish moving averages and profit ratio > 70% in this snapshot."))

        # Section 3: Froth Warnings
        st.markdown(tr("### ⚠️ 3. 泡沫风险与估值过热预警", "### ⚠️ 3. Froth Risk & Overvaluation Warnings"))
        st.caption(tr(
            "特征：触发 Froth Flag 或处于 D1 估值极度透支且资本回报率低 (ROE < 10%)。",
            "Criteria: Froth Flag triggered, or extreme D1 valuation stretch with low capital returns (ROE < 10%).",
        ))
        if froth_list:
            froth_df = pd.DataFrame(froth_list)
            disp_cols = ["ticker", "name", "leg", "layer", "arf", "v_score", "ps_ratio", "roe", "chip_profit_ratio"]
            available_cols = [c for c in disp_cols if c in froth_df.columns]
            st.dataframe(froth_df[available_cols].rename(columns=_RADAR_COL_LABELS), use_container_width=True, hide_index=True)
        else:
            st.success(tr("当前快照日期未检测到显著的泡沫警报。", "No significant froth warnings detected in this snapshot."))

        st.divider()

        # Deep Dive Agent Trigger
        st.subheader(tr("⚡ 触发 Agent 深度研究研判", "⚡ Trigger In-Depth Agent Research"))
        c_pick, c_btn = st.columns([3, 1])
        all_screened = list(dict.fromkeys(
            [r["ticker"] for r in garp_list] + [r["ticker"] for r in breakouts] + [r["ticker"] for r in froth_list]
        ))
        if not all_screened:
            all_screened = ["NVDA", "PLTR", "300308.SZ", "688256.SH"]

        with c_pick:
            target_ticker = st.selectbox(
                tr("选择目标标的生成 Opportunity Card：", "Select a target ticker to generate an Opportunity Card:"),
                options=all_screened,
            )
        with c_btn:
            st.write("")
            st.write("")
            trigger_thesis = st.button(tr("🚀 生成 Opportunity Card", "🚀 Generate Opportunity Card"), disabled=not gemini.is_enabled(), use_container_width=True)

        if trigger_thesis and target_ticker:
            with st.spinner(tr("Agent 正在结合 Gemini Flash 进行 Bull vs Bear 研判并检索全球最新动态...", "Agent is running Bull vs Bear analysis with Gemini Flash and searching the latest global developments...")):
                try:
                    card = generate_opportunity_card(
                        ticker=target_ticker,
                        as_of=as_of,
                        db_path=db_path,
                        persist=True,
                    )
                    st.success(
                        tr(
                            f"✅ 已成功为 **{target_ticker}** 生成并存入 Opportunity Card！请前往第 3 个 Tab 查看完整研报。",
                            f"✅ Successfully generated and saved an Opportunity Card for **{target_ticker}**! See the 3rd tab for the full report.",
                        )
                    )
                except Exception as e:
                    st.error(tr(f"研报生成失败: {e}", f"Report generation failed: {e}"))

    except Exception as e:
        log.exception("Error in anomaly scan")
        st.error(tr(f"雷达异动扫描失败: {e}", f"Radar anomaly scan failed: {e}"))

# ── TAB 2: 全网产业链探针 ───────────────────────────────────────────────────
with tab_discovery:
    st.subheader(tr("🌐 全网 AI 产业链未覆盖标的探针 (Open-World Discovery)", "🌐 Open-World Discovery of Uncovered AI Supply-Chain Targets"))
    st.markdown(tr("""
    当前 ARF 核心评级池涵盖 73 只标的。你可通过输入任何 AI 供应链瓶颈或细分领域，由 **Agent 联网检索、穿透多层供应链**，发掘未覆盖标的并暂存至 `candidate_pool`。
    """, """
    The current ARF core rating pool covers 73 tickers. Enter any AI supply-chain bottleneck or niche, and the **agent will search the web and traverse multiple supply-chain layers** to uncover unlisted targets, staging them in `candidate_pool`.
    """))

    theme_input = st.text_input(
        tr("🔎 请输入想要探索的供应链主题或瓶颈技术：", "🔎 Enter a supply-chain theme or bottleneck technology to explore:"),
        value=tr(
            "AI数据中心液冷冷板与CDU分配单元供应商 (中美核心上市标的)",
            "AI data-center liquid-cooling cold plate and CDU distribution unit suppliers (core listed names in the US and China)",
        ),
        help=tr(
            "例如：800G/1.6T硅光光引擎与DSP芯片供应商，或核电SMR与高压直流电力设备",
            "e.g., 800G/1.6T silicon-photonics optical engine and DSP chip suppliers, or nuclear SMR and HVDC power equipment",
        ),
    )

    c_disc, _ = st.columns([1, 4])
    with c_disc:
        run_discovery = st.button(tr("🚀 启动供应链探针", "🚀 Launch Supply-Chain Discovery"), disabled=not gemini.is_enabled(), use_container_width=True)

    if run_discovery and theme_input:
        with st.spinner(tr("Agent 正在调用 Google Search 遍历产业上下游供应商与客户名录...", "Agent is using Google Search to traverse upstream/downstream supplier and customer lists...")):
            try:
                candidates = discover_supply_chain_candidates(
                    theme=theme_input,
                    db_path=db_path,
                    stage_to_db=True,
                )
                st.success(tr(f"🎯 成功识别并暂存 {len(candidates)} 只产业链标的！", f"🎯 Identified and staged {len(candidates)} supply-chain tickers!"))
                c_data = [
                    {
                        tr("代码", "Ticker"): c.ticker,
                        tr("公司名称", "Company"): c.name,
                        tr("板块", "Leg"): c.leg,
                        tr("层级", "Layer"): c.layer,
                        tr("AI纯度预估", "Est. AI Pure-Play %"): f"{c.pure_play_est}%" if c.pure_play_est else "—",
                        tr("核心角色与产品", "Core Role & Products"): c.supply_role,
                        tr("关键客户", "Key Customers"): ", ".join(c.key_customers),
                        tr("研究简注", "Research Notes"): c.notes,
                    }
                    for c in candidates
                ]
                st.dataframe(pd.DataFrame(c_data), use_container_width=True, hide_index=True)
            except Exception as e:
                st.error(tr(f"探针检索失败: {e}", f"Discovery search failed: {e}"))

    st.divider()
    st.subheader(tr("📋 候选储备池 (Candidate Pool)", "📋 Candidate Pool"))
    conn = init_db(db_path)
    cand_df = query_candidates(conn)
    conn.close()

    if not cand_df.empty:
        cand_labels = {
            "ticker": tr("代码", "Ticker"),
            "name": tr("公司名称", "Company"),
            "leg": tr("板块", "Leg"),
            "layer": tr("层级", "Layer"),
            "source": tr("来源", "Source"),
            "discovered_at": tr("发现日期", "Discovered"),
            "status": tr("状态", "Status"),
            "pure_play_est": tr("AI纯度预估", "Est. AI Pure-Play %"),
            "supply_role": tr("核心角色与产品", "Core Role & Products"),
            "key_customers_json": tr("关键客户", "Key Customers"),
            "notes": tr("研究简注", "Research Notes"),
            "updated_at": tr("更新时间", "Updated"),
        }
        st.dataframe(cand_df.rename(columns=cand_labels), use_container_width=True, hide_index=True)
    else:
        st.info(tr("当前候选储备池为空。可在上方输入主题启动探针。", "The candidate pool is empty. Enter a theme above to launch a discovery search."))

# ── TAB 3: 机会卡与研究池 ───────────────────────────────────────────────────
with tab_theses:
    st.subheader(tr("📑 活跃 Opportunity Cards 库", "📑 Active Opportunity Cards"))
    st.caption(tr(
        "展示由 Agent 多维度推演生成的投资机会卡，包含定量画像、Bull/Bear 对决与失效准则。",
        "Investment opportunity cards generated by the agent's multi-dimensional reasoning, including quantitative profiles, Bull/Bear debates and invalidation criteria.",
    ))

    conn = init_db(db_path)
    theses_df = query_theses(conn, limit=20)
    conn.close()

    if theses_df.empty:
        st.info(tr("暂未生成 Opportunity Card。可在 Tab 1 中选择股票点击生成。", "No Opportunity Cards generated yet. Select a ticker in Tab 1 and click Generate."))
    else:
        for _, row in theses_df.iterrows():
            t_type = row.get("thesis_type", "neutral_watch")
            tag_color = {
                "long_opportunity": tr("🟢 战略做多", "🟢 Strategic Long"),
                "garp_value": tr("💎 GARP 优选", "💎 GARP Pick"),
                "froth_short": tr("🔴 泡沫预警 / 避险", "🔴 Froth Warning / Risk-Off"),
                "neutral_watch": tr("🟡 观望追踪", "🟡 Watch & Track"),
            }.get(t_type, t_type)

            with st.expander(f"{tag_color} | **{row['ticker']}** — {row['title']} ({tr('信心分', 'Confidence')}: {row.get('confidence_score', 50):.1f})", expanded=False):
                st.markdown(tr(
                    f"**快照日期**：`{row['as_of_date']}` | **生成模型**：`{row.get('model', 'gemini-3.8-flash')}`",
                    f"**Snapshot Date**: `{row['as_of_date']}` | **Model**: `{row.get('model', 'gemini-3.8-flash')}`",
                ))

                col_bull, col_bear = st.columns(2)
                with col_bull:
                    st.markdown(tr("#### 🐂 Bull Case (多头驱动)", "#### 🐂 Bull Case"))
                    st.info(row.get("bull_case") or tr("暂无多头阐述", "No bull case provided"))
                with col_bear:
                    st.markdown(tr("#### 🐻 Bear Case (红队风险)", "#### 🐻 Bear Case"))
                    st.warning(row.get("bear_case") or tr("暂无空头阐述", "No bear case provided"))

                st.markdown(tr("#### ⚖️ 综合多因子研判 (Synthesis)", "#### ⚖️ Multi-Factor Synthesis"))
                st.write(row.get("synthesis") or "")

                col_entry, col_inv = st.columns(2)
                with col_entry:
                    st.markdown(tr("🎯 **建议估值介入区间**", "🎯 **Suggested Valuation Entry Zone**"))
                    st.code(row.get("valuation_entry_zone") or tr("暂无", "N/A"), language="text")
                with col_inv:
                    st.markdown(tr("🚫 **逻辑证伪与失效触发条件 (Invalidation)**", "🚫 **Thesis Invalidation Triggers**"))
                    st.code(row.get("invalidation_criteria") or tr("暂无", "N/A"), language="text")

                catalysts = row.get("catalysts_json")
                if catalysts:
                    st.markdown(tr("⏳ **关键催化剂与时间表**", "⏳ **Key Catalysts & Timeline**"))
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
