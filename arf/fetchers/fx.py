"""USD → local-currency FX rates with yfinance-first + constant fallback.

The A-share/HK fetchers previously hard-coded USDCNY=7.20 / USDHKD=7.78.
Rates are now fetched from yfinance (``USDCNY=X`` / ``USDHKD=X``) once per
process and cached; any network failure falls back to the constants so the
pipeline never breaks (consistent with the "single failed ticker must never
crash the pipeline" rule).
"""
from __future__ import annotations

import logging
import threading

from tenacity import retry, stop_after_attempt, wait_exponential

log = logging.getLogger(__name__)

# Fallback constants (kept in sync with the historical hard-coded values).
DEFAULT_CNY = 7.20
DEFAULT_HKD = 7.78

# Process-wide cache — rates are fetched at most once per pipeline run.
_cache: dict[str, float] | None = None
_lock = threading.Lock()


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=3),
    reraise=False,
)
def _yf_rate(symbol: str) -> float | None:
    """Fetch one USD-quoted FX pair (e.g. USDCNY=X) from yfinance."""
    import yfinance as yf

    try:
        t = yf.Ticker(symbol)
        info = t.info or {}
        rate = info.get("regularMarketPrice") or info.get("previousClose")
        if rate is not None and float(rate) > 0:
            return float(rate)
        # info can be empty for FX pairs on some yfinance versions — try fast_info.
        fi = t.fast_info
        last = fi.get("lastPrice") if hasattr(fi, "get") else None
        if last is not None and float(last) > 0:
            return float(last)
    except Exception:
        log.warning("FX fetch failed for %s — using fallback constant", symbol, exc_info=True)
    return None


def fetch_fx_rates() -> dict[str, float]:
    """Return USD→local rates {CNY, HKD}; yfinance first, constants on failure."""
    cny = _yf_rate("USDCNY=X")
    hkd = _yf_rate("USDHKD=X")
    return {
        "CNY": cny or DEFAULT_CNY,
        "HKD": hkd or DEFAULT_HKD,
    }


def get_fx_rates() -> dict[str, float]:
    """Cached, thread-safe access to FX rates (one fetch per process)."""
    global _cache
    if _cache is None:
        with _lock:
            if _cache is None:
                _cache = fetch_fx_rates()
                log.info(
                    "FX rates: USDCNY=%.4f USDHKD=%.4f", _cache["CNY"], _cache["HKD"]
                )
    return _cache


def reset_fx_cache() -> None:
    """Clear the process cache (used by tests)."""
    global _cache
    _cache = None
