"""Offline tests for the research-report fetcher + its DuckDB persistence.

Network calls (AkShare/yfinance) are exercised in integration, not here — these
cover the deterministic normalisation helpers and the idempotent upsert.
"""
from datetime import date

import pandas as pd
import pytest

from arf.db import (
    init_db,
    query_research_reports,
    query_research_synthesis,
    upsert_research_reports,
    upsert_research_synthesis,
)
from arf.fetchers.research import (
    RESEARCH_COLUMNS,
    _a_share_code,
    _pick_eps_col,
    compute_consensus,
)


@pytest.fixture
def conn(tmp_path):
    c = init_db(tmp_path / "test_arf.db")
    yield c
    c.close()


def test_a_share_code_strips_suffix():
    assert _a_share_code("688256.SH") == "688256"
    assert _a_share_code("300308.SZ") == "300308"
    assert _a_share_code("688256") == "688256"


def test_pick_eps_col_picks_earliest_year():
    cols = ["序号", "机构", "2028-盈利预测-收益", "2026-盈利预测-收益", "2027-盈利预测-收益"]
    assert _pick_eps_col(cols) == "2026-盈利预测-收益"


def test_pick_eps_col_none_when_absent():
    assert _pick_eps_col(["序号", "机构", "东财评级"]) is None


def _sample_rows(as_of: date) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ticker": "688256.SH",
                "report_date": date(2026, 4, 28),
                "institution": "第一上海证券",
                "rating": "买入",
                "target_price": None,
                "eps_forecast": 16.1,
                "title": "AI Agent时代来临",
                "pdf_url": "https://pdf.dfcfw.com/x.pdf",
                "source": "eastmoney",
                "currency": "CNY",
            },
            {
                "ticker": "NVDA",
                "report_date": date(2026, 6, 30),
                "institution": "Consensus",
                "rating": "strong_buy",
                "target_price": 300.5,
                "eps_forecast": None,
                "title": "58 analysts",
                "pdf_url": None,
                "source": "yfinance-consensus",
                "currency": "USD",
            },
        ],
        columns=RESEARCH_COLUMNS,
    )


def test_upsert_and_query_roundtrip(conn):
    as_of = date(2026, 6, 30)
    upsert_research_reports(conn, _sample_rows(as_of), as_of)
    got = query_research_reports(conn, as_of)
    assert len(got) == 2
    nvda = query_research_reports(conn, as_of, "NVDA")
    assert len(nvda) == 1
    assert nvda.iloc[0]["target_price"] == pytest.approx(300.5)


def test_upsert_is_idempotent(conn):
    as_of = date(2026, 6, 30)
    upsert_research_reports(conn, _sample_rows(as_of), as_of)
    upsert_research_reports(conn, _sample_rows(as_of), as_of)
    assert len(query_research_reports(conn, as_of)) == 2


def test_empty_upsert_clears_stale_rows(conn):
    as_of = date(2026, 6, 30)
    upsert_research_reports(conn, _sample_rows(as_of), as_of)
    # A later run that finds no coverage must not leave stale rows behind.
    upsert_research_reports(conn, pd.DataFrame(columns=RESEARCH_COLUMNS), as_of)
    assert query_research_reports(conn, as_of).empty


def _research_rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {**dict.fromkeys(RESEARCH_COLUMNS), "ticker": "NVDA", "report_date": date(2026, 6, 5),
             "institution": "Needham", "rating": "Buy", "target_price": 270.0,
             "source": "yfinance", "currency": "USD"},
            {**dict.fromkeys(RESEARCH_COLUMNS), "ticker": "NVDA", "report_date": date(2026, 6, 30),
             "institution": "Consensus", "rating": "strong_buy", "target_price": 300.5,
             "source": "yfinance-consensus", "currency": "USD"},
            {**dict.fromkeys(RESEARCH_COLUMNS), "ticker": "688256.SH", "report_date": date(2026, 4, 28),
             "institution": "第一上海证券", "rating": "买入", "eps_forecast": 16.1,
             "source": "eastmoney", "currency": "CNY"},
            {**dict.fromkeys(RESEARCH_COLUMNS), "ticker": "688256.SH", "report_date": date(2026, 3, 19),
             "institution": "东海证券", "rating": "增持", "eps_forecast": 11.67,
             "source": "eastmoney", "currency": "CNY"},
        ],
        columns=RESEARCH_COLUMNS,
    )


def test_compute_consensus_target_and_upside():
    cons = compute_consensus(_research_rows(), {"NVDA": 194.97, "688256.SH": 700.0})
    nv = cons[cons["ticker"] == "NVDA"].iloc[0]
    # The synthetic consensus row is excluded from the per-firm report count.
    assert nv["n_reports"] == 1
    assert nv["consensus_target"] == pytest.approx(300.5)
    assert nv["implied_upside_pct"] == pytest.approx((300.5 - 194.97) / 194.97 * 100)


def test_compute_consensus_a_share_eps_no_target():
    cons = compute_consensus(_research_rows(), {"688256.SH": 700.0})
    cb = cons[cons["ticker"] == "688256.SH"].iloc[0]
    assert pd.isna(cb["consensus_target"])
    assert pd.isna(cb["implied_upside_pct"])
    assert cb["eps_forecast"] == pytest.approx((16.1 + 11.67) / 2)
    assert cb["n_reports"] == 2


def test_compute_consensus_empty():
    assert compute_consensus(pd.DataFrame(columns=RESEARCH_COLUMNS)).empty


def test_research_synthesis_roundtrip_and_idempotent(conn):
    as_of = date(2026, 6, 30)
    upsert_research_synthesis(conn, as_of, "### 一、概览\n初版", "[]", '["NVDA"]', "gemini-2.5-pro")
    upsert_research_synthesis(conn, as_of, "### updated", "[]", '["NVDA"]', "gemini-2.5-pro")
    got = query_research_synthesis(conn, as_of)
    assert len(got) == 1
    assert got.iloc[0]["synthesis_text"] == "### updated"
