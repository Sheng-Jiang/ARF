"""Shared UI helpers: sidebar, table renderer, scatter plot, Gemini cards."""
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from webapp import gemini
from webapp.data import (
    list_dates,
    load_gemini_summaries,
    load_research_reports,
    load_research_synthesis,
    refresh_data,
)
from webapp.mobile import is_mobile

_LANG_QUERY_KEY = "lang"
_SUPPORTED_LANGS = ("en", "zh")


def _lang_from_query() -> str | None:
    """Read ?lang=... and normalise it to 'en'/'zh' (None if absent/invalid)."""
    raw = st.query_params.get(_LANG_QUERY_KEY)
    if isinstance(raw, (list, tuple)):
        raw = raw[0] if raw else None
    if not raw:
        return None
    token = str(raw).strip().lower()
    for code in _SUPPORTED_LANGS:
        if token.startswith(code):
            return code
    return None


def get_current_lang() -> str:
    """Return active language code ('en' or 'zh')."""
    query_lang = _lang_from_query()
    if "lang" not in st.session_state:
        st.session_state["lang"] = query_lang or "en"
    elif query_lang is not None and not st.session_state.get("_lang_user_set"):
        # Honour deep links (?lang=zh) unless the user already chose explicitly.
        st.session_state["lang"] = query_lang
    return str(st.session_state["lang"])


def set_current_lang(lang: str) -> None:
    """Update active language in session_state and query_params."""
    st.session_state["lang"] = lang
    st.session_state["_lang_user_set"] = True
    st.query_params[_LANG_QUERY_KEY] = lang


def tr(zh: str, en: str) -> str:
    """Translate string based on active language."""
    return en if get_current_lang() == "en" else zh


def render_language_switcher() -> None:
    """Sidebar language toggle.

    Rendered once from ``app.py`` (not from ``render_sidebar``) so that every
    page — including those without a date selector — gets the same switcher.
    """
    curr_lang = get_current_lang()
    sel_lang = st.sidebar.radio(
        "🌐 Language / 语言",
        ["English", "中文"],
        index=0 if curr_lang == "en" else 1,
        horizontal=True,
        key="_sidebar_lang_selector",
    )
    new_lang = "en" if sel_lang == "English" else "zh"
    if new_lang != curr_lang:
        set_current_lang(new_lang)
        st.rerun()


def render_freshness_badge(latest: date | None = None) -> None:
    """Sidebar badge for how current the latest snapshot is (weekly cadence)."""
    from arf.health import freshness_status, next_monday_utc

    dates = list_dates() if latest is None else [latest]
    latest_as_of = dates[0] if dates else None
    status = freshness_status(latest_as_of)
    icon = {
        "fresh": "🟢",
        "stale": "🟡",
        "critical": "🔴",
        "unknown": "⚪",
    }.get(status.level, "⚪")

    is_en = get_current_lang() == "en"
    if is_en:
        en_labels = {
            "fresh": "Up to Date",
            "stale": "Stale",
            "critical": "Outdated",
            "unknown": "Unknown",
        }
        lbl = en_labels.get(status.level, status.level)
        st.sidebar.markdown(f"**Data Freshness** {icon} {lbl}")
        if latest_as_of is None:
            detail = "No ARF snapshots in the database. Run the pipeline first."
        elif status.level == "fresh" and (status.age_days or 0) < 0:
            detail = f"Latest snapshot {latest_as_of} is dated in the future (possible timezone issue)."
        elif status.level == "fresh":
            detail = f"Latest snapshot {latest_as_of}, {status.age_days} days ago (within weekly cadence)."
        elif status.level == "stale":
            detail = (
                f"Latest snapshot {latest_as_of}, {status.age_days} days ago. "
                "Past the weekly window — check that the scheduler ran."
            )
        elif status.level == "critical":
            detail = (
                f"Latest snapshot {latest_as_of}, {status.age_days} days ago. "
                "Beyond two weeks — rankings are unreliable; trigger the pipeline now."
            )
        else:
            detail = f"Latest snapshot {latest_as_of}."
        st.sidebar.caption(detail)
        if status.level in ("stale", "critical"):
            nxt = next_monday_utc()
            st.sidebar.caption(f"Next scheduled run (Mon UTC): {nxt}")
    else:
        st.sidebar.markdown(f"**数据新鲜度** {icon} {status.label}")
        st.sidebar.caption(status.detail)
        if status.level in ("stale", "critical"):
            nxt = next_monday_utc()
            st.sidebar.caption(f"下次计划周更（周一 UTC）：{nxt}")


def render_sidebar() -> date | None:
    """Render date selector + refresh button; return selected date.

    The language switcher lives in ``render_language_switcher`` and is rendered
    once from ``app.py`` so it appears on every page.
    """
    dates = list_dates()
    if not dates:
        st.sidebar.warning(tr("未找到快照数据，请先运行数据管道。", "No snapshot data found. Please run data pipeline first."))
        render_freshness_badge(None)
        return None
    render_freshness_badge(dates[0])
    date_strs = [str(d) for d in dates]
    sel = st.sidebar.selectbox(tr("快照日期", "Snapshot Date"), date_strs, key="selected_date_str")
    if st.sidebar.button(tr("刷新数据", "Refresh Data")):
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
    is_en = get_current_lang() == "en"
    cols = (
        {
            "ticker": "Ticker",
            "name": "Company",
            "layer": "Layer",
            "fwd_pe": "Fwd P/E",
            "ps": "P/S",
            "rev": "Rev YoY",
            "roe": "ROE",
        }
        if is_en
        else {
            "ticker": "代码",
            "name": "公司",
            "layer": "层级",
            "fwd_pe": "预期P/E",
            "ps": "P/S",
            "rev": "营收同比",
            "roe": "ROE",
        }
    )
    rows = []
    for _, r in df.sort_values("arf", ascending=False, na_position="last").iterrows():
        d = r.get("decile")
        rows.append({
            cols["ticker"]: r.get("ticker", ""),
            cols["name"]: r.get("name", ""),
            cols["layer"]: r.get("layer", ""),
            "D": int(d) if pd.notna(d) else None,
            "ARF": _fmt_num(r.get("arf")),
            "E": _fmt_num(r.get("e_score")),
            "V": _fmt_num(r.get("v_score")),
            "★": "★" if r.get("froth_flag") else "",
            cols["fwd_pe"]: _fmt_num(r.get("forward_pe")),
            cols["ps"]: _fmt_num(r.get("ps_ratio")),
            cols["rev"]: _fmt_pct(r.get("revenue_yoy_growth")),
            cols["roe"]: _fmt_pct(r.get("roe")),
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
    """Render a ranked leg table with decile row colouring.

    On phones the interactive ``st.dataframe`` widget captures touch and is awkward
    to scroll past, so we emit a static HTML table (row colours preserved) inside a
    horizontally-scrollable box — it flows with the page instead of floating.
    """
    display = _build_display_df(df)
    styled = display.style.apply(_row_style, axis=1).hide(["_decile", "_froth"], axis="columns")
    if is_mobile():
        html = styled.hide(axis="index").to_html()
        st.markdown(
            '<div style="overflow-x:auto;-webkit-overflow-scrolling:touch;font-size:0.85rem">'
            + html
            + "</div>",
            unsafe_allow_html=True,
        )
    else:
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
    is_en = get_current_lang() == "en"

    def _hover(row: pd.Series) -> str:
        d = int(row["decile"]) if pd.notna(row.get("decile")) else "?"
        ps = _fmt_num(row.get("ps_ratio"))
        roe = _fmt_pct(row.get("roe"))
        e_lbl = "E" if is_en else "E分"
        v_lbl = "V" if is_en else "V分"
        return (
            f"<b>{row['ticker']}</b> — {row.get('name', '')}<br>"
            f"ARF {_fmt_num(row.get('arf'))}  D{d}  {'★' if row.get('froth_flag') else ''}<br>"
            f"{e_lbl} {_fmt_num(row.get('e_score'))}  {v_lbl} {_fmt_num(row.get('v_score'))}<br>"
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
    q_labels = (
        ("High-Risk Bubble", "Fundamentally Supported", "AI-Exposed & Overvalued", "Low Exposure, Low Valuation")
        if is_en
        else ("高风险泡沫区", "基本面支撑区", "非AI高估区", "低参与低估值")
    )
    fig.add_annotation(x=90, y=90, text=q_labels[0], **quadrant_style)
    fig.add_annotation(x=90, y=8,  text=q_labels[1], **quadrant_style)
    fig.add_annotation(x=8,  y=90, text=q_labels[2], **quadrant_style)
    fig.add_annotation(x=8,  y=8,  text=q_labels[3], **quadrant_style)

    fig.update_layout(
        title=(
            f"{leg_name} — AI Exposure (E) vs Valuation Stretch (V)"
            if is_en
            else f"{leg_name} — AI曝光度（E）vs 估值拉伸（V）"
        ),
        xaxis_title="E — AI Exposure →" if is_en else "E分 — AI曝光度 →",
        yaxis_title="V — Valuation Stretch →" if is_en else "V分 — 估值拉伸 →",
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
    st.markdown(tr("### 🤖 Ask Gemini — 新闻与叙事补充", "### 🤖 Ask Gemini — News & Narrative"))
    st.caption(label_intro)

    if not gemini.is_enabled():
        st.info(
            tr(
                "未配置 Gemini API 密钥。请在 Cloud Run 上挂载 `GEMINI_API_KEY` "
                "（推荐通过 Secret Manager），按钮即可启用。",
                "No Gemini API key configured. Mount `GEMINI_API_KEY` on Cloud Run "
                "(Secret Manager recommended) to enable this button.",
            )
        )
        return

    cohort = gemini.cohort_for_overview(snapshot_df)
    if not cohort:
        st.warning(tr("该快照无评分股票，无法生成新闻摘要。", "No scored stocks in this snapshot — cannot generate a news summary."))
        return

    cache_key_str = gemini.to_session_cache_key(as_of, cohort)
    cache_slot = f"gemini_cache_{section_key}"
    cache = st.session_state.setdefault(cache_slot, {})

    # 1) Try session cache (already refreshed this browser session)
    cached_report = cache.get(cache_key_str)
    is_precomputed = False

    # 2) Fall back to pipeline pre-compute in DuckDB
    if cached_report is None:
        try:
            db_rows = load_gemini_summaries(as_of, gemini.OVERVIEW_COHORT_KEY)
        except Exception:  # noqa: BLE001
            db_rows = None
        precomputed = gemini.db_rows_to_report(db_rows, as_of) if db_rows is not None else None
        if precomputed and precomputed.stocks:
            cached_report = precomputed
            is_precomputed = True

    btn_label = (
        tr(f"🔄 重新生成最新新闻（{len(cohort)} 只）", f"🔄 Regenerate Latest News ({len(cohort)} tickers)")
        if cached_report
        else tr(f"✨ 询问 Gemini（{len(cohort)} 只股票）", f"✨ Ask Gemini ({len(cohort)} tickers)")
    )

    if st.button(btn_label, key=f"ask_gemini_btn_{section_key}"):
        with st.spinner(tr("Gemini 正在检索最新新闻并撰写摘要……（约30–45秒）", "Gemini is searching live news and drafting summaries… (~30–45s)")):
            try:
                report = gemini.summarize_stocks(snapshot_df, cohort, as_of)
                cache[cache_key_str] = report
                cached_report = report
                is_precomputed = False
            except Exception as exc:  # noqa: BLE001
                st.error(tr(f"调用 Gemini 失败：{exc}", f"Gemini call failed: {exc}"))
                return

    if cached_report is None:
        st.caption(tr("点击上方按钮，由 Gemini 联网检索此快照中股票的最新新闻。", "Click the button above to have Gemini search live news for the stocks in this snapshot."))
        return

    if not cached_report.stocks:
        st.warning(tr("Gemini 未返回任何可解析的股票卡片。原始输出：", "Gemini returned no parseable stock cards. Raw output:"))
        st.code(cached_report.raw_text[:2000] or tr("(空)", "(empty)"))
        return

    if is_precomputed:
        st.info(
            tr(
                "📦 显示本次快照运行时预先生成的新闻摘要 · 点击「重新生成」获取实时最新版本。",
                "📦 Showing the news summary precomputed during this snapshot run · click Regenerate for a live version.",
            ),
            icon="📦",
        )

    name_lookup = dict(
        zip(snapshot_df["ticker"], snapshot_df["name"], strict=False)
    )

    total_sources = 0
    for s in cached_report.stocks:
        display_name = name_lookup.get(s.ticker, s.name)
        header = f"**{s.ticker}** · {display_name}"
        if s.headline:
            header += f" — {s.headline}"
        stock_citations = getattr(s, "citations", []) or []
        domain_mentions = getattr(s, "domain_mentions", []) or []
        source_count = len(stock_citations) or len(domain_mentions)
        total_sources += source_count
        if source_count:
            header += f"  · {source_count}🔗"

        with st.expander(header, expanded=False):
            if s.bullets:
                for b in s.bullets:
                    st.markdown(f"- {b}")
            else:
                st.caption(tr("（无要点）", "(no key points)"))
            if s.reconcile:
                st.markdown(tr(f"**与ARF读数的关系：** {s.reconcile}", f"**Reconciled with ARF readings:** {s.reconcile}"))

            if stock_citations:
                st.markdown(tr("**来源：**", "**Sources:**"))
                for c in stock_citations:
                    title = c.title or c.uri
                    st.markdown(f"- [{title}]({c.uri})")
            elif domain_mentions:
                st.markdown(tr("**引用来源：** ", "**Cited sources:** ") + " · ".join(f"`{d}`" for d in domain_mentions))

            queries = getattr(s, "search_queries", []) or []
            if queries:
                with st.expander(tr(f"🔍 检索关键词（{len(queries)}）", f"🔍 Search Queries ({len(queries)})"), expanded=False):
                    for q in queries:
                        st.markdown(f"- `{q}`")

    st.caption(
        tr(
            f"模型：{cached_report.model} · 快照日期：{cached_report.as_of} · 共 {total_sources} 条来源",
            f"Model: {cached_report.model} · Snapshot: {cached_report.as_of} · {total_sources} sources",
        )
    )


_CONSENSUS_DISPLAY_COLS_ZH = {
    "ticker": "代码",
    "name": "名称",
    "n_institutions": "机构数",
    "n_reports": "报告数",
    "rating_summary": "评级分布",
    "consensus_target": "一致目标价",
    "implied_upside_pct": "隐含空间%",
    "eps_forecast": "EPS预测",
    "latest_report": "最新研报",
}

_CONSENSUS_DISPLAY_COLS_EN = {
    "ticker": "Ticker",
    "name": "Company",
    "n_institutions": "Institutions",
    "n_reports": "Reports",
    "rating_summary": "Ratings",
    "consensus_target": "Consensus Target",
    "implied_upside_pct": "Implied Upside %",
    "eps_forecast": "EPS Forecast",
    "latest_report": "Latest Report",
}


def _consensus_display_cols() -> dict[str, str]:
    return _CONSENSUS_DISPLAY_COLS_EN if get_current_lang() == "en" else _CONSENSUS_DISPLAY_COLS_ZH


def render_research_synthesis(snapshot_df: pd.DataFrame, as_of: date) -> None:
    """Render the institutional-research consensus table + Gemini synthesis.

    Layer 1 (the deterministic consensus table) always renders when reports exist,
    even without a Gemini key. Layer 2 (the narrative) shows the batch-precomputed
    synthesis, with an on-demand regenerate button when a key is configured.
    """
    from arf.fetchers.research import compute_consensus

    display_cols = _consensus_display_cols()

    st.markdown(tr("### 🏦 机构研报综述 — 卖方一致预期 × ARF 估值", "### 🏦 Sell-Side Consensus × ARF Valuation"))
    st.caption(
        tr(
            "以本快照美股+中股各前5名（共10只）为口径，汇总各机构最新研报评级与目标价，"
            "并与 ARF 估值泡沫读数对照，识别卖方乐观与模型分歧之处。",
            "Covering the top 5 US and top 5 China names (10 tickers), aggregates the latest sell-side ratings and "
            "price targets from each institution and contrasts them with ARF bubble readings to surface gaps "
            "between analyst optimism and the model.",
        )
    )

    try:
        research_df = load_research_reports(as_of)
    except Exception as exc:  # noqa: BLE001
        st.info(tr(f"研报数据暂不可用：{exc}", f"Research data unavailable: {exc}"))
        return
    if research_df.empty:
        st.info(tr("本快照尚未抓取机构研报，将在下次数据管道运行时生成。", "No sell-side research has been fetched for this snapshot yet; it will be generated on the next pipeline run."))
        return

    cohort = gemini.cohort_for_overview(snapshot_df)
    prices = {
        str(t): p
        for t, p in zip(snapshot_df["ticker"], snapshot_df.get("price"), strict=False)
        if pd.notna(p)
    }
    consensus = compute_consensus(research_df, prices)
    if cohort:
        consensus = consensus[consensus["ticker"].isin(cohort)]
    if consensus.empty:
        st.info(tr("本快照评分股票暂无机构研报覆盖。", "No sell-side coverage for the scored stocks in this snapshot."))
        return

    name_lookup = dict(zip(snapshot_df["ticker"], snapshot_df["name"], strict=False))
    consensus = consensus.copy()
    consensus["name"] = consensus["ticker"].map(name_lookup)
    show = consensus[[c for c in display_cols if c in consensus.columns]]
    st.dataframe(
        show.rename(columns=display_cols),
        hide_index=True,
        use_container_width=True,
        column_config={
            display_cols["consensus_target"]: st.column_config.NumberColumn(format="%.2f"),
            display_cols["implied_upside_pct"]: st.column_config.NumberColumn(format="%+.1f"),
            display_cols["eps_forecast"]: st.column_config.NumberColumn(format="%.2f"),
        },
    )

    # Layer 2 — narrative synthesis.
    try:
        synth_df = load_research_synthesis(as_of)
    except Exception:  # noqa: BLE001
        synth_df = None
    synth_text = ""
    synth_model = ""
    synth_citations: list = []
    if synth_df is not None and not synth_df.empty:
        import json as _json

        r = synth_df.iloc[0]
        synth_text = str(r.get("synthesis_text") or "")
        synth_model = str(r.get("model") or "")
        try:
            synth_citations = _json.loads(r.get("citations_json") or "[]")
        except (TypeError, ValueError):
            synth_citations = []

    # On-demand (re)generation when a key is configured.
    session_slot = "research_synth_text"
    if gemini.is_enabled():
        btn = (
            tr("🔄 重新生成研报综述", "🔄 Regenerate Research Synthesis")
            if synth_text
            else tr("✨ 生成研报综述（Gemini）", "✨ Generate Research Synthesis (Gemini)")
        )
        if st.button(btn, key="research_synth_btn"):
            with st.spinner(tr("Gemini 正在综合各机构研报……（约20–40秒）", "Gemini is synthesizing sell-side research… (~20–40s)")):
                try:
                    synth = gemini.synthesize_research(snapshot_df, research_df, as_of, cohort)
                    st.session_state[session_slot] = synth.text
                    st.session_state["research_synth_model"] = synth.model
                    st.session_state["research_synth_citations"] = [
                        {"title": c.title, "uri": c.uri} for c in synth.citations
                    ]
                except Exception as exc:  # noqa: BLE001
                    st.error(tr(f"调用 Gemini 失败：{exc}", f"Gemini call failed: {exc}"))
        if st.session_state.get(session_slot):
            synth_text = st.session_state[session_slot]
            synth_model = st.session_state.get("research_synth_model", synth_model)
            synth_citations = st.session_state.get("research_synth_citations", synth_citations)
    elif not synth_text:
        st.info(
            tr(
                "未配置 Gemini API 密钥时仅显示上方一致预期表格。挂载 `GEMINI_API_KEY` "
                "后，数据管道会自动生成卖方叙事综述。",
                "Without a Gemini API key only the consensus table above is shown. Mount "
                "`GEMINI_API_KEY` and the pipeline will generate the sell-side narrative synthesis.",
            )
        )

    if synth_text:
        st.markdown(synth_text)
        if synth_citations:
            st.markdown(tr("**来源：**", "**Sources:**"))
            for c in synth_citations:
                title = c.get("title") or c.get("uri")
                st.markdown(f"- [{title}]({c.get('uri')})")
        if synth_model:
            st.caption(tr(f"模型：{synth_model} · 快照日期：{as_of}", f"Model: {synth_model} · Snapshot: {as_of}"))
