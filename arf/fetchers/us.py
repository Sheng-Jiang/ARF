"""US stock fetcher: yfinance primary, stockanalysis.com for EV/S 5yr percentile."""
import logging
import math
from datetime import date

import requests
import yfinance as yf
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from arf.config import UniverseEntry
from arf.fetchers.base import StockData

log = logging.getLogger(__name__)

_SA_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}


def _safe(val: object) -> float | None:
    """Return float or None; suppress NaN."""
    if val is None:
        return None
    try:
        f = float(val)
        return None if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return None


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _yf_info(ticker: str) -> dict:
    t = yf.Ticker(ticker)
    return t.info or {}


def _ev_sales_percentile_from_stockanalysis(ticker: str) -> float | None:
    """Scrape 5-year EV/Revenue history from stockanalysis.com and return current percentile."""
    url = f"https://stockanalysis.com/stocks/{ticker.lower()}/financials/ratios/"
    try:
        resp = requests.get(url, headers=_SA_HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        # Look for EV/Revenue row in the ratios table
        for row in soup.find_all("tr"):
            cells = row.find_all("td")
            if not cells:
                continue
            label = cells[0].get_text(strip=True).lower()
            if "ev/revenue" in label or "ev / revenue" in label:
                values = [_safe(c.get_text(strip=True).replace(",", "")) for c in cells[1:]]
                values = [v for v in values if v is not None and v > 0]
                if len(values) >= 2:
                    current = values[0]
                    pct = sum(1 for v in values if v <= current) / len(values) * 100
                    return pct
    except Exception as exc:
        log.debug("stockanalysis scrape failed for %s: %s", ticker, exc)
    return None


def fetch_us(entry: UniverseEntry, as_of: date) -> StockData:
    """Fetch market data and fundamentals for a US-listed stock."""
    result = StockData(ticker=entry.ticker, as_of_date=as_of, currency="USD", fx_rate_usd=1.0)
    try:
        info = _yf_info(entry.ticker)
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
        result.eps_2yr_cagr = _safe(info.get("earningsGrowth"))
        result.revenue_3yr_cagr = _safe(info.get("revenueGrowth"))
        result.revenue_ntm = _safe(info.get("totalRevenue"))
        result.ps_ratio = _safe(info.get("priceToSalesTrailing12Months"))
        result.ev_sales = _safe(info.get("enterpriseToRevenue"))
        result.data_source = "yfinance"

        # EV/Sales 5yr percentile from stockanalysis.com
        ev_pct = _ev_sales_percentile_from_stockanalysis(entry.ticker)
        if ev_pct is not None:
            result.ev_sales_5yr_percentile = ev_pct
            result.data_source = "yfinance+stockanalysis"

        # Per-share FCF → absolute (yfinance sometimes returns per-share)
        if (result.free_cash_flow is not None
                and result.shares_outstanding is not None
                and abs(result.free_cash_flow) < 1e6):
            result.free_cash_flow = result.free_cash_flow * result.shares_outstanding

    except Exception as exc:
        log.warning("fetch_us failed for %s: %s", entry.ticker, exc)

    return result
