"""AkShare fetcher: Tencent-based daily price history for cloud-safety."""
import logging

import akshare as ak
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential

log = logging.getLogger(__name__)

def _tx_symbol(ticker: str) -> str:
    """Convert ARF tickers to Tencent-compatible symbols.
    
    Examples:
    - '300308.SZ' -> 'sz300308'
    - '688256.SH' -> 'sh688256'
    - '0700.HK'   -> 'hk00700'
    """
    if "." in ticker:
        code, exchange = ticker.split(".")
        exchange = exchange.upper()
        if exchange == "SZ":
            return f"sz{code}"
        elif exchange == "SH":
            return f"sh{code}"
        elif exchange == "HK":
            padded_code = code.zfill(5)
            return f"hk{padded_code}"
    
    ticker_lower = ticker.lower()
    if ticker_lower.startswith(("sh", "sz", "hk")):
        return ticker_lower
        
    if ticker.startswith(("5", "6", "9")):
        return f"sh{ticker}"
    if ticker.startswith(("4", "8")):
        return f"bj{ticker}"
    return f"sz{ticker}"

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True
)
def fetch_daily_prices_raw(symbol: str, start_date: str, end_date: str, adjust: str = "qfq") -> pd.DataFrame:
    """Fetch daily price history from Tencent via AkShare with retry logic."""
    log.info(f"Fetching daily prices for {symbol} from {start_date} to {end_date} (adjust={adjust})")
    try:
        df = ak.stock_zh_a_hist_tx(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            adjust=adjust
        )
        return df
    except Exception as e:
        log.warning(f"Error fetching from AkShare for {symbol}: {e}")
        raise e

def fetch_daily_prices(ticker: str, start_date: str, end_date: str, adjust: str = "qfq") -> pd.DataFrame:
    """Fetch and format daily prices for a ticker.
    
    Returns a DataFrame with columns:
    ['ticker', 'date', 'open', 'high', 'low', 'close', 'volume']
    All column names are standardized for DuckDB.
    """
    symbol = _tx_symbol(ticker)
    try:
        df = fetch_daily_prices_raw(symbol, start_date, end_date, adjust)
        if df.empty:
            log.warning(f"No daily price data returned for {ticker}")
            return pd.DataFrame()
            
        df = df.copy()
        df["ticker"] = ticker
        df = df.rename(columns={
            "amount": "volume"
        })
        
        df = df[["ticker", "date", "open", "high", "low", "close", "volume"]]
        df["date"] = pd.to_datetime(df["date"]).dt.date
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            
        return df
    except Exception as e:
        log.error(f"Failed to fetch daily prices for {ticker}: {e}")
        return pd.DataFrame()

def fetch_outstanding_shares(ticker: str) -> float:
    """Fetch outstanding shares for an A-share ticker using Baostock.
    
    Queries quarterly financial reports to get the latest share count.
    Falls back to a reasonable default (100 million shares) on failure.
    """
    # Convert ticker to Baostock format, e.g. "300308.SZ" -> "sz.300308"
    if "." in ticker:
        code, exchange = ticker.split(".")
        bs_code = f"sh.{code}" if exchange.upper() == "SH" else f"sz.{code}"
    else:
        # Fallback for bare symbols
        bs_code = f"sh.{ticker}" if ticker.startswith(("5", "6", "9")) else f"sz.{ticker}"
            
    import datetime

    import baostock as bs
    
    log.info(f"Fetching outstanding shares for {ticker} using Baostock ({bs_code})")
    
    # Baostock connection requires serialization
    import threading
    bs_lock = threading.Lock()
    
    shares = 100_000_000.0  # default fallback (100M shares)
    
    with bs_lock:
        lg = bs.login()
        if lg.error_code != "0":
            log.warning(f"Baostock login failed for outstanding shares: {lg.error_msg}")
            return shares
            
        try:
            today = datetime.date.today()
            year, quarter = today.year, (today.month - 1) // 3 + 1
            
            # Step back through the last 4 quarters to find a populated report
            for _ in range(4):
                rs = bs.query_profit_data(code=bs_code, year=year, quarter=quarter)
                if rs.error_code == "0" and rs.next():
                    row = dict(zip(rs.fields, rs.get_row_data(), strict=False))
                    val = row.get("totalShare")
                    if val:
                        try:
                            f_val = float(val)
                            if f_val > 0:
                                shares = f_val
                                log.info(f"Successfully retrieved outstanding shares for {ticker}: {shares:.0f}")
                                break
                        except (ValueError, TypeError):
                            pass
                quarter -= 1
                if quarter == 0:
                    quarter, year = 4, year - 1
        except Exception as e:
            log.warning(f"Failed to query outstanding shares for {ticker}: {e}")
        finally:
            bs.logout()
            
    return shares

