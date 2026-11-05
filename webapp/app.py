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
            {"path": "pages/0_📊_核心概览.py", "zh": "核心指标概览", "en": "Executive Overview", "icon": "📊", "default": True},
            {"path": "pages/1_🧮_估值榜单.py", "zh": "估值榜单", "en": "Valuation Leaderboard", "icon": "🧮"},
            {"path": "pages/3_🌡️_泡沫温度计.py", "zh": "泡沫温度计", "en": "Bubble Thermometer", "icon": "🌡️"},
            {"path": "pages/8_⚖️_双价值链.py", "zh": "双价值链", "en": "Dual Value Chain", "icon": "⚖️"},
        ],
    ),
    "research": (
        {"zh": "研究", "en": "Research"},
        [
            {"path": "pages/9_🤖_AI_投资雷达.py", "zh": "AI 投资雷达", "en": "AI Opportunity Radar", "icon": "🤖"},
            {"path": "pages/5_🔍_AI_智能选股.py", "zh": "AI 智能选股", "en": "AI Stock Screener", "icon": "🔍"},
            {"path": "pages/7_📝_一键研报.py", "zh": "一键研报", "en": "1-Click Research Note", "icon": "📝"},
            {"path": "pages/4_📈_技术指标与回测.py", "zh": "技术指标与回测", "en": "Technical Analysis & Backtest", "icon": "📈"},
        ],
    ),
    "idc": (
        {"zh": "IDC 研究", "en": "IDC Intelligence"},
        [
            {
                "path": "pages/11_🌐_IDC_MarketScape.py",
                "zh": "IDC 智库与厂商全景",
                "en": "IDC MarketScape™ Research Desk",
                "icon": "🌐",
                "url_path": "IDC_MarketScape",
            },
            {
                "path": "pages/11_🌐_IDC_MarketScape.py",
                "zh": "IDC 智库与厂商全景 (别名)",
                "en": "IDC MarketScape (alias)",
                "icon": "🌐",
                "url_path": "IDC_智库与厂商全景",
                "visibility": "hidden",
            },
            {
                "path": "pages/11_🌐_IDC_MarketScape.py",
                "zh": "IDC MarketScape (alias)",
                "en": "IDC MarketScape (alias 2)",
                "icon": "🌐",
                "url_path": "idc-marketscape",
                "visibility": "hidden",
            },
        ],
    ),
    "execution": (
        {"zh": "执行与模拟", "en": "Execution & Simulation"},
        [
            {"path": "pages/10_💼_CIO_投资总监.py", "zh": "AI CIO 投资总监", "en": "AI CIO Executive Desk", "icon": "💼"},
        ],
    ),
    "system": (
        {"zh": "系统", "en": "System"},
        [
            {"path": "pages/6_⚙️_系统管理.py", "zh": "系统管理", "en": "System Administration", "icon": "⚙️"},
        ],
    ),
}

# English keeps the IDC desk first for analyst-facing demos; Chinese mirrors
# the historical ordering.
_GROUP_ORDER = {
    "en": ("idc", "valuation", "research", "execution", "system"),
    "zh": ("valuation", "research", "idc", "execution", "system"),
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
