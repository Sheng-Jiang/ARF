"""Streamlit Page: AI Chief Investment Officer (CIO) Executive Cockpit.

The cockpit replays the ARF mandate over the US leg with ai-hedge-fund's
backtest engine and renders the last session of that replay: the book, the
orders, the risk clamps and the scorecard. Nothing on this page is a
hardcoded sample — if the replay cannot run, the page says so.
"""

from __future__ import annotations

import math
import os
from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from webapp import data
from webapp.mobile import inject_mobile_css
from webapp.ui import render_sidebar

st.set_page_config(
    page_title="ARF — AI CIO 投资总监驾驶舱",
    page_icon="💼",
    layout="wide",
)
inject_mobile_css()

st.markdown(
    """
    <style>
    .cio-header-card {
        background: linear-gradient(135deg, rgba(20, 28, 45, 0.9) 0%, rgba(13, 17, 28, 0.95) 100%);
        border: 1px solid rgba(56, 189, 248, 0.25);
        border-radius: 12px;
        padding: 20px 24px;
        margin-bottom: 20px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("💼 AI CIO 投资总监驾驶舱 (Autonomous AI CIO Cockpit)")
st.caption(
    "由 AI-CIO Supervisory Brain 驱动的对冲基金管理中心：回放 ARF Thematic 委托，"
    "展示真实持仓、调仓指令、风控熔断与分析师计分卡。"
)

selected_date = render_sidebar()
if selected_date is None:
    st.info("👈 请在左侧边栏选择快照日期。")
    st.stop()

as_of = data.latest_scored_date(selected_date)
if as_of is None:
    st.error(f"{selected_date} 及之前的快照都没有完成评分（ARF 为空），无法回放。")
    st.stop()
if as_of != selected_date:
    st.warning(
        f"快照 **{selected_date}** 尚未完成评分（ARF 为空），"
        f"以下使用最近一个完成评分的快照 **{as_of}**。"
    )

try:
    from hedge_fund.fund import load_spec

    from arf.cio import (
        build_cockpit,
        default_mandate_path,
        fetch_benchmark,
        replay_window,
        run_replay,
    )
except Exception as exc:  # noqa: BLE001 — the page must explain a broken install
    st.error(
        "AI CIO 依赖未安装：需要 `aihf`（ai-hedge-fund）。"
        f"请安装 `pip install -e '.[webapp]'` 后重试。\n\n`{exc}`"
    )
    st.stop()

mandate_path = default_mandate_path()
if not mandate_path.exists():
    st.error(f"找不到 ARF 委托文件：{mandate_path}")
    st.stop()

try:
    spec = load_spec(mandate_path)
except Exception as exc:  # noqa: BLE001
    st.error(f"无法加载基金委托 ({mandate_path}): {exc}")
    st.stop()


# ---------------------------------------------------------------------------
# Replay (cached; the inputs are the frames the page already loaded)
# ---------------------------------------------------------------------------


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_benchmark(start_iso: str, end_iso: str) -> pd.DataFrame:
    return fetch_benchmark("SPY", date.fromisoformat(start_iso), date.fromisoformat(end_iso))


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_replay(
    snapshots_df: pd.DataFrame,
    price_items: tuple[tuple[str, pd.DataFrame], ...],
    mandate: str,
    universe: tuple[str, ...],
    start: str,
    end: str,
    forecasts_df: pd.DataFrame | None = None,
):
    return run_replay(
        snapshots_df=snapshots_df,
        prices=dict(price_items),
        mandate_path=mandate,
        universe=list(universe),
        start=start,
        end=end,
        forecasts_df=forecasts_df,
    )


snapshot_df = data.load_snapshot(as_of)
us_rows = snapshot_df[snapshot_df["leg"] == "US"] if "leg" in snapshot_df.columns else snapshot_df
universe = tuple(sorted(us_rows["ticker"].dropna().unique()))
start_iso, _ = replay_window(as_of, days=120)

prices = data.load_price_history(universe, date.fromisoformat(start_iso), as_of)
# The ARF price table can lag the snapshot date (a Sunday snapshot, or a run
# whose US fetch failed). End the replay on the last date every name has a
# bar: the engine refuses to value a held name without a mark.
coverage_ends = [
    frame["date"].max() for frame in prices.values() if not frame.empty
]
if not coverage_ends:
    end_iso = as_of.isoformat()
    st.error("所选区间没有美股日线数据，回放无法运行。")
else:
    end_iso = pd.Timestamp(min(coverage_ends)).date().isoformat()
    if end_iso < as_of.isoformat():
        st.caption(f"美股日线覆盖至 **{end_iso}**（快照日 {as_of}），回放在此截止。")
    try:
        benchmark = _cached_benchmark(start_iso, end_iso)
        if benchmark is None or benchmark.empty:
            raise RuntimeError("SPY 没有返回任何交易日")
        prices["SPY"] = benchmark
    except Exception as exc:  # noqa: BLE001 — a missing benchmark blocks the replay
        st.error(f"无法获取 SPY 基准数据，回放暂停：{exc}")

replay = None
cockpit = None
if "SPY" in prices and universe and end_iso >= start_iso:
    try:
        with st.spinner("正在回放 ARF Thematic 委托…"):
            replay = _cached_replay(
                data.load_snapshot_history(),
                tuple(sorted(prices.items())),
                str(mandate_path),
                universe,
                start_iso,
                end_iso,
                forecasts_df=data.load_forecasts(),
            )
            cockpit = build_cockpit(replay, snapshot_df=snapshot_df, spec_path=mandate_path)
    except Exception as exc:  # noqa: BLE001 — surface the real failure
        st.error(f"回放失败：{exc}")


# ---------------------------------------------------------------------------
# KPI cards
# ---------------------------------------------------------------------------

kpis = cockpit.kpis if cockpit is not None else {}

col1, col2, col3, col4, col5, col6 = st.columns(6)
with col1:
    st.metric(
        "💰 基金总净值 (NAV)",
        f"${kpis['nav']:,.0f}" if kpis else "—",
        f"{kpis['total_return']:+.2%}" if kpis else None,
        help="回放窗口期末清算资产总值",
    )
with col2:
    st.metric(
        "💵 现金储备",
        f"${kpis['cash']:,.0f}" if kpis else "—",
        f"{kpis['cash_pct']:.1%}" if kpis and kpis.get("cash_pct") is not None else None,
        help="现金 / NAV",
    )
with col3:
    st.metric(
        "⚖️ 净敞口",
        f"{kpis['net_exposure']:+.1%}" if kpis and kpis.get("net_exposure") is not None else "—",
        f"Gross {kpis['gross_exposure']:.1%}" if kpis and kpis.get("gross_exposure") is not None else None,
        help="多头市值减空头市值；括号内为总敞口",
    )
with col4:
    st.metric(
        "🎯 超额收益 (Alpha)",
        f"{kpis['excess_return']:+.2%}" if kpis else "—",
        f"vs SPY {kpis['benchmark_return']:+.2%}" if kpis else None,
        help="基金总收益减去基准总收益",
    )
with col5:
    st.metric(
        "📊 夏普比率",
        f"{kpis['sharpe']:.2f}" if kpis else "—",
        "年化",
        help="年化超额回报 / 波动率 (Sharpe ratio)",
    )
with col6:
    st.metric(
        "🛡️ 最大回撤",
        f"{kpis['max_drawdown']:.2%}" if kpis else "—",
        f"{kpis['n_cycles']} 次调仓" if kpis else None,
        help="回放窗口内的峰谷回撤",
    )

if cockpit is not None:
    st.caption(
        f"回放窗口 {start_iso} → {end_iso} · 最后交易日 **{cockpit.last_session}** · "
        f"{kpis.get('n_orders', 0)} 笔成交"
    )

st.divider()

tab_regime, tab_barometer, tab_book, tab_rebalance, tab_scorecard, tab_control = st.tabs([
    "🌐 宏观政体与 Pod 资本分配",
    "🔮 预测晴雨表与前瞻 Alpha",
    "📚 投资组合底仓与价值链结构",
    "📋 调仓指令与风控熔断",
    "🏆 分析师与策略计分卡",
    "🎮 CIO 指挥中心与数据同步",
])

# ── TAB 1: 宏观政体与 Pod 资本分配 ───────────────────────────────────────────
with tab_regime:
    st.subheader("🌐 AI 产业宏观估值政体 (Macro AI Valuation Regime)")

    try:
        regime = data.load_regime_stats(as_of)
    except Exception as exc:  # noqa: BLE001
        regime = None
        st.error(f"无法读取泡沫温度计：{exc}")

    regime_col1, regime_col2 = st.columns([2, 3])
    with regime_col1:
        st.markdown("#### 🌡️ 泡沫温度计与估值状态")
        if regime and regime["total_scored"]:
            froth_count = regime["froth_count"]
            median_gap = regime["median_gap"] or 0.0
            is_frothy = froth_count >= 3 or median_gap > 0.05
            if is_frothy:
                st.warning(
                    f"⚠️ **高泡沫警报期 (Elevated Froth Regime)**: 检测到 {froth_count} 只股票触发 "
                    f"Froth Flag，中位数隐含增长差额为 {median_gap:+.1%}。"
                )
                rec_text = "CIO 建议：提高美元中性对冲比例，加大 D1 极度拉伸标的做空权重，严控多头单票上限。"
            else:
                st.success(
                    f"💎 **理性复利增长期 (Compounder Regime)**: 泡沫警报数 {froth_count} 只，"
                    f"估值拉伸中位数 {median_gap:+.1%}，基本面韧性良好。"
                )
                rec_text = "CIO 建议：保持 ARF Thematic 多头优质高 ROE 标的分配，对冲低效产能资产。"
            st.info(rec_text)
            st.markdown(f"""
            - **核心组合已覆盖 AI 标的**: {regime['total_scored']} 只
            - **触发 Froth Flag 泡沫警报**: {froth_count} 只
            - **DCF 逆向隐含增长差额 (g* vs 预期)**: {median_gap:+.1%}
            - **核心组合 ARF 平均得分**: {regime['avg_arf']:.1f} / 100
            - **统计快照日**: {regime['snapshot_date']}
            """)
        else:
            st.info("所选日期没有可用的核心组合评分。")

    with regime_col2:
        st.markdown("#### 🍰 多策略 Pod 资本分配权重 (Capital Slices)")
        pod_df = pd.DataFrame([
            {
                "Pod": strategy.display_name or strategy.name,
                "Weight": strategy.weight,
                "Style": strategy.blend.mode,
                "Staff": ", ".join(model.name for model in strategy.models),
            }
            for strategy in spec.strategies
        ])
        fig_donut = px.pie(
            pod_df,
            names="Pod",
            values="Weight",
            hole=0.45,
            color_discrete_sequence=["#38bdf8", "#818cf8", "#34d399"],
        )
        fig_donut.update_layout(
            margin=dict(l=10, r=10, t=10, b=10),
            height=260,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#cbd5e1"),
        )
        st.plotly_chart(fig_donut, use_container_width=True)
        st.dataframe(pod_df, use_container_width=True, hide_index=True)

# ── TAB 2: 预测晴雨表与前瞻 Alpha ──────────────────────────────────────────
with tab_barometer:
    st.subheader("🔮 4 层前瞻预测晴雨表与机会雷达 (Predictive Barometer)")
    st.markdown(
        """
        > **从滞后温度计到前瞻晴雨表**：传统 ARF 温度计仅测量市场*已经定价了多少*（Trailing FCF 逆向 DCF）；
        > 4 层前瞻晴雨表系统性预测**未来 1–4 个季度的超预期弹性 (Alpha)**，在财报披露前 6 周捕获一致预期修正动能。
        """
    )

    fc_df = data.load_forecasts(as_of)
    if fc_df.empty:
        fc_df = data.load_forecasts(None)

    # 1. CapEx 传导与供应链瓶颈敏感性沙盒 (Interactive Sandbox)
    with st.expander("🛠️ 下游云厂商 CapEx 传导与物理产能瓶颈压力测试 (Interactive CapEx Shock Simulator)", expanded=False):
        sim_col1, sim_col2, sim_col3 = st.columns([2, 2, 2])
        with sim_col1:
            capex_shock = st.slider(
                "☁️ 下游云巨头 (MSFT/GOOGL/META) CapEx 变动冲击",
                min_value=-30,
                max_value=60,
                value=0,
                step=5,
                format="%+d%%",
                help="调整下游 Hyperscaler 算力资本开支假设，实时传导至中上游硬件与光模块供应商",
            )
        with sim_col2:
            capacity_cap = st.slider(
                "🏭 晶圆/先进封装 (CoWoS) 物理产能扩张上限",
                min_value=20,
                max_value=120,
                value=80,
                step=10,
                format="%d%%",
                help="Leontief 瓶颈夹钳：物理产能上限硬性截断名义需求拉动，防止虚假高增长",
            )
        with sim_col3:
            st.metric(
                "📡 传导效应状态",
                f"{'正向拉动' if capex_shock > 0 else ('削减承压' if capex_shock < 0 else '基准中性')}",
                f"冲击 {capex_shock:+d}% / 产能截断 {capacity_cap}%",
            )

    if not fc_df.empty:
        display_df = fc_df.copy()
        if capex_shock != 0 or capacity_cap < 100:
            clamp_val = capacity_cap / 100.0
            shock_factor = 1.0 + (capex_shock / 100.0)
            sim_preds = []
            sim_beats = []
            sim_probs = []
            for _, r in display_df.iterrows():
                base_p = float(r.get("predicted_rev_growth") or 0.15)
                cons_g = float(r.get("consensus_rev_growth") or 0.15)
                sim_p = min(base_p * shock_factor, clamp_val)
                sim_b = sim_p - cons_g
                prob = 1.0 / (1.0 + math.exp(-max(-3.0, min(3.0, sim_b * 10.0))))
                sim_preds.append(round(sim_p, 4))
                sim_beats.append(round(sim_b, 4))
                sim_probs.append(round(prob, 4))
            display_df["predicted_rev_growth"] = sim_preds
            display_df["expected_beat_pct"] = sim_beats
            display_df["eps_surprise_prob"] = sim_probs

        # 2. 前瞻晴雨表雷达散点图
        snap_df = data.load_snapshot(as_of)
        if snap_df.empty:
            snap_df = data.load_snapshot_history()

        merged_radar = display_df.copy()
        if not snap_df.empty:
            merged_radar = pd.merge(
                display_df,
                snap_df[["ticker", "name", "v_score", "arf", "market_cap_usd"]].drop_duplicates("ticker"),
                on="ticker",
                how="left",
            )
            merged_radar["v_score"] = pd.to_numeric(merged_radar["v_score"], errors="coerce").fillna(50.0)
            merged_radar["expected_beat_pct"] = pd.to_numeric(merged_radar["expected_beat_pct"], errors="coerce").fillna(0.0)
            merged_radar["eps_surprise_prob"] = pd.to_numeric(merged_radar["eps_surprise_prob"], errors="coerce").fillna(0.5)

            st.markdown("#### 🎯 前瞻业绩超越预期 vs 滞后估值倍数 (Alpha Opportunity Radar)")
            fig_radar = px.scatter(
                merged_radar,
                x="v_score",
                y="expected_beat_pct",
                size=merged_radar["market_cap_usd"].map(lambda v: max(1e9, float(v)) if pd.notna(v) else 1e9),
                color="eps_surprise_prob",
                hover_name="ticker",
                hover_data=["predicted_rev_growth", "fair_value_p50", "expected_return_p50"],
                color_continuous_scale=["#f87171", "#fbbf24", "#34d399"],
                labels={
                    "v_score": "滞后估值拉伸 (V-score 0-100)",
                    "expected_beat_pct": "前瞻超越一致预期幅度 (ĝ_ARF - Consensus)",
                    "eps_surprise_prob": "超预期胜率",
                },
            )
            fig_radar.add_hline(y=0.0, line_dash="dash", line_color="rgba(148, 163, 184, 0.4)")
            fig_radar.add_vline(x=50.0, line_dash="dash", line_color="rgba(148, 163, 184, 0.4)")
            fig_radar.update_layout(
                height=380,
                margin=dict(l=20, r=20, t=20, b=20),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#cbd5e1"),
            )
            st.plotly_chart(fig_radar, use_container_width=True)

        # 3. 4-Layer Multi-Horizon Metrics Table
        st.markdown("#### 📑 4 层全景预测明细表 (Multi-Horizon Forecast Fan)")
        table_cols = [
            "ticker", "predicted_rev_growth", "consensus_rev_growth",
            "expected_beat_pct", "eps_surprise_prob", "revision_velocity_14d",
            "fair_value_p10", "fair_value_p50", "fair_value_p90",
            "expected_return_p50", "regime_breakout_prob",
        ]
        available_cols = [c for c in table_cols if c in display_df.columns]
        view_df = display_df[available_cols].copy()

        for col in ["predicted_rev_growth", "consensus_rev_growth", "expected_beat_pct", "expected_return_p50", "revision_velocity_14d"]:
            if col in view_df.columns:
                view_df[col] = view_df[col].map(lambda v: f"{v:+.1%}" if pd.notna(v) else "—")
        for col in ["eps_surprise_prob", "regime_breakout_prob"]:
            if col in view_df.columns:
                view_df[col] = view_df[col].map(lambda v: f"{v:.0%}" if pd.notna(v) else "—")
        for col in ["fair_value_p10", "fair_value_p50", "fair_value_p90"]:
            if col in view_df.columns:
                view_df[col] = view_df[col].map(lambda v: f"${v:,.2f}" if pd.notna(v) else "—")

        rename_dict = {
            "ticker": "标的代码",
            "predicted_rev_growth": "L1 预测营收增速 (ĝ)",
            "consensus_rev_growth": "卖方一致增速",
            "expected_beat_pct": "预期超额差 (Beat)",
            "eps_surprise_prob": "L2 超预期胜率",
            "revision_velocity_14d": "14天修正动能",
            "fair_value_p10": "L3 悲观估值 (P10)",
            "fair_value_p50": "基准估值 (P50)",
            "fair_value_p90": "乐观估值 (P90)",
            "expected_return_p50": "12月空间 (P50)",
            "regime_breakout_prob": "L4 筹码突破率",
        }
        view_df = view_df.rename(columns=rename_dict)
        st.dataframe(view_df, use_container_width=True, hide_index=True)
    else:
        st.info("当前快照日暂无前瞻预测晴雨表数据，请在【CIO 指挥中心】运行预测管线。")

# ── TAB 3: 投资组合持仓与价值链结构 ───────────────────────────────────────────
with tab_book:
    st.subheader("📚 基金活跃持仓与 5 层价值链分布 (Current Book)")
    if cockpit is None or cockpit.positions.empty:
        st.info("没有可展示的持仓：回放尚未完成。")
    else:
        st.markdown(f"##### 📑 最后交易日持仓 · {cockpit.last_session}")
        shown = cockpit.positions.copy()
        shown["组合权重"] = shown["组合权重"].map(lambda v: f"{v:+.1%}")
        st.dataframe(shown, use_container_width=True, hide_index=True)

        st.markdown("##### 🍰 Jensen Huang 5 层价值链风险暴露")
        fig_bar = px.bar(
            cockpit.layer_exposure,
            x="Layer",
            y="Exposure",
            color="Exposure",
            color_continuous_scale=["#f87171", "#94a3b8", "#38bdf8"],
        )
        fig_bar.update_layout(
            margin=dict(l=10, r=10, t=10, b=10),
            height=320,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#cbd5e1"),
        )
        st.plotly_chart(fig_bar, use_container_width=True)

# ── TAB 3: 调仓指令与风控熔断 ────────────────────────────────────────────────
with tab_rebalance:
    st.subheader("📋 调仓指令与风控审计 (T+1 Execution Pipeline)")
    if cockpit is None:
        st.info("没有可展示的调仓记录：回放尚未完成。")
    else:
        st.markdown(
            "根据 **Decide at T, Execute at T+1** 铁律，以下订单来自回放引擎的实际决策与撮合记录："
        )
        col_orders, col_clamps = st.columns([3, 2])
        with col_orders:
            st.markdown("##### 🎯 报单票据 (Orders)")
            if cockpit.order_note:
                st.caption(cockpit.order_note)
            if cockpit.staged_orders.empty:
                st.info("该交易日没有产生订单。")
            else:
                st.dataframe(cockpit.staged_orders, use_container_width=True, hide_index=True)
        with col_clamps:
            st.markdown("##### 🛡️ 主风控硬阈值触发日志 (Risk Clamps)")
            if cockpit.clamps.empty:
                st.info("该周期没有触发风控阈值。")
            else:
                st.dataframe(cockpit.clamps, use_container_width=True, hide_index=True)
        for note in cockpit.notes:
            st.caption(f"ℹ️ {note}")

# ── TAB 4: 分析师与策略计分卡 ────────────────────────────────────────────────
with tab_scorecard:
    st.subheader("🏆 分析师与策略量化计分卡 (Scorecard)")
    st.caption("基于回放期间的前瞻预测与实际价格反馈（无前视偏误）统计：")

    scorecard = cockpit.scorecard if cockpit is not None else None
    if scorecard is None:
        st.info("计分卡不可用：回放尚未完成，或窗口内没有足够的决策记录。")
    else:
        col_analyst, col_strat = st.columns(2)
        with col_analyst:
            st.markdown("##### 🧑‍💼 分析师能力评估 (Analyst Performance)")
            analysts_score = pd.DataFrame([
                {
                    "Analyst": row.name,
                    "Views": row.n_views,
                    "Hit Rate": row.hit_rate,
                    "Slugging": row.slugging,
                    "IC": row.ic_mean,
                    "Dates": row.n_dates,
                }
                for row in scorecard.analysts
            ])
            st.dataframe(
                analysts_score.style.format({
                    "Hit Rate": "{:.1%}", "Slugging": "{:.2f}×", "IC": "{:+.3f}",
                }, na_rep="—"),
                use_container_width=True,
                hide_index=True,
            )
        with col_strat:
            st.markdown("##### 💼 策略 Pod 盈亏归因 (Strategy Attribution)")
            strategy_score = pd.DataFrame([
                {
                    "Strategy": row.name,
                    "Periods": row.n_periods,
                    "P&L ($)": row.pnl,
                    "Return": row.return_pct,
                    "Win Rate": row.win_rate,
                    "Max DD": row.max_drawdown_pct,
                }
                for row in scorecard.strategies
            ])
            st.dataframe(
                strategy_score.style.format({
                    "P&L ($)": "{:,.0f}", "Return": "{:+.2%}",
                    "Win Rate": "{:.1%}", "Max DD": "{:.2%}",
                }, na_rep="—"),
                use_container_width=True,
                hide_index=True,
            )

# ── TAB 5: CIO 指挥中心与数据同步 ────────────────────────────────────────────
with tab_control:
    st.subheader("🎮 CIO 控制中心与数据同步 (Control Center)")
    st.caption("生产环境的数据源是 GCS 中的权威 arf.db；Lighthouse 定时把中国腿推送进同一对象。")

    st.session_state.setdefault("cio_halted", False)
    halted = bool(st.session_state["cio_halted"])

    if halted:
        st.error("🛑 **本会话已冻结**：驾驶舱操作已锁定。解除后需重新运行回放。")
    else:
        st.success("🟢 **ACTIVE NORMAL**：回放只读运行，未发现挂起风控违规。")

    try:
        freshness = data.load_data_freshness()
    except Exception as exc:  # noqa: BLE001
        freshness = {"legs": {}, "runs": {}}
        st.warning(f"无法读取数据新鲜度：{exc}")

    from arf.cloud_sync import SyncResult, gcs_blob_info, sync_dual_cloud

    @st.cache_data(ttl=300, show_spinner=False)
    def _blob_info() -> dict[str, object]:
        return gcs_blob_info()

    act_col1, act_col2, act_col3 = st.columns(3)

    with act_col1:
        st.markdown("#### ☁️ 1. 刷新权威数据")
        st.caption("GCS 模式：丢弃缓存并重新下载权威 arf.db。")
        if st.button("🔄 刷新数据", use_container_width=True, disabled=halted):
            with st.spinner("正在刷新…"):
                report: dict[str, SyncResult] = {}
                if os.getenv("DATA_SOURCE", "local").lower() == "gcs":
                    try:
                        data.refresh_data()
                        data.get_conn()  # forces a fresh download
                        report["gcs"] = SyncResult(
                            "gcs", "ok", "re-downloaded the authoritative GCS database"
                        )
                    except Exception as exc:  # noqa: BLE001
                        report["gcs"] = SyncResult("gcs", "error", str(exc))
                    report["lighthouse"] = SyncResult(
                        "lighthouse",
                        "skipped",
                        "Lighthouse publishes the China leg to GCS on its systemd timer.",
                    )
                else:
                    report = sync_dual_cloud(
                        data.get_db_path(), connection=data.get_conn()
                    )
                    data.refresh_data()
            st.session_state["cio_sync_report"] = {
                name: (result.status, result.message, result.rows)
                for name, result in report.items()
            }
            st.rerun()

        for name, (status, message, rows) in st.session_state.get("cio_sync_report", {}).items():
            if status == "error":
                st.error(f"{name}: {message}")
            elif status == "skipped":
                st.info(f"{name}: {message}")
            else:
                suffix = f" · {rows}" if rows else ""
                st.success(f"{name}: {message}{suffix}")

        blob = _blob_info()
        if blob:
            st.caption(
                f"GCS: gs://{blob.get('bucket')}/{blob.get('object')} · "
                f"{blob.get('size', 0) / 1e6:.1f} MB · updated {blob.get('updated')}"
            )
        legs = freshness.get("legs", {})
        if legs:
            st.caption(
                "最新快照 · " + " · ".join(f"{leg}: {latest}" for leg, latest in legs.items())
            )
        runs = freshness.get("runs", {})
        if runs:
            st.caption(
                "最近运行 · " + " · ".join(
                    f"{source}: {started} ({status})"
                    for source, (started, status) in runs.items()
                )
            )

    with act_col2:
        st.markdown("#### ⚡ 2. 模拟实盘状态")
        st.caption("本环境未部署持久化 paper fund；驾驶舱展示的是只读回放。")
        st.info(
            "Paper tick 需要 `aihf paper create` 部署的基金目录。"
            "生产容器没有持久磁盘，因此这里不伪造推进结果。"
        )

    with act_col3:
        st.markdown("#### 📈 3. 重新回放")
        st.caption(f"窗口 {start_iso} → {end_iso}，{len(universe)} 只美股 AI 标的。")
        if st.button("🚀 重新运行回放", use_container_width=True, disabled=halted):
            st.cache_data.clear()
            st.rerun()

        if st.button("🔮 计算前瞻晴雨表", use_container_width=True, disabled=halted):
            with st.spinner("正在计算 4 层前瞻预测晴雨表…"):
                from arf.forecast import generate_forecasts_for_universe
                conn = data.get_conn()
                generate_forecasts_for_universe(as_of, conn, persist=True)
                st.cache_data.clear()
                st.rerun()

    st.divider()
    st.markdown("#### 🛡️ 风控冻结开关 (Session Kill-Switch)")
    st.caption(
        "本环境没有持久化账本，此开关只冻结当前浏览器会话中的驾驶舱操作；"
        "它不会改写 GCS 中的数据，也不会阻止其他会话。"
    )
    c_halt1, c_halt2 = st.columns([1, 4])
    with c_halt1:
        if halted:
            if st.button("✅ 解除冻结", use_container_width=True):
                st.session_state["cio_halted"] = False
                st.rerun()
        else:
            if st.button("🛑 冻结本会话", type="primary", use_container_width=True):
                st.session_state["cio_halted"] = True
                st.rerun()
    with c_halt2:
        state_text = "🛑 **SESSION FROZEN**" if halted else "🟢 **ACTIVE NORMAL**"
        st.caption(f"当前会话状态：{state_text}")
