"""Market-aware daily price + outstanding-shares fetchers.

Routes A-shares (.SZ/.SH) to the existing AkShare/Tencent + Baostock path, and
HK (.HK) / US tickers to yfinance — reusing the data sources already proven in
``arf/fetchers/us.py`` and ``arf/fetchers/china.py``. Used by the
"技术指标与回测" Streamlit page so it can analyse A股、港股 and 美股 alike.
"""
import logging
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf
from tenacity import retry, stop_after_attempt, wait_exponential

from arf.fetchers.akshare import (
    fetch_daily_prices as _fetch_a_prices,
)
from arf.fetchers.akshare import (
    fetch_hk_daily_prices as _fetch_hk_prices,
)
from arf.fetchers.akshare import (
    fetch_outstanding_shares as _fetch_a_shares,
)

log = logging.getLogger(__name__)

# Currency symbol per market, for display only.
CURRENCY_SYMBOLS = {"A": "¥", "HK": "HK$", "US": "$"}

_SHARES_FALLBACK = 100_000_000.0  # 100M shares, matches akshare.fetch_outstanding_shares

# Below this many bars, treat a yfinance HK result as throttled (Yahoo serves newly
# listed HK names only a 1d/5d window) and fall back to AkShare for full history.
_HK_MIN_HISTORY_ROWS = 30


def detect_market(ticker: str) -> str:
    """Classify a ticker into 'A' (A-share), 'HK' (Hong Kong) or 'US'.

    A-shares carry a .SZ/.SH suffix, HK carries .HK, and everything else
    (bare symbols, ADRs like BIDU/BABA/GDS) is treated as US-listed.
    """
    t = ticker.strip().upper()
    if t.endswith((".SZ", ".SH")):
        return "A"
    if t.endswith(".HK"):
        return "HK"
    return "US"


def _yf_symbol(ticker: str) -> str:
    """Convert an ARF ticker to a yfinance symbol.

    - HK: '0700.HK' / '700.HK' -> '0700.HK' (4-digit zero-padded)
    - US: 'NVDA' -> 'NVDA'
    """
    t = ticker.strip().upper()
    if t.endswith(".HK"):
        code = t[:-3].lstrip("0").zfill(4)
        return f"{code}.HK"
    return t


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def _yf_history(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Fetch split/dividend-adjusted daily OHLCV from yfinance with retry."""
    # yfinance treats `end` as exclusive — bump it a day to include end_date.
    end_excl = (datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    log.info("Fetching yfinance history for %s from %s to %s", symbol, start_date, end_date)
    hist = yf.Ticker(symbol).history(start=start_date, end=end_excl, auto_adjust=True)
    return hist


def _fetch_yf_prices(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Fetch HK/US daily prices via yfinance, normalised to ARF columns.

    Returns ['ticker', 'date', 'open', 'high', 'low', 'close', 'volume'].
    Volume is in raw shares (unlike A-share AkShare 手/hands).
    """
    symbol = _yf_symbol(ticker)
    try:
        hist = _yf_history(symbol, start_date, end_date)
        if hist is None or hist.empty:
            log.warning("No yfinance price data returned for %s", ticker)
            return pd.DataFrame()

        hist = hist.reset_index()
        date_col = "Date" if "Date" in hist.columns else hist.columns[0]
        df = pd.DataFrame(
            {
                "ticker": ticker,
                "date": pd.to_datetime(hist[date_col]).dt.tz_localize(None).dt.date,
                "open": pd.to_numeric(hist["Open"], errors="coerce"),
                "high": pd.to_numeric(hist["High"], errors="coerce"),
                "low": pd.to_numeric(hist["Low"], errors="coerce"),
                "close": pd.to_numeric(hist["Close"], errors="coerce"),
                "volume": pd.to_numeric(hist["Volume"], errors="coerce"),
            }
        )
        return df.dropna(subset=["close"]).reset_index(drop=True)
    except Exception as e:
        log.error("Failed to fetch yfinance prices for %s: %s", ticker, e)
        return pd.DataFrame()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def _yf_info(symbol: str) -> dict:
    return yf.Ticker(symbol).info or {}


def _fetch_yf_shares(ticker: str) -> float:
    """Fetch outstanding shares for an HK/US ticker via yfinance info."""
    symbol = _yf_symbol(ticker)
    try:
        info = _yf_info(symbol)
        shares = info.get("sharesOutstanding") or info.get("impliedSharesOutstanding")
        if shares and float(shares) > 0:
            return float(shares)
        log.warning("yfinance returned no sharesOutstanding for %s", ticker)
    except Exception as e:
        log.warning("Failed to fetch yfinance shares for %s: %s", ticker, e)
    return _SHARES_FALLBACK


def fetch_daily_prices_any(
    ticker: str, start_date: str, end_date: str, adjust: str = "qfq"
) -> pd.DataFrame:
    """Fetch daily prices for any market.

    A-shares use AkShare; HK/US use yfinance. For HK, if yfinance returns too few
    bars (Yahoo throttles newly-listed names like MiniMax 0100.HK to a 1d/5d
    window), fall back to AkShare's Eastmoney history. `adjust` applies to A-shares
    and the HK AkShare fallback; yfinance always auto-adjusts.
    """
    market = detect_market(ticker)
    if market == "A":
        return _fetch_a_prices(ticker, start_date, end_date, adjust)
    if market == "HK":
        df = _fetch_yf_prices(ticker, start_date, end_date)
        if len(df) >= _HK_MIN_HISTORY_ROWS:
            return df
        log.warning(
            "yfinance returned only %d row(s) for %s; falling back to AkShare HK history",
            len(df),
            ticker,
        )
        ak_df = _fetch_hk_prices(ticker, start_date, end_date, adjust)
        return ak_df if len(ak_df) > len(df) else df
    return _fetch_yf_prices(ticker, start_date, end_date)


def fetch_outstanding_shares_any(ticker: str) -> float:
    """Fetch outstanding shares for any market (Baostock for A, yfinance otherwise)."""
    if detect_market(ticker) == "A":
        return _fetch_a_shares(ticker)
    return _fetch_yf_shares(ticker)
