import uuid
from datetime import date, datetime

import pandas as pd
import pytest

from arf.db import (
    finish_run,
    init_db,
    query_fetch_outcomes,
    query_gemini_summaries,
    query_latest,
    query_latest_run,
    query_runs,
    query_snapshot,
    record_fetch_outcomes,
    start_run,
    upsert_gemini_summaries,
    upsert_snapshot,
)


@pytest.fixture
def conn(tmp_path):
    db_path = tmp_path / "test_arf.db"
    c = init_db(db_path)
    yield c
    c.close()


def _sample_df(tickers: list[str], as_of: date) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "ticker": t,
            "as_of_date": as_of,
            "leg": "US",
            "layer": "L2",
            "name": f"Company {t}",
            "price": 100.0 + i,
            "market_cap_usd": 1e9 + i,
            "ev_usd": 1.1e9 + i,
            "revenue_ttm": 5e8 + i,
            "revenue_yoy_growth": 0.10 + i * 0.01,
            "gross_margin": 0.50,
            "roe": 0.15,
            "free_cash_flow": 1e7 + i,
            "forward_pe": 20.0 + i,
            "eps_2yr_cagr": 0.12,
            "revenue_3yr_cagr": 0.10,
            "ps_ratio": 5.0,
            "ev_sales": 6.0,
            "ev_sales_5yr_percentile": 60.0,
            "e_score": 50.0 + i,
            "v_score": 40.0 + i,
            "arf": 45.0 + i,
            "decile": 5,
            "froth_flag": False,
            "implied_growth": 0.05,
            "implied_growth_gap": -0.05,
            "policy_premium": False,
            "data_source": "test",
            "currency": "USD",
            "fx_rate_usd": 1.0,
        }
        for i, t in enumerate(tickers)
    ])


class TestInitDB:
    def test_init_creates_snapshots_table(self, conn):
        tables = conn.execute("SHOW TABLES").fetchdf()
        assert "snapshots" in tables["name"].values

    def test_init_creates_required_columns(self, conn):
        cols = conn.execute("DESCRIBE snapshots").fetchdf()["column_name"].tolist()
        required = ["ticker", "as_of_date", "arf", "e_score", "v_score", "decile", "froth_flag"]
        for col in required:
            assert col in cols, f"Missing column: {col}"

    def test_init_idempotent(self, tmp_path):
        db_path = tmp_path / "idempotent.db"
        c1 = init_db(db_path)
        c1.close()
        c2 = init_db(db_path)  # should not raise
        c2.close()


class TestUpsertSnapshot:
    def test_upsert_inserts_rows(self, conn):
        df = _sample_df(["NVDA", "PLTR"], date(2026, 5, 28))
        upsert_snapshot(conn, df, date(2026, 5, 28))
        count = conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
        assert count == 2

    def test_upsert_idempotent_same_date(self, conn):
        df = _sample_df(["NVDA"], date(2026, 5, 28))
        upsert_snapshot(conn, df, date(2026, 5, 28))
        upsert_snapshot(conn, df, date(2026, 5, 28))
        count = conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
        assert count == 1  # second upsert must not duplicate

    def test_upsert_overwrites_previous_values(self, conn):
        df1 = _sample_df(["NVDA"], date(2026, 5, 28))
        df1.loc[0, "arf"] = 60.0
        upsert_snapshot(conn, df1, date(2026, 5, 28))

        df2 = _sample_df(["NVDA"], date(2026, 5, 28))
        df2.loc[0, "arf"] = 75.0
        upsert_snapshot(conn, df2, date(2026, 5, 28))

        row = conn.execute(
            "SELECT arf FROM snapshots WHERE ticker='NVDA' AND as_of_date='2026-05-28'"
        ).fetchone()
        assert row[0] == pytest.approx(75.0)

    def test_null_fields_stored_as_null(self, conn):
        df = _sample_df(["NVDA"], date(2026, 5, 28))
        df.loc[0, "forward_pe"] = None
        upsert_snapshot(conn, df, date(2026, 5, 28))
        row = conn.execute(
            "SELECT forward_pe FROM snapshots WHERE ticker='NVDA'"
        ).fetchone()
        assert row[0] is None


class TestQuerySnapshot:
    def test_query_by_date_returns_correct_rows(self, conn):
        df1 = _sample_df(["NVDA", "PLTR"], date(2026, 5, 28))
        df2 = _sample_df(["NVDA"], date(2026, 6, 4))
        upsert_snapshot(conn, df1, date(2026, 5, 28))
        upsert_snapshot(conn, df2, date(2026, 6, 4))

        result = query_snapshot(conn, date(2026, 5, 28))
        assert len(result) == 2
        assert set(result["ticker"]) == {"NVDA", "PLTR"}

    def test_query_latest_returns_most_recent(self, conn):
        df1 = _sample_df(["NVDA"], date(2026, 5, 21))
        df2 = _sample_df(["NVDA"], date(2026, 5, 28))
        upsert_snapshot(conn, df1, date(2026, 5, 21))
        upsert_snapshot(conn, df2, date(2026, 5, 28))

        result = query_latest(conn)
        assert all(pd.to_datetime(result["as_of_date"]).dt.date == date(2026, 5, 28))

    def test_query_snapshot_empty_date_returns_empty_df(self, conn):
        result = query_snapshot(conn, date(2020, 1, 1))
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0


class TestRunTracking:
    def test_start_run_inserts_running_row(self, conn):
        rid = uuid.uuid4().hex
        start_run(conn, rid, date(2026, 5, 28), trigger_source="manual")
        row = conn.execute("SELECT status, trigger_source FROM runs WHERE run_id = ?", [rid]).fetchone()
        assert row == ("running", "manual")

    def test_finish_run_records_duration_and_status(self, conn):
        rid = uuid.uuid4().hex
        start = datetime(2026, 5, 28, 12, 0, 0)
        finish = datetime(2026, 5, 28, 12, 2, 30)
        start_run(conn, rid, date(2026, 5, 28), trigger_source="scheduler", started_at=start)
        finish_run(conn, rid, status="success",
                   tickers_total=32, tickers_ok=32, tickers_failed=0,
                   finished_at=finish)
        row = conn.execute(
            "SELECT status, tickers_total, tickers_ok, tickers_failed, duration_sec "
            "FROM runs WHERE run_id = ?", [rid]
        ).fetchone()
        assert row[0] == "success"
        assert row[1:4] == (32, 32, 0)
        assert row[4] == pytest.approx(150.0)

    def test_finish_run_partial_with_error_message(self, conn):
        rid = uuid.uuid4().hex
        start_run(conn, rid, date(2026, 5, 28), trigger_source="manual")
        finish_run(conn, rid, status="partial",
                   tickers_total=32, tickers_ok=30, tickers_failed=2,
                   error_message="2 tickers failed")
        row = conn.execute("SELECT status, error_message FROM runs WHERE run_id = ?", [rid]).fetchone()
        assert row == ("partial", "2 tickers failed")

    def test_record_fetch_outcomes_round_trip(self, conn):
        rid = uuid.uuid4().hex
        start_run(conn, rid, date(2026, 5, 28), trigger_source="manual")
        record_fetch_outcomes(conn, rid, [
            ("NVDA", "ok", "yfinance"),
            ("PLTR", "ok", "yfinance"),
            ("BROKEN", "error", "error"),
        ])
        df = query_fetch_outcomes(conn, rid)
        assert len(df) == 3
        assert set(df["ticker"]) == {"NVDA", "PLTR", "BROKEN"}
        assert df[df["ticker"] == "BROKEN"]["status"].iloc[0] == "error"

    def test_record_fetch_outcomes_replaces_previous(self, conn):
        rid = uuid.uuid4().hex
        start_run(conn, rid, date(2026, 5, 28), trigger_source="manual")
        record_fetch_outcomes(conn, rid, [("NVDA", "ok", "yfinance")])
        record_fetch_outcomes(conn, rid, [("NVDA", "error", "yfinance"), ("AMD", "ok", "yfinance")])
        df = query_fetch_outcomes(conn, rid)
        assert len(df) == 2
        assert df[df["ticker"] == "NVDA"]["status"].iloc[0] == "error"

    def test_query_latest_run_returns_most_recent(self, conn):
        old = uuid.uuid4().hex
        new = uuid.uuid4().hex
        start_run(conn, old, date(2026, 5, 21), trigger_source="manual",
                  started_at=datetime(2026, 5, 21, 10, 0, 0))
        start_run(conn, new, date(2026, 5, 28), trigger_source="scheduler",
                  started_at=datetime(2026, 5, 28, 10, 0, 0))
        df = query_latest_run(conn)
        assert len(df) == 1
        assert df.iloc[0]["run_id"] == new

    def test_query_runs_returns_in_descending_order(self, conn):
        for i in range(3):
            rid = uuid.uuid4().hex
            start_run(conn, rid, date(2026, 5, 7 + 7 * i), trigger_source="manual",
                      started_at=datetime(2026, 5, 7 + 7 * i, 10, 0, 0))
        df = query_runs(conn, limit=5)
        assert len(df) == 3
        dates = pd.to_datetime(df["started_at"]).dt.date.tolist()
        assert dates == sorted(dates, reverse=True)


class TestGeminiSummaries:
    def _row(self, ticker: str, as_of: date, cohort_key: str = "overview") -> dict:
        return {
            "as_of_date": as_of,
            "ticker": ticker,
            "cohort_key": cohort_key,
            "name": f"Co {ticker}",
            "headline": f"{ticker} latest news",
            "bullets_json": '["bullet1 (reuters.com)", "bullet2 (eastmoney.com)"]',
            "reconcile": "consistent with D1",
            "domain_mentions_json": '["reuters.com", "eastmoney.com"]',
            "search_queries_json": '["q1", "q2"]',
            "citations_json": '[{"title": "Reuters", "uri": "https://reuters.com/1"}]',
            "model": "gemini-2.5-pro",
            "generated_at": datetime(2026, 5, 29, 4, 30, 0),
        }

    def test_upsert_inserts_rows(self, conn):
        upsert_gemini_summaries(
            conn,
            [self._row("NVDA", date(2026, 5, 28)),
             self._row("PLTR", date(2026, 5, 28))],
            date(2026, 5, 28), "overview",
        )
        df = query_gemini_summaries(conn, date(2026, 5, 28), "overview")
        assert len(df) == 2
        assert set(df["ticker"]) == {"NVDA", "PLTR"}

    def test_upsert_idempotent_replaces_cohort(self, conn):
        upsert_gemini_summaries(
            conn, [self._row("NVDA", date(2026, 5, 28))],
            date(2026, 5, 28), "overview",
        )
        # Replace with a different set
        upsert_gemini_summaries(
            conn, [self._row("PLTR", date(2026, 5, 28))],
            date(2026, 5, 28), "overview",
        )
        df = query_gemini_summaries(conn, date(2026, 5, 28), "overview")
        assert len(df) == 1
        assert df.iloc[0]["ticker"] == "PLTR"

    def test_upsert_preserves_other_dates(self, conn):
        upsert_gemini_summaries(
            conn, [self._row("NVDA", date(2026, 5, 21))],
            date(2026, 5, 21), "overview",
        )
        upsert_gemini_summaries(
            conn, [self._row("PLTR", date(2026, 5, 28))],
            date(2026, 5, 28), "overview",
        )
        assert len(query_gemini_summaries(conn, date(2026, 5, 21), "overview")) == 1
        assert len(query_gemini_summaries(conn, date(2026, 5, 28), "overview")) == 1

    def test_upsert_preserves_other_cohort_keys(self, conn):
        upsert_gemini_summaries(
            conn, [self._row("NVDA", date(2026, 5, 28), cohort_key="overview")],
            date(2026, 5, 28), "overview",
        )
        upsert_gemini_summaries(
            conn, [self._row("MRVL", date(2026, 5, 28), cohort_key="us_leg")],
            date(2026, 5, 28), "us_leg",
        )
        assert len(query_gemini_summaries(conn, date(2026, 5, 28), "overview")) == 1
        assert len(query_gemini_summaries(conn, date(2026, 5, 28), "us_leg")) == 1

    def test_empty_rows_clears_cohort(self, conn):
        upsert_gemini_summaries(
            conn, [self._row("NVDA", date(2026, 5, 28))],
            date(2026, 5, 28), "overview",
        )
        upsert_gemini_summaries(conn, [], date(2026, 5, 28), "overview")
        assert len(query_gemini_summaries(conn, date(2026, 5, 28), "overview")) == 0


class TestGeminiSerialization:
    def test_summary_to_row_round_trip(self, conn):
        from webapp.gemini import (
            Citation,
            StockSummary,
            db_rows_to_report,
            summary_to_db_row,
        )
        s = StockSummary(
            ticker="NVDA",
            name="NVIDIA",
            headline="Q1 beat",
            bullets=["bullet A (reuters.com)", "bullet B (bloomberg.com)"],
            reconcile="non-bubbly given fundamentals",
            citations=[
                Citation(title="Reuters", uri="https://reuters.com/1"),
                Citation(title="Bloomberg", uri="https://bloomberg.com/2"),
            ],
            search_queries=["NVDA Q1 earnings", "Marvell custom silicon"],
            domain_mentions=["reuters.com", "bloomberg.com"],
        )
        gen_at = datetime(2026, 5, 29, 4, 30, 0)
        row = summary_to_db_row(s, date(2026, 5, 28), "overview", "gemini-2.5-pro", gen_at)
        upsert_gemini_summaries(conn, [row], date(2026, 5, 28), "overview")

        df = query_gemini_summaries(conn, date(2026, 5, 28), "overview")
        report = db_rows_to_report(df, date(2026, 5, 28))
        assert report is not None
        assert len(report.stocks) == 1
        rs = report.stocks[0]
        assert rs.ticker == "NVDA"
        assert rs.name == "NVIDIA"
        assert rs.headline == "Q1 beat"
        assert rs.bullets == ["bullet A (reuters.com)", "bullet B (bloomberg.com)"]
        assert rs.reconcile == "non-bubbly given fundamentals"
        assert rs.search_queries == ["NVDA Q1 earnings", "Marvell custom silicon"]
        assert rs.domain_mentions == ["reuters.com", "bloomberg.com"]
        assert [c.uri for c in rs.citations] == [
            "https://reuters.com/1", "https://bloomberg.com/2"
        ]
        assert report.model == "gemini-2.5-pro"

    def test_db_rows_to_report_empty_df_returns_none(self):
        from webapp.gemini import db_rows_to_report
        assert db_rows_to_report(pd.DataFrame(), date(2026, 5, 28)) is None
