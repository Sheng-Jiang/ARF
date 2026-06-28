"""Streamlit page: One-Click Weekly Report — 一键生成综合研报."""
import streamlit as st
import json
from datetime import date
from pathlib import Path

from webapp.data import _open_conn, list_dates
from webapp.ui import render_sidebar

st.set_page_config(
    page_title="一键研报 — ARF Weekly Report",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📝 一键生成综合研报")
st.caption(
    "一键生成包含 ARF 快照概览、泡沫温度计趋势、Top 5 中国 A+H 股策略回测与 Gemini AI 综合研判的独立 HTML 研报。"
)

as_of = render_sidebar()
if as_of is None:
    st.stop()

# ── Configuration ────────────────────────────────────────────────────────────
st.sidebar.divider()
st.sidebar.subheader("📝 研报配置")
enable_gemini = st.sidebar.checkbox(
    "启用 Gemini AI 综合研判",
    value=True,
    help="由 Gemini 2.5 Pro 联网检索最新新闻，撰写跨维度综合研报。需配置 GEMINI_API_KEY。",
)
lookback_months = st.sidebar.selectbox(
    "回测窗口",
    options=[3, 6, 9, 12],
    index=1,
    format_func=lambda x: f"{x} 个月",
    help="策略回测的历史窗口长度",
)
top_n = st.sidebar.number_input(
    "回测股票数量",
    min_value=3,
    max_value=10,
    value=5,
    help="从中国 A+H 股中选取 ARF 最高的 N 只进行回测",
)

# ── Main Button ──────────────────────────────────────────────────────────────
col_btn, col_info = st.columns([1, 3])
with col_btn:
    generate_btn = st.button(
        "🚀 一键生成本周研报",
        use_container_width=True,
        type="primary",
    )
with col_info:
    st.info(
        f"将基于 **{as_of}** 快照，回测 Top {top_n} 中国 A+H 股（{lookback_months} 个月窗口），"
        f"运行 3 种量化策略，{'并由 Gemini AI 撰写综合研判' if enable_gemini else '不含 AI 研判'}。"
        f" 预计耗时 2–5 分钟。"
    )

if generate_btn:
    # Import the engine
    from arf.oneclick import (
        BACKTEST_LOOKBACK_DAYS,
        build_report_data,
        generate_report_html,
        select_top_china_stocks,
        run_batch_backtests,
        _backtest_summary_for_gemini,
    )
    import arf.oneclick as oneclick_mod

    # Override lookback from sidebar
    oneclick_mod.BACKTEST_LOOKBACK_DAYS = lookback_months * 30
    oneclick_mod.TOP_N_STOCKS = top_n

    progress = st.progress(0, text="正在加载快照数据...")

    # Step 1: Load data
    try:
        from arf.db import init_db, query_snapshot, query_thermometer_series, upsert_weekly_report
        from arf.oneclick import (
            ReportData,
            _compute_thermo_deltas,
            _render_thermo_chart,
            _render_valuation_chart,
        )
        from webapp.data import get_db_path
        import os

        db_path = get_db_path()
        conn = init_db(db_path)
        snapshot = query_snapshot(conn, as_of)
        thermo = query_thermometer_series(conn)
        conn.close()

        us = snapshot[snapshot["leg"] == "US"]
        china = snapshot[snapshot["leg"] == "China"]
        scored = snapshot[snapshot["leg"].isin(["US", "China"])]

        report = ReportData(as_of=as_of)
        report.us_df = us
        report.china_df = china
        report.d1_us = int((us["decile"] == 1).sum()) if len(us) else 0
        report.d1_china = int((china["decile"] == 1).sum()) if len(china) else 0
        report.froth_us = int((us["froth_flag"] == True).sum()) if len(us) else 0  # noqa: E712
        report.froth_china = int((china["froth_flag"] == True).sum()) if len(china) else 0  # noqa: E712
        report.thermo_deltas = _compute_thermo_deltas(thermo)
        report.thermo_chart_html = _render_thermo_chart(thermo)
        report.valuation_chart_html = _render_valuation_chart(thermo)

        progress.progress(20, text="快照数据加载完成 ✓ 正在选取 Top 股票...")
    except Exception as exc:
        st.error(f"加载快照数据失败: {exc}")
        st.exception(exc)
        st.stop()

    # Step 2: Select top stocks and run backtests
    try:
        top_china = select_top_china_stocks(scored, n=top_n)
        if top_china.empty:
            st.warning("当前快照中无可评分的中国 A+H 股。跳过回测。")
        else:
            tickers = top_china["ticker"].tolist()
            progress.progress(30, text=f"正在回测 {len(tickers)} 只股票 × 3 策略... ({', '.join(tickers)})")
            report.backtest_stocks = run_batch_backtests(top_china, as_of, lookback_days=lookback_months * 30)
            progress.progress(70, text="策略回测完成 ✓")
    except Exception as exc:
        st.warning(f"回测过程出现错误（研报仍将生成）: {exc}")

    # Step 3: Gemini synthesis
    if enable_gemini:
        progress.progress(75, text="正在调用 Gemini AI 生成综合研判...")
        try:
            from webapp.gemini import generate_weekly_synthesis, is_enabled
            if is_enabled():
                synthesis = generate_weekly_synthesis(report)
                report.gemini_synthesis = synthesis.get("report_text", "")
                report.gemini_citations = [
                    {"title": getattr(c, "title", "") or getattr(c, "uri", ""),
                     "uri": getattr(c, "uri", "")}
                    for c in synthesis.get("citations", [])
                ]
            else:
                st.info("未配置 GEMINI_API_KEY — 研报将不含 AI 综合研判。")
        except Exception as exc:
            st.warning(f"Gemini 综合研判生成失败: {exc}")
        progress.progress(90, text="AI 综合研判完成 ✓ 正在渲染报告...")
    else:
        progress.progress(90, text="正在渲染报告...")

    # Step 4: Render HTML
    try:
        html = generate_report_html(report)
        report_dir = Path(os.getenv("REPORT_DIR", "reports"))
        report_dir.mkdir(parents=True, exist_ok=True)
        out_path = report_dir / f"weekly_report_{as_of}.html"
        out_path.write_text(html, encoding="utf-8")

        # Record in DB
        try:
            conn = init_db(db_path)
            upsert_weekly_report(
                conn,
                as_of_date=as_of,
                report_path=str(out_path),
                gemini_summary=report.gemini_synthesis[:2000] if report.gemini_synthesis else "",
                stocks_covered=json.dumps([s.ticker for s in report.backtest_stocks]),
                trigger_source="webapp",
            )
            conn.close()

            # Sync database and HTML report back to GCS if in GCS mode
            from arf import storage
            if storage.is_gcs_mode():
                storage.upload_db(db_path)
                storage.upload_artifact(out_path, f"reports/weekly_report_{as_of}.html")
        except Exception:
            pass

        progress.progress(100, text="✅ 研报生成完成！")

        # Success message + download
        st.success(f"🎉 研报已生成并保存至 `{out_path}`")

        col_dl, col_preview = st.columns([1, 3])
        with col_dl:
            st.download_button(
                label="⬇️ 下载 HTML 研报",
                data=html,
                file_name=f"ARF_Weekly_Report_{as_of}.html",
                mime="text/html",
                use_container_width=True,
            )

        # Preview key sections inline
        st.divider()
        st.subheader("📋 研报预览")

        # Metrics preview
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("🇺🇸 D1 数量", report.d1_us)
        m2.metric("🇺🇸 泡沫预警", report.froth_us)
        m3.metric("🇨🇳 D1 数量", report.d1_china)
        m4.metric("🇨🇳 泡沫预警", report.froth_china)

        # Backtest summary
        if report.backtest_stocks:
            st.subheader("🏁 回测结果摘要")
            bt_rows = []
            for s in report.backtest_stocks:
                bt_rows.append({
                    "代码": s.ticker,
                    "公司": s.name,
                    "技术评分": f"{s.tech_score:.1f}" if s.tech_score else "N/A",
                    "最优策略": s.best_strategy.split(" ")[0] if s.best_strategy else "—",
                    "夏普比率": f"{s.best_sharpe:.2f}",
                    "年化收益%": f"{s.best_return:.1f}",
                    "最大回撤%": f"{s.best_max_dd:.1f}",
                })
            import pandas as pd
            st.dataframe(pd.DataFrame(bt_rows), hide_index=True, use_container_width=True)

        # Gemini synthesis preview
        if report.gemini_synthesis:
            st.subheader("🤖 Gemini AI 综合研判")
            st.markdown(report.gemini_synthesis)

            if report.gemini_citations:
                with st.expander(f"🔗 引用来源 ({len(report.gemini_citations)})", expanded=False):
                    for c in report.gemini_citations:
                        title = c.get("title") or c.get("uri", "")
                        uri = c.get("uri", "")
                        if uri:
                            st.markdown(f"- [{title}]({uri})")

    except Exception as exc:
        st.error(f"渲染研报失败: {exc}")
        st.exception(exc)

# ── Historical Reports ───────────────────────────────────────────────────────
st.divider()
st.subheader("📚 历史研报")

try:
    conn = _open_conn()
    # Use raw query since _open_conn is read-only and may not have the table
    try:
        reports_df = conn.execute(
            "SELECT * FROM weekly_reports ORDER BY as_of_date DESC LIMIT 20"
        ).fetchdf()
    except Exception:
        reports_df = None

    if reports_df is not None and not reports_df.empty:
        for _, r in reports_df.iterrows():
            report_path = Path(r.get("report_path", ""))
            as_of_date = r.get("as_of_date", "")
            generated_at = r.get("generated_at", "")
            stocks = r.get("stocks_covered", "[]")
            trigger = r.get("trigger_source", "")

            try:
                stocks_list = json.loads(stocks) if stocks else []
            except Exception:
                stocks_list = []

            col_info2, col_action = st.columns([4, 1])
            with col_info2:
                st.markdown(
                    f"**{as_of_date}** · 来源: `{trigger}` · "
                    f"覆盖: {', '.join(stocks_list[:5]) if stocks_list else '—'} · "
                    f"生成时间: {generated_at}"
                )
            with col_action:
                if report_path.exists():
                    html_content = report_path.read_text(encoding="utf-8")
                    st.download_button(
                        label="⬇️",
                        data=html_content,
                        file_name=f"ARF_Weekly_{as_of_date}.html",
                        mime="text/html",
                        key=f"dl_{as_of_date}",
                    )
    else:
        st.caption("暂无历史研报记录。点击上方按钮生成第一份。")
except Exception:
    st.caption("暂无历史研报记录。")
