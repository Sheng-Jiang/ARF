"""Streamlit page: AI-Screener - Natural Language Multi-Factor Stock Selector."""
import logging

import pandas as pd
import streamlit as st

from webapp import gemini

# Local imports
from webapp.data import _open_conn
from webapp.mobile import inject_mobile_css
from webapp.ui import get_current_lang, render_sidebar, tr

is_en = get_current_lang() == "en"

inject_mobile_css()

st.title(tr("🔍 AI 智能多因子筛选器", "🔍 AI Multi-Factor Stock Screener"))
st.caption(
    tr(
        "使用自然语言输入选股条件，由 Gemini 自动解析为 SQL 查询并实时跨板块筛选股票。",
        "Describe your screening criteria in natural language; Gemini parses them into a SQL query "
        "and screens stocks across legs in real time.",
    )
)

# Date selector in sidebar
as_of = render_sidebar()
if as_of is None:
    st.info(tr("👈 请在左侧边栏选择快照日期以开始。", "👈 Select a snapshot date in the left sidebar to begin."))
    st.stop()

# ── Screener Pool Display ───────────────────────────────────────────────────
log = logging.getLogger(__name__)

try:
    conn = _open_conn()
    pool_df = conn.execute("""
        SELECT
            s.ticker AS ticker,
            s.name AS name,
            s.leg AS leg,
            s.layer AS layer,
            CASE WHEN t.technical_score IS NOT NULL THEN 1 ELSE 0 END AS tech_covered
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
        us_count = len(pool_df[pool_df["leg"] == "US"])
        cn_count = len(pool_df[pool_df["leg"] == "China"])
        covered_count = int(pool_df["tech_covered"].sum())
        
        with st.expander(
            tr(
                f"📊 查看当前可供筛选的股票池 (当前共 {total_count} 只股票，已加载技术面 {covered_count} 只)",
                f"📊 View the Current Screener Universe ({total_count} tickers, {covered_count} with technicals loaded)",
            ),
            expanded=False,
        ):
            st.markdown(tr(
                f"""
            当前快照日期 **{as_of}** 的可供多因子筛选的股票池共包含 **{total_count}** 只核心 AI 股票：
            - 🇺🇸 **美股板块**: **{us_count}** 只
            - 🇨🇳 **中股/港股板块**: **{cn_count}** 只
            - 🛠️ **技术面与筹码覆盖**: **{covered_count}/{total_count}** 只已成功提取日 K 线并完成量化指标计算

            你可以使用下面的自然语言输入框，输入任何关于**基本面、估值、技术形态或筹码获利分布**的组合条件进行实时筛选！
            """,
                f"""
            The multi-factor screener universe for snapshot **{as_of}** contains **{total_count}** core AI stocks:
            - 🇺🇸 **US Leg**: **{us_count}** tickers
            - 🇨🇳 **China / HK Leg**: **{cn_count}** tickers
            - 🛠️ **Technical & chip coverage**: **{covered_count}/{total_count}** tickers have daily K-lines and quantitative indicators computed

            Use the natural-language input below to screen in real time with any combination of **fundamental, valuation, technical or chip-profit** criteria!
            """,
            ))
            pool_view = pool_df.copy()
            pool_view["tech_covered"] = pool_view["tech_covered"].map(
                {1: tr("已覆盖 ✅", "Covered ✅"), 0: tr("暂无技术面 ❌", "No technicals ❌")}
            )
            pool_view = pool_view.rename(columns={
                "ticker": tr("代码", "Ticker"),
                "name": tr("公司名称", "Company"),
                "leg": tr("板块", "Leg"),
                "layer": tr("层级", "Layer"),
                "tech_covered": tr("技术与筹码数据", "Technical & Chip Data"),
            })
            st.dataframe(pool_view, use_container_width=True, hide_index=True)
except Exception as e:
    log.warning("Failed to load screener pool display: %s", e)

# Guidance and examples
with st.expander(tr("💡 选股条件输入指南与示例", "💡 Screening Criteria Guide & Examples"), expanded=True):
    st.markdown(tr("""
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
    """, """
    You can describe arbitrarily complex combinations of financial, valuation, technical and chip-distribution criteria in **Chinese or English**. The system parses them and queries the database automatically.

    **Common indicator reference:**
    * **Fundamentals / valuation**: ARF score (arf), valuation stretch (v_score), AI exposure (e_score), forward P/E (forward_pe), P/S (ps_ratio), ROE (roe), revenue YoY growth (revenue_yoy_growth), froth flag (froth_flag)
    * **Technicals**: technical score (technical_score), RSI, bullish MA alignment (ma_bullish_alignment), ATR
    * **Chip distribution**: chip profit ratio (chip_profit_ratio), average chip cost (chip_avg_cost)

    **💡 Classic screening examples (copy and try directly):**
    1. *“Bullish MA alignment confirmed, with chip profit ratio above 80% (strong breakout stocks)”*
    2. *“ARF above 70 and ROE above 12%, excluding froth-flagged stocks (high AI exposure with solid fundamentals)”*
    3. *“Technical score above 75 and RSI below 50 (strong technicals but not overbought — a safe uptrend)”*
    4. *“Chip profit ratio below 30% with a froth flag (heavily trapped holders and extremely stretched valuations — high risk)”*
    """))

# Text input for query
query_input = st.text_input(
    tr("📝 请输入选股条件：", "📝 Enter screening criteria:"),
    value=tr(
        "均线确认多头排列，且筹码获利盘大于80%",
        "Bullish MA alignment confirmed, with chip profit ratio above 80%",
    ),
    help=tr(
        "例如：筛选出技术评分大于70，且ARF分数大于50，并且获利盘大于70%的股票",
        "e.g., screen for stocks with technical score above 70, ARF above 50, and profit ratio above 70%",
    ),
)

# API key check
api_key_enabled = gemini.is_enabled()

col_btn, _ = st.columns([1, 4])
with col_btn:
    submit_button = st.button(tr("🚀 开始智能筛选", "🚀 Run AI Screen"), use_container_width=True, disabled=not api_key_enabled)

if not api_key_enabled:
    st.info(
        tr(
            "ℹ️ 未配置 Gemini API 密钥。请在环境变量中设置 `GEMINI_API_KEY` 即可启用 AI 智能选股功能。",
            "ℹ️ No Gemini API key configured. Set `GEMINI_API_KEY` in the environment to enable AI stock screening.",
        )
    )
    st.stop()

if submit_button and query_input.strip():
    with st.spinner(tr("Gemini 正在解析选股逻辑并检索数据库...", "Gemini is parsing the screening logic and querying the database...")):
        api_key = gemini.os.environ["GEMINI_API_KEY"]

        # Translate NLP to SQL
        sql_query = gemini.parse_nlp_screener_query(api_key, query_input.strip(), as_of)

        # Display the SQL query for transparency
        with st.expander(tr("🔍 查看 AI 生成的 SQL 查询逻辑", "🔍 View AI-Generated SQL Query"), expanded=False):
            st.code(sql_query, language="sql")

        # Execute query against DuckDB
        if sql_query.strip().startswith("--"):
            st.error(
                tr(
                    "❌ AI 解析选股逻辑失败，请尝试用更清晰的指标词汇描述。",
                    "❌ AI failed to parse the screening logic. Try describing it with clearer indicator terms.",
                )
            )
            st.code(sql_query)
        else:
            try:
                conn = _open_conn()
                results_df = conn.execute(sql_query).fetchdf()

                if results_df.empty:
                    st.info(
                        tr(
                            f"📅 在快照日期 **{as_of}** 中，没有找到符合条件的股票。您可以尝试放宽筛选条件。",
                            f"📅 No stocks matched the criteria in snapshot **{as_of}**. Try loosening the filters.",
                        )
                    )
                else:
                    st.success(
                        tr(
                            f"🎉 筛选完成！共找到 **{len(results_df)}** 只符合条件的股票。",
                            f"🎉 Screening complete! Found **{len(results_df)}** matching stocks.",
                        )
                    )

                    # Formatting helpers for display
                    display_df = results_df.copy()

                    # Map raw column names to user-friendly display labels
                    rename_dict = {
                        "ticker": tr("代码", "Ticker"),
                        "name": tr("公司名称", "Company"),
                        "arf": tr("ARF 评分", "ARF Score"),
                        "decile": tr("ARF 十分位", "ARF Decile"),
                        "e_score": tr("E分 (AI曝光)", "E-Score (AI Exposure)"),
                        "v_score": tr("V分 (估值偏离)", "V-Score (Valuation Stretch)"),
                        "technical_score": tr("技术评分", "Technical Score"),
                        "rsi": "RSI (14)",
                        "chip_profit_ratio": tr("筹码获利比例", "Chip Profit Ratio"),
                        "chip_avg_cost": tr("平均持仓成本", "Avg Chip Cost"),
                        "price": tr("最新价格", "Latest Price"),
                        "forward_pe": tr("预期 P/E", "Fwd P/E"),
                        "ps_ratio": tr("P/S 比例", "P/S Ratio"),
                        "roe": "ROE",
                        "revenue_yoy_growth": tr("营收同比增速", "Revenue YoY"),
                    }

                    # If columns match, rename them
                    display_df = display_df.rename(columns={k: v for k, v in rename_dict.items() if k in display_df.columns})

                    # Format float columns
                    float_cols_fmt = {
                        rename_dict["arf"]: "{:.1f}",
                        rename_dict["e_score"]: "{:.1f}",
                        rename_dict["v_score"]: "{:.1f}",
                        rename_dict["technical_score"]: "{:.1f}",
                        rename_dict["rsi"]: "{:.1f}",
                        rename_dict["price"]: "¥{:.2f}",
                        rename_dict["chip_avg_cost"]: "¥{:.2f}",
                        rename_dict["forward_pe"]: "{:.1f}",
                        rename_dict["ps_ratio"]: "{:.2f}",
                    }

                    # Format percentage columns
                    pct_cols = [rename_dict["chip_profit_ratio"], "ROE", rename_dict["revenue_yoy_growth"]]
                    
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
                st.error(
                    tr(
                        "❌ 数据库执行失败。这可能是由于 AI 生成了非法的 SQL 语法。",
                        "❌ Database execution failed. The AI may have generated invalid SQL syntax.",
                    )
                )
                st.exception(e)
                st.info(
                    tr(
                        "💡 建议：请尝试使用更简单的语句，例如：'技术评分大于70且RSI小于50'",
                        "💡 Tip: try a simpler statement, e.g. 'technical score above 70 and RSI below 50'",
                    )
                )
