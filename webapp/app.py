"""ARF 仪表盘 — 页面导航路由与配置。"""
import streamlit as st

st.set_page_config(
    page_title="ARF 仪表盘",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

pages = {
    "ARF 核心功能": [
        st.Page("pages/0_📊_核心概览.py", title="核心指标概览", icon="📊", default=True),
        st.Page("pages/1_🇺🇸_美股估值.py", title="美股估值", icon="🇺🇸"),
        st.Page("pages/2_🇨🇳_中股估值.py", title="中股估值", icon="🇨🇳"),
        st.Page("pages/3_🌡️_泡沫温度计.py", title="泡沫温度计", icon="🌡️"),
        st.Page("pages/4_📈_技术指标与回测.py", title="技术指标与回测", icon="📈"),
        st.Page("pages/5_🔍_AI_智能选股.py", title="AI 智能选股", icon="🔍"),
        st.Page("pages/7_📝_一键研报.py", title="一键研报", icon="📝"),
        st.Page("pages/6_⚙️_系统管理.py", title="系统管理", icon="⚙️"),
    ]
}

pg = st.navigation(pages)
pg.run()
