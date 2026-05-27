from datetime import date
from pathlib import Path

import duckdb
import pandas as pd

_SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    ticker                  TEXT        NOT NULL,
    as_of_date              DATE        NOT NULL,
    leg                     TEXT,
    layer                   TEXT,
    name                    TEXT,
    -- market data
    price                   DOUBLE,
    market_cap_usd          DOUBLE,
    ev_usd                  DOUBLE,
    -- fundamentals
    revenue_ttm             DOUBLE,
    revenue_yoy_growth      DOUBLE,
    gross_margin            DOUBLE,
    roe                     DOUBLE,
    free_cash_flow          DOUBLE,
    net_income_excl_nr      DOUBLE,
    -- forward estimates
    forward_pe              DOUBLE,
    eps_2yr_cagr            DOUBLE,
    revenue_3yr_cagr        DOUBLE,
    revenue_ntm             DOUBLE,
    -- valuation ratios
    ps_ratio                DOUBLE,
    ev_sales                DOUBLE,
    ev_sales_5yr_percentile DOUBLE,
    -- computed
    e_score                 DOUBLE,
    v_score                 DOUBLE,
    arf                     DOUBLE,
    decile                  INTEGER,
    froth_flag              BOOLEAN,
    implied_growth          DOUBLE,
    implied_growth_gap      DOUBLE,
    -- metadata
    policy_premium          BOOLEAN,
    data_source             TEXT,
    currency                TEXT,
    fx_rate_usd             DOUBLE,
    PRIMARY KEY (ticker, as_of_date)
)
"""


def init_db(path: Path = Path("data/arf.db")) -> duckdb.DuckDBPyConnection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(path))
    conn.execute(_SCHEMA)
    return conn


def upsert_snapshot(
    conn: duckdb.DuckDBPyConnection,
    df: pd.DataFrame,
    as_of_date: date,
) -> None:
    """Insert or overwrite all rows for the given as_of_date.

    Only df columns that match schema columns are inserted; extra schema
    columns default to NULL. Extra df columns are silently ignored.
    """
    df = df.copy()
    df["as_of_date"] = as_of_date

    schema_cols = [
        row[0]
        for row in conn.execute("DESCRIBE snapshots").fetchall()
    ]
    df_cols = [c for c in schema_cols if c in df.columns]
    cols_sql = ", ".join(df_cols)
    conn.execute("DELETE FROM snapshots WHERE as_of_date = ?", [as_of_date])
    conn.execute(f"INSERT INTO snapshots ({cols_sql}) SELECT {cols_sql} FROM df")
    conn.commit()


def query_snapshot(
    conn: duckdb.DuckDBPyConnection,
    as_of_date: date,
) -> pd.DataFrame:
    return conn.execute(
        "SELECT * FROM snapshots WHERE as_of_date = ?", [as_of_date]
    ).fetchdf()


def query_latest(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return conn.execute(
        "SELECT * FROM snapshots WHERE as_of_date = (SELECT MAX(as_of_date) FROM snapshots)"
    ).fetchdf()


def query_thermometer_series(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Return weekly bubble-thermometer metrics over time."""
    return conn.execute("""
        SELECT
            as_of_date,
            leg,
            COUNT(*) FILTER (WHERE arf >= 90) AS count_arf_gte_90,
            COUNT(*) FILTER (WHERE froth_flag = TRUE) AS count_froth,
            MEDIAN(arf) AS median_arf
        FROM snapshots
        GROUP BY as_of_date, leg
        ORDER BY as_of_date, leg
    """).fetchdf()
