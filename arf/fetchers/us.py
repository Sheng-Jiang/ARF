"""US stock fetcher: yfinance primary, historical P/S for EV/S percentile."""
import logging
import math
from datetime import date

import pandas as pd
import yfinance as yf
from tenacity import retry, stop_after_attempt, wait_exponential

from arf.config import UniverseEntry
from arf.fetchers.base import StockData

log = logging.getLogger(__name__)


def _safe(val: object) -> float | None:
    """Return float or None; suppress NaN and Inf."""
    if val is None:
        return None
    try:
        f = float(val)
        return None if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return None


def _to_naive(ts: pd.Timestamp) -> pd.Timestamp:
    return ts.tz_localize(None) if ts.tzinfo is not None else ts


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _yf_fetch(ticker: str) -> tuple[dict, yf.Ticker]:
    """Fetch yfinance info dict and return it alongside the Ticker object."""
    t = yf.Ticker(ticker)
    return t.info or {}, t


def _eps_forward_growth(info: dict) -> float | None:
    """Compute 1yr forward EPS growth from forwardEps / trailingEps.

    Falls back to earningsGrowth if trailing EPS is unavailable or negative
    (e.g., loss-making companies where the ratio is undefined).
    """
    trailing = _safe(info.get("trailingEps"))
    forward = _safe(info.get("forwardEps"))
    if trailing is not None and forward is not None and trailing > 0:
        return (forward / trailing) - 1.0
    return _safe(info.get("earningsGrowth"))


def _ev_sales_5yr_percentile(t: yf.Ticker, info: dict) -> float | None:
    """Compute EV/Sales 5yr percentile from yfinance historical data.

    Uses historical P/S (price × shares / annual revenue) as a proxy for EV/Sales,
    since historical debt/cash data is not available from the yfinance free tier.
    Compares the current EV/Sales (enterpriseToRevenue) against the resulting
    distribution to produce a 0–100 percentile rank.
    """
    current_ev_sales = _safe(info.get("enterpriseToRevenue"))
    shares = _safe(info.get("sharesOutstanding"))
    if current_ev_sales is None or not shares:
        return None
    try:
        income = t.income_stmt
        if income is None or income.empty or "Total Revenue" not in income.index:
            return None
        rev_series = income.loc["Total Revenue"].dropna().sort_index(ascending=False)
        if len(rev_series) == 0:
            return None

        hist = t.history(period="5y", interval="3mo")
        if hist.empty or len(hist) < 4:
            return None

        # Build (date, revenue) pairs with timezone-naive dates
        rev_pairs = [
            (_to_naive(pd.Timestamp(d)), float(v))
            for d, v in zip(rev_series.index, rev_series.values, strict=False)
            if v and not math.isnan(float(v)) and float(v) > 0
        ]
        if not rev_pairs:
            return None

        historical_ps: list[float] = []
        for dt, row in hist.iterrows():
            price = _safe(row["Close"])
            if price is None:
                continue
            mktcap = price * shares
            dt_naive = _to_naive(pd.Timestamp(dt))
            # Use the most recent annual revenue report within 90 days after this quarter
            rev = None
            for rd, rv in rev_pairs:
                if rd <= dt_naive + pd.Timedelta(days=90):
                    rev = rv
                    break
            if rev is None:
                rev = rev_pairs[-1][1]  # oldest available as last resort
            if rev > 0:
                historical_ps.append(mktcap / rev)

        if len(historical_ps) < 4:
            return None

        return sum(1 for v in historical_ps if v <= current_ev_sales) / len(historical_ps) * 100

    except Exception as exc:
        log.debug("EV/S percentile failed for %s: %s", info.get("symbol", "?"), exc)
        return None


def fetch_us(entry: UniverseEntry, as_of: date) -> StockData:
    """Fetch market data and fundamentals for a US-listed stock."""
    result = StockData(ticker=entry.ticker, as_of_date=as_of, currency="USD", fx_rate_usd=1.0)
    try:
        info, t = _yf_fetch(entry.ticker)
        if not info:
            log.warning("yfinance returned empty info for %s", entry.ticker)
            return result

        result.price = _safe(info.get("currentPrice") or info.get("regularMarketPrice"))
        result.market_cap_usd = _safe(info.get("marketCap"))
        result.ev_usd = _safe(info.get("enterpriseValue"))
        result.shares_outstanding = _safe(info.get("sharesOutstanding"))
        result.revenue_ttm = _safe(info.get("totalRevenue"))
        result.revenue_yoy_growth = _safe(info.get("revenueGrowth"))
        result.gross_margin = _safe(info.get("grossMargins"))
        result.operating_income = _safe(info.get("operatingIncome") or info.get("operatingCashflow"))
        result.net_income = _safe(info.get("netIncomeToCommon"))
        result.free_cash_flow = _safe(info.get("freeCashflow"))
        result.total_equity = _safe(info.get("bookValue"))
        result.roe = _safe(info.get("returnOnEquity"))
        result.roic = _safe(info.get("returnOnAssets"))
        result.forward_pe = _safe(info.get("forwardPE"))
        result.eps_2yr_cagr = _eps_forward_growth(info)
        result.revenue_3yr_cagr = _safe(info.get("revenueGrowth"))
        result.revenue_ntm = _safe(info.get("totalRevenue"))
        result.ps_ratio = _safe(info.get("priceToSalesTrailing12Months"))
        result.ev_sales = _safe(info.get("enterpriseToRevenue"))
        result.data_source = "yfinance"

        # Per-share FCF → absolute (yfinance sometimes returns per-share)
        if (result.free_cash_flow is not None
                and result.shares_outstanding is not None
                and abs(result.free_cash_flow) < 1e6):
            result.free_cash_flow = result.free_cash_flow * result.shares_outstanding

        # EV/Sales 5yr percentile from historical yfinance data
        ev_pct = _ev_sales_5yr_percentile(t, info)
        if ev_pct is not None:
            result.ev_sales_5yr_percentile = ev_pct

    except Exception as exc:
        log.warning("fetch_us failed for %s: %s", entry.ticker, exc)

    return result
