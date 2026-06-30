"""Streamlit page: AI-Screener - Natural Language Multi-Factor Stock Selector."""
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from webapp import gemini

# Local imports
from webapp.data import _open_conn, list_dates, refresh_data
from webapp.mobile import inject_mobile_css
from webapp.ui import render_sidebar

st.set_page_config(
    page_title="AI 智能选股器",
    page_icon="🔍",
    layout="wide",
)
inject_mobile_css()

st.title("🔍 AI 智能多因子筛选器")
st.caption("使用自然语言输入选股条件，由 Gemini 自动解析为 SQL 查询并实时跨板块筛选股票。")

# Date selector in sidebar
as_of = render_sidebar()
if as_of is None:
    st.info("👈 请在左侧边栏选择快照日期以开始。")
    st.stop()

# ── Screener Pool Display ───────────────────────────────────────────────────
import logging

log = logging.getLogger(__name__)

try:
    conn = _open_conn()
    pool_df = conn.execute("""
        SELECT 
            s.ticker AS "代码", 
            s.name AS "公司名称", 
            s.leg AS "板块", 
            s.layer AS "层级",
            CASE WHEN t.technical_score IS NOT NULL THEN '已覆盖 ✅' ELSE '暂无技术面 ❌' END AS "技术与筹码数据"
        FROM snapshots s
        LEFT JOIN (
            SELECT ticker, technical_score 
            FROM technical_metrics 
            WHERE as_of_date = ?
        ) t ON s.ticker = t.ticker
        WHERE s.as_of_date = ? AND s.leg IN ('US', 'China')
        ORDER BY s.leg DESC, s.ticker
    """, [as_of, as_of]).fetchdf()
    
    if not pool_df.empty:
        total_count = len(pool_df)
        us_count = len(pool_df[pool_df["板块"] == "US"])
        cn_count = len(pool_df[pool_df["板块"] == "China"])
        covered_count = len(pool_df[pool_df["技术与筹码数据"] == "已覆盖 ✅"])
        
        with st.expander(f"📊 查看当前可供筛选的股票池 (当前共 {total_count} 只股票，已加载技术面 {covered_count} 只)", expanded=False):
            st.markdown(f"""
            当前快照日期 **{as_of}** 的可供多因子筛选的股票池共包含 **{total_count}** 只核心 AI 股票：
            - 🇺🇸 **美股板块**: **{us_count}** 只
            - 🇨🇳 **中股/港股板块**: **{cn_count}** 只
            - 🛠️ **技术面与筹码覆盖**: **{covered_count}/{total_count}** 只已成功提取日 K 线并完成量化指标计算
            
            你可以使用下面的自然语言输入框，输入任何关于**基本面、估值、技术形态或筹码获利分布**的组合条件进行实时筛选！
            """)
            st.dataframe(pool_df, use_container_width=True, hide_index=True)
except Exception as e:
    log.warning("Failed to load screener pool display: %s", e)

# Guidance and examples
with st.expander("💡 选股条件输入指南与示例", expanded=True):
    st.markdown("""
    你可以使用**中文或英文**输入任意复杂的财务、估值、技术指标和筹码分布的组合条件。系统会自动解析并查询数据库。
    
    **常用指标参考：**
    * **基本面/估值**：ARF分数 (arf)、估值偏离度 (v_score)、AI曝光度 (e_score)、预期P/E (forward_pe)、P/S (ps_ratio)、ROE (roe)、营收同比增速 (revenue_yoy_growth)、泡沫预警 (froth_flag)
    * **技术面**：技术评分 (technical_score)、RSI、均线多头排列 (ma_bullish_alignment)、ATR
    * **筹码面**：筹码获利比例 (chip_profit_ratio)、持仓平均成本 (chip_avg_cost)
    
    **💡 经典选股语句示例（可直接复制体验）：**
    1. *“均线确认多头排列，且筹码获利盘大于80% (强势突破股)”*
    2. *“ARF大于70，且ROE大于12%，排除泡沫预警股票 (AI高曝光且基本面优秀的良质股)”*
    3. *“技术评分大于75，且RSI小于50 (技术面强势但未超买，处于安全拉升通道)”*
    4. *“筹码获利盘小于30%，且有泡沫预警 (套牢严重且估值极度拉伸的高风险股)”*
    """)

# Text input for query
query_input = st.text_input(
    "📝 请输入选股条件：",
    value="均线确认多头排列，且筹码获利盘大于80%",
    help="例如：筛选出技术评分大于70，且ARF分数大于50，并且获利盘大于70%的股票"
)

# API key check
api_key_enabled = gemini.is_enabled()

col_btn, _ = st.columns([1, 4])
with col_btn:
    submit_button = st.button("🚀 开始智能筛选", use_container_width=True, disabled=not api_key_enabled)

if not api_key_enabled:
    st.info("ℹ️ 未配置 Gemini API 密钥。请在环境变量中设置 `GEMINI_API_KEY` 即可启用 AI 智能选股功能。")
    st.stop()

if submit_button and query_input.strip():
    with st.spinner("Gemini 正在解析选股逻辑并检索数据库..."):
        api_key = gemini.os.environ["GEMINI_API_KEY"]
        
        # Translate NLP to SQL
        sql_query = gemini.parse_nlp_screener_query(api_key, query_input.strip(), as_of)
        
        # Display the SQL query for transparency
        with st.expander("🔍 查看 AI 生成的 SQL 查询逻辑", expanded=False):
            st.code(sql_query, language="sql")
            
        # Execute query against DuckDB
        if sql_query.strip().startswith("--"):
            st.error("❌ AI 解析选股逻辑失败，请尝试用更清晰的指标词汇描述。")
            st.code(sql_query)
        else:
            try:
                conn = _open_conn()
                results_df = conn.execute(sql_query).fetchdf()
                
                if results_df.empty:
                    st.info(f"📅 在快照日期 **{as_of}** 中，没有找到符合条件的股票。您可以尝试放宽筛选条件。")
                else:
                    st.success(f"🎉 筛选完成！共找到 **{len(results_df)}** 只符合条件的股票。")
                    
                    # Formatting helpers for display
                    display_df = results_df.copy()
                    
                    # Convert column names to user friendly Chinese labels where appropriate
                    rename_dict = {
                        "ticker": "代码",
                        "name": "公司名称",
                        "arf": "ARF 评分",
                        "decile": "ARF 十分位",
                        "e_score": "E分 (AI曝光)",
                        "v_score": "V分 (估值偏离)",
                        "technical_score": "技术评分",
                        "rsi": "RSI (14)",
                        "chip_profit_ratio": "筹码获利比例",
                        "chip_avg_cost": "平均持仓成本",
                        "price": "最新价格",
                        "forward_pe": "预期 P/E",
                        "ps_ratio": "P/S 比例",
                        "roe": "ROE",
                        "revenue_yoy_growth": "营收同比增速"
                    }
                    
                    # If columns match, rename them
                    display_df = display_df.rename(columns={k: v for k, v in rename_dict.items() if k in display_df.columns})
                    
                    # Format float columns
                    float_cols_fmt = {
                        "ARF 评分": "{:.1f}",
                        "E分 (AI曝光)": "{:.1f}",
                        "V分 (估值偏离)": "{:.1f}",
                        "技术评分": "{:.1f}",
                        "RSI (14)": "{:.1f}",
                        "最新价格": "¥{:.2f}",
                        "平均持仓成本": "¥{:.2f}",
                        "预期 P/E": "{:.1f}",
                        "P/S 比例": "{:.2f}",
                    }
                    
                    # Format percentage columns
                    pct_cols = ["筹码获利比例", "ROE", "营收同比增速"]
                    
                    styled_df = display_df.style
                    
                    # Apply float formatting
                    for col, fmt in float_cols_fmt.items():
                        if col in display_df.columns:
                            styled_df = styled_df.format({col: fmt})
                            
                    # Apply percentage formatting
                    for col in pct_cols:
                        if col in display_df.columns:
                            styled_df = styled_df.format({col: lambda x: f"{x * 100:.1f}%" if pd.notna(x) else "—"})
                            
                    st.dataframe(styled_df, use_container_width=True, hide_index=True)
            except Exception as e:
                st.error(f"❌ 数据库执行失败。这可能是由于 AI 生成了非法的 SQL 语法。")
                st.exception(e)
                st.info("💡 建议：请尝试使用更简单的语句，例如：'技术评分大于70且RSI小于50'")
