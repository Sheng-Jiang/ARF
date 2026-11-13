"""Streamlit page: One-Click Weekly Report — 一键生成综合研报."""
import json
from pathlib import Path

import streamlit as st

from webapp.data import _open_conn
from webapp.mobile import inject_mobile_css
from webapp.ui import get_current_lang, render_sidebar, tr

is_en = get_current_lang() == "en"

inject_mobile_css()

st.title(tr("📝 一键生成综合研报", "📝 Generate Comprehensive Research Report"))
st.caption(
    tr(
        "一键生成包含 ARF 快照概览、泡沫温度计趋势、Top 5 中国 A+H 股策略回测与 Gemini AI 综合研判的独立 HTML 研报。",
        "One-click standalone HTML report covering the ARF snapshot overview, bubble thermometer trend, "
        "backtest of the Top 5 China A+H strategy, and Gemini AI synthesis.",
    )
)

as_of = render_sidebar()
if as_of is None:
    st.stop()

# ── Configuration ────────────────────────────────────────────────────────────
st.sidebar.divider()
st.sidebar.info(
    tr(
        "💡 提示：本页面主要用于浏览、预览和下载已生成的历史周报。",
        "💡 Tip: this page is mainly for browsing, previewing and downloading generated historical reports.",
    )
)

st.info(
    tr(
        "💡 **关于研报生成：**\n\n"
        "完整的周度研报包含全量数据抓取、中股 Top 5 策略回测以及 Gemini AI 的跨维度深度研判，计算耗时通常为 2–5 分钟。\n\n"
        "为了确保执行稳定、避免页面请求超时，**研报生成已迁移至后台异步任务**。\n\n"
        "👉 请前往 **[⚙️ 系统管理](system-admin)** 页面触发管道运行。系统将通过 Cloud Run 异步作业自动完成计算并保存结果。运行过程中您可以在该页面实时查看看板与进度条。任务完成后，本页面将自动刷新并加载最新生成的研报。",
        "💡 **About report generation:**\n\n"
        "A full weekly report includes comprehensive data fetching, the Top 5 China-leg strategy backtest, "
        "and a cross-dimensional Gemini AI synthesis; computation typically takes 2–5 minutes.\n\n"
        "To ensure stable execution and avoid page request timeouts, **report generation has moved to a background async job**.\n\n"
        "👉 Go to the **[⚙️ System Administration](system-admin)** page to trigger the pipeline. The system runs the "
        "computation automatically via a Cloud Run async job and saves the result. While it runs you can watch the "
        "dashboard and progress bar there. When the job finishes, this page reloads automatically and loads the latest report.",
    )
)

# ── Historical Reports ───────────────────────────────────────────────────────
st.divider()
st.subheader(tr("📚 历史研报", "📚 Historical Reports"))

def get_report_html_content(report_path_str: str, as_of_date_str: str) -> str | None:
    # 1. Try local read if path exists
    path = Path(report_path_str)
    if path.exists():
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            pass
    
    # 2. Check GCS if local read failed or file is absent
    import os

    from arf import storage
    if storage.is_gcs_mode():
        try:
            from google.cloud import storage as gcs_storage
            bucket_name = os.getenv("GCS_BUCKET")
            if bucket_name:
                prefix = os.getenv("GCS_PREFIX", "").strip("/")
                # Standardize object key to reports/weekly_report_YYYY-MM-DD.html
                # and override with relative report_path if it starts with reports/
                cleaned_path = report_path_str.replace("\\", "/").strip("/")
                if cleaned_path.startswith("reports/"):
                    object_name = cleaned_path
                else:
                    object_name = f"reports/weekly_report_{as_of_date_str}.html"
                
                key = f"{prefix}/{object_name}" if prefix else object_name
                
                bucket = gcs_storage.Client().bucket(bucket_name)
                blob = bucket.blob(key)
                if blob.exists():
                    return blob.download_as_text(encoding="utf-8")
        except Exception:
            pass
    return None

try:
    conn = _open_conn()
    try:
        reports_df = conn.execute(
            "SELECT * FROM weekly_reports ORDER BY as_of_date DESC LIMIT 20"
        ).fetchdf()
    except Exception:
        reports_df = None

    if reports_df is not None and not reports_df.empty:
        # Let user select from dropdown
        dates_list = reports_df["as_of_date"].tolist()
        
        def _fmt_report_option(d):
            row = reports_df[reports_df["as_of_date"] == d].iloc[0]
            src = row.get("trigger_source", "manual")
            src_lbl = (
                tr("自动调度", "Automated")
                if src in ("scheduler", "pipeline")
                else tr("手动生成", "Manual")
            )
            # format option date
            import pandas as pd
            d_str = pd.to_datetime(d).strftime('%Y-%m-%d')
            return f"📅 {d_str} ({src_lbl})"

        selected_date = st.selectbox(
            tr("🔎 选择要审查/下载的历史周报", "🔎 Select a historical report to review / download"),
            options=dates_list,
            format_func=_fmt_report_option,
            key="hist_report_select",
        )
        
        row_sel = reports_df[reports_df["as_of_date"] == selected_date].iloc[0]
        # Clean selected date format to YYYY-MM-DD to avoid Timestamp string conversion issues
        import pandas as pd
        clean_date_str = pd.to_datetime(selected_date).strftime('%Y-%m-%d')
        html_content = get_report_html_content(row_sel.get("report_path", ""), clean_date_str)
        
        if html_content:
            st.success(
                tr(
                    f"已成功加载 {selected_date} 的周度研报！",
                    f"Successfully loaded the weekly report for {selected_date}!",
                )
            )

            c_dl, c_src = st.columns([1, 3])
            with c_dl:
                st.download_button(
                    label=tr("⬇️ 下载 HTML 研报", "⬇️ Download HTML Report"),
                    data=html_content,
                    file_name=f"ARF_Weekly_Report_{selected_date}.html",
                    mime="text/html",
                    key=f"dl_hist_{selected_date}",
                    use_container_width=True,
                )
            with c_src:
                st.info(
                    tr(
                        f"**报告生成时间：** {row_sel.get('generated_at', '—')}  \n"
                        f"**覆盖股票数：** {len(json.loads(row_sel.get('stocks_covered', '[]')))} 只",
                        f"**Report generated at:** {row_sel.get('generated_at', '—')}  \n"
                        f"**Tickers covered:** {len(json.loads(row_sel.get('stocks_covered', '[]')))}",
                    )
                )

            # Show Gemini interpretation
            gemini_sum = row_sel.get("gemini_summary", "")
            if gemini_sum and not gemini_sum.startswith("⚠️"):
                st.markdown(tr("### 🤖 Gemini AI 综合研判 (历史记录)", "### 🤖 Gemini AI Synthesis (Historical)"))
                st.markdown(gemini_sum)

            # Preview the report inside an expander
            with st.expander(
                tr("👁️ 预览完整 HTML 研报内容 (嵌入式页面)", "👁️ Preview Full HTML Report (embedded page)"),
                expanded=False,
            ):
                st.components.v1.html(html_content, height=800, scrolling=True)
        else:
            st.error(
                tr(
                    "无法加载该周研报的 HTML 文件内容。",
                    "Could not load the HTML content of this weekly report.",
                )
            )
    else:
        st.caption(
            tr(
                "暂无历史研报记录。点击上方按钮生成第一份。",
                "No historical reports yet. Click the button above to generate the first one.",
            )
        )
except Exception as exc:
    st.caption(tr(f"加载历史研报发生错误: {exc}", f"Error loading historical reports: {exc}"))
