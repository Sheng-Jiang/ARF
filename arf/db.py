import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import duckdb
import pandas as pd

_SCHEMA_SNAPSHOTS = """
CREATE TABLE IF NOT EXISTS snapshot_revisions (
    ticker                  TEXT        NOT NULL,
    as_of_date              DATE        NOT NULL,
    -- Append-only history: each upsert_snapshot call writes the next revision
    -- (1, 2, …) of its as_of_date and nothing is ever deleted. Readers use the
    -- ``snapshots`` view, which serves only the latest revision per date.
    revision                INTEGER     NOT NULL,
    -- Naive UTC write time. NULL on rows migrated from the pre-revision table:
    -- when those were fetched was never recorded.
    fetched_at              TIMESTAMP,
    run_id                  TEXT,       -- runs.run_id that wrote the row
    leg                     TEXT,
    layer                   TEXT,
    name                    TEXT,
    -- core | newcomer. Percentiles are ranked within (leg, cohort), so
    -- newcomers are not comparable to the core board and must be filtered
    -- out of any cross-sectional aggregate. NULL on pre-cohort rows = core.
    cohort                  TEXT,
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
    -- Reporting currency of the financial statements; differs from `currency`
    -- for ADRs (BABA reports CNY, TSM reports TWD) and sets the reverse-DCF's
    -- unit basis. See arf.scoring._local_market_cap.
    financial_currency      TEXT,
    financial_fx_usd        DOUBLE,
    PRIMARY KEY (ticker, as_of_date, revision)
)
"""

# Latest revision per as_of_date — the *whole* revision, not the newest row per
# ticker: a ticker missing from a re-run must not resurface from an older run,
# because its percentile scores were ranked against a different peer set.
# Bookkeeping columns are excluded so SELECT * readers see the original schema.
_VIEW_SNAPSHOTS = """
CREATE OR REPLACE VIEW snapshots AS
SELECT * EXCLUDE (revision, fetched_at, run_id)
FROM snapshot_revisions r
WHERE revision = (
    SELECT MAX(revision) FROM snapshot_revisions m WHERE m.as_of_date = r.as_of_date
)
"""

_REVISION_COLUMNS = ("revision", "fetched_at", "run_id")

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

_SCHEMA_VALUE_CHAIN = """
CREATE TABLE IF NOT EXISTS value_chain_snapshot (
    as_of_date          DATE        NOT NULL,
    leg                 TEXT        NOT NULL,
    layer               TEXT        NOT NULL,
    layer_name          TEXT,
    market_cap_usd      DOUBLE,
    constituents_json   TEXT,
    generated_at        TIMESTAMP   NOT NULL,
    PRIMARY KEY (as_of_date, leg, layer)
)
"""

_SCHEMA_POOL_MEMBERSHIP = """
CREATE TABLE IF NOT EXISTS pool_membership (
    pool_id      TEXT        NOT NULL,
    ticker       TEXT        NOT NULL,
    leg          TEXT,
    cohort       TEXT,       -- core | newcomer
    listed_at    DATE,
    added_at     TIMESTAMP   NOT NULL,
    reason       TEXT,
    PRIMARY KEY (pool_id, ticker)
)
"""

_SCHEMA_POOL_CHANGES = """
CREATE TABLE IF NOT EXISTS pool_changes (
    pool_id     TEXT        NOT NULL,
    ticker      TEXT        NOT NULL,
    direction   TEXT        NOT NULL,  -- in | out
    cohort      TEXT,
    reason      TEXT,
    applied_at  TIMESTAMP   NOT NULL,
    PRIMARY KEY (pool_id, ticker, direction)
)
"""

_SCHEMA_CANDIDATE_POOL = """
CREATE TABLE IF NOT EXISTS candidate_pool (
    ticker              TEXT        PRIMARY KEY,
    name                TEXT,
    leg                 TEXT        NOT NULL,  -- 'US' or 'China'
    layer               TEXT,                  -- 'L1' to 'L5'
    source              TEXT        NOT NULL,  -- 'sec_filing', 'capex_radar', 'news_crawler', 'manual'
    discovered_at       DATE        NOT NULL,
    status              TEXT        NOT NULL,  -- 'discovered', 'qualified', 'monitored', 'rejected'
    pure_play_est       DOUBLE,
    supply_role         TEXT,
    key_customers_json  TEXT,                  -- e.g. '["NVDA", "MSFT"]'
    notes               TEXT,
    updated_at          TIMESTAMP   NOT NULL
)
"""

_SCHEMA_INVESTMENT_THESES = """
CREATE TABLE IF NOT EXISTS investment_theses (
    thesis_id               TEXT        PRIMARY KEY,
    ticker                  TEXT        NOT NULL,
    as_of_date              DATE        NOT NULL,
    thesis_type             TEXT        NOT NULL,  -- 'long_opportunity', 'garp_value', 'froth_short', 'neutral_watch'
    title                   TEXT        NOT NULL,
    bull_case               TEXT,
    bear_case               TEXT,
    synthesis               TEXT,
    valuation_entry_zone    TEXT,
    invalidation_criteria   TEXT,
    confidence_score        DOUBLE,
    catalysts_json          TEXT,
    model                   TEXT,
    created_at              TIMESTAMP   NOT NULL
)
"""

_SCHEMA_INVESTMENT_DECISION_RECORDS = """
CREATE TABLE IF NOT EXISTS investment_decision_records (
    idr_id                  TEXT        PRIMARY KEY,
    ticker                  TEXT        NOT NULL,
    name                    TEXT,
    as_of_date              DATE        NOT NULL,
    stage                   TEXT        NOT NULL,  -- 'discovered', 'qualified', 'under_review', 'thesis_formulated', 'committee_pending', 'active_watch', 'harvested', 'invalidated'
    trigger_type            TEXT,
    trigger_summary         TEXT,
    observed_metrics_json   TEXT,
    leg                     TEXT,
    layer                   TEXT,
    cost_of_equity          DOUBLE,
    policy_rules_json       TEXT,
    bull_arguments_json     TEXT,
    bear_arguments_json     TEXT,
    deliberation_synthesis  TEXT,
    gate_verdict            TEXT,       -- 'PASSED', 'BLOCKED_FROTH', 'BLOCKED_HURDLE', etc.
    gate_details            TEXT,
    froth_flag              BOOLEAN,
    hurdle_met              BOOLEAN,
    recommended_action      TEXT,       -- 'BUY_ZONE', 'MONITOR', 'AVOID_FROTH', 'HARVEST', 'INVALIDATE'
    valuation_entry_zone    TEXT,
    invalidation_criteria   TEXT,
    confidence_score        DOUBLE,
    catalysts_json          TEXT,
    citations_json          TEXT,
    human_pm_decision       TEXT,
    human_pm_notes          TEXT,
    model                   TEXT,
    created_at              TIMESTAMP   NOT NULL
)
"""

_SCHEMA_OPPORTUNITY_STATE = """
CREATE TABLE IF NOT EXISTS opportunity_states (
    ticker                  TEXT        PRIMARY KEY,
    name                    TEXT,
    leg                     TEXT,
    layer                   TEXT,
    current_stage           TEXT        NOT NULL,
    latest_idr_id           TEXT,
    valuation_entry_zone    TEXT,
    invalidation_criteria   TEXT,
    notes                   TEXT,
    updated_at              TIMESTAMP   NOT NULL
)
"""


def init_db(path: Path = Path("data/arf.db")) -> duckdb.DuckDBPyConnection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(path))
    conn.execute(_SCHEMA_SNAPSHOTS)
    _migrate_legacy_snapshots_table(conn)
    conn.execute(_SCHEMA_RUNS)
    conn.execute(_SCHEMA_FETCH_OUTCOMES)
    conn.execute(_SCHEMA_GEMINI_SUMMARIES)
    conn.execute(_SCHEMA_DAILY_PRICES)
    conn.execute(_SCHEMA_TECHNICAL_METRICS)
    conn.execute(_SCHEMA_RESEARCH_REPORTS)
    conn.execute(_SCHEMA_RESEARCH_SYNTHESIS)
    conn.execute(_SCHEMA_WEEKLY_REPORTS)
    conn.execute(_SCHEMA_VALUE_CHAIN)
    conn.execute(_SCHEMA_POOL_MEMBERSHIP)
    conn.execute(_SCHEMA_POOL_CHANGES)
    conn.execute(_SCHEMA_CANDIDATE_POOL)
    conn.execute(_SCHEMA_INVESTMENT_THESES)
    conn.execute(_SCHEMA_INVESTMENT_DECISION_RECORDS)
    conn.execute(_SCHEMA_OPPORTUNITY_STATE)
    _add_missing_columns(conn)
    conn.execute(_VIEW_SNAPSHOTS)
    _mark_stale_runs_interrupted(conn)
    return conn


def _migrate_legacy_snapshots_table(conn: duckdb.DuckDBPyConnection) -> None:
    """Migration: move a pre-revision physical ``snapshots`` table into history.

    Its rows become revision 1 of their date, then the table is dropped so the
    ``snapshots`` view can take its name. Atomic, and a no-op once ``snapshots``
    is a view — safe on every connect.
    """
    kind = conn.execute(
        "SELECT table_type FROM information_schema.tables "
        "WHERE table_schema = 'main' AND table_name = 'snapshots'"
    ).fetchone()
    if kind is None or kind[0] != "BASE TABLE":
        return
    conn.begin()
    try:
        conn.execute(
            "INSERT INTO snapshot_revisions BY NAME "
            "SELECT *, 1 AS revision FROM snapshots"
        )
        conn.execute("DROP TABLE snapshots")
        conn.commit()
    except Exception:
        conn.rollback()
        raise


# Columns added after the first release. CREATE TABLE IF NOT EXISTS leaves an
# existing table untouched, so each one needs an explicit ALTER on old DBs.
_ADDED_COLUMNS: dict[str, dict[str, str]] = {
    "snapshot_revisions": {
        "cohort": "TEXT",
        "financial_currency": "TEXT",
        "financial_fx_usd": "DOUBLE",
    },
}

# Predicate restricting a snapshots query to the comparable core board.
# Rows written before the cohort column existed are all core, hence COALESCE.
CORE_ONLY = "COALESCE(cohort, 'core') = 'core'"


def _add_missing_columns(conn: duckdb.DuckDBPyConnection) -> None:
    """Bring an existing DB up to the current schema (idempotent)."""
    for table, columns in _ADDED_COLUMNS.items():
        existing = {row[0] for row in conn.execute(f"DESCRIBE {table}").fetchall()}
        for name, sql_type in columns.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {sql_type}")
    conn.commit()


def _mark_stale_runs_interrupted(conn: duckdb.DuckDBPyConnection) -> None:
    """Migration: close out zombie 'running' rows left by crashed executions.

    A run stuck in 'running' for >6 hours is a crashed process (pipelines take
    ~3–5 minutes), not a live one. Marking it 'interrupted' keeps the admin UI
    from showing a perpetual spinner. Idempotent — safe on every connect.

    ``started_at`` is stored as a naive UTC TIMESTAMP (see :func:`start_run`),
    so the cutoff must be naive UTC too. Comparing against bare ``now()`` (a
    TIMESTAMPTZ) makes DuckDB read the naive column in the session time zone:
    east of UTC that shifts it forward and a run started *this second* already
    looks 8 hours old, so every connect would kill the live pipeline.
    """
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=6)
    conn.execute(
        """
        UPDATE runs
        SET status = 'interrupted'
        WHERE status = 'running'
          AND finished_at IS NULL
          AND started_at < ?
        """,
        [cutoff],
    )
    conn.commit()


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
    run_id: str | None = None,
) -> None:
    """Append ``df`` as the next revision of ``as_of_date``.

    Nothing is deleted: re-running a date writes revision N+1, the
    ``snapshots`` view switches to it, and earlier revisions stay in
    ``snapshot_revisions``. Only df columns that match schema columns are
    inserted; extra schema columns default to NULL. Extra df columns are
    silently ignored.
    """
    df = df.copy()
    df["as_of_date"] = as_of_date

    schema_cols = [
        row[0]
        for row in conn.execute("DESCRIBE snapshot_revisions").fetchall()
    ]
    df_cols = [c for c in schema_cols if c in df.columns and c not in _REVISION_COLUMNS]
    cols_sql = ", ".join(df_cols)
    fetched_at = datetime.now(UTC).replace(tzinfo=None)
    conn.begin()
    try:
        revision = conn.execute(
            "SELECT COALESCE(MAX(revision), 0) + 1 FROM snapshot_revisions "
            "WHERE as_of_date = ?",
            [as_of_date],
        ).fetchone()[0]
        conn.execute(
            f"INSERT INTO snapshot_revisions ({cols_sql}, revision, fetched_at, run_id) "
            f"SELECT {cols_sql}, ?, ?, ? FROM df",
            [revision, fetched_at, run_id],
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


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
    """Return weekly bubble-thermometer metrics over time (core board only).

    Newcomers are percentile-ranked inside their own 5-name cohort, so the top
    one always scores arf = 100 and the group is spread 20/40/…/100 regardless
    of valuation. Pooling them with the core board would add a guaranteed
    phantom D1 per leg every week and drag MEDIAN(arf) toward 60 — and would
    disagree with render_markdown, which already counts core only.
    """
    return conn.execute(f"""
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
        WHERE {CORE_ONLY}
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


def upsert_value_chain(
    conn: duckdb.DuckDBPyConnection,
    as_of_date: date,
    rows: list[dict],
    generated_at: datetime | None = None,
) -> None:
    """Insert or overwrite the 双价值链 layer snapshot for a date.

    Each row must have keys: leg, layer, layer_name, market_cap_usd,
    constituents_json.
    """
    generated = generated_at or datetime.now(UTC).replace(tzinfo=None)
    conn.execute("DELETE FROM value_chain_snapshot WHERE as_of_date = ?", [as_of_date])
    if not rows:
        conn.commit()
        return
    conn.executemany(
        "INSERT INTO value_chain_snapshot (as_of_date, leg, layer, layer_name, "
        "market_cap_usd, constituents_json, generated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            (as_of_date, r["leg"], r["layer"], r["layer_name"],
             r["market_cap_usd"], r["constituents_json"], generated)
            for r in rows
        ],
    )
    conn.commit()


def query_value_chain(
    conn: duckdb.DuckDBPyConnection,
    as_of_date: date | None = None,
) -> pd.DataFrame:
    """Return the 双价值链 snapshot for a date, or the latest one if omitted."""
    if as_of_date is not None:
        return conn.execute(
            "SELECT * FROM value_chain_snapshot WHERE as_of_date = ? "
            "ORDER BY leg, layer",
            [as_of_date],
        ).fetchdf()
    return conn.execute(
        "SELECT * FROM value_chain_snapshot "
        "WHERE as_of_date = (SELECT MAX(as_of_date) FROM value_chain_snapshot) "
        "ORDER BY leg, layer"
    ).fetchdf()


def upsert_pool_membership(
    conn: duckdb.DuckDBPyConnection,
    pool_id: str,
    rows: list[dict],
    generated_at: datetime | None = None,
) -> None:
    """Replace all memberships for ``pool_id`` with ``rows`` (idempotent).

    Each row must have keys: ticker, leg, cohort, listed_at (date | None),
    reason (str). ``added_at`` defaults to now. Used by the rotation stage to
    record which names were in each quarter's pool — the percentile rankings
    are pool-relative, so this table is the audit trail for comparability.
    """
    added = generated_at or datetime.now(UTC).replace(tzinfo=None)
    conn.execute("DELETE FROM pool_membership WHERE pool_id = ?", [pool_id])
    if not rows:
        conn.commit()
        return
    conn.executemany(
        "INSERT INTO pool_membership (pool_id, ticker, leg, cohort, listed_at, "
        "added_at, reason) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            (
                pool_id,
                r["ticker"],
                r.get("leg"),
                r.get("cohort"),
                r.get("listed_at"),
                added,
                r.get("reason", ""),
            )
            for r in rows
        ],
    )
    conn.commit()


def query_pool_membership(
    conn: duckdb.DuckDBPyConnection,
    pool_id: str | None = None,
) -> pd.DataFrame:
    """Return memberships for a pool id, or the latest pool if omitted."""
    if pool_id is not None:
        return conn.execute(
            "SELECT * FROM pool_membership WHERE pool_id = ? ORDER BY leg, cohort, ticker",
            [pool_id],
        ).fetchdf()
    return conn.execute(
        "SELECT * FROM pool_membership "
        "WHERE pool_id = (SELECT MAX(pool_id) FROM pool_membership) "
        "ORDER BY leg, cohort, ticker"
    ).fetchdf()


def list_pool_ids(conn: duckdb.DuckDBPyConnection) -> list[str]:
    """Distinct pool ids, newest first (e.g. ['2026Q3', '2026Q2'])."""
    rows = conn.execute(
        "SELECT DISTINCT pool_id FROM pool_membership ORDER BY pool_id DESC"
    ).fetchall()
    return [r[0] for r in rows]


def upsert_pool_changes(
    conn: duckdb.DuckDBPyConnection,
    pool_id: str,
    changes: list[dict],
    generated_at: datetime | None = None,
) -> None:
    """Record the in/out swaps of one rotation (replace per pool_id).

    Each change dict must have keys: ticker, direction ('in'|'out'),
    cohort, reason. Used by the rotation stage to audit every quarterly swap.
    """
    applied = generated_at or datetime.now(UTC).replace(tzinfo=None)
    conn.execute("DELETE FROM pool_changes WHERE pool_id = ?", [pool_id])
    if not changes:
        conn.commit()
        return
    conn.executemany(
        "INSERT INTO pool_changes (pool_id, ticker, direction, cohort, reason, "
        "applied_at) VALUES (?, ?, ?, ?, ?, ?)",
        [
            (
                pool_id,
                c["ticker"],
                c["direction"],
                c.get("cohort"),
                c.get("reason", ""),
                applied,
            )
            for c in changes
        ],
    )
    conn.commit()


def query_pool_changes(
    conn: duckdb.DuckDBPyConnection,
    pool_id: str | None = None,
) -> pd.DataFrame:
    """Return rotation changes for a pool, or the latest pool if omitted."""
    if pool_id is not None:
        return conn.execute(
            "SELECT * FROM pool_changes WHERE pool_id = ? ORDER BY direction, ticker",
            [pool_id],
        ).fetchdf()
    return conn.execute(
        "SELECT * FROM pool_changes "
        "WHERE pool_id = (SELECT MAX(pool_id) FROM pool_changes) "
        "ORDER BY direction, ticker"
    ).fetchdf()


# ---------- Candidate Pool & Investment Theses ----------

def upsert_candidate(
    conn: duckdb.DuckDBPyConnection,
    candidate: dict,
    updated_at: datetime | None = None,
) -> None:
    """Insert or update a discovered company in candidate_pool."""
    ts = updated_at or datetime.now(UTC).replace(tzinfo=None)
    customers = candidate.get("key_customers_json")
    if isinstance(customers, list):
        customers = json.dumps(customers, ensure_ascii=False)
    elif customers is None:
        customers = "[]"

    conn.execute(
        """
        INSERT OR REPLACE INTO candidate_pool (
            ticker, name, leg, layer, source, discovered_at, status,
            pure_play_est, supply_role, key_customers_json, notes, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            candidate["ticker"],
            candidate.get("name", candidate["ticker"]),
            candidate.get("leg", "US"),
            candidate.get("layer"),
            candidate.get("source", "manual"),
            candidate.get("discovered_at", date.today()),
            candidate.get("status", "discovered"),
            candidate.get("pure_play_est"),
            candidate.get("supply_role", ""),
            customers,
            candidate.get("notes", ""),
            ts,
        ],
    )
    conn.commit()


def query_candidates(
    conn: duckdb.DuckDBPyConnection,
    status: str | None = None,
    leg: str | None = None,
) -> pd.DataFrame:
    """Return candidates filtered by status and/or leg."""
    clauses = []
    params = []
    if status is not None:
        clauses.append("status = ?")
        params.append(status)
    if leg is not None:
        clauses.append("leg = ?")
        params.append(leg)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return conn.execute(
        f"SELECT * FROM candidate_pool {where} ORDER BY updated_at DESC, ticker",
        params,
    ).fetchdf()


def update_candidate_status(
    conn: duckdb.DuckDBPyConnection,
    ticker: str,
    status: str,
    notes: str | None = None,
    updated_at: datetime | None = None,
) -> None:
    """Update status and optional notes for a candidate."""
    ts = updated_at or datetime.now(UTC).replace(tzinfo=None)
    if notes is not None:
        conn.execute(
            "UPDATE candidate_pool SET status = ?, notes = ?, updated_at = ? WHERE ticker = ?",
            [status, notes, ts, ticker],
        )
    else:
        conn.execute(
            "UPDATE candidate_pool SET status = ?, updated_at = ? WHERE ticker = ?",
            [status, ts, ticker],
        )
    conn.commit()


def upsert_thesis(
    conn: duckdb.DuckDBPyConnection,
    thesis: dict,
    created_at: datetime | None = None,
) -> None:
    """Insert or update an investment thesis / opportunity card."""
    ts = created_at or datetime.now(UTC).replace(tzinfo=None)
    catalysts = thesis.get("catalysts_json")
    if isinstance(catalysts, list):
        catalysts = json.dumps(catalysts, ensure_ascii=False)
    elif catalysts is None:
        catalysts = "[]"

    conn.execute(
        """
        INSERT OR REPLACE INTO investment_theses (
            thesis_id, ticker, as_of_date, thesis_type, title,
            bull_case, bear_case, synthesis, valuation_entry_zone,
            invalidation_criteria, confidence_score, catalysts_json,
            model, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            thesis["thesis_id"],
            thesis["ticker"],
            thesis["as_of_date"],
            thesis.get("thesis_type", "long_opportunity"),
            thesis.get("title", f"Thesis for {thesis['ticker']}"),
            thesis.get("bull_case", ""),
            thesis.get("bear_case", ""),
            thesis.get("synthesis", ""),
            thesis.get("valuation_entry_zone", ""),
            thesis.get("invalidation_criteria", ""),
            thesis.get("confidence_score", 50.0),
            catalysts,
            thesis.get("model", "gemini-3.8-flash"),
            ts,
        ],
    )
    conn.commit()


def query_theses(
    conn: duckdb.DuckDBPyConnection,
    ticker: str | None = None,
    thesis_type: str | None = None,
    limit: int = 50,
) -> pd.DataFrame:
    """Query stored investment theses."""
    clauses = []
    params = []
    if ticker is not None:
        clauses.append("ticker = ?")
        params.append(ticker)
    if thesis_type is not None:
        clauses.append("thesis_type = ?")
        params.append(thesis_type)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return conn.execute(
        f"SELECT * FROM investment_theses {where} ORDER BY created_at DESC LIMIT {int(limit)}",
        params,
    ).fetchdf()


def _json_dumps_safe(val: object) -> str:
    """Safely convert a dict, list, or Pydantic model to a JSON string."""
    if val is None:
        return "[]"
    if hasattr(val, "model_dump"):
        return json.dumps(val.model_dump(), ensure_ascii=False)
    if isinstance(val, (list, dict)):
        return json.dumps(val, ensure_ascii=False)
    if isinstance(val, str):
        return val
    return json.dumps(val, ensure_ascii=False)


# Callers may pass either the storage column name (``*_json``) or the Pydantic
# field name used by ``InvestmentDecisionRecord.model_dump()``.
_IDR_JSON_FIELD_ALIASES = {
    "observed_metrics_json": "observed_metrics",
    "policy_rules_json": "policy_rules_evaluated",
    "bull_arguments_json": "bull_arguments",
    "bear_arguments_json": "bear_arguments",
    "catalysts_json": "catalysts",
    "citations_json": "citations",
}

# Lifecycle order of ``OpportunityStage`` (arf/agent/schemas.py). Kept as plain
# strings so this storage module does not depend on the agent package.
_OPPORTUNITY_STAGE_ORDER = (
    "discovered",
    "qualified",
    "under_review",
    "thesis_formulated",
    "committee_pending",
    "active_watch",
    "harvested",
    "invalidated",
)


def _stage_rank(stage: str) -> int:
    try:
        return _OPPORTUNITY_STAGE_ORDER.index(str(stage))
    except ValueError:
        return -1


def _fetch_row_dict(
    conn: duckdb.DuckDBPyConnection, sql: str, params: list[object]
) -> dict[str, object] | None:
    """Run a query and return its first row as a column→value dict."""
    cursor = conn.execute(sql, params)
    row = cursor.fetchone()
    if row is None:
        return None
    return dict(zip((desc[0] for desc in cursor.description), row, strict=True))


def upsert_idr(
    conn: duckdb.DuckDBPyConnection,
    idr: dict,
    created_at: datetime | None = None,
    auto_update_state: bool = True,
) -> None:
    """Insert or update a 5-step Investment Decision Record (IDR).

    Updates merge onto the stored row: columns absent from ``idr`` keep their
    stored value instead of being reset to a schema default. A partial write
    (recording ``human_pm_decision``, say) therefore cannot erase the
    machine-generated gate verdict, recommended action, or invalidation
    criteria of the record it is annotating.
    """
    ts = created_at or datetime.now(UTC).replace(tzinfo=None)
    idr_id = idr["idr_id"]

    provided: dict[str, object] = dict(idr)
    for canonical, alias in _IDR_JSON_FIELD_ALIASES.items():
        if canonical not in provided and alias in provided:
            provided[canonical] = provided[alias]

    existing = _fetch_row_dict(
        conn,
        "SELECT * FROM investment_decision_records WHERE idr_id = ?",
        [idr_id],
    )

    def pick(key: str, default: object = None) -> object:
        if key in provided:
            return provided[key]
        if existing is not None and existing.get(key) is not None:
            return existing[key]
        return default

    ticker = pick("ticker")
    if not ticker:
        raise ValueError("upsert_idr requires 'ticker'")
    as_of_date = pick("as_of_date")
    if as_of_date is None:
        raise ValueError("upsert_idr requires 'as_of_date'")

    values = [
        ticker,
        pick("name", ticker),
        as_of_date,
        str(pick("stage", "thesis_formulated")),
        pick("trigger_type", "radar_scan"),
        pick("trigger_summary", ""),
        _json_dumps_safe(pick("observed_metrics_json")),
        pick("leg", "US"),
        pick("layer", "L3"),
        float(pick("cost_of_equity", 0.10)),
        _json_dumps_safe(pick("policy_rules_json")),
        _json_dumps_safe(pick("bull_arguments_json")),
        _json_dumps_safe(pick("bear_arguments_json")),
        pick("deliberation_synthesis", ""),
        str(pick("gate_verdict", "PASSED")),
        pick("gate_details", ""),
        bool(pick("froth_flag", False)),
        bool(pick("hurdle_met", True)),
        str(pick("recommended_action", "MONITOR")),
        pick("valuation_entry_zone", ""),
        pick("invalidation_criteria", ""),
        float(pick("confidence_score", 50.0)),
        _json_dumps_safe(pick("catalysts_json")),
        _json_dumps_safe(pick("citations_json")),
        pick("human_pm_decision"),
        pick("human_pm_notes"),
        pick("model", "gemini-3.8-flash"),
    ]
    # created_at records when the IDR was first written; an annotation must not
    # rewrite it. An explicit created_at argument still wins (used by tests).
    created_ts = created_at or (existing["created_at"] if existing is not None else ts)

    if existing is None:
        conn.execute(
            """
            INSERT INTO investment_decision_records (
                idr_id, ticker, name, as_of_date, stage,
                trigger_type, trigger_summary, observed_metrics_json,
                leg, layer, cost_of_equity, policy_rules_json,
                bull_arguments_json, bear_arguments_json, deliberation_synthesis,
                gate_verdict, gate_details, froth_flag, hurdle_met,
                recommended_action, valuation_entry_zone, invalidation_criteria,
                confidence_score, catalysts_json, citations_json,
                human_pm_decision, human_pm_notes, model, created_at
            ) VALUES (
                ?, ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?
            )
            """,
            [idr_id, *values, created_ts],
        )
    else:
        conn.execute(
            """
            UPDATE investment_decision_records SET
                ticker = ?, name = ?, as_of_date = ?, stage = ?,
                trigger_type = ?, trigger_summary = ?, observed_metrics_json = ?,
                leg = ?, layer = ?, cost_of_equity = ?, policy_rules_json = ?,
                bull_arguments_json = ?, bear_arguments_json = ?,
                deliberation_synthesis = ?,
                gate_verdict = ?, gate_details = ?, froth_flag = ?, hurdle_met = ?,
                recommended_action = ?, valuation_entry_zone = ?,
                invalidation_criteria = ?,
                confidence_score = ?, catalysts_json = ?, citations_json = ?,
                human_pm_decision = ?, human_pm_notes = ?, model = ?, created_at = ?
            WHERE idr_id = ?
            """,
            [*values, created_ts, idr_id],
        )

    if auto_update_state:
        desired_stage = str(pick("stage", "thesis_formulated"))
        state = _fetch_row_dict(
            conn,
            "SELECT current_stage FROM opportunity_states WHERE ticker = ?",
            [ticker],
        )
        if state is not None and _stage_rank(desired_stage) < _stage_rank(
            str(state["current_stage"])
        ):
            # Every freshly compiled IDR is stamped thesis_formulated, but a
            # new card must not roll back a lifecycle the PM already advanced
            # or closed (e.g. harvested/invalidated). Keep the current stage
            # while still refreshing the link and metadata below.
            desired_stage = str(state["current_stage"])

        update_opportunity_stage(
            conn,
            ticker=str(ticker),
            stage=desired_stage,
            name=str(pick("name", ticker)),
            leg=str(pick("leg", "US")),
            layer=str(pick("layer", "L3")),
            latest_idr_id=idr_id,
            valuation_entry_zone=str(pick("valuation_entry_zone", "")),
            invalidation_criteria=str(pick("invalidation_criteria", "")),
            updated_at=ts,
        )
    conn.commit()


def query_idrs(
    conn: duckdb.DuckDBPyConnection,
    ticker: str | None = None,
    stage: str | None = None,
    limit: int = 50,
) -> pd.DataFrame:
    """Query stored Investment Decision Records."""
    clauses = []
    params = []
    if ticker is not None:
        clauses.append("ticker = ?")
        params.append(ticker)
    if stage is not None:
        clauses.append("stage = ?")
        params.append(stage)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return conn.execute(
        f"SELECT * FROM investment_decision_records {where} ORDER BY created_at DESC LIMIT {int(limit)}",
        params,
    ).fetchdf()


def update_opportunity_stage(
    conn: duckdb.DuckDBPyConnection,
    ticker: str,
    stage: str,
    name: str = "",
    leg: str = "",
    layer: str = "",
    latest_idr_id: str | None = None,
    valuation_entry_zone: str = "",
    invalidation_criteria: str = "",
    notes: str = "",
    updated_at: datetime | None = None,
) -> None:
    """Update or insert the current lifecycle stage for an Opportunity Alpha."""
    ts = updated_at or datetime.now(UTC).replace(tzinfo=None)
    existing = conn.execute(
        "SELECT name, leg, layer, latest_idr_id, valuation_entry_zone, invalidation_criteria, notes "
        "FROM opportunity_states WHERE ticker = ?",
        [ticker],
    ).fetchone()

    if existing:
        ex_name, ex_leg, ex_layer, ex_idr, ex_zone, ex_inval, ex_notes = existing
        final_name = name or ex_name or ticker
        final_leg = leg or ex_leg or "US"
        final_layer = layer or ex_layer or "L3"
        final_idr = latest_idr_id or ex_idr
        final_zone = valuation_entry_zone or ex_zone or ""
        final_inval = invalidation_criteria or ex_inval or ""
        final_notes = notes or ex_notes or ""

        conn.execute(
            """
            UPDATE opportunity_states SET
                current_stage = ?,
                latest_idr_id = ?,
                name = ?,
                leg = ?,
                layer = ?,
                valuation_entry_zone = ?,
                invalidation_criteria = ?,
                notes = ?,
                updated_at = ?
            WHERE ticker = ?
            """,
            [
                stage,
                final_idr,
                final_name,
                final_leg,
                final_layer,
                final_zone,
                final_inval,
                final_notes,
                ts,
                ticker,
            ],
        )
    else:
        conn.execute(
            """
            INSERT INTO opportunity_states (
                ticker, name, leg, layer, current_stage,
                latest_idr_id, valuation_entry_zone, invalidation_criteria,
                notes, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ticker,
                name or ticker,
                leg or "US",
                layer or "L3",
                stage,
                latest_idr_id,
                valuation_entry_zone,
                invalidation_criteria,
                notes,
                ts,
            ],
        )
    conn.commit()


def query_opportunity_states(
    conn: duckdb.DuckDBPyConnection,
    stage: str | None = None,
) -> pd.DataFrame:
    """Query current opportunity alpha lifecycle states."""
    if stage is not None:
        return conn.execute(
            "SELECT * FROM opportunity_states WHERE current_stage = ? ORDER BY updated_at DESC",
            [stage],
        ).fetchdf()
    return conn.execute("SELECT * FROM opportunity_states ORDER BY updated_at DESC").fetchdf()


