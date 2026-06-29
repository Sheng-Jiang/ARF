"""Institutional research-report fetcher (layer 1: structured consensus data).

Pulls *other institutions'* sell-side coverage and normalises it to one schema so
the thermometer / Gemini narrative layer can reconcile sell-side optimism against
ARF's valuation-stretch verdict using real reports rather than open-web search.

Sources per leg:
- **A-share** (`.SZ`/`.SH`): AkShare ``stock_research_report_em`` (Eastmoney) —
  report title, institution, 东财评级 rating, per-year EPS forecast, and a link to
  the actual report PDF.
- **US / HK**: yfinance analyst data — per-firm rating changes with current price
  target (``upgrades_downgrades``) plus a single consensus row (mean target +
  ``recommendationKey``). HK per-firm history is usually empty, but the consensus
  target is still available for the liquid names.

Reliability: every network call is retry-wrapped, and ``fetch_research_reports``
is per-ticker failure-tolerant — a single bad ticker logs a warning and yields an
empty frame so it can never crash the batch job (see ``arf/run.py``).
"""
from __future__ import annotations

import logging
import re
from datetime import date, timedelta

import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential

from arf.fetchers.prices import _yf_symbol, detect_market

log = logging.getLogger(__name__)

# Normalised output columns (``as_of_date`` is attached at upsert time).
RESEARCH_COLUMNS = [
    "ticker",
    "report_date",
    "institution",
    "rating",
    "target_price",
    "eps_forecast",
    "title",
    "pdf_url",
    "source",
    "currency",
]

_CURRENCY_BY_MARKET = {"A": "CNY", "HK": "HKD", "US": "USD"}

# Deterministic per-ticker rollup of the report rows (layer-1 consensus view).
CONSENSUS_COLUMNS = [
    "ticker",
    "n_reports",
    "n_institutions",
    "rating_summary",
    "consensus_target",
    "implied_upside_pct",
    "eps_forecast",
    "latest_report",
    "currency",
]

# Eastmoney forecast columns look like "2026-盈利预测-收益"; pick the earliest year.
_EPS_COL_RE = re.compile(r"^(\d{4})-盈利预测-收益$")


def _empty() -> pd.DataFrame:
    return pd.DataFrame(columns=RESEARCH_COLUMNS)


def _a_share_code(ticker: str) -> str:
    """'688256.SH' -> '688256' (Eastmoney wants the bare 6-digit code)."""
    return ticker.split(".")[0].strip()


def _pick_eps_col(columns: list[str]) -> str | None:
    """Return the nearest-year EPS-forecast column name, or None if absent."""
    years = [(int(m.group(1)), c) for c in columns if (m := _EPS_COL_RE.match(c))]
    return min(years)[1] if years else None


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def _research_em_raw(code: str) -> pd.DataFrame:
    """Fetch the Eastmoney research-report list for an A-share code, with retry."""
    import akshare as ak

    log.info("Fetching Eastmoney research reports for %s", code)
    return ak.stock_research_report_em(symbol=code)


def _fetch_research_a(ticker: str, cutoff: date) -> pd.DataFrame:
    """A-share leg: normalise ``stock_research_report_em`` to RESEARCH_COLUMNS."""
    df = _research_em_raw(_a_share_code(ticker))
    if df is None or df.empty:
        return _empty()

    eps_col = _pick_eps_col(list(df.columns))
    out = pd.DataFrame()
    out["report_date"] = pd.to_datetime(df.get("日期"), errors="coerce").dt.date
    out["institution"] = df.get("机构")
    out["rating"] = df.get("东财评级")
    out["target_price"] = pd.NA  # Eastmoney list endpoint carries no target price.
    out["eps_forecast"] = (
        pd.to_numeric(df[eps_col], errors="coerce") if eps_col else pd.NA
    )
    out["title"] = df.get("报告名称")
    out["pdf_url"] = df.get("报告PDF链接")
    out["ticker"] = ticker
    out["source"] = "eastmoney"
    out["currency"] = "CNY"
    out = out[out["report_date"].notna() & (out["report_date"] >= cutoff)]
    return out.reindex(columns=RESEARCH_COLUMNS)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def _yf_ticker(symbol: str):
    import yfinance as yf

    return yf.Ticker(symbol)


def _fetch_research_yf(ticker: str, cutoff: date, as_of: date, currency: str) -> pd.DataFrame:
    """US/HK leg: per-firm rating changes + one consensus row from yfinance."""
    symbol = _yf_symbol(ticker)
    t = _yf_ticker(symbol)
    rows: list[dict] = []

    # Per-firm rating changes (rich for US; usually empty for HK).
    try:
        ud = t.upgrades_downgrades
    except Exception as exc:  # noqa: BLE001 — yfinance raises ad-hoc network errors
        log.warning("yfinance upgrades_downgrades failed for %s: %s", ticker, exc)
        ud = None
    if ud is not None and not ud.empty:
        ud = ud.reset_index()  # GradeDate index -> column
        for _, r in ud.iterrows():
            rdate = pd.to_datetime(r.get("GradeDate"), errors="coerce")
            rdate = rdate.date() if pd.notna(rdate) else None
            if rdate is None or rdate < cutoff:
                continue
            tgt = pd.to_numeric(r.get("currentPriceTarget"), errors="coerce")
            rows.append({
                "ticker": ticker,
                "report_date": rdate,
                "institution": r.get("Firm"),
                "rating": r.get("ToGrade") or None,
                "target_price": float(tgt) if pd.notna(tgt) and tgt > 0 else None,
                "eps_forecast": None,
                "title": " / ".join(
                    str(v) for v in (r.get("Action"), r.get("priceTargetAction")) if v
                ) or None,
                "pdf_url": None,
                "source": "yfinance",
                "currency": currency,
            })

    # Consensus row: mean target + headline rating, when yfinance exposes them.
    try:
        pt = t.analyst_price_targets or {}
    except Exception as exc:  # noqa: BLE001
        log.warning("yfinance price targets failed for %s: %s", ticker, exc)
        pt = {}
    mean_target = pd.to_numeric(pt.get("mean"), errors="coerce")
    rating = None
    n_analysts = None
    try:
        info = t.info or {}
        rating = info.get("recommendationKey")
        n_analysts = info.get("numberOfAnalystOpinions")
    except Exception as exc:  # noqa: BLE001 — HK names 404 on the fundamentals endpoint
        log.info("yfinance info unavailable for %s: %s", ticker, exc)
    if pd.notna(mean_target) or rating:
        rows.append({
            "ticker": ticker,
            "report_date": as_of,
            "institution": "Consensus",
            "rating": rating,
            "target_price": float(mean_target) if pd.notna(mean_target) else None,
            "eps_forecast": None,
            "title": f"{n_analysts} analysts" if n_analysts else "consensus",
            "pdf_url": None,
            "source": "yfinance-consensus",
            "currency": currency,
        })

    return pd.DataFrame(rows, columns=RESEARCH_COLUMNS) if rows else _empty()


def compute_consensus(
    research_df: pd.DataFrame, prices: dict[str, float] | None = None
) -> pd.DataFrame:
    """Roll up per-report rows into a per-ticker sell-side consensus view.

    This is the deterministic layer-1 summary the thermometer shows even when no
    LLM is available: report count, rating mix, consensus target → implied upside
    vs the snapshot price, mean EPS forecast, and the latest report headline.

    Args:
        research_df: rows shaped like ``RESEARCH_COLUMNS`` (any number per ticker).
        prices: ticker → current price (local currency) for the upside calc.
    """
    prices = prices or {}
    if research_df is None or research_df.empty:
        return pd.DataFrame(columns=CONSENSUS_COLUMNS)

    rows: list[dict] = []
    for ticker, g in research_df.groupby("ticker"):
        firm = g[g["source"] != "yfinance-consensus"]
        consensus = g[g["source"] == "yfinance-consensus"]

        # Prefer the yfinance consensus mean target; else average per-firm targets.
        target = None
        ct = pd.to_numeric(consensus["target_price"], errors="coerce").dropna()
        if not ct.empty:
            target = float(ct.iloc[0])
        else:
            ft = pd.to_numeric(firm["target_price"], errors="coerce").dropna()
            target = float(ft.mean()) if not ft.empty else None

        price = prices.get(ticker)
        upside = (
            (target - price) / price * 100.0
            if target is not None and price not in (None, 0)
            else None
        )

        ratings = firm["rating"].dropna().astype(str)
        if ratings.empty:
            ratings = consensus["rating"].dropna().astype(str)
        rating_summary = (
            " ".join(f"{r}×{c}" for r, c in ratings.value_counts().items()) or "—"
        )

        eps = pd.to_numeric(firm["eps_forecast"], errors="coerce").dropna()
        eps_fcst = float(eps.mean()) if not eps.empty else None

        latest = firm.dropna(subset=["report_date"]).sort_values(
            "report_date", ascending=False
        )
        latest_report = str(latest.iloc[0]["title"]) if not latest.empty else ""

        currency = str(g["currency"].dropna().iloc[0]) if g["currency"].notna().any() else ""

        rows.append({
            "ticker": ticker,
            "n_reports": int(len(firm)),
            "n_institutions": int(firm["institution"].dropna().nunique()),
            "rating_summary": rating_summary,
            "consensus_target": target,
            "implied_upside_pct": upside,
            "eps_forecast": eps_fcst,
            "latest_report": latest_report,
            "currency": currency,
        })
    return pd.DataFrame(rows, columns=CONSENSUS_COLUMNS)


def fetch_research_reports(
    ticker: str, as_of: date, lookback_days: int = 90
) -> pd.DataFrame:
    """Fetch normalised institutional research for one ticker.

    Returns a DataFrame with ``RESEARCH_COLUMNS`` (empty on any failure or when no
    coverage exists). Never raises — a bad ticker must not crash the batch.

    Args:
        ticker: ARF ticker, e.g. ``688256.SH``, ``0700.HK``, ``NVDA``.
        as_of: snapshot date; also the report_date stamped on consensus rows.
        lookback_days: only keep reports dated within this many days of ``as_of``.
    """
    cutoff = as_of - timedelta(days=lookback_days)
    market = detect_market(ticker)
    try:
        if market == "A":
            return _fetch_research_a(ticker, cutoff)
        currency = _CURRENCY_BY_MARKET.get(market, "USD")
        return _fetch_research_yf(ticker, cutoff, as_of, currency)
    except Exception as exc:  # noqa: BLE001 — last-resort guard for the batch job
        log.warning("Research fetch failed for %s: %s", ticker, exc)
        return _empty()
