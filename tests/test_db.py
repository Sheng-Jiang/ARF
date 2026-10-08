import uuid
from datetime import UTC, date, datetime, timedelta

import pandas as pd
import pytest

from arf.db import (
    finish_run,
    init_db,
    list_pool_ids,
    query_candidates,
    query_fetch_outcomes,
    query_gemini_summaries,
    query_latest,
    query_latest_run,
    query_pool_membership,
    query_runs,
    query_snapshot,
    query_theses,
    record_fetch_outcomes,
    start_run,
    update_candidate_status,
    upsert_candidate,
    upsert_gemini_summaries,
    upsert_pool_membership,
    upsert_snapshot,
    upsert_thesis,
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


class TestSnapshotRevisions:
    """Snapshot history is append-only.

    Re-running a past as_of_date must not replace what was recorded then —
    a re-run sees today's data (restated fundamentals, a different set of
    tickers that resolved), so overwriting it silently rewrites history.
    ``snapshots`` is a view of the latest revision per date; every revision
    stays in ``snapshot_revisions``.
    """

    def _revisions(self, conn, ticker: str, as_of: date) -> list[tuple]:
        return conn.execute(
            "SELECT revision, arf FROM snapshot_revisions "
            "WHERE ticker = ? AND as_of_date = ? ORDER BY revision",
            [ticker, as_of],
        ).fetchall()

    def test_rerun_same_date_preserves_earlier_revision(self, conn):
        as_of = date(2026, 5, 28)
        df1 = _sample_df(["NVDA"], as_of)
        df1.loc[0, "arf"] = 60.0
        upsert_snapshot(conn, df1, as_of)
        df2 = _sample_df(["NVDA"], as_of)
        df2.loc[0, "arf"] = 75.0
        upsert_snapshot(conn, df2, as_of)

        assert self._revisions(conn, "NVDA", as_of) == [(1, 60.0), (2, 75.0)]

    def test_view_serves_only_the_latest_run_for_a_date(self, conn):
        """A ticker that failed to fetch on the re-run must not resurface from
        the earlier revision — its scores were ranked against a different
        peer set and are not comparable with the re-run's rows."""
        as_of = date(2026, 5, 28)
        upsert_snapshot(conn, _sample_df(["NVDA", "AMD"], as_of), as_of)
        upsert_snapshot(conn, _sample_df(["NVDA"], as_of), as_of)

        assert query_snapshot(conn, as_of)["ticker"].tolist() == ["NVDA"]

    def test_revision_counter_is_per_date(self, conn):
        d1, d2 = date(2026, 5, 28), date(2026, 6, 4)
        upsert_snapshot(conn, _sample_df(["NVDA"], d1), d1)
        upsert_snapshot(conn, _sample_df(["NVDA"], d2), d2)
        upsert_snapshot(conn, _sample_df(["NVDA"], d1), d1)

        assert [r[0] for r in self._revisions(conn, "NVDA", d1)] == [1, 2]
        assert [r[0] for r in self._revisions(conn, "NVDA", d2)] == [1]

    def test_write_records_run_id_and_fetched_at(self, conn):
        as_of = date(2026, 5, 28)
        before = datetime.now(UTC).replace(tzinfo=None, microsecond=0)
        upsert_snapshot(conn, _sample_df(["NVDA"], as_of), as_of, run_id="run-abc")
        after = datetime.now(UTC).replace(tzinfo=None) + timedelta(seconds=1)

        run_id, fetched_at = conn.execute(
            "SELECT run_id, fetched_at FROM snapshot_revisions WHERE ticker = 'NVDA'"
        ).fetchone()
        assert run_id == "run-abc"
        assert before <= fetched_at <= after

    def test_view_keeps_the_pre_revision_columns(self, conn):
        """Readers doing SELECT * FROM snapshots (webapp tables, pool.py) must
        not start receiving bookkeeping columns."""
        cols = set(conn.execute("DESCRIBE snapshots").fetchdf()["column_name"])
        assert not cols & {"revision", "fetched_at", "run_id"}


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


class TestZombieRunMigration:
    """init_db() closes out stale 'running' rows left by crashed executions."""

    def test_stale_running_marked_interrupted_on_reopen(self, tmp_path):
        db_path = tmp_path / "zombie.db"
        c = init_db(db_path)
        c.execute(
            "INSERT INTO runs (run_id, as_of_date, started_at, status) "
            "VALUES ('old', '2026-06-26', now() - INTERVAL '1 day', 'running')"
        )
        c.execute(
            "INSERT INTO runs (run_id, as_of_date, started_at, status) "
            "VALUES ('fresh', '2026-07-19', now(), 'running')"
        )
        c.commit()
        # The migration must run on every init, not just the first connect.
        c.close()
        c2 = init_db(db_path)
        statuses = dict(c2.execute("SELECT run_id, status FROM runs").fetchall())
        c2.close()
        assert statuses["old"] == "interrupted"
        assert statuses["fresh"] == "running"

    def test_live_run_survives_an_eastern_session_timezone(self, tmp_path):
        """started_at is naive UTC; the cutoff must be too.

        Compared against bare now() (a TIMESTAMPTZ), DuckDB reads the naive
        column in the session time zone. At UTC+8 that shifts it 8 hours
        forward, so a run started this instant already looks stale and every
        connect would mark the *live* pipeline interrupted.
        """
        from datetime import UTC, datetime

        from arf.db import _mark_stale_runs_interrupted, start_run

        db_path = tmp_path / "tz.db"
        c = init_db(db_path)
        c.execute("SET TimeZone='Asia/Shanghai'")
        start_run(c, "live", date(2026, 8, 10), "manual")
        start_run(
            c, "zombie", date(2026, 8, 9), "manual",
            started_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=9),
        )

        _mark_stale_runs_interrupted(c)
        statuses = dict(c.execute("SELECT run_id, status FROM runs").fetchall())
        c.close()
        assert statuses["live"] == "running"
        assert statuses["zombie"] == "interrupted"

    def test_mark_stale_runs_idempotent(self, conn):
        from arf.db import _mark_stale_runs_interrupted

        conn.execute(
            "INSERT INTO runs (run_id, as_of_date, started_at, status) "
            "VALUES ('old', '2026-06-26', now() - INTERVAL '2 days', 'running')"
        )
        conn.commit()
        _mark_stale_runs_interrupted(conn)
        _mark_stale_runs_interrupted(conn)  # second pass must not raise
        row = conn.execute("SELECT status FROM runs WHERE run_id = 'old'").fetchone()
        assert row[0] == "interrupted"


class TestThermometerCohortFilter:
    """The thermometer aggregates the core board only.

    Newcomers are percentile-ranked inside their own 5-name cohort, so the top
    one always scores arf = 100. Pooling them with the core board adds a
    guaranteed phantom D1 per leg every week and drags MEDIAN(arf) upward —
    and disagrees with render_markdown, which already counts core only.
    """

    def _rows(self, cohorts: list[tuple[str, str, float]]) -> pd.DataFrame:
        return pd.DataFrame([
            {"ticker": f"T{i}", "leg": "US", "cohort": cohort, "arf": arf,
             "froth_flag": False, "roe": 0.5, "ps_ratio": 3.0,
             "ev_sales_5yr_percentile": 50.0, "implied_growth_gap": 0.01,
             "name": name}
            for i, (name, cohort, arf) in enumerate(cohorts)
        ])

    def test_newcomers_excluded_from_counts_and_median(self, conn):
        from arf.db import query_thermometer_series

        upsert_snapshot(conn, self._rows([
            ("core-low", "core", 10.0),
            ("core-mid", "core", 20.0),
            ("core-high", "core", 30.0),
            ("newcomer-top", "newcomer", 100.0),  # always 100 within its cohort
            ("newcomer-2", "newcomer", 80.0),
        ]), date(2026, 8, 9))

        row = query_thermometer_series(conn).iloc[0]
        assert row["count_arf_gte_90"] == 0      # the phantom D1 is gone
        assert row["median_arf"] == 20.0         # median of the 3 core rows

    def test_rows_without_a_cohort_are_treated_as_core(self, conn):
        """Snapshots written before the cohort column must still aggregate."""
        from arf.db import query_thermometer_series

        df = self._rows([("legacy", "core", 40.0)])
        df["cohort"] = None
        upsert_snapshot(conn, df, date(2026, 8, 9))
        assert query_thermometer_series(conn).iloc[0]["median_arf"] == 40.0


class TestSchemaMigration:
    def test_cohort_column_added_to_an_existing_db(self, tmp_path):
        """CREATE TABLE IF NOT EXISTS leaves an old table untouched."""
        import duckdb

        db_path = tmp_path / "old.db"
        c = duckdb.connect(str(db_path))
        c.execute(
            "CREATE TABLE snapshots (ticker TEXT, as_of_date DATE, leg TEXT, "
            "arf DOUBLE, PRIMARY KEY (ticker, as_of_date))"
        )
        c.close()

        c2 = init_db(db_path)
        cols = {r[0] for r in c2.execute("DESCRIBE snapshots").fetchall()}
        c2.close()
        assert {"cohort", "financial_currency", "financial_fx_usd"} <= cols

    def _legacy_db(self, tmp_path):
        """A DB from before snapshots became append-only: a physical table."""
        import duckdb

        db_path = tmp_path / "legacy.db"
        c = duckdb.connect(str(db_path))
        c.execute(
            "CREATE TABLE snapshots (ticker TEXT, as_of_date DATE, leg TEXT, "
            "arf DOUBLE, PRIMARY KEY (ticker, as_of_date))"
        )
        c.execute(
            "INSERT INTO snapshots VALUES "
            "('NVDA', DATE '2026-05-28', 'US', 60.0), "
            "('AMD',  DATE '2026-05-28', 'US', 70.0)"
        )
        c.close()
        return db_path

    def test_legacy_rows_survive_as_revision_one(self, tmp_path):
        db_path = self._legacy_db(tmp_path)
        init_db(db_path).close()
        c = init_db(db_path)  # reopening must not migrate twice

        rows = c.execute(
            "SELECT ticker, revision, arf, fetched_at FROM snapshot_revisions "
            "ORDER BY ticker"
        ).fetchall()
        served = query_snapshot(c, date(2026, 5, 28))
        c.close()

        assert rows == [("AMD", 1, 70.0, None), ("NVDA", 1, 60.0, None)]
        assert sorted(served["ticker"]) == ["AMD", "NVDA"]

    def test_rerun_after_migration_becomes_revision_two(self, tmp_path):
        db_path = self._legacy_db(tmp_path)
        c = init_db(db_path)
        as_of = date(2026, 5, 28)
        upsert_snapshot(c, _sample_df(["NVDA"], as_of), as_of)

        revisions = c.execute(
            "SELECT revision FROM snapshot_revisions WHERE ticker = 'NVDA' "
            "ORDER BY revision"
        ).fetchall()
        c.close()
        assert revisions == [(1,), (2,)]


class TestPoolMembership:
    """Quarterly pool audit trail: upsert idempotency + query by pool."""

    def _sample_rows(self):
        return [
            {"ticker": "NVDA", "leg": "US", "cohort": "core",
             "listed_at": None, "reason": "initial"},
            {"ticker": "CRWV", "leg": "US", "cohort": "newcomer",
             "listed_at": date(2025, 3, 28), "reason": "new listing"},
            {"ticker": "688041.SH", "leg": "China", "cohort": "core",
             "listed_at": date(2022, 8, 12), "reason": "initial"},
        ]

    def test_upsert_and_query_round_trip(self, conn):
        upsert_pool_membership(conn, "2026Q3", self._sample_rows())
        df = query_pool_membership(conn, "2026Q3")
        assert len(df) == 3
        by_ticker = {r["ticker"]: r for _, r in df.iterrows()}
        assert by_ticker["NVDA"]["cohort"] == "core"
        assert by_ticker["CRWV"]["cohort"] == "newcomer"
        assert by_ticker["688041.SH"]["leg"] == "China"

    def test_upsert_replaces_same_pool(self, conn):
        upsert_pool_membership(conn, "2026Q3", self._sample_rows())
        upsert_pool_membership(conn, "2026Q3", [self._sample_rows()[0]])
        df = query_pool_membership(conn, "2026Q3")
        assert len(df) == 1  # replaced, not appended
        assert df.iloc[0]["ticker"] == "NVDA"

    def test_query_latest_pool(self, conn):
        upsert_pool_membership(conn, "2026Q2", self._sample_rows()[:1])
        upsert_pool_membership(conn, "2026Q3", self._sample_rows()[:2])
        df = query_pool_membership(conn)  # latest = 2026Q3
        assert set(df["pool_id"]) == {"2026Q3"}
        assert len(df) == 2
        assert list_pool_ids(conn) == ["2026Q3", "2026Q2"]

    def test_upsert_empty_clears_pool(self, conn):
        upsert_pool_membership(conn, "2026Q3", self._sample_rows())
        upsert_pool_membership(conn, "2026Q3", [])
        assert query_pool_membership(conn, "2026Q3").empty


class TestCandidatePool:
    def test_upsert_and_query_candidates(self, conn):
        cand = {
            "ticker": "VRT",
            "name": "Vertiv Holdings",
            "leg": "US",
            "layer": "L1",
            "source": "capex_radar",
            "discovered_at": date(2026, 6, 1),
            "status": "discovered",
            "pure_play_est": 45.0,
            "supply_role": "Liquid cooling and power management",
            "key_customers_json": ["NVDA", "MSFT"],
            "notes": "Fastest growing cooling vendor",
        }
        upsert_candidate(conn, cand)
        df = query_candidates(conn)
        assert len(df) == 1
        assert df.iloc[0]["ticker"] == "VRT"
        assert df.iloc[0]["supply_role"] == "Liquid cooling and power management"
        assert "NVDA" in df.iloc[0]["key_customers_json"]

    def test_filter_candidates(self, conn):
        upsert_candidate(conn, {"ticker": "US1", "leg": "US", "status": "qualified"})
        upsert_candidate(conn, {"ticker": "CN1", "leg": "China", "status": "discovered"})
        
        us_df = query_candidates(conn, leg="US")
        assert len(us_df) == 1
        assert us_df.iloc[0]["ticker"] == "US1"

        qual_df = query_candidates(conn, status="qualified")
        assert len(qual_df) == 1
        assert qual_df.iloc[0]["ticker"] == "US1"

    def test_update_candidate_status(self, conn):
        upsert_candidate(conn, {"ticker": "TEST", "leg": "US", "status": "discovered"})
        update_candidate_status(conn, "TEST", "monitored", notes="Promoted to watch")
        df = query_candidates(conn, status="monitored")
        assert len(df) == 1
        assert df.iloc[0]["notes"] == "Promoted to watch"


class TestInvestmentTheses:
    def test_upsert_and_query_theses(self, conn):
        thesis = {
            "thesis_id": "th-001",
            "ticker": "NVDA",
            "as_of_date": date(2026, 6, 1),
            "thesis_type": "garp_value",
            "title": "Blackwell transition margin inflection",
            "bull_case": "Blackwell ultra demand accelerates",
            "bear_case": "ASIC competition and power bottleneck",
            "synthesis": "Strong buy in D3-D5 range",
            "valuation_entry_zone": "Forward P/E < 28",
            "invalidation_criteria": "Gross margin drops below 70%",
            "confidence_score": 85.0,
            "catalysts_json": ["GTC conference", "Q2 earnings"],
            "model": "gemini-3.7-flash",
        }
        upsert_thesis(conn, thesis)
        df = query_theses(conn, ticker="NVDA")
        assert len(df) == 1
        assert df.iloc[0]["thesis_type"] == "garp_value"
        assert df.iloc[0]["confidence_score"] == 85.0
        assert "GTC conference" in df.iloc[0]["catalysts_json"]

    def test_query_theses_filtering(self, conn):
        upsert_thesis(conn, {
            "thesis_id": "t1", "ticker": "T1", "as_of_date": date(2026, 6, 1),
            "thesis_type": "long_opportunity", "title": "T1 thesis"
        })
        upsert_thesis(conn, {
            "thesis_id": "t2", "ticker": "T2", "as_of_date": date(2026, 6, 1),
            "thesis_type": "froth_short", "title": "T2 thesis"
        })
        short_df = query_theses(conn, thesis_type="froth_short")
        assert len(short_df) == 1
        assert short_df.iloc[0]["ticker"] == "T2"

