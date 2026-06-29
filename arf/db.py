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

_SCHEMA_DAILY_PRICES = """
CREATE TABLE IF NOT EXISTS daily_prices (
    ticker          TEXT        NOT NULL,
    date            DATE        NOT NULL,
    open            DOUBLE,
    high            DOUBLE,
    low             DOUBLE,
    close           DOUBLE,
    volume          DOUBLE,
    turnover_rate   DOUBLE,
    PRIMARY KEY (ticker, date)
)
"""

_SCHEMA_TECHNICAL_METRICS = """
CREATE TABLE IF NOT EXISTS technical_metrics (
    ticker                  TEXT        NOT NULL,
    as_of_date              DATE        NOT NULL,
    technical_score         DOUBLE,
    ma5                     DOUBLE,
    ma10                    DOUBLE,
    ma20                    DOUBLE,
    ma30                    DOUBLE,
    ma60                    DOUBLE,
    ma120                   DOUBLE,
    ma_bullish_alignment    BOOLEAN,
    macd_dif                DOUBLE,
    macd_dea                DOUBLE,
    macd_hist               DOUBLE,
    rsi                     DOUBLE,
    bollinger_mid           DOUBLE,
    bollinger_upper         DOUBLE,
    bollinger_lower         DOUBLE,
    atr                     DOUBLE,
    chip_profit_ratio       DOUBLE,
    chip_avg_cost           DOUBLE,
    chip_90_cost_min        DOUBLE,
    chip_90_cost_max        DOUBLE,
    chip_70_cost_min        DOUBLE,
    chip_70_cost_max        DOUBLE,
    PRIMARY KEY (ticker, as_of_date)
)
"""

_SCHEMA_RESEARCH_REPORTS = """
CREATE TABLE IF NOT EXISTS research_reports (
    ticker        TEXT        NOT NULL,
    as_of_date    DATE        NOT NULL,
    report_date   DATE,
    institution   TEXT,
    rating        TEXT,
    target_price  DOUBLE,
    eps_forecast  DOUBLE,
    title         TEXT,
    pdf_url       TEXT,
    source        TEXT,
    currency      TEXT
)
"""

_SCHEMA_RESEARCH_SYNTHESIS = """
CREATE TABLE IF NOT EXISTS research_synthesis (
    as_of_date     DATE        PRIMARY KEY,
    synthesis_text TEXT,
    citations_json TEXT,
    cohort_json    TEXT,
    model          TEXT,
    generated_at   TIMESTAMP   NOT NULL
)
"""

_SCHEMA_WEEKLY_REPORTS = """
CREATE TABLE IF NOT EXISTS weekly_reports (
    as_of_date      DATE        PRIMARY KEY,
    generated_at    TIMESTAMP   NOT NULL,
    report_path     TEXT,
    gemini_summary  TEXT,
    stocks_covered  TEXT,
    trigger_source  TEXT
)
"""


def init_db(path: Path = Path("data/arf.db")) -> duckdb.DuckDBPyConnection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(path))
    conn.execute(_SCHEMA_SNAPSHOTS)
    conn.execute(_SCHEMA_RUNS)
    conn.execute(_SCHEMA_FETCH_OUTCOMES)
    conn.execute(_SCHEMA_GEMINI_SUMMARIES)
    conn.execute(_SCHEMA_DAILY_PRICES)
    conn.execute(_SCHEMA_TECHNICAL_METRICS)
    conn.execute(_SCHEMA_RESEARCH_REPORTS)
    conn.execute(_SCHEMA_RESEARCH_SYNTHESIS)
    conn.execute(_SCHEMA_WEEKLY_REPORTS)
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
            -- Absolute froth count: ROE < WACC (10% US, 12% China) AND P/S > 25
            COUNT(*) FILTER (
                WHERE (leg = 'US' AND roe < 0.10 AND ps_ratio > 25) OR
                      (leg = 'China' AND roe < 0.12 AND ps_ratio > 25)
            ) AS count_absolute_froth,
            MEDIAN(ev_sales_5yr_percentile) AS median_ev_sales_pct,
            MEDIAN(implied_growth_gap) * 100 AS median_growth_gap_pct,
            MEDIAN(arf) AS median_arf
        FROM snapshots
        GROUP BY as_of_date, leg
        ORDER BY as_of_date, leg
    """).fetchdf()


def upsert_daily_prices(
    conn: duckdb.DuckDBPyConnection,
    df: pd.DataFrame,
) -> None:
    """Insert or overwrite daily prices.

    Matches columns of daily_prices table.
    """
    if df.empty:
        return
    df = df.copy()
    
    # Ensure dates are date objects for DuckDB
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"]).dt.date

    # Delete existing data for the tickers in the input dataframe to ensure idempotency
    tickers = list(df["ticker"].unique())
    if len(tickers) == 1:
        conn.execute("DELETE FROM daily_prices WHERE ticker = ?", [tickers[0]])
    elif len(tickers) > 1:
        tickers_str = ", ".join(f"'{t}'" for t in tickers)
        conn.execute(f"DELETE FROM daily_prices WHERE ticker IN ({tickers_str})")

    schema_cols = [
        row[0]
        for row in conn.execute("DESCRIBE daily_prices").fetchall()
    ]
    df_cols = [c for c in schema_cols if c in df.columns]
    cols_sql = ", ".join(df_cols)
    conn.execute(f"INSERT INTO daily_prices ({cols_sql}) SELECT {cols_sql} FROM df")
    conn.commit()


def query_daily_prices(
    conn: duckdb.DuckDBPyConnection,
    ticker: str,
) -> pd.DataFrame:
    """Query daily prices for a given ticker, sorted by date ascending."""
    return conn.execute(
        "SELECT * FROM daily_prices WHERE ticker = ? ORDER BY date ASC",
        [ticker]
    ).fetchdf()


def upsert_technical_metrics(
    conn: duckdb.DuckDBPyConnection,
    df: pd.DataFrame,
    as_of_date: date,
) -> None:
    """Insert or overwrite technical metrics for the given as_of_date."""
    if df.empty:
        return
    df = df.copy()
    df["as_of_date"] = as_of_date

    schema_cols = [
        row[0]
        for row in conn.execute("DESCRIBE technical_metrics").fetchall()
    ]
    df_cols = [c for c in schema_cols if c in df.columns]
    cols_sql = ", ".join(df_cols)
    conn.execute("DELETE FROM technical_metrics WHERE as_of_date = ?", [as_of_date])
    conn.execute(f"INSERT INTO technical_metrics ({cols_sql}) SELECT {cols_sql} FROM df")
    conn.commit()


def query_technical_metrics(
    conn: duckdb.DuckDBPyConnection,
    as_of_date: date,
) -> pd.DataFrame:
    """Query technical metrics for a given date."""
    return conn.execute(
        "SELECT * FROM technical_metrics WHERE as_of_date = ?",
        [as_of_date]
    ).fetchdf()


def upsert_research_reports(
    conn: duckdb.DuckDBPyConnection,
    df: pd.DataFrame,
    as_of_date: date,
) -> None:
    """Insert or overwrite all institutional research rows for the given as_of_date.

    Idempotent per snapshot: every row carried for ``as_of_date`` is replaced, so a
    re-run of the pipeline overwrites rather than duplicates. ``df`` may hold many
    rows per ticker (one per report + a consensus row).
    """
    if df.empty:
        # Still clear the date so a re-run that now finds no coverage doesn't leave
        # stale rows behind.
        conn.execute("DELETE FROM research_reports WHERE as_of_date = ?", [as_of_date])
        conn.commit()
        return
    df = df.copy()
    df["as_of_date"] = as_of_date
    for col in ("report_date",):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.date

    schema_cols = [row[0] for row in conn.execute("DESCRIBE research_reports").fetchall()]
    df_cols = [c for c in schema_cols if c in df.columns]
    cols_sql = ", ".join(df_cols)
    conn.execute("DELETE FROM research_reports WHERE as_of_date = ?", [as_of_date])
    conn.execute(f"INSERT INTO research_reports ({cols_sql}) SELECT {cols_sql} FROM df")
    conn.commit()


def query_research_reports(
    conn: duckdb.DuckDBPyConnection,
    as_of_date: date,
    ticker: str | None = None,
) -> pd.DataFrame:
    """Query institutional research for a date, optionally filtered to one ticker."""
    if ticker is not None:
        return conn.execute(
            "SELECT * FROM research_reports WHERE as_of_date = ? AND ticker = ? "
            "ORDER BY report_date DESC",
            [as_of_date, ticker],
        ).fetchdf()
    return conn.execute(
        "SELECT * FROM research_reports WHERE as_of_date = ? "
        "ORDER BY ticker, report_date DESC",
        [as_of_date],
    ).fetchdf()


def upsert_research_synthesis(
    conn: duckdb.DuckDBPyConnection,
    as_of_date: date,
    synthesis_text: str,
    citations_json: str,
    cohort_json: str,
    model: str,
    generated_at: datetime | None = None,
) -> None:
    """Insert or overwrite the institutional-research narrative for a date."""
    generated = generated_at or datetime.now(UTC).replace(tzinfo=None)
    conn.execute("DELETE FROM research_synthesis WHERE as_of_date = ?", [as_of_date])
    conn.execute(
        "INSERT INTO research_synthesis (as_of_date, synthesis_text, citations_json, "
        "cohort_json, model, generated_at) VALUES (?, ?, ?, ?, ?, ?)",
        [as_of_date, synthesis_text, citations_json, cohort_json, model, generated],
    )
    conn.commit()


def query_research_synthesis(
    conn: duckdb.DuckDBPyConnection,
    as_of_date: date,
) -> pd.DataFrame:
    """Return the research-synthesis row for a date (empty frame if none)."""
    return conn.execute(
        "SELECT * FROM research_synthesis WHERE as_of_date = ?", [as_of_date]
    ).fetchdf()


def upsert_weekly_report(
    conn: duckdb.DuckDBPyConnection,
    as_of_date: date,
    report_path: str,
    gemini_summary: str,
    stocks_covered: str,
    trigger_source: str,
    generated_at: datetime | None = None,
) -> None:
    """Insert or overwrite a weekly report record."""
    generated = generated_at or datetime.now(UTC).replace(tzinfo=None)
    conn.execute("DELETE FROM weekly_reports WHERE as_of_date = ?", [as_of_date])
    conn.execute(
        "INSERT INTO weekly_reports (as_of_date, generated_at, report_path, "
        "gemini_summary, stocks_covered, trigger_source) VALUES (?, ?, ?, ?, ?, ?)",
        [as_of_date, generated, report_path, gemini_summary, stocks_covered, trigger_source],
    )
    conn.commit()


def query_weekly_reports(
    conn: duckdb.DuckDBPyConnection,
    limit: int = 20,
) -> pd.DataFrame:
    """List weekly reports ordered by date descending."""
    return conn.execute(
        "SELECT * FROM weekly_reports ORDER BY as_of_date DESC LIMIT ?", [limit]
    ).fetchdf()

