from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
import pandas as pd

_SCHEMA_SNAPSHOTS = """
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

_SCHEMA_RUNS = """
CREATE TABLE IF NOT EXISTS runs (
    run_id          TEXT       PRIMARY KEY,
    as_of_date      DATE       NOT NULL,
    started_at      TIMESTAMP  NOT NULL,
    finished_at     TIMESTAMP,
    status          TEXT,
    tickers_total   INTEGER,
    tickers_ok      INTEGER,
    tickers_failed  INTEGER,
    duration_sec    DOUBLE,
    error_message   TEXT,
    trigger_source  TEXT
)
"""

_SCHEMA_FETCH_OUTCOMES = """
CREATE TABLE IF NOT EXISTS fetch_outcomes (
    run_id       TEXT  NOT NULL,
    ticker       TEXT  NOT NULL,
    status       TEXT,
    data_source  TEXT,
    PRIMARY KEY (run_id, ticker)
)
"""

_SCHEMA_GEMINI_SUMMARIES = """
CREATE TABLE IF NOT EXISTS gemini_summaries (
    as_of_date           DATE      NOT NULL,
    ticker               TEXT      NOT NULL,
    cohort_key           TEXT      NOT NULL,
    name                 TEXT,
    headline             TEXT,
    bullets_json         TEXT,
    reconcile            TEXT,
    domain_mentions_json TEXT,
    search_queries_json  TEXT,
    citations_json       TEXT,
    model                TEXT,
    generated_at         TIMESTAMP NOT NULL,
    PRIMARY KEY (as_of_date, ticker, cohort_key)
)
"""


def init_db(path: Path = Path("data/arf.db")) -> duckdb.DuckDBPyConnection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(path))
    conn.execute(_SCHEMA_SNAPSHOTS)
    conn.execute(_SCHEMA_RUNS)
    conn.execute(_SCHEMA_FETCH_OUTCOMES)
    conn.execute(_SCHEMA_GEMINI_SUMMARIES)
    return conn


def start_run(
    conn: duckdb.DuckDBPyConnection,
    run_id: str,
    as_of_date: date,
    trigger_source: str,
    started_at: datetime | None = None,
) -> None:
    conn.execute(
        "INSERT INTO runs (run_id, as_of_date, started_at, status, trigger_source) "
        "VALUES (?, ?, ?, 'running', ?)",
        [run_id, as_of_date, started_at or datetime.now(UTC).replace(tzinfo=None), trigger_source],
    )
    conn.commit()


def finish_run(
    conn: duckdb.DuckDBPyConnection,
    run_id: str,
    status: str,
    tickers_total: int,
    tickers_ok: int,
    tickers_failed: int,
    error_message: str | None = None,
    finished_at: datetime | None = None,
) -> None:
    finished = finished_at or datetime.now(UTC).replace(tzinfo=None)
    row = conn.execute("SELECT started_at FROM runs WHERE run_id = ?", [run_id]).fetchone()
    duration = (finished - row[0]).total_seconds() if row else None
    conn.execute(
        """UPDATE runs SET
            finished_at = ?,
            status = ?,
            tickers_total = ?,
            tickers_ok = ?,
            tickers_failed = ?,
            duration_sec = ?,
            error_message = ?
           WHERE run_id = ?""",
        [finished, status, tickers_total, tickers_ok, tickers_failed,
         duration, error_message, run_id],
    )
    conn.commit()


def record_fetch_outcomes(
    conn: duckdb.DuckDBPyConnection,
    run_id: str,
    outcomes: list[tuple[str, str, str | None]],
) -> None:
    """outcomes: list of (ticker, status, data_source) tuples."""
    if not outcomes:
        return
    conn.execute("DELETE FROM fetch_outcomes WHERE run_id = ?", [run_id])
    conn.executemany(
        "INSERT INTO fetch_outcomes (run_id, ticker, status, data_source) VALUES (?, ?, ?, ?)",
        [(run_id, t, s, ds) for t, s, ds in outcomes],
    )
    conn.commit()


def query_latest_run(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return conn.execute(
        "SELECT * FROM runs ORDER BY started_at DESC LIMIT 1"
    ).fetchdf()


def query_runs(conn: duckdb.DuckDBPyConnection, limit: int = 20) -> pd.DataFrame:
    return conn.execute(
        "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?", [limit]
    ).fetchdf()


def query_fetch_outcomes(
    conn: duckdb.DuckDBPyConnection,
    run_id: str,
) -> pd.DataFrame:
    return conn.execute(
        "SELECT * FROM fetch_outcomes WHERE run_id = ? ORDER BY ticker", [run_id]
    ).fetchdf()


_GEMINI_COLS = [
    "as_of_date", "ticker", "cohort_key", "name", "headline",
    "bullets_json", "reconcile", "domain_mentions_json",
    "search_queries_json", "citations_json", "model", "generated_at",
]


def upsert_gemini_summaries(
    conn: duckdb.DuckDBPyConnection,
    rows: list[dict],
    as_of_date: date,
    cohort_key: str,
) -> None:
    """Replace any existing summaries for (as_of_date, cohort_key) with `rows`.

    Each row must contain all _GEMINI_COLS keys (the *_json fields as JSON strings).
    """
    conn.execute(
        "DELETE FROM gemini_summaries WHERE as_of_date = ? AND cohort_key = ?",
        [as_of_date, cohort_key],
    )
    if not rows:
        conn.commit()
        return
    conn.executemany(
        f"INSERT INTO gemini_summaries ({', '.join(_GEMINI_COLS)}) "
        f"VALUES ({', '.join(['?'] * len(_GEMINI_COLS))})",
        [tuple(r[c] for c in _GEMINI_COLS) for r in rows],
    )
    conn.commit()


def query_gemini_summaries(
    conn: duckdb.DuckDBPyConnection,
    as_of_date: date,
    cohort_key: str,
) -> pd.DataFrame:
    return conn.execute(
        "SELECT * FROM gemini_summaries WHERE as_of_date = ? AND cohort_key = ? "
        "ORDER BY ticker",
        [as_of_date, cohort_key],
    ).fetchdf()


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
