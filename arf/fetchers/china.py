"""China/HK stock fetcher: Baostock for A-shares, yfinance for HK/ADR."""
import contextlib
import logging
import math
import threading
from datetime import date, timedelta

import baostock as bs
import yfinance as yf
from tenacity import retry, stop_after_attempt, wait_exponential

from arf.config import UniverseEntry
from arf.fetchers.base import StockData
from arf.fetchers.fx import get_fx_rates
from arf.fetchers.us import calculate_ev_sales_5yr_percentile

log = logging.getLogger(__name__)

# Baostock uses a global singleton connection — serialise all calls.
_bs_lock = threading.Lock()

# Fallback rates used by fx.py when yfinance is unreachable.
_FX_CNY_TO_USD = 7.20
_FX_HKD_TO_USD = 7.78


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


def _bs_code(ticker: str) -> str:
    """'300308.SZ' → 'sz.300308', '688256.SH' → 'sh.688256'."""
    code, exchange = ticker.split(".")
    return f"sh.{code}" if exchange == "SH" else f"sz.{code}"


def _bs_rows(rs) -> list[dict]:
    """Drain a baostock ResultData into a list of field dicts."""
    rows = []
    while rs.error_code == "0" and rs.next():
        rows.append(dict(zip(rs.fields, rs.get_row_data(), strict=False)))
    return rows


def _pct_to_decimal(val: float | None) -> float | None:
    """Convert a baostock percentage value (e.g. 15.3) to a decimal (0.153).

    Baostock returns ratios as percentages for most financial indicators.
    Guard against values already in decimal form (<= 1 in absolute value).
    """
    if val is None:
        return None
    return val / 100.0 if abs(val) > 1 else val


def _fetch_a_share(entry: UniverseEntry, as_of: date) -> StockData:
    """Fetch A-share data from Baostock (works outside China, no API token needed)."""
    result = StockData(ticker=entry.ticker, as_of_date=as_of, currency="CNY",
                       fx_rate_usd=get_fx_rates()["CNY"])
    code = _bs_code(entry.ticker)

    with _bs_lock:
        # Watchdog: if this baostock session takes >60 s, log a warning and move on.
        _timed_out: list[bool] = [False]

        def _watchdog() -> None:
            _timed_out[0] = True
            log.warning("baostock session for %s timed out — skipping", entry.ticker)
            with contextlib.suppress(Exception):
                bs.logout()

        timer = threading.Timer(60.0, _watchdog)
        timer.start()
        try:
            lg = bs.login()
            if lg.error_code != "0":
                log.warning("baostock login failed for %s: %s", entry.ticker, lg.error_msg)
                return result
            try:
                _populate_a_share(result, code, as_of)
            except Exception as exc:
                if not _timed_out[0]:
                    log.warning("baostock fetch failed for %s: %s", entry.ticker, exc)
            finally:
                if not _timed_out[0]:
                    bs.logout()
        finally:
            timer.cancel()

    return result


def _populate_a_share(result: StockData, code: str, as_of: date) -> None:
    end_str = str(as_of)
    # Look back up to 10 calendar days to skip weekends / holidays
    start_str = str(as_of - timedelta(days=10))

    # ── 1. Price and valuation ratios ────────────────────────────────────────
    rs = bs.query_history_k_data_plus(
        code, "date,close,peTTM,psTTM",
        start_date=start_str, end_date=end_str,
        frequency="d", adjustflag="3",
    )
    daily = _bs_rows(rs)
    if daily:
        row = daily[-1]  # most recent trading day
        result.price = _safe(row.get("close"))
        pe = _safe(row.get("peTTM"))
        if pe and pe > 0:
            result.forward_pe = pe  # TTM P/E as proxy for forward P/E
        result.ps_ratio = _safe(row.get("psTTM"))

    # ── 2. EV/Sales 5yr percentile from daily P/S history ───────────────────
    # psTTM is only available at daily frequency in Baostock (not weekly/monthly).
    if result.ps_ratio is not None:
        five_yr_start = str(date(as_of.year - 5, as_of.month, 1))
        rs_hist = bs.query_history_k_data_plus(
            code, "date,psTTM",
            start_date=five_yr_start, end_date=end_str,
            frequency="d", adjustflag="3",
        )
        ps_hist = [_safe(r.get("psTTM")) for r in _bs_rows(rs_hist)]
        ps_hist = [v for v in ps_hist if v is not None and v > 0]
        if len(ps_hist) >= 60:  # at least ~3 months of daily trading days
            curr = result.ps_ratio
            result.ev_sales_5yr_percentile = (
                sum(1 for v in ps_hist if v <= curr) / len(ps_hist) * 100
            )

    # ── 3. Quarterly profit data ──────────────────────────────────────────────
    # Step back through recent quarters until we find a populated report.
    profit_row: dict | None = None
    year, quarter = as_of.year, (as_of.month - 1) // 3 + 1
    for _ in range(6):
        rs_p = bs.query_profit_data(code=code, year=year, quarter=quarter)
        rows_p = _bs_rows(rs_p)
        if rows_p:
            profit_row = rows_p[0]
            break
        quarter -= 1
        if quarter == 0:
            quarter, year = 4, year - 1

    if profit_row:
        result.gross_margin = _pct_to_decimal(_safe(profit_row.get("gpMargin")))
        result.roe = _pct_to_decimal(_safe(profit_row.get("roeAvg")))
        result.revenue_ttm = _safe(profit_row.get("MBRevenue"))
        # netProfit is the closest Baostock provides to 扣非 at the free tier
        result.net_income_excl_nonrecurring = _safe(profit_row.get("netProfit"))
        # Market cap from price × total shares (local currency → USD via the
        # same fx rate carried on the result, so V_score C1's local-currency
        # re-conversion round-trips to the true local market cap).
        total_shares = _safe(profit_row.get("totalShare"))
        if result.price and total_shares:
            result.market_cap_usd = result.price * total_shares / result.fx_rate_usd

    # ── 4. Revenue YoY growth ─────────────────────────────────────────────────
    if profit_row and result.revenue_ttm:
        year_cur, quarter_cur = as_of.year, (as_of.month - 1) // 3 + 1
        rs_prior = bs.query_profit_data(code=code, year=year_cur - 1, quarter=quarter_cur)
        rows_prior = _bs_rows(rs_prior)
        if rows_prior:
            rev_prior = _safe(rows_prior[0].get("MBRevenue"))
            if rev_prior and rev_prior > 0:
                result.revenue_yoy_growth = (result.revenue_ttm - rev_prior) / rev_prior

    # ── 5. EPS / net-income growth (for PEG component of V_score) ────────────
    year_g, quarter_g = as_of.year, (as_of.month - 1) // 3 + 1
    for _ in range(6):
        rs_g = bs.query_growth_data(code=code, year=year_g, quarter=quarter_g)
        rows_g = _bs_rows(rs_g)
        if rows_g:
            # YOYNI = net income YoY (%), used as eps_2yr_cagr proxy
            yoy_ni = _pct_to_decimal(_safe(rows_g[0].get("YOYNI")))
            if yoy_ni is not None:
                result.eps_2yr_cagr = yoy_ni
            break
        quarter_g -= 1
        if quarter_g == 0:
            quarter_g, year_g = 4, year_g - 1

    # ── 6. Operating cash flow proxy for free_cash_flow ──────────────────────
    year_cf, quarter_cf = as_of.year, (as_of.month - 1) // 3 + 1
    for _ in range(6):
        rs_cf = bs.query_cash_flow_data(code=code, year=year_cf, quarter=quarter_cf)
        rows_cf = _bs_rows(rs_cf)
        if rows_cf:
            # CFOToOR = operating cash flow / revenue (ratio)
            cfo_ratio = _pct_to_decimal(_safe(rows_cf[0].get("CFOToOR")))
            if cfo_ratio is not None and result.revenue_ttm:
                result.free_cash_flow = cfo_ratio * result.revenue_ttm
            break
        quarter_cf -= 1
        if quarter_cf == 0:
            quarter_cf, year_cf = 4, year_cf - 1

    result.data_source = "baostock"


# ── HK / ADR path (unchanged) ─────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _yf_info(ticker: str) -> dict:
    t = yf.Ticker(ticker)
    return t.info or {}


def _fetch_hk_or_adr(entry: UniverseEntry, as_of: date) -> StockData:
    """Fetch HK-listed or ADR via yfinance."""
    result = StockData(ticker=entry.ticker, as_of_date=as_of)
    try:
        info = _yf_info(entry.ticker)
        if not info:
            return result

        currency = info.get("currency", "HKD" if entry.ticker.endswith(".HK") else "USD")
        result.currency = currency
        rates = get_fx_rates()
        fx = rates["HKD"] if currency == "HKD" else (rates["CNY"] if currency == "CNY" else 1.0)
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

        # Calculate EV/Sales 5-year percentile
        t = yf.Ticker(entry.ticker)
        ev_pct = calculate_ev_sales_5yr_percentile(t, info)
        if ev_pct is not None:
            result.ev_sales_5yr_percentile = ev_pct
    except Exception as exc:
        log.warning("yfinance failed for %s: %s", entry.ticker, exc)
    return result


def fetch_china(entry: UniverseEntry, as_of: date) -> StockData:
    """Fetch data for a China-leg stock (A-share via Baostock, HK/ADR via yfinance)."""
    if _is_a_share(entry.ticker):
        return _fetch_a_share(entry, as_of)
    return _fetch_hk_or_adr(entry, as_of)
