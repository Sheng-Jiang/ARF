"""ARF 仪表盘 — 页面导航路由与配置。"""
import streamlit as st

from webapp.ui import get_current_lang

# Determine active language before building navigation
is_en = get_current_lang() == "en"

st.set_page_config(
    page_title="ARF Intelligence Dashboard" if is_en else "ARF 仪表盘",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="auto",
)

if is_en:
    pages = {
        "IDC Intelligence": [
            st.Page(
                "pages/11_🌐_IDC_MarketScape.py",
                title="IDC MarketScape™ Research Desk",
                icon="🌐",
                url_path="IDC_MarketScape",
            ),
            st.Page(
                "pages/11_🌐_IDC_MarketScape.py",
                title="IDC MarketScape (alias)",
                icon="🌐",
                url_path="IDC_智库与厂商全景",
                visibility="hidden",
            ),
            st.Page(
                "pages/11_🌐_IDC_MarketScape.py",
                title="IDC MarketScape (alias 2)",
                icon="🌐",
                url_path="idc-marketscape",
                visibility="hidden",
            ),
        ],
        "Valuation": [
            st.Page("pages/0_📊_核心概览.py", title="Executive Overview", icon="📊", default=True),
            st.Page("pages/1_🧮_估值榜单.py", title="Valuation Leaderboard", icon="🧮"),
            st.Page("pages/3_🌡️_泡沫温度计.py", title="Bubble Thermometer", icon="🌡️"),
            st.Page("pages/8_⚖️_双价值链.py", title="Dual Value Chain", icon="⚖️"),
        ],
        "Research": [
            st.Page("pages/9_🤖_AI_投资雷达.py", title="AI Opportunity Radar", icon="🤖"),
            st.Page("pages/5_🔍_AI_智能选股.py", title="AI Stock Screener", icon="🔍"),
            st.Page("pages/7_📝_一键研报.py", title="1-Click Research Note", icon="📝"),
            st.Page("pages/4_📈_技术指标与回测.py", title="Technical Analysis & Backtest", icon="📈"),
        ],
        "Execution & Simulation": [
            st.Page("pages/10_💼_CIO_投资总监.py", title="AI CIO Executive Desk", icon="💼"),
        ],
        "System": [
            st.Page("pages/6_⚙️_系统管理.py", title="System Administration", icon="⚙️"),
        ],
    }
else:
    pages = {
        "估值": [
            st.Page("pages/0_📊_核心概览.py", title="核心指标概览", icon="📊", default=True),
            st.Page("pages/1_🧮_估值榜单.py", title="估值榜单", icon="🧮"),
            st.Page("pages/3_🌡️_泡沫温度计.py", title="泡沫温度计", icon="🌡️"),
            st.Page("pages/8_⚖️_双价值链.py", title="双价值链", icon="⚖️"),
        ],
        "研究": [
            st.Page("pages/9_🤖_AI_投资雷达.py", title="AI 投资雷达", icon="🤖"),
            st.Page("pages/5_🔍_AI_智能选股.py", title="AI 智能选股", icon="🔍"),
            st.Page("pages/7_📝_一键研报.py", title="一键研报", icon="📝"),
            st.Page("pages/4_📈_技术指标与回测.py", title="技术指标与回测", icon="📈"),
        ],
        "IDC 研究": [
            st.Page(
                "pages/11_🌐_IDC_MarketScape.py",
                title="IDC 智库与厂商全景",
                icon="🌐",
                url_path="IDC_MarketScape",
            ),
            st.Page(
                "pages/11_🌐_IDC_MarketScape.py",
                title="IDC 智库与厂商全景 (别名)",
                icon="🌐",
                url_path="IDC_智库与厂商全景",
                visibility="hidden",
            ),
            st.Page(
                "pages/11_🌐_IDC_MarketScape.py",
                title="IDC MarketScape (alias)",
                icon="🌐",
                url_path="idc-marketscape",
                visibility="hidden",
            ),
        ],
        "执行与模拟": [
            st.Page("pages/10_💼_CIO_投资总监.py", title="AI CIO 投资总监", icon="💼"),
        ],
        "系统": [
            st.Page("pages/6_⚙️_系统管理.py", title="系统管理", icon="⚙️"),
        ],
    }

pg = st.navigation(pages)
pg.run()
