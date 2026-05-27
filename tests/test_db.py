from datetime import date

import pandas as pd
import pytest

from arf.db import init_db, query_latest, query_snapshot, upsert_snapshot


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
