"""China/HK stock fetcher: AkShare primary, yfinance for HK/ADR tickers."""
import logging
import math
from datetime import date

import akshare as ak
import pandas as pd
import yfinance as yf
from tenacity import retry, stop_after_attempt, wait_exponential

from arf.config import UniverseEntry
from arf.fetchers.base import StockData

log = logging.getLogger(__name__)


def _safe(val: object) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        return None if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return None


def _is_a_share(ticker: str) -> bool:
    return ticker.endswith(".SZ") or ticker.endswith(".SH")


def _is_hk(ticker: str) -> bool:
    return ticker.endswith(".HK")


def _a_share_code(ticker: str) -> str:
    """Convert '300308.SZ' → '300308'."""
    return ticker.split(".")[0]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _fetch_akshare_spot(code: str) -> dict:
    """Fetch real-time quote for an A-share stock."""
    df = ak.stock_individual_info_em(symbol=code)
    return {row["item"]: row["value"] for _, row in df.iterrows()}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _fetch_akshare_financials(code: str) -> pd.DataFrame:
    """Fetch key financial indicators for an A-share stock."""
    return ak.stock_financial_abstract_ths(symbol=code, indicator="按年度")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _yf_info(ticker: str) -> dict:
    t = yf.Ticker(ticker)
    return t.info or {}


def _fetch_a_share(entry: UniverseEntry, as_of: date) -> StockData:
    code = _a_share_code(entry.ticker)
    result = StockData(ticker=entry.ticker, as_of_date=as_of, currency="CNY")

    try:
        spot = _fetch_akshare_spot(code)
        result.price = _safe(spot.get("最新") or spot.get("股价") or spot.get("现价"))
        market_cap_cny = _safe(spot.get("总市值"))
        if market_cap_cny is not None:
            result.market_cap_usd = market_cap_cny / 7.20
        ps_val = _safe(spot.get("市销率") or spot.get("PS"))
        if ps_val is not None:
            result.ps_ratio = ps_val
        pe_val = _safe(spot.get("市盈率-动态") or spot.get("市盈率TTM") or spot.get("PE"))
        if pe_val and pe_val > 0:
            result.forward_pe = pe_val
        result.data_source = "akshare"
    except Exception as exc:
        log.debug("akshare spot failed for %s: %s", code, exc)

    try:
        fin = _fetch_akshare_financials(code)
        if not fin.empty:
            latest = fin.iloc[0]
            # Revenue and growth
            rev_col = next((c for c in fin.columns if "营业收入" in c or "总收入" in c), None)
            if rev_col:
                result.revenue_ttm = _safe(latest.get(rev_col))
            # 扣非净利润 (after non-recurring items)
            kuofei_col = next(
                (c for c in fin.columns if "扣非" in c or "非经常" in c), None
            )
            if kuofei_col:
                result.net_income_excl_nonrecurring = _safe(latest.get(kuofei_col))
            # ROE (使用扣非 if available)
            roe_col = next((c for c in fin.columns if "净资产收益率" in c or "ROE" in c), None)
            if roe_col:
                roe_val = _safe(latest.get(roe_col))
                if roe_val is not None:
                    result.roe = roe_val / 100.0 if roe_val > 1 else roe_val
            # Gross margin
            gm_col = next((c for c in fin.columns if "毛利率" in c), None)
            if gm_col:
                gm = _safe(latest.get(gm_col))
                if gm is not None:
                    result.gross_margin = gm / 100.0 if gm > 1 else gm
    except Exception as exc:
        log.debug("akshare financials failed for %s: %s", code, exc)

    return result


def _fetch_hk_or_adr(entry: UniverseEntry, as_of: date) -> StockData:
    """Fetch HK-listed or ADR via yfinance."""
    result = StockData(ticker=entry.ticker, as_of_date=as_of)
    try:
        # yfinance uses e.g. "0700.HK"
        yf_ticker = entry.ticker if "." in entry.ticker else entry.ticker
        info = _yf_info(yf_ticker)
        if not info:
            return result

        result.currency = info.get("currency", "HKD" if _is_hk(entry.ticker) else "USD")
        fx = 7.78 if result.currency == "HKD" else (7.20 if result.currency == "CNY" else 1.0)
        result.fx_rate_usd = fx

        result.price = _safe(info.get("currentPrice") or info.get("regularMarketPrice"))
        mktcap_local = _safe(info.get("marketCap"))
        result.market_cap_usd = mktcap_local / fx if mktcap_local else None
        result.ev_usd = _safe(info.get("enterpriseValue"))
        if result.ev_usd and fx != 1.0:
            result.ev_usd = result.ev_usd / fx
        result.revenue_ttm = _safe(info.get("totalRevenue"))
        result.revenue_yoy_growth = _safe(info.get("revenueGrowth"))
        result.gross_margin = _safe(info.get("grossMargins"))
        result.roe = _safe(info.get("returnOnEquity"))
        result.free_cash_flow = _safe(info.get("freeCashflow"))
        result.forward_pe = _safe(info.get("forwardPE"))
        trailing = _safe(info.get("trailingEps"))
        forward = _safe(info.get("forwardEps"))
        if trailing is not None and forward is not None and trailing > 0:
            result.eps_2yr_cagr = (forward / trailing) - 1.0
        else:
            result.eps_2yr_cagr = _safe(info.get("earningsGrowth"))
        result.ps_ratio = _safe(info.get("priceToSalesTrailing12Months"))
        result.ev_sales = _safe(info.get("enterpriseToRevenue"))
        result.data_source = "yfinance"
    except Exception as exc:
        log.warning("yfinance failed for %s: %s", entry.ticker, exc)
    return result


def fetch_china(entry: UniverseEntry, as_of: date) -> StockData:
    """Fetch data for a China-leg stock (A-share, HK, or ADR)."""
    if _is_a_share(entry.ticker):
        return _fetch_a_share(entry, as_of)
    else:
        return _fetch_hk_or_adr(entry, as_of)
