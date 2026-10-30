"""Storage abstraction: DATA_SOURCE=local reads data/arf.db, DATA_SOURCE=gcs downloads from GCS."""
import os
import tempfile
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

DATA_SOURCE = os.getenv("DATA_SOURCE", "local")
LOCAL_DB_PATH = Path(os.getenv("LOCAL_DB_PATH", "data/arf.db"))
GCS_BUCKET = os.getenv("GCS_BUCKET", "")
GCS_DB_OBJECT = os.getenv("GCS_DB_OBJECT", "arf.db")


def _ensure_schema(path: Path) -> None:
    """Apply ARF DB schema migrations (idempotent) before opening read-only."""
    from arf.db import init_db  # local import to avoid Streamlit reload churn
    conn = init_db(path)
    conn.close()


_ACTIVE_DB_PATH: Path | None = None


@st.cache_resource(ttl=3600)
def _open_conn() -> duckdb.DuckDBPyConnection:
    global _ACTIVE_DB_PATH
    if DATA_SOURCE == "gcs":
        from google.cloud import storage  # type: ignore[import]
        client = storage.Client()
        tmp_path = Path(tempfile.mkdtemp()) / "arf.db"
        client.bucket(GCS_BUCKET).blob(GCS_DB_OBJECT).download_to_filename(str(tmp_path))
        _ensure_schema(tmp_path)
        _ACTIVE_DB_PATH = tmp_path
        return duckdb.connect(str(tmp_path), read_only=False)
    _ensure_schema(LOCAL_DB_PATH)
    _ACTIVE_DB_PATH = LOCAL_DB_PATH
    return duckdb.connect(str(LOCAL_DB_PATH), read_only=False)


def get_db_path() -> Path:
    """Get the active database file path (resolves temp path in GCS mode)."""
    if _ACTIVE_DB_PATH is None:
        _open_conn()
    return _ACTIVE_DB_PATH


def list_dates() -> list[date]:
    rows = _open_conn().execute(
        "SELECT DISTINCT as_of_date FROM snapshots ORDER BY as_of_date DESC"
    ).fetchall()
    return [r[0] for r in rows]


def load_snapshot(as_of: date) -> pd.DataFrame:
    return _open_conn().execute(
        "SELECT * FROM snapshots WHERE as_of_date = ?", [as_of]
    ).fetchdf()


def load_thermometer_series() -> pd.DataFrame:
    """Weekly bubble-thermometer metrics, core board only.

    Mirrors arf.db.query_thermometer_series — newcomers rank inside their own
    5-name cohort, so including them adds a phantom D1 per leg every week.
    """
    from arf.db import CORE_ONLY

    return _open_conn().execute(f"""
        SELECT
            as_of_date,
            leg,
            COUNT(*) FILTER (WHERE arf >= 90)       AS count_arf_gte_90,
            COUNT(*) FILTER (WHERE froth_flag = TRUE) AS count_froth,
            -- Absolute froth count: ROE < WACC (10% US, 12% China) AND P/S > 25
            COUNT(*) FILTER (
                WHERE (leg = 'US' AND roe < 0.10 AND ps_ratio > 25) OR
                      (leg = 'China' AND roe < 0.12 AND ps_ratio > 25)
            ) AS count_absolute_froth,
            MEDIAN(ev_sales_5yr_percentile)          AS median_ev_sales_pct,
            MEDIAN(implied_growth_gap) * 100         AS median_growth_gap_pct,
            MEDIAN(arf)                              AS median_arf,
            COUNT(*)                                 AS total
        FROM snapshots
        WHERE {CORE_ONLY}
        GROUP BY as_of_date, leg
        ORDER BY as_of_date, leg
    """).fetchdf()


def refresh_data() -> None:
    """Drop the cached connection so the next query re-reads the source.

    In GCS mode the active path is a downloaded temp file; it must be cleared
    too, otherwise `get_db_path()` keeps handing out the stale download.
    """
    global _ACTIVE_DB_PATH
    _open_conn.clear()
    _ACTIVE_DB_PATH = None


def get_conn() -> duckdb.DuckDBPyConnection:
    """The process-wide connection.

    Pages that need to hand data to another component (the CIO replay engine)
    must use this rather than opening a second connection: DuckDB refuses two
    connections to the same file with different configurations.
    """
    return _open_conn()


def load_snapshot_history() -> pd.DataFrame:
    """Every snapshot revision, for point-in-time filtering by the ARF model.

    The `snapshots` view intentionally hides `revision`/`fetched_at`; a
    backtest needs them to avoid reading a correction made after its date.
    """
    try:
        return _open_conn().execute(
            """
            SELECT ticker, as_of_date, revision, fetched_at, leg, arf, decile,
                   froth_flag, e_score, v_score, implied_growth_gap, roe, ps_ratio
            FROM snapshot_revisions
            """
        ).fetchdf()
    except duckdb.Error:
        return _open_conn().execute(
            """
            SELECT ticker, as_of_date, NULL::INTEGER AS revision,
                   NULL::TIMESTAMP AS fetched_at, leg, arf, decile, froth_flag,
                   e_score, v_score, implied_growth_gap, roe, ps_ratio
            FROM snapshots
            """
        ).fetchdf()


def load_price_history(
    tickers: list[str] | tuple[str, ...], start: date, end: date
) -> dict[str, pd.DataFrame]:
    """Daily OHLCV for *tickers* in [start, end], keyed by ticker.

    One query for the whole universe: a replay asks for a rolling window on
    every session, and per-session queries would dominate its runtime.
    """
    if not tickers:
        return {}
    placeholders = ",".join("?" for _ in tickers)
    frame = _open_conn().execute(
        f"""
        SELECT ticker, date, open, high, low, close, volume
        FROM daily_prices
        WHERE ticker IN ({placeholders}) AND date >= ? AND date <= ?
        ORDER BY ticker, date
        """,
        [*tickers, start, end],
    ).fetchdf()
    return {ticker: group.reset_index(drop=True) for ticker, group in frame.groupby("ticker")}


def load_regime_stats(as_of: date) -> dict[str, float | int | date | None]:
    """Bubble-thermometer stats for the latest core-cohort snapshot <= as_of."""
    from arf.db import CORE_ONLY

    row = _open_conn().execute(
        f"""
        SELECT COUNT(*)                                   AS total_scored,
               COUNT(*) FILTER (WHERE froth_flag)         AS froth_count,
               MEDIAN(implied_growth_gap)                 AS median_gap,
               AVG(arf)                                   AS avg_arf,
               MAX(as_of_date)                            AS snapshot_date
        FROM snapshots
        WHERE as_of_date = (
                  SELECT MAX(as_of_date) FROM snapshots
                  WHERE as_of_date <= ? AND arf IS NOT NULL
              )
          AND {CORE_ONLY}
        """,
        [as_of],
    ).fetchone()
    return {
        "total_scored": int(row[0] or 0),
        "froth_count": int(row[1] or 0),
        "median_gap": float(row[2]) if row[2] is not None else None,
        "avg_arf": float(row[3]) if row[3] is not None else None,
        "snapshot_date": row[4],
    }


def load_data_freshness() -> dict[str, object]:
    """Latest snapshot per leg and latest pipeline run per trigger source."""
    conn = _open_conn()
    legs = {
        leg: latest
        for leg, latest in conn.execute(
            "SELECT leg, MAX(as_of_date) FROM snapshots GROUP BY leg ORDER BY leg"
        ).fetchall()
    }
    runs = {
        source or "unknown": (started, status)
        for source, started, status in conn.execute(
            """
            SELECT trigger_source, MAX(started_at), arg_max(status, started_at)
            FROM runs GROUP BY trigger_source
            """
        ).fetchall()
    }
    return {"legs": legs, "runs": runs}


def latest_scored_date(as_of: date, leg: str = "US") -> date | None:
    """The newest snapshot on or before *as_of* whose scores are computed.

    A partially written snapshot (prices/fundamentals fetched, scoring not yet
    run) has rows but NULL ARF; replaying it would silently produce a flat,
    all-neutral book. Filter by *leg* because the two legs complete scoring at
    different times — a China-only score is useless to a US replay.
    """
    row = _open_conn().execute(
        """
        SELECT MAX(as_of_date) FROM snapshots
        WHERE as_of_date <= ? AND leg = ? AND arf IS NOT NULL
        """,
        [as_of, leg],
    ).fetchone()
    return row[0] if row else None


def db_signature() -> str:
    """A cheap fingerprint used as part of replay cache keys."""
    row = _open_conn().execute(
        "SELECT MAX(as_of_date), COUNT(*) FROM snapshots"
    ).fetchone()
    return f"{row[0]}:{row[1]}"


def load_runs(limit: int = 20) -> pd.DataFrame:
    return _open_conn().execute(
        "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?", [limit]
    ).fetchdf()


def load_latest_run() -> pd.DataFrame:
    return _open_conn().execute(
        "SELECT * FROM runs ORDER BY started_at DESC LIMIT 1"
    ).fetchdf()


def load_fetch_outcomes(run_id: str) -> pd.DataFrame:
    return _open_conn().execute(
        "SELECT * FROM fetch_outcomes WHERE run_id = ? ORDER BY ticker", [run_id]
    ).fetchdf()


def load_gemini_summaries(as_of: date, cohort_key: str) -> pd.DataFrame:
    return _open_conn().execute(
        "SELECT * FROM gemini_summaries WHERE as_of_date = ? AND cohort_key = ? "
        "ORDER BY ticker",
        [as_of, cohort_key],
    ).fetchdf()


def load_research_reports(as_of: date) -> pd.DataFrame:
    return _open_conn().execute(
        "SELECT * FROM research_reports WHERE as_of_date = ? "
        "ORDER BY ticker, report_date DESC",
        [as_of],
    ).fetchdf()


def load_research_synthesis(as_of: date) -> pd.DataFrame:
    return _open_conn().execute(
        "SELECT * FROM research_synthesis WHERE as_of_date = ?", [as_of]
    ).fetchdf()


def list_value_chain_dates(limit: int = 2) -> list[date]:
    rows = _open_conn().execute(
        "SELECT DISTINCT as_of_date FROM value_chain_snapshot ORDER BY as_of_date DESC LIMIT ?",
        [limit],
    ).fetchall()
    return [r[0] for r in rows]


def load_value_chain(as_of: date | None = None) -> pd.DataFrame:
    """Load the 双价值链 layer/leg snapshot for a date, or the latest one."""
    if as_of is not None:
        return _open_conn().execute(
            "SELECT * FROM value_chain_snapshot WHERE as_of_date = ? ORDER BY leg, layer",
            [as_of],
        ).fetchdf()
    return _open_conn().execute(
        "SELECT * FROM value_chain_snapshot "
        "WHERE as_of_date = (SELECT MAX(as_of_date) FROM value_chain_snapshot) "
        "ORDER BY leg, layer"
    ).fetchdf()


UNIVERSE_PATH = Path(os.getenv("UNIVERSE_PATH", "config/universe.yaml"))

_MEMBERSHIP_COLUMNS = [
    "pool_id", "ticker", "leg", "cohort", "listed_at", "added_at", "reason",
]


def _config_pool_ids() -> list[str]:
    """Pool ids assigned in universe.yaml (usually just the active quarter)."""
    try:
        from arf.config import load_universe
        return sorted({e.pool for e in load_universe(UNIVERSE_PATH) if e.pool})
    except Exception:  # noqa: BLE001 — a missing/unreadable config is not fatal
        return []


def _config_pool_membership(pool_id: str) -> pd.DataFrame:
    """Roster for ``pool_id`` read straight from universe.yaml.

    pool_membership is only written by a full pipeline run, so a freshly
    deployed DB has none — but universe.yaml already carries the roster, which
    is what the page is actually asking for. Shape matches the table so the
    caller cannot tell the difference.
    """
    try:
        from arf.config import load_universe
        universe = load_universe(UNIVERSE_PATH)
    except Exception:  # noqa: BLE001
        return pd.DataFrame(columns=_MEMBERSHIP_COLUMNS)

    rows = [
        {
            "pool_id": pool_id,
            "ticker": e.ticker,
            "leg": e.leg,
            "cohort": e.cohort,
            "listed_at": e.listed_at,
            "added_at": pd.NaT,
            "reason": "universe.yaml",
        }
        for e in universe
        if e.pool == pool_id
    ]
    df = pd.DataFrame(rows, columns=_MEMBERSHIP_COLUMNS)
    return df.sort_values(["leg", "cohort", "ticker"]).reset_index(drop=True)


def list_pool_ids() -> list[str]:
    """Quarterly pool ids, newest first.

    Union of what the DB has archived and what universe.yaml currently
    assigns, so the active quarter is listed before its first pipeline run.
    """
    rows = _open_conn().execute(
        "SELECT DISTINCT pool_id FROM pool_membership"
    ).fetchall()
    return sorted({r[0] for r in rows} | set(_config_pool_ids()), reverse=True)


def pool_membership_is_archived(pool_id: str) -> bool:
    """True when ``pool_id`` has rows in pool_membership (vs. config-only)."""
    n = _open_conn().execute(
        "SELECT COUNT(*) FROM pool_membership WHERE pool_id = ?", [pool_id]
    ).fetchone()[0]
    return bool(n)


def load_pool_membership(pool_id: str | None = None) -> pd.DataFrame:
    """Members of a pool (or the latest one if omitted).

    Falls back to universe.yaml when the DB has nothing archived for the pool.
    """
    if pool_id is None:
        ids = list_pool_ids()
        if not ids:
            return pd.DataFrame(columns=_MEMBERSHIP_COLUMNS)
        pool_id = ids[0]
    df = _open_conn().execute(
        "SELECT * FROM pool_membership WHERE pool_id = ? ORDER BY leg, cohort, ticker",
        [pool_id],
    ).fetchdf()
    if df.empty:
        return _config_pool_membership(pool_id)
    return df


def load_pool_changes(pool_id: str | None = None) -> pd.DataFrame:
    """Rotation in/out changes for a pool (or the latest one if omitted)."""
    if pool_id is not None:
        return _open_conn().execute(
            "SELECT * FROM pool_changes WHERE pool_id = ? ORDER BY direction, ticker",
            [pool_id],
        ).fetchdf()
    return _open_conn().execute(
        "SELECT * FROM pool_changes "
        "WHERE pool_id = (SELECT MAX(pool_id) FROM pool_changes) "
        "ORDER BY direction, ticker"
    ).fetchdf()


def load_forecasts(as_of: date | None = None) -> pd.DataFrame:
    """Load the 4-layer predictive forecasts for a date, or the latest available."""
    conn = _open_conn()
    if as_of is not None:
        return conn.execute(
            "SELECT * FROM forecasts WHERE as_of_date = ? ORDER BY expected_beat_pct DESC NULLS LAST",
            [as_of],
        ).fetchdf()
    return conn.execute(
        "SELECT * FROM forecasts "
        "WHERE as_of_date = (SELECT MAX(as_of_date) FROM forecasts) "
        "ORDER BY expected_beat_pct DESC NULLS LAST"
    ).fetchdf()


def load_forecast_history(as_of: date | None = None) -> pd.DataFrame:
    """Every forecast revision visible at *as_of*, for the point-in-time replay.

    ``load_forecasts()`` returns a single date (the latest, or an exact one).
    The replay's forecast model filters ``as_of_date <= session`` itself, so
    handing it only the latest snapshot makes it abstain for every earlier
    session — the blend silently falls back to the lagging ARF model.
    """
    conn = _open_conn()
    if as_of is not None:
        return conn.execute(
            "SELECT * FROM forecasts WHERE as_of_date <= ? ORDER BY as_of_date, ticker",
            [as_of],
        ).fetchdf()
    return conn.execute(
        "SELECT * FROM forecasts ORDER BY as_of_date, ticker"
    ).fetchdf()


def load_supply_chain_links(supplier_ticker: str | None = None) -> pd.DataFrame:
    """Load verified supply chain linkages."""
    conn = _open_conn()
    if supplier_ticker:
        return conn.execute(
            "SELECT * FROM supply_chain_links WHERE supplier_ticker = ? ORDER BY revenue_share_pct DESC",
            [supplier_ticker.strip().upper()],
        ).fetchdf()
    return conn.execute(
        "SELECT * FROM supply_chain_links ORDER BY supplier_ticker, revenue_share_pct DESC"
    ).fetchdf()

