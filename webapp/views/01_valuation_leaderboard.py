"""估值榜单 — 美股/中股排名表与 E-V 散点图，外加当季池结构与轮换记录。

美股与中股此前是两个逐行相同的页面（仅腿、WACC、数据源脚注不同），组合管理则是
榜单名单的来源说明。三者合并为一页三个标签：先看名单怎么来的，再看名单排出什么。
"""
from pathlib import Path

import pandas as pd
import streamlit as st

from webapp.data import (
    list_pool_ids,
    load_pool_changes,
    load_pool_membership,
    load_snapshot,
    pool_membership_is_archived,
)
from webapp.mobile import inject_mobile_css, is_mobile, show_plotly
from webapp.ui import render_sidebar, render_table, scatter_plot, tr

st.set_page_config(
    page_title=tr("ARF — 估值榜单", "ARF — Valuation Leaderboard"),
    layout="wide",
)

inject_mobile_css()

# 每条腿的差异只有三处：显示名、WACC 阈值、数据来源。
LEGS = {
    "US": {
        "label": tr("美股", "US Leg"),
        "icon": "🇺🇸",
        "wacc_text": tr("美股10%", "US 10%"),
        "sources": tr(
            "美股数据来源：yfinance（主）+ SEC EDGAR（分部营收）+ Macrotrends（历史EV/S）",
            "US data sources: yfinance (primary) + SEC EDGAR (segment revenue) + Macrotrends (historical EV/S)",
        ),
    },
    "China": {
        "label": tr("中股", "China Leg"),
        "icon": "🇨🇳",
        "wacc_text": tr("中股12%", "China 12%"),
        "sources": tr(
            "A股数据来源：Baostock；港股/ADR：yfinance\n"
            "- A股使用**扣非净利润**计算ROE（剔除非经常性损益，更能反映主业盈利质量）",
            "A-share data sources: Baostock; HK/ADR: yfinance\n"
            "- A-shares use **net profit excluding non-recurring items** for ROE "
            "(strips out non-recurring gains/losses, better reflecting core operating profitability)",
        ),
    },
}

SCATTER_LEGEND = tr(
    """
**散点图解读：**
横轴 E分 = AI曝光度，纵轴 V分 = 估值拉伸程度，均为板块内百分位排名（0–100）。
- 🔴 **右上角**（高E + 高V）：AI叙事泡沫核心区，ARF最高，风险最集中
- 🟢 **右下角**（高E + 低V）：AI核心受益股且估值合理，基本面支撑充分
- 🟡 **左上角**（低E + 高V）：非AI驱动的高估值，需关注其他风险因素
- ⚪ **左下角**（低E + 低V）：AI参与度低且估值合理，ARF最低
- 气泡大小 = 市值；颜色由红（D1，泡沫最重）渐变至深绿（D10，最理性）
""",
    """
**Reading the scatter:**
X-axis E-score = AI exposure, Y-axis V-score = valuation stretch, both percentile-ranked within the leg (0–100).
- 🔴 **Top-right** (high E + high V): core AI-narrative bubble zone, highest ARF, most concentrated risk
- 🟢 **Bottom-right** (high E + low V): core AI beneficiaries at reasonable valuations, well supported by fundamentals
- 🟡 **Top-left** (low E + high V): high valuation not driven by AI — watch for other risk factors
- ⚪ **Bottom-left** (low E + low V): low AI participation and reasonable valuation, lowest ARF
- Bubble size = market cap; colour fades from red (D1, most frothy) to dark green (D10, most rational)
""",
)

st.title(tr("🧮 估值榜单", "🧮 Valuation Leaderboard"))
st.caption(
    tr(
        "按ARF分数排名。D1 = AI叙事估值拉伸最大。红色行 = D1，橙色 = D2，绿色 = D8–D10。★ = 泡沫预警。",
        "Ranked by ARF score. D1 = Peak AI-narrative valuation stretch. Red rows = D1, orange = D2, "
        "green = D8–D10. ★ = froth warning.",
    )
)

as_of = render_sidebar()
if as_of is None:
    st.stop()

snapshot = load_snapshot(as_of)


def render_leg(leg: str) -> None:
    """排名表 + 散点图 + 指标定义，参数化到一条腿。"""
    cfg = LEGS[leg]
    rows = snapshot[snapshot["leg"] == leg]
    if rows.empty:
        st.warning(
            tr(
                f"该快照日期暂无{cfg['label']}数据。",
                f"No {cfg['label']} data in this snapshot date.",
            )
        )
        return

    def _table_block() -> None:
        st.subheader(tr(f"排名表 — {as_of}", f"Ranking Table — {as_of}"))
        render_table(rows)

    def _scatter_block() -> None:
        st.subheader(tr("E分 vs V分 散点图", "E-Score vs V-Score Scatter"))
        show_plotly(scatter_plot(rows, cfg["label"]), key=f"scatter_{leg}")
        st.markdown(SCATTER_LEGEND)

    # 手机端单列堆叠（左右分栏会把散点图挤成不可读的窄条）；桌面端保持 表格 | 散点。
    if is_mobile():
        _table_block()
        _scatter_block()
    else:
        col_table, col_scatter = st.columns([3, 2], gap="large")
        with col_table:
            _table_block()
        with col_scatter:
            _scatter_block()

    with st.expander(tr("评分指标定义", "Scoring Metric Definitions")):
        st.markdown(tr(f"""
- **E分（AI曝光度）**：在AI产业链中的层级位置（30%）+ 纯AI业务占比（40%）+ 毛利率（20%）+ AI营收增速（上限200%）（10%）
- **V分（估值拉伸）**：反向DCF隐含增长缺口 + PEG类比 + EV/Sales五年百分位，减去ROE质量加成（±20分）
- **ARF** = √(E × V)，在板块内百分位排名，再分为D1–D10十分位
- **泡沫预警 ★**：D1 且 ROE < WACC（{cfg['wacc_text']}） 且 P/S > 25
- {cfg['sources']}
""", f"""
- **E-score (AI Exposure)**: stack layer position (30%) + pure-play AI revenue share (40%) + gross margin (20%) + AI revenue growth capped at 200% (10%)
- **V-score (Valuation Stretch)**: reverse-DCF implied growth gap + PEG analog + EV/Sales 5-year percentile, minus ROE quality adjustment (±20 pts)
- **ARF** = √(E × V), percentile-ranked within the leg, then split into D1–D10 deciles
- **Froth Warning ★**: D1 AND ROE < WACC ({cfg['wacc_text']}) AND P/S > 25
- {cfg['sources']}
"""))


def render_pool() -> None:
    """当季 50/50 池结构、轮换历史与轮换报告。"""
    st.caption(
        tr(
            "季度 50/50 池：US 50（45 核心 + 5 新秀）+ China 50（45 核心 + 5 新秀）。"
            "每季度自动轮换最多 3 只/边，成员快照归档于 pool_membership。",
            "Quarterly 50/50 pool: US 50 (45 core + 5 newcomers) + China 50 (45 core + 5 newcomers). "
            "Up to 3 tickers per side rotate each quarter; membership snapshots are archived in pool_membership.",
        )
    )

    pool_ids = list_pool_ids()
    if not pool_ids:
        st.info(
            tr(
                "universe.yaml 未分配季度池，数据库中也无成员快照。",
                "No quarterly pool assigned in universe.yaml, and no membership snapshots in the database.",
            )
        )
        return

    selected = st.selectbox(tr("季度池", "Quarterly Pool"), pool_ids, index=0, key="pool_id")
    members = load_pool_membership(selected)
    changes = load_pool_changes(selected)

    if not pool_membership_is_archived(selected):
        st.info(
            tr(
                f"**配置视图 · 尚未归档** — {selected} 的名单读自 config/universe.yaml。"
                "管道运行一次后会归档到 pool_membership，届时改为展示归档快照。",
                f"**Config View · Not Yet Archived** — Membership for {selected} is read from "
                "config/universe.yaml. After the pipeline runs once it will be archived to "
                "pool_membership, and this view will switch to the archived snapshot.",
            )
        )

    st.subheader(tr(f"池结构 — {selected}", f"Pool Structure — {selected}"))
    if members.empty:
        st.warning(tr(f"{selected} 无成员记录。", f"{selected} has no membership records."))
        return

    summary = (
        members.groupby(["leg", "cohort"])
        .size()
        .reset_index(name="count")
        .pivot(index="leg", columns="cohort", values="count")
        .fillna(0)
    )
    for col in ("core", "newcomer"):
        if col not in summary.columns:
            summary[col] = 0
    summary_display = summary[["core", "newcomer"]].astype(int).rename(
        columns={"core": tr("核心", "Core"), "newcomer": tr("新秀", "Newcomer")}
    )
    summary_display.index.name = tr("板块", "Leg")
    st.dataframe(summary_display, use_container_width=True)

    # 合并当前快照的 ARF/Decile 做一览。占位帧必须带上 arf/decile，
    # 否则快照缺失时下面的列选择会 KeyError。
    detail = members.merge(
        snapshot[["ticker", "arf", "decile"]]
        if not snapshot.empty
        else pd.DataFrame(columns=["ticker", "arf", "decile"]),
        on="ticker",
        how="left",
    )
    st.caption(
        tr(
            f"成员明细（ARF/Decile 来自 {as_of} 快照，可能晚于轮换时点）",
            f"Member detail (ARF/Decile from the {as_of} snapshot, may postdate rotation)",
        )
    )
    detail_cols = {
        "ticker": tr("代码", "Ticker"),
        "leg": tr("板块", "Leg"),
        "cohort": tr("队列", "Cohort"),
        "arf": "ARF",
        "decile": tr("十分位", "Decile"),
    }
    st.dataframe(
        detail[["ticker", "leg", "cohort", "arf", "decile"]].rename(columns=detail_cols),
        hide_index=True,
        use_container_width=True,
    )

    st.divider()

    st.subheader(tr(f"轮换历史 — {selected}", f"Rotation History — {selected}"))
    if changes.empty:
        st.info(
            tr(
                "本季度无轮换记录（新池首建）。",
                "No rotation records this quarter (first build of the pool).",
            )
        )
    else:
        dir_col = tr("方向", "Direction")
        ticker_col = tr("代码", "Ticker")
        cohort_col = tr("队列", "Cohort")
        reason_col = tr("原因", "Reason")
        time_col = tr("时间", "Time")
        view = changes.rename(columns={
            "direction": dir_col, "ticker": ticker_col, "cohort": cohort_col,
            "reason": reason_col, "applied_at": time_col,
        })
        view[dir_col] = view[dir_col].map({
            "in": tr("🟢 换入", "🟢 Added"),
            "out": tr("🔴 换出", "🔴 Removed"),
        })
        st.dataframe(view[[dir_col, ticker_col, cohort_col, reason_col, time_col]],
                     hide_index=True, use_container_width=True)

    st.divider()

    st.subheader(tr("轮换报告", "Rotation Report"))
    report_path = Path("reports") / f"rotation_{selected}.md"
    if report_path.exists():
        st.markdown(report_path.read_text(encoding="utf-8"))
    else:
        st.info(
            tr(
                f"本地未找到 reports/rotation_{selected}.md。"
                "轮换由调度器执行（python -m arf.pool --rotate），报告同步至 GCS 后在云端环境展示。",
                f"reports/rotation_{selected}.md not found locally. Rotation is run by the scheduler "
                "(python -m arf.pool --rotate); the report syncs to GCS and is shown in the cloud environment.",
            )
        )

    st.caption(
        tr(
            "轮换规则：换出综合分 = 0.4×流动性 + 0.3×数据质量 + 0.2×量能萎缩 + 0.1×惰性；"
            "换入综合分 = 0.4×新上市 + 0.4×流动性 + 0.2×热度。数据缺失维度按 50 分中性处理。",
            "Rotation rules: removal composite = 0.4×liquidity + 0.3×data quality + 0.2×volume shrinkage "
            "+ 0.1×inertia; addition composite = 0.4×new listings + 0.4×liquidity + 0.2×heat. "
            "Missing dimensions are treated as a neutral 50.",
        )
    )


tab_us, tab_cn, tab_pool = st.tabs([
    tr("🇺🇸 美股", "🇺🇸 US Leg"),
    tr("🇨🇳 中股", "🇨🇳 China Leg"),
    tr("🗂️ 池与轮换", "🗂️ Pool & Rotation"),
])
with tab_us:
    render_leg("US")
with tab_cn:
    render_leg("China")
with tab_pool:
    render_pool()
