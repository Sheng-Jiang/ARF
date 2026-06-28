"""管理面板 — 运行历史、抓取状态、手动触发管道。"""
from datetime import date

import pandas as pd
import streamlit as st

from webapp import jobs
from webapp.data import (
    list_dates,
    load_fetch_outcomes,
    load_latest_run,
    load_runs,
    refresh_data,
)

st.set_page_config(page_title="ARF — 管理面板", layout="wide")
st.title("⚙️ 管理面板")
st.caption("查看管道运行历史、抓取明细，并按需触发新一轮数据更新。")

# ---------- Last run summary ----------
latest = load_latest_run()
col1, col2, col3, col4 = st.columns(4)

if latest.empty:
    col1.metric("最近运行", "—")
    col2.metric("状态", "—")
    col3.metric("成功抓取", "—")
    col4.metric("耗时（秒）", "—")
    st.info("尚无运行记录。请触发首次运行。")
else:
    r = latest.iloc[0]
    started = r.get("started_at")
    if isinstance(started, pd.Timestamp):
        started_str = started.strftime("%Y-%m-%d %H:%M UTC")
    else:
        started_str = str(started)
    status = str(r.get("status") or "unknown")
    status_icon = {"success": "✅", "partial": "⚠️", "running": "🔄", "error": "❌"}.get(status, "❔")
    total = int(r.get("tickers_total") or 0)
    ok = int(r.get("tickers_ok") or 0)
    failed = int(r.get("tickers_failed") or 0)
    dur = r.get("duration_sec")
    col1.metric("最近运行", started_str)
    col2.metric("状态", f"{status_icon} {status}")
    col3.metric("成功 / 总数", f"{ok}/{total}", delta=f"-{failed} 失败" if failed else None)
    col4.metric("耗时（秒）", f"{dur:.0f}" if pd.notna(dur) else "—")

st.divider()

# ---------- Trigger refresh ----------
st.subheader("触发数据刷新")

trigger_enabled = jobs.is_enabled()

with st.form("trigger_form"):
    as_of_input = st.date_input(
        "数据快照日期",
        value=date.today(),
        help="管道将抓取该日期的最新可用数据。",
    )
    submitted = st.form_submit_button(
        "🔄 立即运行管道" if trigger_enabled else "未配置触发器",
        disabled=not trigger_enabled,
        type="primary",
    )
    if submitted:
        try:
            execution = jobs.trigger_pipeline(as_of=as_of_input)
            st.success(f"已成功提交管道运行请求。执行ID：`{execution}`")
            
            # Start monitoring with a progress bar
            progress_bar = st.progress(0, text="正在初始化管道任务...")
            status_container = st.empty()
            
            import time
            start_time = time.time()
            max_duration = 300  # 5 minutes timeout
            
            while time.time() - start_time < max_duration:
                status_dict = jobs.get_execution_status(execution)
                status = status_dict.get("status", "running")
                percent = status_dict.get("percent", 50)
                msg = status_dict.get("message", "正在运行...")
                
                # Estimate percent based on elapsed time to make the progress bar look alive
                elapsed = int(time.time() - start_time)
                if status == "running":
                    # Slow progress estimation from 10% to 90% over 150 seconds
                    percent = min(90, int(10 + (elapsed / 150.0) * 80))
                    msg = f"正在执行管道任务... ({elapsed} 秒) - {msg}"
                
                progress_bar.progress(percent, text=msg)
                
                if status == "succeeded":
                    st.success("🎉 管道异步任务运行成功！数据已更新。")
                    # Refresh cached connection
                    refresh_data()
                    st.rerun()
                    break
                elif status in ("failed", "cancelled"):
                    st.error(f"❌ 管道运行未成功。状态: {status}. 原因: {msg}")
                    break
                    
                time.sleep(5)
            else:
                st.warning("⚠️ 监控超时。管道可能仍在后台运行，请稍后手动重新加载数据库以刷新结果。")
        except Exception as exc:  # noqa: BLE001
            st.error(f"触发失败：{exc}")

if not trigger_enabled:
    st.warning(
        "未配置触发器。请在Cloud Run服务上设置环境变量 `GCP_PROJECT`（以及可选的 `GCP_REGION`、"
        "`PIPELINE_JOB`），并授予Webapp服务账号 `roles/run.invoker` 权限。"
    )

col_refresh, col_dates = st.columns([1, 3])
with col_refresh:
    if st.button("⟳ 重新加载数据库"):
        refresh_data()
        st.rerun()
with col_dates:
    dates = list_dates()
    st.caption(f"数据库中已存快照数：**{len(dates)}** 个 · 最近：{dates[0] if dates else '—'}")

st.divider()

# ---------- Run history ----------
st.subheader("运行历史（最近20次）")
runs = load_runs(limit=20)
if runs.empty:
    st.info("尚无运行记录。")
else:
    display = runs.copy()
    display["started_at"] = pd.to_datetime(display["started_at"]).dt.strftime("%Y-%m-%d %H:%M UTC")
    display["duration_sec"] = display["duration_sec"].apply(
        lambda v: f"{v:.0f}s" if pd.notna(v) else "—"
    )
    display = display[[
        "started_at", "as_of_date", "status", "trigger_source",
        "tickers_ok", "tickers_failed", "duration_sec", "run_id",
    ]].rename(columns={
        "started_at": "开始时间",
        "as_of_date": "快照日期",
        "status": "状态",
        "trigger_source": "触发来源",
        "tickers_ok": "成功",
        "tickers_failed": "失败",
        "duration_sec": "耗时",
        "run_id": "运行ID",
    })
    st.dataframe(display, use_container_width=True, hide_index=True)

# ---------- Per-ticker outcomes for latest run ----------
st.divider()
st.subheader("抓取明细（最近一次运行）")
if latest.empty:
    st.info("尚无运行记录。")
else:
    run_id = latest.iloc[0]["run_id"]
    outcomes = load_fetch_outcomes(run_id)
    if outcomes.empty:
        st.info("该运行无抓取记录。")
    else:
        ok = (outcomes["status"] == "ok").sum()
        partial = (outcomes["status"] == "partial").sum()
        err = (outcomes["status"] == "error").sum()
        skipped = (outcomes["status"] == "skipped").sum()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("✅ 成功", ok)
        c2.metric("⚠️ 部分缺失", partial)
        c3.metric("❌ 失败", err)
        c4.metric("⏭️ 跳过", skipped, help="Pre-IPO / 欧洲参考股，不抓取行情")
        failed_only = st.checkbox("只显示失败/部分缺失", value=err + partial > 0)
        view = (
            outcomes
            if not failed_only
            else outcomes[outcomes["status"].isin(["error", "partial"])]
        )
        view = view.rename(columns={
            "ticker": "代码",
            "status": "状态",
            "data_source": "数据源",
        })[["代码", "状态", "数据源"]]
        st.dataframe(view, use_container_width=True, hide_index=True)
