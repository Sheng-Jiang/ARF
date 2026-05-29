"""Shared UI helpers: sidebar, table renderer, scatter plot, Gemini cards."""
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from webapp import gemini
from webapp.data import list_dates, refresh_data


def render_sidebar() -> date | None:
    """Render date selector + refresh button; return selected date."""
    dates = list_dates()
    if not dates:
        st.sidebar.warning("未找到快照数据，请先运行数据管道。")
        return None
    date_strs = [str(d) for d in dates]
    sel = st.sidebar.selectbox("快照日期", date_strs, key="selected_date_str")
    if st.sidebar.button("刷新数据"):
        refresh_data()
        st.rerun()
    return date.fromisoformat(sel)


def _fmt_num(v: object, decimals: int = 1) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    try:
        return f"{float(v):.{decimals}f}"
    except (TypeError, ValueError):
        return "—"


def _fmt_pct(v: object) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    try:
        return f"{float(v) * 100:.1f}%"
    except (TypeError, ValueError):
        return "—"


def _build_display_df(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in df.sort_values("arf", ascending=False, na_position="last").iterrows():
        d = r.get("decile")
        rows.append({
            "代码": r.get("ticker", ""),
            "公司": r.get("name", ""),
            "层级": r.get("layer", ""),
            "D": int(d) if pd.notna(d) else None,
            "ARF": _fmt_num(r.get("arf")),
            "E": _fmt_num(r.get("e_score")),
            "V": _fmt_num(r.get("v_score")),
            "★": "★" if r.get("froth_flag") else "",
            "预期P/E": _fmt_num(r.get("forward_pe")),
            "P/S": _fmt_num(r.get("ps_ratio")),
            "营收同比": _fmt_pct(r.get("revenue_yoy_growth")),
            "ROE": _fmt_pct(r.get("roe")),
            "_decile": d,
            "_froth": bool(r.get("froth_flag")),
        })
    return pd.DataFrame(rows)


def _row_style(row: pd.Series) -> list[str]:
    d = row.get("_decile")
    froth = bool(row.get("_froth", False))
    try:
        d = int(d) if d is not None and not pd.isna(d) else None
    except (TypeError, ValueError):
        d = None

    if d == 1:
        bg = "background-color: #ffcccc"
    elif d == 2:
        bg = "background-color: #ffe0b3"
    elif d is not None and d >= 8:
        bg = "background-color: #d4edda"
    else:
        bg = ""

    weight = "font-weight: bold" if froth else ""
    style = "; ".join(s for s in [bg, weight] if s)
    return [style] * len(row)


def render_table(df: pd.DataFrame) -> None:
    """Render a ranked leg table with decile row colouring."""
    display = _build_display_df(df)
    styled = display.style.apply(_row_style, axis=1).hide(["_decile", "_froth"], axis="columns")
    st.dataframe(styled, use_container_width=True, hide_index=True)


_DECILE_COLOR = {
    1: "#d62728", 2: "#ff7f0e", 3: "#e8b85d", 4: "#bcbd22",
    5: "#999999", 6: "#98df8a", 7: "#4caf50", 8: "#2ca02c",
    9: "#1a7a20", 10: "#0d5e14",
}


def scatter_plot(df: pd.DataFrame, leg_name: str) -> go.Figure:
    """E-score vs V-score scatter; bubbles sized by market cap, coloured by decile."""
    plot_df = df.dropna(subset=["e_score", "v_score"]).copy()
    if plot_df.empty:
        return go.Figure()

    mktcap = plot_df.get("market_cap_usd", pd.Series([1.0] * len(plot_df), index=plot_df.index))
    mktcap = mktcap.fillna(1.0).clip(lower=1.0)
    sizes = (mktcap / mktcap.max() * 55 + 8).tolist()

    colors = [
        _DECILE_COLOR.get(int(d), "#999999") if pd.notna(d) else "#999999"
        for d in plot_df.get("decile", pd.Series([None] * len(plot_df), index=plot_df.index))
    ]

    def _hover(row: pd.Series) -> str:
        d = int(row["decile"]) if pd.notna(row.get("decile")) else "?"
        ps = _fmt_num(row.get("ps_ratio"))
        roe = _fmt_pct(row.get("roe"))
        return (
            f"<b>{row['ticker']}</b> — {row.get('name', '')}<br>"
            f"ARF {_fmt_num(row.get('arf'))}  D{d}  {'★' if row.get('froth_flag') else ''}<br>"
            f"E分 {_fmt_num(row.get('e_score'))}  V分 {_fmt_num(row.get('v_score'))}<br>"
            f"P/S {ps}  ROE {roe}"
        )

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=plot_df["e_score"].tolist(),
        y=plot_df["v_score"].tolist(),
        mode="markers+text",
        marker=dict(
            size=sizes,
            color=colors,
            opacity=0.85,
            line=dict(width=1, color="#333"),
        ),
        text=plot_df["ticker"].tolist(),
        textposition="top center",
        hovertext=[_hover(row) for _, row in plot_df.iterrows()],
        hoverinfo="text",
    ))
    fig.add_hline(y=50, line_dash="dot", line_color="gray", opacity=0.4)
    fig.add_vline(x=50, line_dash="dot", line_color="gray", opacity=0.4)

    quadrant_style = dict(xref="x", yref="y", showarrow=False,
                          font=dict(size=10, color="rgba(120,120,120,0.6)"))
    fig.add_annotation(x=90, y=90, text="高风险泡沫区", **quadrant_style)
    fig.add_annotation(x=90, y=8,  text="基本面支撑区", **quadrant_style)
    fig.add_annotation(x=8,  y=90, text="非AI高估区",  **quadrant_style)
    fig.add_annotation(x=8,  y=8,  text="低参与低估值", **quadrant_style)

    fig.update_layout(
        title=f"{leg_name} — AI曝光度（E）vs 估值拉伸（V）",
        xaxis_title="E分 — AI曝光度 →",
        yaxis_title="V分 — 估值拉伸 →",
        xaxis=dict(range=[-5, 105]),
        yaxis=dict(range=[-5, 105]),
        height=480,
        showlegend=False,
        margin=dict(t=50, b=40),
    )
    return fig


def render_ask_gemini(
    snapshot_df: pd.DataFrame,
    as_of: date,
    *,
    section_key: str,
    label_intro: str,
) -> None:
    """Render the "Ask Gemini" button + per-stock expandable cards.

    `section_key` namespaces the session_state cache so multiple pages don't collide.
    `label_intro` is the caption above the button explaining what cohort is covered.
    """
    st.markdown("### 🤖 Ask Gemini — 新闻与叙事补充")
    st.caption(label_intro)

    if not gemini.is_enabled():
        st.info(
            "未配置 Gemini API 密钥。请在 Cloud Run 上挂载 `GEMINI_API_KEY` "
            "（推荐通过 Secret Manager），按钮即可启用。"
        )
        return

    cohort = gemini.cohort_for_overview(snapshot_df)
    if not cohort:
        st.warning("该快照无评分股票，无法生成新闻摘要。")
        return

    cache_key_str = gemini.to_session_cache_key(as_of, cohort)
    cache_slot = f"gemini_cache_{section_key}"
    cache = st.session_state.setdefault(cache_slot, {})

    cached_report = cache.get(cache_key_str)
    btn_label = "🔄 重新生成" if cached_report else f"✨ 询问 Gemini（{len(cohort)} 只股票）"

    if st.button(btn_label, key=f"ask_gemini_btn_{section_key}"):
        with st.spinner("Gemini 正在检索最新新闻并撰写摘要……（约15–30秒）"):
            try:
                report = gemini.summarize_stocks(snapshot_df, cohort, as_of)
                cache[cache_key_str] = report
                cached_report = report
            except Exception as exc:  # noqa: BLE001
                st.error(f"调用 Gemini 失败：{exc}")
                return

    if cached_report is None:
        return

    if not cached_report.stocks:
        st.warning("Gemini 未返回任何可解析的股票卡片。原始输出：")
        st.code(cached_report.raw_text[:2000] or "(空)")
        return

    name_lookup = dict(
        zip(snapshot_df["ticker"], snapshot_df["name"], strict=False)
    )

    for s in cached_report.stocks:
        display_name = name_lookup.get(s.ticker, s.name)
        header = f"**{s.ticker}** · {display_name}"
        if s.headline:
            header += f" — {s.headline}"
        with st.expander(header, expanded=False):
            if s.bullets:
                for b in s.bullets:
                    st.markdown(f"- {b}")
            else:
                st.caption("（无要点）")
            if s.reconcile:
                st.markdown(f"**与ARF读数的关系：** {s.reconcile}")

    if cached_report.citations:
        with st.expander(f"📚 引用来源（{len(cached_report.citations)}）", expanded=False):
            for c in cached_report.citations:
                title = c.title or c.uri
                st.markdown(f"- [{title}]({c.uri})")

    st.caption(f"模型：{cached_report.model} · 快照日期：{cached_report.as_of}")
