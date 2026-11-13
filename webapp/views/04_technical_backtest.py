"""Streamlit page: A-share Technical Indicator Analysis and Backtesting Dashboard."""
import datetime
from pathlib import Path

import numpy as np
import streamlit as st
import yaml

from arf.fetchers.prices import (
    CURRENCY_SYMBOLS,
    detect_market,
    fetch_daily_prices_any,
    fetch_outstanding_shares_any,
)
from arf.technical import (
    calculate_chip_distribution,
    calculate_technical_indicators,
    score_history,
    score_stock_technical,
)

# Local imports
from webapp import gemini
from webapp.backtest import run_backtrader
from webapp.charts import draw_pro_kline, draw_result_bar
from webapp.data import _open_conn
from webapp.mobile import inject_mobile_css, is_mobile, show_plotly
from webapp.schemas import BacktraderParams, StrategyBase
from webapp.ui import get_current_lang, tr

is_en = get_current_lang() == "en"

inject_mobile_css()

st.title(tr("📈 技术面多因子评分 & 策略回测仪表盘", "📈 Multi-Factor Technical Scoring & Strategy Backtest Dashboard"))
st.caption(tr(
    "融合技术指标 (MAs/MACD/RSI/ATR)、筹码分布 (CYQ) 及 Backtrader 历史回测的一站式量化研究平台 — 支持 A股 / 港股 / 美股",
    "A one-stop quantitative research platform combining technical indicators (MAs/MACD/RSI/ATR), "
    "chip distribution (CYQ) and Backtrader historical backtests — covering A-shares / HK / US",
))

# ── Regulatory and Compliance Safety Disclaimer ──────────────────────────────────
st.warning(tr(
    "⚠️ **合规与参考提示**：本仪表盘所展示的“技术评分”、“量化信号”及“测算价位”均基于预设量化规则与客观历史数据自动计算，"
    "仅作为量化分析与学术研究的**参考工具**，**决不构成任何实际的证券买卖建议或投资决策推荐**。本平台不具备证券投资咨询业务资格。所有信号均为回测与历史规律参考，请投资者务必保持独立决策，自主承担风险。",
    "⚠️ **Compliance & Reference Notice**: The \"technical scores\", \"quantitative signals\" and \"price levels\" shown on this "
    "dashboard are all computed automatically from preset quantitative rules and objective historical data. They are "
    "**reference tools for quantitative analysis and academic research only**, and **in no way constitute actual securities "
    "trading advice or investment recommendations**. This platform is not licensed to provide securities investment advisory "
    "services. All signals are backtest and historical-pattern references; investors must make independent decisions and bear "
    "the risks themselves.",
))

# ── Load Universe Helper ──────────────────────────────────────────────────────
@st.cache_data
def get_universe_stocks():
    """Load all scored stocks from config/universe.yaml, tagged by market."""
    universe_path = Path("config/universe.yaml")
    if not universe_path.exists():
        return []
    try:
        with open(universe_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        stocks = []
        for item in data:
            ticker = item.get("ticker", "")
            if not ticker:
                continue
            stocks.append({
                "ticker": ticker,
                "name": item.get("name", ticker),
                "layer": item.get("layer", ""),
                "leg": item.get("leg", ""),
                "market": detect_market(ticker),
            })
        return stocks
    except Exception as e:
        st.sidebar.error(tr(f"加载 universe.yaml 失败: {e}", f"Failed to load universe.yaml: {e}"))
        return []

all_stocks = get_universe_stocks()


# ── Cached data + computation helpers (keyed on inputs; skip recompute on rerun) ─
@st.cache_data(show_spinner=False, ttl=3600)
def load_prices(ticker: str, start_str: str, end_str: str, adjust: str):
    """Cached daily-price fetch (1h TTL) — avoids re-hitting the data source on rerun."""
    return fetch_daily_prices_any(ticker, start_str, end_str, adjust)


@st.cache_data(show_spinner=False, ttl=3600)
def load_outstanding_shares(ticker: str) -> float:
    """Cached outstanding-shares fetch (1h TTL) — Baostock/yfinance can be slow."""
    return fetch_outstanding_shares_any(ticker)


@st.cache_data(show_spinner=False)
def compute_analysis(df_raw, outstanding_shares: float, is_a_share: bool):
    """Cached indicators + chip distribution + per-row technical score.

    The per-row score is O(bars × lookback); caching keyed on the price frame and
    inputs means it only recomputes when the underlying data actually changes.
    """
    df_ind = calculate_technical_indicators(df_raw)
    chip = calculate_chip_distribution(df_raw, outstanding_shares, is_a_share=is_a_share)
    df_ind = score_history(df_ind, outstanding_shares, is_a_share=is_a_share)
    return df_ind, chip


# ── Sidebar Configurations ──────────────────────────────────────────────────
st.sidebar.header(tr("⚙️ 仪表盘配置", "⚙️ Dashboard Settings"))

# 1. Market + Ticker Selection
st.sidebar.subheader(tr("🎯 股票选择", "🎯 Stock Selection"))
MARKET_CODES = ["A", "HK", "US"]
MARKET_LABELS = {
    "A": tr("A股 (A-share)", "A-shares (A)"),
    "HK": tr("港股 (HK)", "Hong Kong (HK)"),
    "US": tr("美股 (US)", "US Stocks (US)"),
}
sel_market = st.sidebar.radio(
    tr("选择市场", "Select Market"),
    MARKET_CODES,
    format_func=lambda m: MARKET_LABELS[m],
    horizontal=True,
)
selected_market_label = MARKET_LABELS[sel_market]
ccy = CURRENCY_SYMBOLS[sel_market]

market_stocks = [s for s in all_stocks if s["market"] == sel_market]
dropdown_options = {f"{s['ticker']} ({s['name']})": s["ticker"] for s in market_stocks}

use_manual_ticker = st.sidebar.checkbox(
    tr("手动输入股票代码", "Enter ticker manually"),
    value=False,
    help=tr("勾选此项以输入任意代码（无需在 seed universe 中）", "Check this to enter any ticker (no need for it to be in the seed universe)"),
)
selected_option = None

if use_manual_ticker:
    if sel_market == "A":
        raw_ticker = st.sidebar.text_input(
            tr("输入 A 股代码", "Enter A-share ticker"),
            value="300296",
            help=tr("6位数字代码，例如 300296（利亚德）或 600070（浙江富润）", "6-digit code, e.g. 300296 (Leyard) or 600070 (Zhejiang Furun)"),
        )
        ticker = raw_ticker.strip()
        if ticker and not ticker.endswith((".SZ", ".SH")):
            ticker = f"{ticker}.SH" if ticker.startswith(("60", "68", "90")) else f"{ticker}.SZ"
    elif sel_market == "HK":
        raw_ticker = st.sidebar.text_input(
            tr("输入港股代码", "Enter HK ticker"),
            value="0700",
            help=tr("数字代码，例如 0700（腾讯）、3690（美团）；自动补足为 4 位", "Numeric code, e.g. 0700 (Tencent), 3690 (Meituan); padded to 4 digits automatically"),
        )
        ticker = raw_ticker.strip()
        if ticker:
            ticker = ticker if ticker.upper().endswith(".HK") else f"{ticker.lstrip('0').zfill(4)}.HK"
    else:  # US
        raw_ticker = st.sidebar.text_input(
            tr("输入美股代码", "Enter US ticker"),
            value="NVDA",
            help=tr("美股代码，例如 NVDA、AAPL、BABA", "US ticker, e.g. NVDA, AAPL, BABA"),
        )
        ticker = raw_ticker.strip().upper()
else:
    if dropdown_options:
        selected_option = st.sidebar.selectbox(tr("从 Universe 选择 stock", "Select a stock from the Universe"), list(dropdown_options.keys()))
        ticker = dropdown_options.get(selected_option)
    else:
        st.sidebar.info(tr(
            f"Universe 中暂无{selected_market_label}标的，请勾选“手动输入股票代码”。",
            f"No {selected_market_label} stocks in the Universe — please tick \"Enter ticker manually\".",
        ))
        ticker = None

# 2. Market Data Configs
st.sidebar.subheader(tr("📊 行情配置", "📊 Market Data Settings"))
period = st.sidebar.selectbox(
    tr("数据周期", "Data Period"),
    ["daily", "weekly", "monthly"],
    index=0,
    format_func=lambda p: {
        "daily": tr("日线", "Daily"),
        "weekly": tr("周线", "Weekly"),
        "monthly": tr("月线", "Monthly"),
    }[p],
)
adjust = st.sidebar.selectbox(
    tr("复权方式", "Price Adjustment"),
    ["qfq", "hfq", ""],
    index=0,
    format_func=lambda x: (
        tr("前复权 (qfq)", "Forward-adjusted (qfq)")
        if x == "qfq"
        else tr("后复权 (hfq)", "Backward-adjusted (hfq)")
        if x == "hfq"
        else tr("不复权", "Unadjusted")
    ),
)

# Lookback range (3 years default for history)
today_dt = datetime.date.today()
three_years_ago = today_dt - datetime.timedelta(days=3 * 365)
start_date = st.sidebar.date_input(tr("行情起始日期", "Price Start Date"), three_years_ago)
end_date = st.sidebar.date_input(tr("行情结束日期", "Price End Date"), today_dt)

# 3. Backtrader Parameters
st.sidebar.subheader(tr("🏁 回测配置", "🏁 Backtest Settings"))
bt_start = st.sidebar.date_input(tr("回测起始日期", "Backtest Start Date"), today_dt - datetime.timedelta(days=365))
bt_end = st.sidebar.date_input(tr("回测结束日期", "Backtest End Date"), today_dt)
start_cash = st.sidebar.number_input(tr(f"初始资金 ({ccy})", f"Initial Capital ({ccy})"), min_value=1000, value=100000, step=10000)
commission_fee = st.sidebar.number_input(
    tr("佣金费率", "Commission Rate"),
    min_value=0.0, max_value=0.05, value=0.001, step=0.0001, format="%.4f",
    help=tr("双边交易佣金，默认 0.1%", "Two-sided trading commission; default 0.1%"),
)
sizer_percent = st.sidebar.number_input(
    tr("单笔仓位占用资金 (%)", "Position Size (% of capital)"),
    min_value=1.0, max_value=100.0, value=95.0, step=5.0,
    help=tr(
        "每次买入使用可用资金的百分比 (PercentSizer)，反映完整资金部署；默认 95% 以预留佣金",
        "Percentage of available cash used per buy (PercentSizer), reflecting full capital deployment; defaults to 95% to leave room for commission",
    ),
)

# ── Data Loading & Processing Flow ──────────────────────────────────────────
if not ticker:
    st.info(tr("👈 请在左侧边栏配置股票代码以开始。", "👈 Configure a ticker in the left sidebar to begin."))
    st.stop()

with st.spinner(tr("正在获取股票历史行情...", "Fetching historical price data...")):
    # Convert dates to string format
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    df_raw = load_prices(ticker, start_str, end_str, adjust)

if df_raw.empty:
    # A transient source failure must not be pinned by the 1h cache: evict this
    # key so a page refresh actually re-fetches instead of replaying the error.
    load_prices.clear(ticker, start_str, end_str, adjust)
    st.error(tr(
        f"❌ 获取股票 {ticker} 的历史数据失败，请检查网络或确认代码是否正确"
        "（部分退市/停牌标的或数据源不支持）。A 股已自动尝试腾讯 + Baostock 双源。",
        f"❌ Failed to fetch historical data for {ticker}. Please check your network or verify the ticker "
        "(some delisted/suspended names or data sources are unsupported). For A-shares, both Tencent and "
        "Baostock sources have already been tried.",
    ))
    st.stop()

# Newly-listed names (e.g. MiniMax 0100.HK) may only have a few months of bars.
# The longest-window indicators (MA120, then MA60) need at least that many bars
# to be fully defined; below MA120 they render partial/all-NaN lines. Warn rather
# than block — partial analysis still renders — and surface which indicators are
# unreliable so the threshold tracks the actual longest MA window.
_LONGEST_MA = 120
if len(df_raw) < _LONGEST_MA:
    st.warning(tr(
        f"⚠️ {ticker} 仅获取到 {len(df_raw)} 根 K 线，不足以稳定计算长周期指标"
        f"（MA120 需 ≥120 根、MA60 需 ≥60 根；常见于新上市标的或数据源限制）。"
        f"长均线、回测等结果可能不完整或不可靠，请谨慎参考。",
        f"⚠️ Only {len(df_raw)} bars were fetched for {ticker}, which is not enough to compute long-window "
        f"indicators reliably (MA120 needs ≥120 bars, MA60 needs ≥60; common for newly listed names or "
        f"data-source limits). Long moving averages and backtest results may be incomplete or unreliable — "
        f"use with caution.",
    ))

# Get outstanding shares
outstanding_shares = None

# Try to get from DuckDB first if it's a universe stock
is_universe_stock = any(item['ticker'] == ticker for item in all_stocks)
if is_universe_stock:
    try:
        conn = _open_conn()
        # Query latest snapshots to estimate outstanding shares: MC_USD * FX / PRICE
        row = conn.execute(
            "SELECT market_cap_usd, fx_rate_usd, price FROM snapshots WHERE ticker = ? ORDER BY as_of_date DESC LIMIT 1",
            [ticker]
        ).fetchone()
        if row and row[0] and row[1] and row[2]:
            mc_usd, fx, price = row
            outstanding_shares = (mc_usd * fx) / price
            # Adjust if scale is wrong (snapshots might store MC in millions or absolute. Let's make sure it's absolute)
            # If outstanding shares is too small (e.g. less than 1 million), adjust it
            if outstanding_shares < 1_000_000:
                outstanding_shares *= 1_000_000
    except Exception:
        pass

# Fallback: Fetch dynamically (Baostock for A-shares, yfinance for HK/US)
if not outstanding_shares:
    with st.spinner(tr("正在拉取最新股本数据...", "Fetching latest shares outstanding...")):
        outstanding_shares = load_outstanding_shares(ticker)

# Indicators + chip distribution + per-row technical score (cached; see compute_analysis)
with st.spinner(tr("正在计算技术指标与逐日评分序列...", "Computing technical indicators and daily score series...")):
    df_indicators, chip_metrics = compute_analysis(df_raw, outstanding_shares, sel_market == "A")
profit_ratio, avg_cost, c90_min, c90_max, c70_min, c70_max = chip_metrics

# Latest day's indicators
latest_row = df_indicators.iloc[-1]
tech_score = score_stock_technical(latest_row, chip_metrics)

# ── Section 1: Multi-Factor Technical & Chip Summary ──────────────────────────
st.subheader(tr("📊 智能多因子评估中心", "📊 Smart Multi-Factor Evaluation Centre"))

c1, c2, c3 = st.columns(3)

# Card 1: Technical Score with visual strength
with c1:
    st.markdown("<div style='border:1px solid #e0e0e0; padding:15px; border-radius:10px; background-color:#fcfcfc;'>", unsafe_allow_html=True)
    st.write(tr("#### 🎯 智能技术评分", "#### 🎯 Smart Technical Score"))

    # Visual badge for strength
    if tech_score >= 70:
        strength_badge = tr("🔴 强多头 / 向上突破", "🔴 Strong Bullish / Breakout")
        strength_color = "#ff4d4f"
    elif 50 <= tech_score < 70:
        strength_badge = tr("🟠 偏多 / 强势震荡", "🟠 Leaning Bullish / Strong Consolidation")
        strength_color = "#ffa940"
    elif 30 <= tech_score < 50:
        strength_badge = tr("⚪ 偏空 / 弱势整理", "⚪ Leaning Bearish / Weak Consolidation")
        strength_color = "#bfbfbf"
    else:
        strength_badge = tr("🟢 极弱 / 超跌反弹契机", "🟢 Very Weak / Oversold Bounce Setup")
        strength_color = "#52c41a"

    st.markdown(f"<h1 style='color:{strength_color}; margin:0; font-size:42px;'>{tech_score:.1f} <span style='font-size:18px;'>{tr('分', 'pts')}</span></h1>", unsafe_allow_html=True)
    st.markdown(f"**{tr('技术状态：', 'Technical State:')}** <span style='color:{strength_color}; font-weight:bold;'>{strength_badge}</span>", unsafe_allow_html=True)

    # Small checklist of strengths
    above_ma20 = "✅" if latest_row["close"] > latest_row["ma20"] else "❌"
    bull_align = "✅" if latest_row["ma_bullish_alignment"] else "❌"
    macd_gold = "✅" if latest_row["macd_dif"] > latest_row["macd_dea"] else "❌"
    st.markdown(tr(
        f"- 站上20日均线: {above_ma20} | 均线多头排列: {bull_align} | MACD金叉: {macd_gold}",
        f"- Above MA20: {above_ma20} | Bullish MA alignment: {bull_align} | MACD golden cross: {macd_gold}",
    ))
    st.markdown("</div>", unsafe_allow_html=True)

# Card 2: Rules-Based Automated Suggestions (Refined for Compliance)
with c2:
    st.markdown("<div style='border:1px solid #e0e0e0; padding:15px; border-radius:10px; background-color:#fcfcfc;'>", unsafe_allow_html=True)
    st.write(tr("#### 🤖 规则量化信号参考", "#### 🤖 Rules-Based Quantitative Signal Reference"))

    # Signal logic
    if tech_score >= 70:
        suggestion = tr("🔴 偏多信号 (Bullish)", "🔴 Bullish Signal")
        sug_color = "#ff4d4f"
    elif tech_score <= 30:
        suggestion = tr("🟢 偏空信号 (Bearish)", "🟢 Bearish Signal")
        sug_color = "#52c41a"
    else:
        suggestion = tr("🟡 震荡信号 (Neutral)", "🟡 Neutral Signal")
        sug_color = "#ffa940"

    # Calculate ATR-based levels (ATR * multiplier)
    atr = latest_row.get("atr", 1.0)
    close_price = latest_row["close"]
    stop_loss = close_price - 2.0 * atr
    target_price = close_price + 3.0 * atr

    st.markdown(f"<h2 style='color:{sug_color}; margin:0;'>{suggestion}</h2>", unsafe_allow_html=True)
    st.write(tr(
        f"**最新价格：** {ccy}{close_price:.2f} (基于指标客观运算)",
        f"**Latest Price:** {ccy}{close_price:.2f} (objective indicator calculation)",
    ))
    st.markdown(tr(
        f"- **🎯 测算止盈价 (参考)**：<span style='color:#ff4d4f; font-weight:bold;'>{ccy}{target_price:.2f}</span> (基于 3×ATR 波动率)",
        f"- **🎯 Estimated Take-Profit (reference)**: <span style='color:#ff4d4f; font-weight:bold;'>{ccy}{target_price:.2f}</span> (based on 3×ATR volatility)",
    ), unsafe_allow_html=True)
    st.markdown(tr(
        f"- **🛡️ 测算止损价 (参考)**：<span style='color:#52c41a; font-weight:bold;'>{ccy}{stop_loss:.2f}</span> (基于 2×ATR 波动率)",
        f"- **🛡️ Estimated Stop-Loss (reference)**: <span style='color:#52c41a; font-weight:bold;'>{ccy}{stop_loss:.2f}</span> (based on 2×ATR volatility)",
    ), unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# Card 3: Chip Distribution (CYQ)
with c3:
    st.markdown("<div style='border:1px solid #e0e0e0; padding:15px; border-radius:10px; background-color:#fcfcfc;'>", unsafe_allow_html=True)
    st.write(tr("#### 🎰 筹码分布微观结构", "#### 🎰 Chip Distribution Microstructure"))

    profit_pct = profit_ratio * 100.0
    if profit_pct >= 80:
        chip_desc = tr("筹码强锁定，上方无套牢盘", "Chips strongly locked up, little overhead supply")
        chip_color = "#ff4d4f"
    elif 50 <= profit_pct < 80:
        chip_desc = tr("筹码中度支撑，震荡上行", "Moderate chip support, grinding higher")
        chip_color = "#ffa940"
    else:
        chip_desc = tr("套牢盘严重，上方抛压沉重", "Heavy trapped positions, strong overhead selling pressure")
        chip_color = "#52c41a"

    st.markdown(f"<h2 style='color:{chip_color}; margin:0;'>{tr('获利盘: ', 'In Profit: ')}{profit_pct:.1f}%</h2>", unsafe_allow_html=True)
    st.write(tr(
        f"**平均持仓成本**：{ccy}{avg_cost:.2f} ({chip_desc})",
        f"**Average Holding Cost**: {ccy}{avg_cost:.2f} ({chip_desc})",
    ))
    st.markdown(tr(
        f"- **70% 筹码支撑区间**：{ccy}{c70_min:.2f} ~ {ccy}{c70_max:.2f}",
        f"- **70% Chip Support Zone**: {ccy}{c70_min:.2f} ~ {ccy}{c70_max:.2f}",
    ))
    st.markdown(tr(
        f"- **90% 筹码套牢区间**：{ccy}{c90_min:.2f} ~ {ccy}{c90_max:.2f}",
        f"- **90% Chip Trapped Zone**: {ccy}{c90_min:.2f} ~ {ccy}{c90_max:.2f}",
    ))
    st.markdown("</div>", unsafe_allow_html=True)

# ── Section 2: Interactive K-Line ──────────────────────────────────────────
st.divider()
_mobile = is_mobile()
st.subheader(f"📈 {ticker} " + (
    tr("日 K 线与均线系统（移动端静态视图）", "Daily Candlestick & Moving Averages (static mobile view)")
    if _mobile
    else tr("交互式日 K 线与均线系统", "Interactive Daily Candlestick & Moving Averages")
))
kline_chart = draw_pro_kline(df_indicators, static=_mobile, lang=get_current_lang())
show_plotly(kline_chart, key="tech_kline")

# ── Section 3: Backtesting & Parameter Optimization ──────────────────────────
st.divider()
st.subheader(tr("🏁 Backtrader 策略历史回测与参数优化", "🏁 Backtrader Strategy Backtest & Parameter Optimisation"))
st.write(tr(
    "选择以下预设策略，调整参数范围进行历史回测。系统将遍历所有参数组合，找出风险调整后收益（夏普比率）最优的参数。",
    "Choose one of the preset strategies below and adjust the parameter ranges for a historical backtest. "
    "The system iterates over every parameter combination to find the one with the best risk-adjusted return (Sharpe ratio).",
))

col_sel, col_run = st.columns([3, 1])

with col_sel:
    # We define the strategy list matching arf.strategy.STRATEGIES
    # Keep names user friendly. Codes are language-neutral; the internal names
    # stay as the canonical keys registered in arf.strategy.STRATEGIES.
    _STRATEGY_NAMES = {
        "technical": "TechnicalScore 策略 (智能技术评分)",
        "ma": "MA 策略 (单均线)",
        "macross": "MACross 策略 (双均线交叉)",
    }
    _STRATEGY_LABELS = {
        "technical": tr("智能技术评分策略 (TechnicalScore)", "Technical Score Strategy (TechnicalScore)"),
        "ma": tr("单均线趋势策略 (MA)", "Single MA Trend Strategy (MA)"),
        "macross": tr("双均线交叉策略 (MACross)", "Dual MA Crossover Strategy (MACross)"),
    }
    selected_strategy_code = st.selectbox(
        tr("选择回测策略", "Backtest Strategy"),
        list(_STRATEGY_NAMES.keys()),
        format_func=lambda c: _STRATEGY_LABELS[c],
    )
    strategy_name = _STRATEGY_NAMES[selected_strategy_code]

with col_run:
    st.markdown("<br>", unsafe_allow_html=True)
    run_button = st.button(tr("🚀 开始执行策略回测", "🚀 Run Strategy Backtest"), use_container_width=True)

# Define parameter inputs dynamically based on selected strategy
st.write(tr(
    "🔧 **参数优化范围设置** (可输入单个数值或以逗号分隔的多个数值进行组合网格搜索)",
    "🔧 **Parameter Optimisation Ranges** (enter a single value, or multiple comma-separated values for a grid search)",
))

c_param1, c_param2 = st.columns(2)

if "TechnicalScore" in strategy_name:
    with c_param1:
        buy_thr_input = st.text_input(
            tr("买入评分阈值范围 (buy_threshold)", "Buy Score Threshold Range (buy_threshold)"),
            value="65, 70, 75",
            help=tr("技术评分达到此分数时买入。", "Buy when the technical score reaches this level."),
        )
    with c_param2:
        sell_thr_input = st.text_input(
            tr("卖出评分阈值范围 (sell_threshold)", "Sell Score Threshold Range (sell_threshold)"),
            value="25, 30, 35",
            help=tr("技术评分低于此分数时卖出。", "Sell when the technical score falls below this level."),
        )

    # Parse inputs into lists
    try:
        buy_thresholds = [float(x.strip()) for x in buy_thr_input.split(",") if x.strip()]
        sell_thresholds = [float(x.strip()) for x in sell_thr_input.split(",") if x.strip()]
        strategy_params = {"buy_threshold": buy_thresholds, "sell_threshold": sell_thresholds}
    except Exception:
        st.error(tr("❌ 参数格式错误，请输入以逗号分隔的数字，例如: 65, 70, 75", "❌ Invalid parameter format. Enter comma-separated numbers, e.g. 65, 70, 75"))
        st.stop()

elif "MACross" in strategy_name:
    with c_param1:
        fast_input = st.text_input(tr("快线均线周期范围 (fast_length)", "Fast MA Period Range (fast_length)"), value="5, 10, 15")
    with c_param2:
        slow_input = st.text_input(tr("慢线均线周期范围 (slow_length)", "Slow MA Period Range (slow_length)"), value="30, 40, 50")

    try:
        fast_lengths = [int(x.strip()) for x in fast_input.split(",") if x.strip()]
        slow_lengths = [int(x.strip()) for x in slow_input.split(",") if x.strip()]
        strategy_params = {"fast_length": fast_lengths, "slow_length": slow_lengths}
    except Exception:
        st.error(tr("❌ 参数格式错误，请输入以逗号分隔的整数", "❌ Invalid parameter format. Enter comma-separated integers"))
        st.stop()

else:  # MA strategy
    with c_param1:
        ma_input = st.text_input(tr("均线周期范围 (maperiod)", "MA Period Range (maperiod)"), value="10, 15, 20, 30")
    with c_param2:
        st.info(tr("ℹ️ 单均线策略仅需配置单一周期参数。", "ℹ️ The single-MA strategy needs only one period parameter."))
        strategy_params = {}

    try:
        ma_periods = [int(x.strip()) for x in ma_input.split(",") if x.strip()]
        strategy_params = {"maperiod": ma_periods}
    except Exception:
        st.error(tr("❌ 参数格式错误，请输入以逗号分隔的整数", "❌ Invalid parameter format. Enter comma-separated integers"))
        st.stop()

# Run the backtest when button is clicked
if run_button:
    # Package parameters
    bt_params = BacktraderParams(
        start_date=bt_start,
        end_date=bt_end,
        start_cash=float(start_cash),
        commission_fee=float(commission_fee),
        sizer_percent=float(sizer_percent),
    )
    strategy_schema = StrategyBase(
        name=strategy_name,
        params=strategy_params
    )
    
    # We filter df_indicators for the backtest window to be precise
    # and to pass the pre-calculated indicators to the strategy
    backtest_df = df_indicators[
        (df_indicators["date"] >= bt_start) & 
        (df_indicators["date"] <= bt_end)
    ].copy()
    
    if len(backtest_df) < 10:
        st.error(tr(
            "❌ 回测窗口内的行情数据过少，请在左侧边栏调整“回测起始日期”或“行情起始日期”以确保充足的回测时间。",
            "❌ Too few price bars in the backtest window. Adjust the \"Backtest Start Date\" or \"Price Start Date\" "
            "in the left sidebar to allow enough backtest history.",
        ))
    else:
        with st.spinner(tr("Backtrader 正在执行历史回测与参数网格搜索...", "Backtrader is running the historical backtest and parameter grid search...")):
            try:
                # We rename columns to match Backtrader requirements in run_backtrader
                results_df = run_backtrader(backtest_df, strategy_schema, bt_params)

                if results_df.empty:
                    st.warning(tr(
                        "⚠️ 回测未产生任何有效结果。可能是因为在回测期间该股票未触发任何交易信号，或者参数范围过窄。",
                        "⚠️ The backtest produced no valid results. The stock may not have triggered any trading signals "
                        "during the backtest window, or the parameter ranges may be too narrow.",
                    ))
                else:
                    st.success(tr(
                        f"🎉 回测优化完成！共对 {len(results_df)} 组参数组合进行了历史回测。",
                        f"🎉 Backtest optimisation complete! {len(results_df)} parameter combinations were backtested.",
                    ))

                    # Sort results by Sharpe ratio descending
                    results_df = results_df.sort_values("sharpe", ascending=False).reset_index(drop=True)

                    # Save to session state for AI Analyst use
                    st.session_state['last_backtest_results'] = results_df
                    st.session_state['last_backtest_ticker'] = ticker

                    # Rename columns for friendly display
                    _col_ma = tr("均线周期", "MA Period")
                    _col_fast = tr("快线周期", "Fast MA Period")
                    _col_slow = tr("慢线周期", "Slow MA Period")
                    _col_buy = tr("买入评分阈值", "Buy Score Threshold")
                    _col_sell = tr("卖出评分阈值", "Sell Score Threshold")
                    _col_return = tr("年化收益率 (%)", "Annualised Return (%)")
                    _col_dd = tr("最大回撤 (%)", "Max Drawdown (%)")
                    _col_sharpe = tr("夏普比率", "Sharpe Ratio")
                    rename_dict = {
                        "maperiod": _col_ma,
                        "fast_length": _col_fast,
                        "slow_length": _col_slow,
                        "buy_threshold": _col_buy,
                        "sell_threshold": _col_sell,
                        "return": _col_return,
                        "dd": _col_dd,
                        "sharpe": _col_sharpe
                    }
                    display_df = results_df.rename(columns={k: v for k, v in rename_dict.items() if k in results_df.columns})

                    st.write(tr("### 🏆 策略回测结果对比表 (按夏普比率降序排列)", "### 🏆 Strategy Backtest Results (sorted by Sharpe ratio, descending)"))
                    st.dataframe(
                        display_df.style.highlight_max(subset=[_col_return, _col_sharpe], color="#ffe5e5")
                                      .highlight_min(subset=[_col_dd], color="#e6ffe6"),
                        use_container_width=True
                    )

                    st.write(tr("### 📊 参数组合绩效指标对比图 (选择图例切换指标)", "### 📊 Performance Metrics by Parameter Combination (use the legend to switch metrics)"))
                    bar_chart = draw_result_bar(display_df)
                    show_plotly(bar_chart, key="backtest_bar")
            except Exception as e:
                st.error(tr(f"❌ 执行回测失败: {e}", f"❌ Backtest failed: {e}"))
                st.exception(e)

# ── Section 4: AI-Analyst Narrative-Technical Synthesis Report ─────────────────
st.divider()
st.subheader(tr("🤖 Ask Gemini — AI 多因子深度剖析报告", "🤖 Ask Gemini — In-Depth AI Multi-Factor Report"))
st.caption(tr(
    "由 Gemini 联网检索最新商业新闻及催化剂，将该股的 AI 叙事热度 (ARF)、技术指标、筹码微观结构及历史回测绩效进行跨维度深度融合，撰写研究报告。",
    "Gemini searches live business news and catalysts, then deeply integrates the stock's AI narrative heat (ARF), "
    "technical indicators, chip microstructure and historical backtest performance into a cross-dimensional research report.",
))

if not gemini.is_enabled():
    st.info(tr(
        "ℹ️ 未配置 Gemini API 密钥。请在环境变量中设置 `GEMINI_API_KEY` 即可启用 AI 深度剖析功能。",
        "ℹ️ No Gemini API key configured. Set `GEMINI_API_KEY` in the environment to enable the in-depth AI analysis.",
    ))
else:
    # Gather data for the AI-Analyst
    # 1. arf_row (from DuckDB if it is a universe stock, otherwise mock)
    arf_row = {}
    try:
        conn = _open_conn()
        row_df = conn.execute(
            "SELECT * FROM snapshots WHERE ticker = ? ORDER BY as_of_date DESC LIMIT 1",
            [ticker]
        ).fetchdf()
        if not row_df.empty:
            arf_row = row_df.iloc[0].to_dict()
    except Exception:
        pass
        
    # If the stock is dynamic and not in snapshots, we construct a default arf_row using its current price
    if not arf_row:
        arf_row = {
            "ticker": ticker,
            "name": ticker,
            "arf": np.nan,
            "decile": np.nan,
            "e_score": np.nan,
            "v_score": np.nan,
            "price": latest_row["close"],
            "market_cap_usd": np.nan,
            "roe": np.nan,
            "ps_ratio": np.nan,
            "forward_pe": np.nan,
            "revenue_yoy_growth": np.nan,
            "froth_flag": False
        }
        
    # 2. backtest_summary (retrieve from session state if ticker matches)
    backtest_summary = tr(
        "用户尚未在此页面执行历史回测。暂无回测绩效数据。",
        "The user has not run a historical backtest on this page yet. No backtest performance data is available.",
    )
    if 'last_backtest_results' in st.session_state and st.session_state.get('last_backtest_ticker') == ticker:
        best_runs = st.session_state['last_backtest_results'].head(3)
        summary_lines = [tr(
            "已执行历史回测，最优的3组参数绩效如下：",
            "A historical backtest has been run; the top 3 parameter sets by performance are:",
        )]
        for idx, r in best_runs.iterrows():
            # Get parameter keys (all columns except return, dd, sharpe)
            param_cols = [c for c in r.index if c not in ["return", "dd", "sharpe"]]
            params_str = ", ".join([f"{col}={r[col]}" for col in param_cols])
            summary_lines.append(tr(
                f"- 组合 {idx+1} ({params_str}): 年化收益率={r.get('return', 0.0):.1f}%, "
                f"最大回撤={r.get('dd', 0.0):.1f}%, 夏普比率={r.get('sharpe', 0.0):.2f}",
                f"- Combination {idx+1} ({params_str}): annualised return={r.get('return', 0.0):.1f}%, "
                f"max drawdown={r.get('dd', 0.0):.1f}%, Sharpe ratio={r.get('sharpe', 0.0):.2f}",
            ))
        backtest_summary = "\n".join(summary_lines)

    col_analyst, _ = st.columns([1, 4])
    with col_analyst:
        analyst_btn = st.button(
            tr("✨ 生成多因子剖析报告 (约 30-45 秒)", "✨ Generate Multi-Factor Report (~30-45s)"),
            key="ai_analyst_btn",
            use_container_width=True,
        )

    if analyst_btn:
        with st.spinner(tr(
            "Gemini 正在联网检索最新资讯并撰写跨维度深度研究报告...",
            "Gemini is searching live news and drafting the cross-dimensional research report...",
        )):
            try:
                api_key = gemini.os.environ["GEMINI_API_KEY"]
                # Resolve name
                display_name = selected_option.split(" (")[1].replace(")", "") if not use_manual_ticker and " (" in selected_option else ticker
                
                report = gemini.generate_narrative_technical_report(
                    api_key=api_key,
                    ticker=ticker,
                    name=display_name,
                    arf_row=arf_row,
                    tech_row=latest_row.to_dict(),
                    chip_metrics=chip_metrics,
                    backtest_summary=backtest_summary,
                    lang=get_current_lang(),
                )
                
                st.markdown("---")
                st.markdown(report["report_text"])
                
                # Display citations and source links
                citations = report.get("citations", [])
                if citations:
                    st.write(tr("### 🔗 引用来源与参考链接", "### 🔗 Citations & Reference Links"))
                    for c in citations:
                        st.markdown(f"- [{c.title or c.uri}]({c.uri})")

                # Display queries
                queries = report.get("queries", [])
                if queries:
                    with st.expander(tr(f"🔍 检索关键词（{len(queries)}）", f"🔍 Search Queries ({len(queries)})"), expanded=False):
                        for q in queries:
                            st.markdown(f"- `{q}`")
            except Exception as exc:
                st.error(tr(f"调用 Gemini 失败: {exc}", f"Gemini call failed: {exc}"))
                st.exception(exc)

