"""Offline tests for arf.fetchers.prices — Baostock A-share fallback."""
from datetime import date
from unittest.mock import patch

import pandas as pd

from arf.fetchers.prices import (
    _fetch_a_prices_baostock,
    fetch_daily_prices_any,
)


class _FakeRs:
    """Mimics a baostock ResultData stream."""

    error_code = "0"
    fields = ["date", "open", "high", "low", "close", "volume"]

    def __init__(self, rows: list[list]):
        self._rows = rows
        self._i = -1

    def next(self) -> bool:
        self._i += 1
        return self._i < len(self._rows)

    def get_row_data(self) -> list[str]:
        return [str(v) for v in self._rows[self._i]]


def _patch_baostock(rows: list[list]):
    class _FakeLogin:
        error_code = "0"

    return patch.multiple(
        "baostock",
        login=lambda: _FakeLogin(),
        query_history_k_data_plus=lambda *a, **k: _FakeRs(rows),
        logout=lambda: None,
    )


def test_baostock_fallback_standardises_columns_and_hands():
    rows = [
        ["2026-08-05", "100.0", "102.0", "99.0", "101.5", "2000000"],
        ["2026-08-06", "101.0", "103.0", "100.0", "102.0", "1500000"],
    ]
    with _patch_baostock(rows):
        df = _fetch_a_prices_baostock("300308.SZ", "2026-08-01", "2026-08-07")

    assert list(df.columns) == ["ticker", "date", "open", "high", "low", "close", "volume"]
    assert df["ticker"].tolist() == ["300308.SZ", "300308.SZ"]
    assert df["close"].tolist() == [101.5, 102.0]
    # Volume converted 股 → 手 (A-share convention, ÷100).
    assert df["volume"].tolist() == [20000.0, 15000.0]
    assert df["date"].tolist() == [date(2026, 8, 5), date(2026, 8, 6)]


def test_baostock_fallback_empty_on_no_rows():
    with _patch_baostock([]):
        df = _fetch_a_prices_baostock("688256.SH", "2026-08-01", "2026-08-07")
    assert df.empty


def test_baostock_fallback_requires_suffix():
    assert _fetch_a_prices_baostock("300308", "2026-08-01", "2026-08-07").empty


def test_fetch_any_a_share_falls_back_to_baostock_when_tencent_empty():
    fallback_df = pd.DataFrame([
        {"ticker": "300308.SZ", "date": date(2026, 8, 6), "open": 1.0,
         "high": 1.0, "low": 1.0, "close": 1.0, "volume": 100.0},
    ])
    with patch("arf.fetchers.prices._fetch_a_prices", return_value=pd.DataFrame()), \
         patch("arf.fetchers.prices._fetch_a_prices_baostock", return_value=fallback_df) as fb:
        df = fetch_daily_prices_any("300308.SZ", "2026-08-01", "2026-08-07")
    fb.assert_called_once()
    assert len(df) == 1


def test_fetch_any_a_share_uses_tencent_when_it_has_data():
    ok_df = pd.DataFrame([
        {"ticker": "300308.SZ", "date": date(2026, 8, 6), "open": 1.0,
         "high": 1.0, "low": 1.0, "close": 1.0, "volume": 100.0},
    ])
    with patch("arf.fetchers.prices._fetch_a_prices", return_value=ok_df) as tx, \
         patch("arf.fetchers.prices._fetch_a_prices_baostock") as fb:
        df = fetch_daily_prices_any("300308.SZ", "2026-08-01", "2026-08-07")
    tx.assert_called_once()
    fb.assert_not_called()
    assert len(df) == 1
