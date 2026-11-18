"""ARF 仪表盘 — 页面导航路由与配置。"""
import streamlit as st

from webapp.ui import get_current_lang, render_language_switcher

# Determine active language before building navigation
is_en = get_current_lang() == "en"

st.set_page_config(
    page_title="ARF Intelligence Dashboard" if is_en else "ARF 仪表盘",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="auto",
)

# Page specs are defined once and titled per language, so adding/renaming a
# page only requires one edit. `url_path` is deliberately language-neutral so
# deep links keep working when the user flips languages.
_PAGES = {
    "valuation": (
        {"zh": "估值", "en": "Valuation"},
        [
            {"path": "views/00_executive_overview.py", "zh": "核心指标概览", "en": "Executive Overview", "icon": "📊", "default": True},
            {"path": "views/01_valuation_leaderboard.py", "zh": "估值榜单", "en": "Valuation Leaderboard", "icon": "🧮", "url_path": "valuation-leaderboard"},
            {"path": "views/03_bubble_thermometer.py", "zh": "泡沫温度计", "en": "Bubble Thermometer", "icon": "🌡️", "url_path": "bubble-thermometer"},
            {"path": "views/08_dual_value_chain.py", "zh": "双价值链", "en": "Dual Value Chain", "icon": "⚖️", "url_path": "dual-value-chain"},
        ],
    ),
    "research": (
        {"zh": "研究", "en": "Research"},
        [
            {"path": "views/09_ai_radar.py", "zh": "AI 投资雷达", "en": "AI Opportunity Radar", "icon": "🤖", "url_path": "ai-radar"},
            {"path": "views/05_ai_screener.py", "zh": "AI 智能选股", "en": "AI Stock Screener", "icon": "🔍", "url_path": "ai-screener"},
            {"path": "views/07_oneclick_report.py", "zh": "一键研报", "en": "1-Click Research Note", "icon": "📝", "url_path": "research-note"},
            {"path": "views/04_technical_backtest.py", "zh": "技术指标与回测", "en": "Technical Analysis & Backtest", "icon": "📈", "url_path": "technical-backtest"},
        ],
    ),
    "analyst": (
        {"zh": "研究台", "en": "Analyst Desk"},
        [
            {
                "path": "views/11_analyst_desk.py",
                "zh": "ARF 分析师工作台",
                "en": "ARF Analyst Desk — Vendor Quadrant",
                "icon": "🌐",
                "url_path": "analyst-desk",
            },
            # Legacy deep links kept alive (hidden) so anything shared before the
            # rename still resolves to the desk instead of a 404.
            {
                "path": "views/11_analyst_desk.py",
                "zh": "分析师工作台 (旧链接)",
                "en": "Analyst Desk (legacy link)",
                "icon": "🌐",
                "url_path": "IDC_MarketScape",
                "visibility": "hidden",
            },
            {
                "path": "views/11_analyst_desk.py",
                "zh": "分析师工作台 (旧链接 2)",
                "en": "Analyst Desk (legacy link 2)",
                "icon": "🌐",
                "url_path": "IDC_智库与厂商全景",
                "visibility": "hidden",
            },
            {
                "path": "views/11_analyst_desk.py",
                "zh": "分析师工作台 (旧链接 3)",
                "en": "Analyst Desk (legacy link 3)",
                "icon": "🌐",
                "url_path": "idc-marketscape",
                "visibility": "hidden",
            },
        ],
    ),
    "execution": (
        {"zh": "执行与模拟", "en": "Execution & Simulation"},
        [
            {"path": "views/10_cio_desk.py", "zh": "AI CIO 投资总监", "en": "AI CIO Executive Desk", "icon": "💼", "url_path": "cio-desk"},
        ],
    ),
    "system": (
        {"zh": "系统", "en": "System"},
        [
            {"path": "views/06_system_admin.py", "zh": "系统管理", "en": "System Administration", "icon": "⚙️", "url_path": "system-admin"},
        ],
    ),
}

# English keeps the analyst desk first for analyst-facing demos; Chinese mirrors
# the historical ordering.
_GROUP_ORDER = {
    "en": ("analyst", "valuation", "research", "execution", "system"),
    "zh": ("valuation", "research", "analyst", "execution", "system"),
}


def _build_pages(lang: str) -> dict[str, list[st.Page]]:
    nav: dict[str, list[st.Page]] = {}
    for group_key in _GROUP_ORDER[lang]:
        group_labels, specs = _PAGES[group_key]
        items: list[st.Page] = []
        for spec in specs:
            kwargs = {}
            if spec.get("url_path"):
                kwargs["url_path"] = spec["url_path"]
            if spec.get("visibility"):
                kwargs["visibility"] = spec["visibility"]
            if spec.get("default"):
                kwargs["default"] = True
            items.append(st.Page(spec["path"], title=spec[lang], icon=spec["icon"], **kwargs))
        nav[group_labels[lang]] = items
    return nav


pg = st.navigation(_build_pages(get_current_lang()))

# Rendered from the root app so the switcher exists on *every* page, including
# pages that do not call render_sidebar().
render_language_switcher()

pg.run()
