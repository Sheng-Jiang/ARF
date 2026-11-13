"""管理面板 — 运行历史、抓取状态、数据覆盖、校准门禁、手动触发管道。"""
from datetime import date

import pandas as pd
import streamlit as st

from arf.health import (
    calibration_check,
    calibration_to_frame,
    coverage_report,
    coverage_to_frame,
    freshness_status,
    next_monday_utc,
)
from webapp import jobs
from webapp.data import (
    get_conn,
    list_dates,
    load_fetch_outcomes,
    load_latest_run,
    load_news_stats,
    load_runs,
    load_snapshot,
    persist_db_to_gcs,
    refresh_data,
)
from webapp.mobile import inject_mobile_css
from webapp.ui import get_current_lang, tr

is_en = get_current_lang() == "en"

inject_mobile_css()
st.title(tr("⚙️ 管理面板", "⚙️ System Administration"))
st.caption(
    tr(
        "查看管道运行历史、数据覆盖、校准门禁，并按需触发新一轮数据更新。",
        "Review pipeline run history, data coverage and calibration gates, and trigger a new data refresh on demand.",
    )
)


# arf.health returns Chinese label/detail strings; localise them for display
# only, keeping the stable `level` codes for all comparisons.
def _fresh_text(fresh) -> tuple[str, str]:
    if not is_en:
        return fresh.label, fresh.detail
    labels = {
        "fresh": "Fresh",
        "stale": "Stale",
        "critical": "Outdated",
        "unknown": "Unknown",
    }
    label = labels.get(fresh.level, fresh.level)
    if fresh.latest_as_of is None:
        detail = "No ARF snapshots in the database. Run the pipeline first."
    elif (fresh.age_days or 0) < 0:
        detail = f"Latest snapshot {fresh.latest_as_of} is dated in the future (possible timezone issue)."
    elif fresh.level == "fresh":
        detail = f"Latest snapshot {fresh.latest_as_of}, {fresh.age_days} days ago (within weekly cadence)."
    elif fresh.level == "stale":
        detail = (
            f"Latest snapshot {fresh.latest_as_of}, {fresh.age_days} days ago. "
            "Past the weekly window — check that the scheduler ran."
        )
    elif fresh.level == "critical":
        detail = (
            f"Latest snapshot {fresh.latest_as_of}, {fresh.age_days} days ago. "
            "Beyond two weeks — rankings are unreliable; trigger the pipeline now."
        )
    else:
        detail = f"Latest snapshot {fresh.latest_as_of}."
    return label, detail


def _coverage_warnings_display(cov) -> list[str]:
    """Localise systemic coverage warnings for display (stable levels untouched)."""
    if not is_en:
        return list(cov.warnings)
    warnings_out: list[str] = []
    for leg_name, leg in cov.legs.items():
        if leg.n_tickers == 0:
            continue
        if leg.scored_rate < 0.9:
            warnings_out.append(
                f"{leg_name}: only {leg.n_scored}/{leg.n_tickers} tickers produced an "
                f"ARF ({leg.scored_rate:.0%}), below the 90% threshold"
            )
        if leg.v_c1_usable / leg.n_tickers < 0.5:
            warnings_out.append(
                f"{leg_name}: reverse-DCF usable on only {leg.v_c1_usable}/{leg.n_tickers} "
                f"({leg.v_c1_usable / leg.n_tickers:.0%}) — V-score mostly relies on PEG/EV·S"
            )
        rev = leg.fields.get("revenue_yoy_growth")
        if rev is not None and rev.rate < 0.5:
            warnings_out.append(
                f"{leg_name}: revenue growth coverage {rev.present}/{rev.total} "
                f"({rev.pct}%) — E-score growth term largely falls back to defaults"
            )
        c3 = leg.fields.get("ev_sales_5yr_percentile")
        if c3 is not None and c3.rate < 0.5:
            warnings_out.append(
                f"{leg_name}: EV/S 5-year percentile coverage {c3.present}/{c3.total} "
                f"({c3.pct}%) — V-C3 missing"
            )
    return warnings_out


_EN_FIELD_LABELS = {
    "price": "Price",
    "gross_margin": "Gross Margin (E)",
    "revenue_yoy_growth": "Revenue Growth (E)",
    "free_cash_flow": "FCF (V-C1)",
    "forward_pe": "Forward P/E (V-C2)",
    "eps_2yr_cagr": "EPS CAGR (V-C2)",
    "ev_sales_5yr_percentile": "EV/S 5Y Percentile (V-C3)",
    "roe": "ROE",
    "ps_ratio": "P/S",
    "e_score": "E-Score",
    "v_score": "V-Score",
    "arf": "ARF",
}


def _leg_label(leg: str) -> str:
    if not is_en:
        return leg
    return {"US": "US Leg", "China": "China Leg"}.get(leg, leg)


# ---------- Last run summary ----------
latest = load_latest_run()
col1, col2, col3, col4 = st.columns(4)

if latest.empty:
    col1.metric(tr("最近运行", "Latest Run"), "—")
    col2.metric(tr("状态", "Status"), "—")
    col3.metric(tr("成功抓取", "Successful Fetches"), "—")
    col4.metric(tr("耗时（秒）", "Duration (s)"), "—")
    st.info(tr("尚无运行记录。请触发首次运行。", "No run records yet. Trigger the first run."))
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
    col1.metric(tr("最近运行", "Latest Run"), started_str)
    col2.metric(tr("状态", "Status"), f"{status_icon} {status}")
    col3.metric(
        tr("成功 / 总数", "Succeeded / Total"),
        f"{ok}/{total}",
        delta=tr(f"-{failed} 失败", f"-{failed} failed") if failed else None,
    )
    col4.metric(tr("耗时（秒）", "Duration (s)"), f"{dur:.0f}" if pd.notna(dur) else "—")

st.divider()

# ---------- Trigger refresh ----------
st.subheader(tr("触发数据刷新", "Trigger Data Refresh"))

trigger_enabled = jobs.is_enabled()

with st.form("trigger_form"):
    as_of_input = st.date_input(
        tr("数据快照日期", "Data Snapshot Date"),
        value=date.today(),
        help=tr("管道将抓取该日期的最新可用数据。", "The pipeline will fetch the latest available data as of this date."),
    )
    submitted = st.form_submit_button(
        tr("🔄 立即运行管道", "🔄 Run Pipeline Now") if trigger_enabled else tr("未配置触发器", "Trigger Not Configured"),
        disabled=not trigger_enabled,
        type="primary",
    )
    if submitted:
        try:
            execution = jobs.trigger_pipeline(as_of=as_of_input)
            st.success(
                tr(
                    f"已成功提交管道运行请求。执行ID：`{execution}`",
                    f"Pipeline run request submitted successfully. Execution ID: `{execution}`",
                )
            )

            # Start monitoring with a progress bar
            progress_bar = st.progress(0, text=tr("正在初始化管道任务...", "Initializing pipeline job..."))
            status_container = st.empty()

            import time
            start_time = time.time()
            max_duration = 300  # 5 minutes timeout

            while time.time() - start_time < max_duration:
                status_dict = jobs.get_execution_status(execution, lang=get_current_lang())
                status = status_dict.get("status", "running")
                percent = status_dict.get("percent", 50)
                msg = status_dict.get("message", tr("正在运行...", "Running..."))

                # Estimate percent based on elapsed time to make the progress bar look alive
                elapsed = int(time.time() - start_time)
                if status == "running":
                    # Slow progress estimation from 10% to 90% over 150 seconds
                    percent = min(90, int(10 + (elapsed / 150.0) * 80))
                    msg = tr(
                        f"正在执行管道任务... ({elapsed} 秒) - {msg}",
                        f"Running pipeline job... ({elapsed}s) - {msg}",
                    )

                progress_bar.progress(percent, text=msg)

                if status == "succeeded":
                    st.success(
                        tr(
                            "🎉 管道异步任务运行成功！数据已更新。",
                            "🎉 Pipeline async job succeeded! Data has been updated.",
                        )
                    )
                    # Refresh cached connection
                    refresh_data()
                    st.rerun()
                    break
                elif status in ("failed", "cancelled"):
                    st.error(
                        tr(
                            f"❌ 管道运行未成功。状态: {status}. 原因: {msg}",
                            f"❌ Pipeline run did not succeed. Status: {status}. Reason: {msg}",
                        )
                    )
                    break

                time.sleep(5)
            else:
                st.warning(
                    tr(
                        "⚠️ 监控超时。管道可能仍在后台运行，请稍后手动重新加载数据库以刷新结果。",
                        "⚠️ Monitoring timed out. The pipeline may still be running in the background; "
                        "reload the database later to refresh the results.",
                    )
                )
        except Exception as exc:  # noqa: BLE001
            st.error(tr(f"触发失败：{exc}", f"Trigger failed: {exc}"))

if not trigger_enabled:
    st.warning(
        tr(
            "未配置触发器。请在Cloud Run服务上设置环境变量 `GCP_PROJECT`（以及可选的 `GCP_REGION`、"
            "`PIPELINE_JOB`），并授予Webapp服务账号 `roles/run.invoker` 权限。",
            "Trigger not configured. Set the `GCP_PROJECT` environment variable (and optionally "
            "`GCP_REGION`, `PIPELINE_JOB`) on the Cloud Run service and grant the webapp service "
            "account `roles/run.invoker`.",
        )
    )

col_refresh, col_dates = st.columns([1, 3])
with col_refresh:
    if st.button(tr("⟳ 重新加载数据库", "⟳ Reload Database")):
        refresh_data()
        st.rerun()
with col_dates:
    dates = list_dates()
    st.caption(
        tr(
            f"数据库中已存快照数：**{len(dates)}** 个 · 最近：{dates[0] if dates else '—'}",
            f"Snapshots stored in the database: **{len(dates)}** · Latest: {dates[0] if dates else '—'}",
        )
    )

st.divider()

# ---------- WSJ & NYT Financial Press Wire ----------
st.subheader(tr("📰 华尔街日报与纽时舆情数据源", "📰 WSJ & NYT Financial Press Data Source"))
news_telemetry = load_news_stats(days=30)
col_sync_news, col_info_news = st.columns([1, 3])
with col_sync_news:
    if st.button(tr("⟳ 立即同步金融舆情", "⟳ Sync Press Wire Now"), key="admin_sync_press_wire"):
        with st.spinner(tr("正在抓取 WSJ、NYT 与专题报道...", "Fetching & classifying WSJ and NYT articles...")):
            from arf.news.sync import sync_financial_press

            # Use the webapp's active connection: in GCS mode that is the
            # downloaded temp DB (data/arf.db does not exist), and the upload
            # makes the new rows survive the next cold start.
            cnt = sync_financial_press(conn=get_conn(), max_items_per_feed=25)
            persist_db_to_gcs()
            st.success(tr(f"同步完成！新增/更新 {cnt} 篇金融报道。", f"Sync complete! Upserted {cnt} articles."))
            refresh_data()
            st.rerun()
with col_info_news:
    total_art = news_telemetry.get("total_articles", 0)
    latest_pub = news_telemetry.get("latest_published_at")
    latest_str = latest_pub.strftime("%Y-%m-%d %H:%M UTC") if latest_pub and hasattr(latest_pub, "strftime") else (str(latest_pub) if latest_pub else "—")
    st.caption(
        tr(
            f"已索引权威报道：**{total_art}** 篇（WSJ: {news_telemetry.get('wsj_count', 0)} · NYT: {news_telemetry.get('nyt_count', 0)}）· 最近更新：{latest_str}",
            f"Indexed Press Articles: **{total_art}** (WSJ: {news_telemetry.get('wsj_count', 0)} · NYT: {news_telemetry.get('nyt_count', 0)}) · Latest: {latest_str}",
        )
    )

st.divider()

# ---------- Health: freshness + coverage + calibration ----------
st.subheader(tr("健康检查（覆盖率 + 校准门禁）", "Health Check (Coverage + Calibration Gates)"))
dates = list_dates()
if not dates:
    st.info(tr("尚无快照，无法评估覆盖率与校准。", "No snapshots yet — coverage and calibration cannot be evaluated."))
else:
    health_as_of = st.selectbox(
        tr("评估快照日期", "Snapshot Date to Evaluate"),
        dates,
        index=0,
        format_func=str,
        key="health_as_of",
    )
    snap_df = load_snapshot(health_as_of)
    fresh = freshness_status(dates[0])  # always vs latest in DB
    cov = coverage_report(snap_df, as_of=health_as_of)
    cal = calibration_check(snap_df, as_of=health_as_of)
    fresh_label, fresh_detail = _fresh_text(fresh)

    f1, f2, f3, f4 = st.columns(4)
    fresh_icon = {"fresh": "🟢", "stale": "🟡", "critical": "🔴", "unknown": "⚪"}[
        fresh.level
    ]
    f1.metric(tr("数据新鲜度", "Data Freshness"), f"{fresh_icon} {fresh_label}", help=fresh_detail)
    f2.metric(
        tr("下次周更（周一 UTC）", "Next Weekly Run (Mon UTC)"),
        str(next_monday_utc()),
        help="Cloud Scheduler: 0 4 * * MON Etc/UTC",
    )
    f3.metric(
        tr("校准门禁", "Calibration Gates"),
        f"{cal.n_pass}✅ / {cal.n_fail}❌ / {cal.n_missing}❔",
        help=tr("关键标的是否落在预期十分位区间", "Whether key tickers land in their expected decile bands"),
    )
    n_warn = len(cov.warnings)
    f4.metric(
        tr("覆盖告警", "Coverage Warnings"),
        n_warn if n_warn else tr("无", "None"),
        help=tr("字段/V分量系统性缺失", "Systematic missing fields / V-components"),
    )

    if fresh.level in ("stale", "critical"):
        st.warning(fresh_detail)
    for w in _coverage_warnings_display(cov):
        st.warning(w)

    # Per-leg V-component summary
    if cov.legs:
        st.markdown(
            tr(
                "**V分三组件可用率**（与 `scoring.py` 门槛一致）",
                "**V-Score Three-Component Usability** (matching `scoring.py` thresholds)",
            )
        )
        vc_rows = []
        for leg in cov.legs.values():
            vc_rows.append({
                tr("板块", "Leg"): _leg_label(leg.leg),
                tr("股票数", "Tickers"): leg.n_tickers,
                tr("已评分", "Scored"): leg.n_scored,
                tr("C1 逆向DCF", "C1 Reverse DCF"): f"{leg.v_c1_usable}/{leg.n_tickers}",
                tr("C2 PEG", "C2 PEG"): f"{leg.v_c2_usable}/{leg.n_tickers}",
                tr("C3 EV/S五年", "C3 EV/S 5Y"): f"{leg.v_c3_usable}/{leg.n_tickers}",
            })
        st.dataframe(pd.DataFrame(vc_rows), use_container_width=True, hide_index=True)

    with st.expander(tr("字段覆盖明细", "Field Coverage Detail"), expanded=False):
        cov_df = coverage_to_frame(cov)
        if cov_df.empty:
            st.info(tr("无覆盖数据。", "No coverage data."))
        else:
            if is_en:
                cov_df = cov_df.assign(
                    label=cov_df["field"].map(_EN_FIELD_LABELS).fillna(cov_df["label"])
                )
            coverage_col = tr("覆盖", "Coverage")
            cov_df = cov_df.assign(
                **{
                    coverage_col: cov_df.apply(
                        lambda r: f"{r['present']}/{r['total']} ({r['pct']}%)", axis=1
                    )
                }
            )
            show = cov_df.pivot_table(
                index=["label", "field"],
                columns="leg",
                values=coverage_col,
                aggfunc="first",
            ).reset_index()
            show = show.rename(
                columns={
                    "label": tr("字段", "Field"),
                    "field": tr("列名", "Column"),
                    "US": tr("美股", "US Leg"),
                    "China": tr("中股", "China Leg"),
                }
            )
            st.dataframe(show, use_container_width=True, hide_index=True)

    st.markdown(
        tr(
            "**校准套件**（PRD §7 + 生产经验区间）",
            "**Calibration Suite** (PRD §7 + production-observed bands)",
        )
    )
    cal_df = calibration_to_frame(cal)
    if cal_df.empty:
        st.info(tr("无校准结果。", "No calibration results."))
    else:
        status_map = {"pass": "✅ PASS", "fail": "❌ FAIL", "missing": "❔ MISSING"}
        result_col = tr("结果", "Result")
        cal_df[result_col] = cal_df["status"].map(status_map)
        cal_df["D"] = cal_df["decile"].apply(
            lambda d: f"D{int(d)}" if pd.notna(d) else "—"
        )
        cal_df["ARF"] = cal_df["arf"].apply(
            lambda v: f"{v:.1f}" if pd.notna(v) else "—"
        )
        cal_df["★"] = cal_df["froth"].apply(lambda f: "★" if f else "")
        display_cal = cal_df[
            ["ticker", "D", "expected", "ARF", "e_score", "v_score", "★", result_col]
        ].rename(columns={
            "ticker": tr("代码", "Ticker"),
            "expected": tr("期望区间", "Expected Band"),
            "e_score": "E",
            "v_score": "V",
        })
        for col in ("E", "V"):
            display_cal[col] = display_cal[col].apply(
                lambda v: f"{v:.0f}" if pd.notna(v) else "—"
            )
        st.dataframe(display_cal, use_container_width=True, hide_index=True)
        if cal.n_fail:
            st.error(
                tr(
                    f"{cal.n_fail} 只股票落在期望区间外 — 请核对抓取质量或公式漂移，"
                    "不要在未解释前对外分享该期排名。",
                    f"{cal.n_fail} tickers fell outside their expected bands — check fetch quality "
                    "or formula drift, and do not share this period's rankings externally before "
                    "explaining the deviation.",
                )
            )
        elif cal.n_missing:
            st.warning(
                tr(
                    f"{cal.n_missing} 只校准标的缺失或未评分。",
                    f"{cal.n_missing} calibration tickers are missing or unscored.",
                )
            )
        else:
            st.success(tr("校准门禁全部通过。", "All calibration gates passed."))

st.divider()

# ---------- Run history ----------
st.subheader(tr("运行历史（最近20次）", "Run History (Latest 20)"))
runs = load_runs(limit=20)
if runs.empty:
    st.info(tr("尚无运行记录。", "No run records yet."))
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
        "started_at": tr("开始时间", "Started At"),
        "as_of_date": tr("快照日期", "Snapshot Date"),
        "status": tr("状态", "Status"),
        "trigger_source": tr("触发来源", "Trigger Source"),
        "tickers_ok": tr("成功", "Succeeded"),
        "tickers_failed": tr("失败", "Failed"),
        "duration_sec": tr("耗时", "Duration"),
        "run_id": tr("运行ID", "Run ID"),
    })
    st.dataframe(display, use_container_width=True, hide_index=True)

# ---------- Per-ticker outcomes for latest run ----------
st.divider()
st.subheader(tr("抓取明细（最近一次运行）", "Fetch Detail (Latest Run)"))
if latest.empty:
    st.info(tr("尚无运行记录。", "No run records yet."))
else:
    run_id = latest.iloc[0]["run_id"]
    outcomes = load_fetch_outcomes(run_id)
    if outcomes.empty:
        st.info(tr("该运行无抓取记录。", "This run has no fetch records."))
    else:
        ok = (outcomes["status"] == "ok").sum()
        partial = (outcomes["status"] == "partial").sum()
        err = (outcomes["status"] == "error").sum()
        skipped = (outcomes["status"] == "skipped").sum()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(tr("✅ 成功", "✅ Succeeded"), ok)
        c2.metric(tr("⚠️ 部分缺失", "⚠️ Partial"), partial)
        c3.metric(tr("❌ 失败", "❌ Failed"), err)
        c4.metric(
            tr("⏭️ 跳过", "⏭️ Skipped"),
            skipped,
            help=tr("Pre-IPO / 欧洲参考股，不抓取行情", "Pre-IPO / Europe reference names — no market data fetched"),
        )
        failed_only = st.checkbox(
            tr("只显示失败/部分缺失", "Show failed/partial only"),
            value=err + partial > 0,
        )
        view = (
            outcomes
            if not failed_only
            else outcomes[outcomes["status"].isin(["error", "partial"])]
        )
        view = view.rename(columns={
            "ticker": tr("代码", "Ticker"),
            "status": tr("状态", "Status"),
            "data_source": tr("数据源", "Data Source"),
        })[[tr("代码", "Ticker"), tr("状态", "Status"), tr("数据源", "Data Source")]]
        st.dataframe(view, use_container_width=True, hide_index=True)
