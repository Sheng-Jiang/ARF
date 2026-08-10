"""ARF 仪表盘 — 页面导航路由与配置。"""
import streamlit as st

st.set_page_config(
    page_title="ARF 仪表盘",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 三组导航对应三种使用意图：看当前估值状态、做个股研究、维护系统。
# 美股/中股/组合管理合并进「估值榜单」的三个标签——前两者除腿以外逐行相同，
# 后者是这份名单的来源，放在同一页比拆成三个入口更好找。
pages = {
    "估值": [
        st.Page("pages/0_📊_核心概览.py", title="核心指标概览", icon="📊", default=True),
        st.Page("pages/1_🧮_估值榜单.py", title="估值榜单", icon="🧮"),
        st.Page("pages/3_🌡️_泡沫温度计.py", title="泡沫温度计", icon="🌡️"),
        st.Page("pages/8_⚖️_双价值链.py", title="双价值链", icon="⚖️"),
    ],
    "研究": [
        st.Page("pages/5_🔍_AI_智能选股.py", title="AI 智能选股", icon="🔍"),
        st.Page("pages/7_📝_一键研报.py", title="一键研报", icon="📝"),
        st.Page("pages/4_📈_技术指标与回测.py", title="技术指标与回测", icon="📈"),
    ],
    "系统": [
        st.Page("pages/6_⚙️_系统管理.py", title="系统管理", icon="⚙️"),
    ],
}

pg = st.navigation(pages)
pg.run()
