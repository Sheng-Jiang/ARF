"""组合管理 — 季度 50/50 池视图、轮换历史与轮换报告。"""
from pathlib import Path

import pandas as pd
import streamlit as st

from webapp.data import (
    list_pool_ids,
    load_pool_changes,
    load_pool_membership,
    load_snapshot,
)
from webapp.mobile import inject_mobile_css

st.set_page_config(page_title="ARF — 组合管理", layout="wide")
inject_mobile_css()

st.title("🗂️ 组合管理")
st.caption(
    "季度 50/50 池：US 50（45 核心 + 5 新秀）+ China 50（45 核心 + 5 新秀）。"
    "每季度自动轮换最多 3 只/边（见轮换报告），成员快照归档于 pool_membership。"
)

pool_ids = list_pool_ids()
if not pool_ids:
    st.info("数据库中尚无季度池成员快照——首次运行管道并完成一次轮换后此处将展示。")
    st.stop()

selected = st.selectbox("季度池", pool_ids, index=0)
members = load_pool_membership(selected)
changes = load_pool_changes(selected)

# ── 池结构概览 ───────────────────────────────────────────────────────────────
st.subheader(f"池结构 — {selected}")
if members.empty:
    st.warning(f"{selected} 无成员记录。")
else:
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
    summary = summary[["core", "newcomer"]].astype(int)
    st.dataframe(summary, use_container_width=True)

    # 合并最新快照的 ARF/decile 做一览（若该季度已有快照）。
    try:
        dates = sorted(members["added_at"].unique())[:1]
    except Exception:  # noqa: BLE001 — added_at may be absent in old rows
        dates = []
    snap = None
    if dates:
        try:
            snap = load_snapshot(pd.Timestamp(dates[0]).date())
        except Exception:  # noqa: BLE001
            snap = None
    view = members.merge(
        snap[["ticker", "arf", "decile"]] if snap is not None else pd.DataFrame(columns=["ticker"]),
        on="ticker",
        how="left",
    )
    st.caption("成员明细（ARF/Decile 来自最新快照，可能晚于轮换时点）")
    st.dataframe(
        view[["ticker", "leg", "cohort", "arf", "decile"]],
        hide_index=True,
        use_container_width=True,
    )

st.divider()

# ── 轮换历史 ─────────────────────────────────────────────────────────────────
st.subheader(f"轮换历史 — {selected}")
if changes.empty:
    st.info("本季度无轮换记录（新池首建）。")
else:
    view = changes.rename(columns={
        "direction": "方向", "ticker": "代码", "cohort": "队列",
        "reason": "原因", "applied_at": "时间",
    })
    view["方向"] = view["方向"].map({"in": "🟢 换入", "out": "🔴 换出"})
    st.dataframe(view[["方向", "代码", "队列", "原因", "时间"]],
                 hide_index=True, use_container_width=True)

st.divider()

# ── 轮换报告 ─────────────────────────────────────────────────────────────────
st.subheader("轮换报告")
report_path = Path("reports") / f"rotation_{selected}.md"
if report_path.exists():
    st.markdown(report_path.read_text(encoding="utf-8"))
else:
    st.info(
        f"本地未找到 reports/rotation_{selected}.md。"
        "轮换由调度器执行（python -m arf.pool --rotate），报告同步至 GCS 后在云端环境展示。"
    )

st.caption(
    "轮换规则：换出综合分 = 0.4×流动性 + 0.3×数据质量 + 0.2×量能萎缩 + 0.1×惰性；"
    "换入综合分 = 0.4×新上市 + 0.4×流动性 + 0.2×热度。数据缺失维度按 50 分中性处理。"
)
