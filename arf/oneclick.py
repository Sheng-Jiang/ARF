"""One-Click Weekly Report generator.

Orchestrates data assembly from DuckDB snapshots, runs batch backtests on top
China-leg stocks, calls Gemini for a synthesis, and renders a standalone HTML
report.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

log = logging.getLogger(__name__)

# Default backtest lookback: 6 months
BACKTEST_LOOKBACK_DAYS = 180
BACKTEST_CASH = 100_000.0
BACKTEST_COMMISSION = 0.001
BACKTEST_STAKE = 100
TOP_N_STOCKS = 5

# Strategy parameter grids (sensible defaults for auto-report)
DEFAULT_STRATEGY_GRIDS: dict[str, dict] = {
    "MA 策略 (单均线)": {"maperiod": [10, 20, 30]},
    "MACross 策略 (双均线交叉)": {"fast_length": [5, 10], "slow_length": [30, 60]},
    "TechnicalScore 策略 (智能技术评分)": {"buy_threshold": [65, 70], "sell_threshold": [30, 35]},
}


@dataclass
class StockBacktestResult:
    """Backtest results for a single stock across all strategies."""
    ticker: str
    name: str
    tech_score: float | None = None
    rsi: float | None = None
    ma_bullish: bool = False
    chip_profit_ratio: float | None = None
    chip_avg_cost: float | None = None
    strategy_results: dict[str, pd.DataFrame] = field(default_factory=dict)
    # Best strategy summary
    best_strategy: str = ""
    best_sharpe: float = 0.0
    best_return: float = 0.0
    best_max_dd: float = 0.0


@dataclass
class ThermometerDelta:
    """Week-over-week thermometer change for one leg."""
    leg: str
    absolute_froth: int = 0
    absolute_froth_delta: str = "—"
    relative_froth: int = 0
    relative_froth_delta: str = "—"
    median_ev_sales_pct: float = 0.0
    ev_sales_delta: str = "—"
    median_growth_gap: float = 0.0
    growth_gap_delta: str = "—"
    total: int = 0


@dataclass
class ReportData:
    """All data needed to render the weekly report."""
    as_of: date
    # Snapshot summary
    us_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    china_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    d1_us: int = 0
    d1_china: int = 0
    froth_us: int = 0
    froth_china: int = 0
    # Thermometer trend
    thermo_deltas: list[ThermometerDelta] = field(default_factory=list)
    thermo_chart_html: str = ""
    valuation_chart_html: str = ""
    # Backtests
    backtest_stocks: list[StockBacktestResult] = field(default_factory=list)
    # Gemini synthesis
    gemini_synthesis: str = ""
    gemini_citations: list[dict] = field(default_factory=list)


def select_top_china_stocks(
    snapshot_df: pd.DataFrame,
    n: int = TOP_N_STOCKS,
) -> pd.DataFrame:
    """Select top-N China-leg stocks by ARF score (A+H shares combined)."""
    china = snapshot_df[snapshot_df["leg"] == "China"].copy()
    china = china.dropna(subset=["arf"])
    return china.sort_values("arf", ascending=False).head(n)


def _fetch_prices_for_ticker(
    ticker: str,
    start_str: str,
    end_str: str,
) -> pd.DataFrame:
    """Fetch daily prices for A-shares (AkShare) or HK (yfinance)."""
    if ticker.endswith((".SZ", ".SH")):
        from arf.fetchers.akshare import fetch_daily_prices
        return fetch_daily_prices(ticker, start_str, end_str, adjust="qfq")
    else:
        from arf.run import fetch_daily_prices_yf
        return fetch_daily_prices_yf(ticker, start_str, end_str)


def run_batch_backtests(
    top_stocks: pd.DataFrame,
    as_of: date,
    lookback_days: int = BACKTEST_LOOKBACK_DAYS,
) -> list[StockBacktestResult]:
    """Run all 3 strategies on each stock and return structured results."""
    from arf.technical import (
        calculate_chip_distribution,
        calculate_technical_indicators,
        score_stock_technical,
    )
    from webapp.backtest import run_backtrader
    from webapp.schemas import BacktraderParams, StrategyBase

    start_date = as_of - timedelta(days=lookback_days + 120)  # extra for MA warm-up
    bt_start = as_of - timedelta(days=lookback_days)
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = as_of.strftime("%Y-%m-%d")

    bt_params = BacktraderParams(
        start_date=bt_start,
        end_date=as_of,
        start_cash=BACKTEST_CASH,
        commission_fee=BACKTEST_COMMISSION,
        stake=BACKTEST_STAKE,
    )

    results: list[StockBacktestResult] = []

    for _, row in top_stocks.iterrows():
        ticker = str(row["ticker"])
        name = str(row.get("name", ticker))
        log.info("Running batch backtest for %s", ticker)

        result = StockBacktestResult(ticker=ticker, name=name)

        try:
            # 1. Fetch prices
            prices_df = _fetch_prices_for_ticker(ticker, start_str, end_str)
            if prices_df.empty:
                log.warning("No price data for %s — skipping backtest", ticker)
                results.append(result)
                continue

            # 2. Technical indicators
            ind_df = calculate_technical_indicators(prices_df)
            if ind_df.empty:
                results.append(result)
                continue

            # 3. Chip distribution
            mc_usd = row.get("market_cap_usd")
            fx = row.get("fx_rate_usd", 1.0)
            price = row.get("price")
            if mc_usd and price and price > 0:
                shares = (mc_usd * (fx or 1.0)) / price
                if shares < 1_000_000:
                    shares *= 1_000_000
            else:
                shares = 100_000_000.0
            is_a = ticker.endswith((".SZ", ".SH"))
            chip_metrics = calculate_chip_distribution(prices_df, shares, is_a_share=is_a)
            profit_ratio, avg_cost, *_ = chip_metrics

            # 4. Score
            latest = ind_df.iloc[-1]
            tech_score = score_stock_technical(latest, chip_metrics)
            result.tech_score = tech_score
            result.rsi = latest.get("rsi")
            result.ma_bullish = bool(latest.get("ma_bullish_alignment", False))
            result.chip_profit_ratio = profit_ratio
            result.chip_avg_cost = avg_cost

            # 5. Run 3 strategies
            best_sharpe = -999.0
            for strat_name, param_grid in DEFAULT_STRATEGY_GRIDS.items():
                try:
                    strategy_schema = StrategyBase(name=strat_name, params=param_grid)
                    bt_df = ind_df[
                        (ind_df["date"] >= bt_start) & (ind_df["date"] <= as_of)
                    ].copy()
                    if len(bt_df) < 10:
                        continue
                    res_df = run_backtrader(bt_df, strategy_schema, bt_params)
                    if not res_df.empty:
                        res_df = res_df.sort_values("sharpe", ascending=False).reset_index(drop=True)
                        result.strategy_results[strat_name] = res_df
                        top_row = res_df.iloc[0]
                        if top_row.get("sharpe", 0.0) > best_sharpe:
                            best_sharpe = top_row["sharpe"]
                            result.best_strategy = strat_name
                            result.best_sharpe = float(top_row.get("sharpe", 0.0))
                            result.best_return = float(top_row.get("return", 0.0))
                            result.best_max_dd = float(top_row.get("dd", 0.0))
                except Exception as exc:
                    log.warning("Strategy %s failed for %s: %s", strat_name, ticker, exc)

        except Exception as exc:
            log.warning("Batch backtest failed for %s: %s", ticker, exc)

        results.append(result)

    return results


def _compute_thermo_deltas(thermo: pd.DataFrame) -> list[ThermometerDelta]:
    """Compute week-over-week thermometer deltas."""
    dates = sorted(thermo["as_of_date"].unique())
    if len(dates) < 2:
        # No delta possible — just return latest
        deltas = []
        for leg in ["US", "China"]:
            leg_df = thermo[thermo["leg"] == leg]
            if leg_df.empty:
                continue
            latest = leg_df.sort_values("as_of_date").iloc[-1]
            deltas.append(ThermometerDelta(
                leg=leg,
                absolute_froth=int(latest.get("count_absolute_froth", 0)),
                relative_froth=int(latest.get("count_froth", 0)),
                median_ev_sales_pct=float(latest.get("median_ev_sales_pct", 0)),
                median_growth_gap=float(latest.get("median_growth_gap_pct", 0)),
                total=int(latest.get("total", 0)),
            ))
        return deltas

    latest_dt, prior_dt = dates[-1], dates[-2]

    def _delta_int(cur, prv, col):
        if prv is None or col not in prv or pd.isna(prv[col]) or pd.isna(cur[col]):
            return "—"
        diff = int(cur[col]) - int(prv[col])
        return f"+{diff}" if diff > 0 else str(diff)

    def _delta_float(cur, prv, col):
        if prv is None or col not in prv or pd.isna(prv[col]) or pd.isna(cur[col]):
            return "—"
        diff = float(cur[col]) - float(prv[col])
        return f"+{diff:.2f}%" if diff > 0 else f"{diff:.2f}%"

    deltas = []
    for leg in ["US", "China"]:
        l_row = thermo[(thermo["as_of_date"] == latest_dt) & (thermo["leg"] == leg)]
        p_row = thermo[(thermo["as_of_date"] == prior_dt) & (thermo["leg"] == leg)]
        if l_row.empty:
            continue
        cur = l_row.iloc[0]
        prv = p_row.iloc[0] if not p_row.empty else None
        deltas.append(ThermometerDelta(
            leg=leg,
            absolute_froth=int(cur.get("count_absolute_froth", 0)),
            absolute_froth_delta=_delta_int(cur, prv, "count_absolute_froth"),
            relative_froth=int(cur.get("count_froth", 0)),
            relative_froth_delta=_delta_int(cur, prv, "count_froth"),
            median_ev_sales_pct=float(cur.get("median_ev_sales_pct", 0) or 0),
            ev_sales_delta=_delta_float(cur, prv, "median_ev_sales_pct"),
            median_growth_gap=float(cur.get("median_growth_gap_pct", 0) or 0),
            growth_gap_delta=_delta_float(cur, prv, "median_growth_gap_pct"),
            total=int(cur.get("total", 0)),
        ))
    return deltas


def _render_thermo_chart(thermo: pd.DataFrame) -> str:
    """Render thermometer froth-count trend as an embeddable Plotly HTML div."""
    fig = go.Figure()
    us = thermo[thermo["leg"] == "US"].sort_values("as_of_date")
    cn = thermo[thermo["leg"] == "China"].sort_values("as_of_date")

    for label, df, color in [("美股", us, "#d62728"), ("中股", cn, "#e6a817")]:
        if df.empty:
            continue
        if "count_absolute_froth" in df.columns:
            fig.add_trace(go.Scatter(
                x=df["as_of_date"], y=df["count_absolute_froth"],
                name=f"{label} — 绝对泡沫数", mode="lines+markers",
                line=dict(color=color, width=3), marker=dict(size=8),
            ))
        fig.add_trace(go.Scatter(
            x=df["as_of_date"], y=df["count_froth"],
            name=f"{label} — 相对泡沫数 (D1)", mode="lines+markers",
            line=dict(color=color, width=1.5, dash="dash"), marker=dict(size=6),
        ))

    fig.update_layout(
        title="ARF 泡沫温度计趋势",
        xaxis_title="日期", yaxis_title="股票数量",
        hovermode="x unified", height=380,
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(30,30,40,0.8)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    return fig.to_html(full_html=False, include_plotlyjs=False)


def _render_valuation_chart(thermo: pd.DataFrame) -> str:
    """Render valuation stretch + growth gap trend as embeddable Plotly HTML div."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    us = thermo[thermo["leg"] == "US"].sort_values("as_of_date")
    cn = thermo[thermo["leg"] == "China"].sort_values("as_of_date")

    for label, df, color in [("美股", us, "#d62728"), ("中股", cn, "#e6a817")]:
        if df.empty:
            continue
        fig.add_trace(go.Scatter(
            x=df["as_of_date"], y=df["median_ev_sales_pct"],
            name=f"{label} — EV/Sales 5年分位数", mode="lines+markers",
            line=dict(color=color, width=2), marker=dict(size=6),
        ), secondary_y=False)
        fig.add_trace(go.Scatter(
            x=df["as_of_date"], y=df["median_growth_gap_pct"],
            name=f"{label} — 隐含增长差值 (%)", mode="lines+markers",
            line=dict(color=color, width=1.5, dash="dash"), marker=dict(size=5),
        ), secondary_y=True)

    fig.add_hline(y=50, line_dash="dot", line_color="gray", opacity=0.5)
    fig.update_layout(
        title="估值热度与隐含增长差值走势",
        xaxis_title="日期", hovermode="x unified", height=350,
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(30,30,40,0.8)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    fig.update_yaxes(title_text="EV/Sales 5年分位数 (%)", range=[0, 100], secondary_y=False)
    fig.update_yaxes(title_text="隐含增长差值 (%)", secondary_y=True)
    return fig.to_html(full_html=False, include_plotlyjs=False)


def build_report_data(
    as_of: date,
    db_path: Path = Path("data/arf.db"),
) -> ReportData:
    """Assemble all data needed for the weekly report."""
    from arf.db import init_db, query_snapshot, query_thermometer_series

    conn = init_db(db_path)
    snapshot = query_snapshot(conn, as_of)
    thermo = query_thermometer_series(conn)
    conn.close()

    us = snapshot[snapshot["leg"] == "US"]
    china = snapshot[snapshot["leg"] == "China"]
    scored = snapshot[snapshot["leg"].isin(["US", "China"])]

    report = ReportData(as_of=as_of)
    report.us_df = us
    report.china_df = china
    report.d1_us = int((us["decile"] == 1).sum()) if len(us) else 0
    report.d1_china = int((china["decile"] == 1).sum()) if len(china) else 0
    report.froth_us = int((us["froth_flag"] == True).sum()) if len(us) else 0  # noqa: E712
    report.froth_china = int((china["froth_flag"] == True).sum()) if len(china) else 0  # noqa: E712

    # Thermometer
    report.thermo_deltas = _compute_thermo_deltas(thermo)
    report.thermo_chart_html = _render_thermo_chart(thermo)
    report.valuation_chart_html = _render_valuation_chart(thermo)

    # Backtests on top-5 China stocks
    top_china = select_top_china_stocks(scored)
    if not top_china.empty:
        log.info("Running backtests on top %d China stocks: %s",
                 len(top_china), top_china["ticker"].tolist())
        report.backtest_stocks = run_batch_backtests(top_china, as_of)

    return report


def _backtest_summary_for_gemini(stocks: list[StockBacktestResult]) -> str:
    """Format backtest results as a text block for the Gemini prompt."""
    lines = []
    for s in stocks:
        lines.append(f"### {s.ticker} ({s.name})")
        lines.append(f"  技术评分: {s.tech_score:.1f}" if s.tech_score else "  技术评分: N/A")
        lines.append(f"  均线多头: {'是' if s.ma_bullish else '否'}")
        lines.append(f"  RSI: {s.rsi:.1f}" if s.rsi else "  RSI: N/A")
        lines.append(
            f"  获利盘: {s.chip_profit_ratio*100:.1f}%"
            if s.chip_profit_ratio is not None else "  获利盘: N/A"
        )
        if s.strategy_results:
            lines.append(f"  最优策略: {s.best_strategy}")
            lines.append(f"  最优夏普: {s.best_sharpe:.2f}, 年化收益: {s.best_return:.1f}%, 最大回撤: {s.best_max_dd:.1f}%")
            for name, df in s.strategy_results.items():
                if not df.empty:
                    top = df.iloc[0]
                    lines.append(
                        f"    {name}: 夏普={top.get('sharpe', 0):.2f}, "
                        f"收益={top.get('return', 0):.1f}%, "
                        f"回撤={top.get('dd', 0):.1f}%"
                    )
        else:
            lines.append("  无回测数据")
        lines.append("")
    return "\n".join(lines)


def generate_report_html(report: ReportData) -> str:
    """Render report data into a standalone HTML file."""
    from jinja2 import Environment, FileSystemLoader

    template_dir = Path(__file__).parent / "templates"
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=True,
    )
    template = env.get_template("report_template.html")

    # Prepare table rows for US and China
    def _prepare_rows(df: pd.DataFrame) -> list[dict]:
        rows = []
        for _, r in df.sort_values("arf", ascending=False, na_position="last").iterrows():
            rows.append({
                "ticker": r.get("ticker", ""),
                "name": r.get("name", ""),
                "layer": r.get("layer", ""),
                "arf": f"{r['arf']:.1f}" if pd.notna(r.get("arf")) else "—",
                "decile": int(r["decile"]) if pd.notna(r.get("decile")) else "—",
                "e_score": f"{r['e_score']:.1f}" if pd.notna(r.get("e_score")) else "—",
                "v_score": f"{r['v_score']:.1f}" if pd.notna(r.get("v_score")) else "—",
                "froth": bool(r.get("froth_flag")),
                "forward_pe": f"{r['forward_pe']:.1f}" if pd.notna(r.get("forward_pe")) else "—",
                "ps_ratio": f"{r['ps_ratio']:.1f}" if pd.notna(r.get("ps_ratio")) else "—",
                "roe": f"{r['roe']*100:.1f}%" if pd.notna(r.get("roe")) else "—",
                "rev_yoy": f"{r['revenue_yoy_growth']*100:.1f}%" if pd.notna(r.get("revenue_yoy_growth")) else "—",
            })
        return rows

    # Prepare backtest cards
    bt_cards = []
    for s in report.backtest_stocks:
        strategies = []
        for name, df in s.strategy_results.items():
            if df.empty:
                continue
            top = df.iloc[0]
            param_cols = [c for c in top.index if c not in ["return", "dd", "sharpe"]]
            params_str = ", ".join(f"{c}={top[c]}" for c in param_cols)
            strategies.append({
                "name": name,
                "params": params_str,
                "ret": f"{top.get('return', 0):.1f}",
                "sharpe": f"{top.get('sharpe', 0):.2f}",
                "dd": f"{top.get('dd', 0):.1f}",
            })
        bt_cards.append({
            "ticker": s.ticker,
            "name": s.name,
            "tech_score": f"{s.tech_score:.1f}" if s.tech_score else "N/A",
            "rsi": f"{s.rsi:.1f}" if s.rsi else "N/A",
            "ma_bullish": "✅ 是" if s.ma_bullish else "❌ 否",
            "chip_profit": f"{s.chip_profit_ratio*100:.1f}%" if s.chip_profit_ratio is not None else "N/A",
            "chip_avg_cost": f"¥{s.chip_avg_cost:.2f}" if s.chip_avg_cost else "N/A",
            "best_strategy": s.best_strategy,
            "best_sharpe": f"{s.best_sharpe:.2f}",
            "best_return": f"{s.best_return:.1f}",
            "best_dd": f"{s.best_max_dd:.1f}",
            "strategies": strategies,
        })

    from datetime import datetime

    html = template.render(
        as_of=report.as_of.isoformat(),
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        d1_us=report.d1_us,
        d1_china=report.d1_china,
        froth_us=report.froth_us,
        froth_china=report.froth_china,
        us_rows=_prepare_rows(report.us_df) if not report.us_df.empty else [],
        china_rows=_prepare_rows(report.china_df) if not report.china_df.empty else [],
        thermo_deltas=report.thermo_deltas,
        thermo_chart=report.thermo_chart_html,
        valuation_chart=report.valuation_chart_html,
        backtest_cards=bt_cards,
        gemini_synthesis=report.gemini_synthesis,
        gemini_citations=report.gemini_citations,
        lookback_months=BACKTEST_LOOKBACK_DAYS // 30,
    )
    return html


def generate_oneclick_report(
    as_of: date,
    db_path: Path = Path("data/arf.db"),
    report_dir: Path = Path("reports"),
    trigger_source: str = "manual",
    enable_gemini: bool = True,
) -> Path:
    """End-to-end: build data, call Gemini, render HTML, save, record in DB.

    Returns the path to the generated HTML report.
    """
    log.info("Generating one-click report for %s (trigger: %s)", as_of, trigger_source)

    report_data = build_report_data(as_of, db_path)

    # Gemini synthesis
    if enable_gemini and os.getenv("GEMINI_API_KEY"):
        try:
            from webapp.gemini import generate_weekly_synthesis
            synthesis_result = generate_weekly_synthesis(report_data)
            report_data.gemini_synthesis = synthesis_result.get("report_text", "")
            report_data.gemini_citations = [
                {"title": c.title, "uri": c.uri}
                for c in synthesis_result.get("citations", [])
            ]
        except Exception:
            log.exception("Gemini weekly synthesis failed — report will lack AI commentary")
    else:
        log.info("Gemini API key not set — skipping AI synthesis")

    html = generate_report_html(report_data)

    report_dir.mkdir(parents=True, exist_ok=True)
    out_path = report_dir / f"weekly_report_{as_of}.html"
    out_path.write_text(html, encoding="utf-8")
    log.info("Report written to %s", out_path)

    # Record in DB
    try:
        from arf.db import init_db, upsert_weekly_report
        conn = init_db(db_path)
        upsert_weekly_report(
            conn,
            as_of_date=as_of,
            report_path=str(out_path),
            gemini_summary=report_data.gemini_synthesis[:2000] if report_data.gemini_synthesis else "",
            stocks_covered=json.dumps([s.ticker for s in report_data.backtest_stocks]),
            trigger_source=trigger_source,
        )
        conn.close()
    except Exception:
        log.exception("Failed to record weekly report in DB")

    return out_path
