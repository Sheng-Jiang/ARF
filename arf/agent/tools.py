"""Deterministic financial and analytical tools callable by the ARF Agent."""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from arf.db import init_db

log = logging.getLogger(__name__)


def _connect_db(db_path: Path = Path("data/arf.db")) -> duckdb.DuckDBPyConnection:
    """Return a connection to DuckDB for query tools.

    Connects using a configuration compatible with any existing open connection
    in the same process (such as Streamlit's cached connection in webapp/data.py),
    avoiding DuckDB's "different configuration than existing connections" error.
    Read-only safety is enforced by ``query_quant_database``'s SELECT-only validation.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        conn = duckdb.connect(str(db_path))
    except duckdb.ConnectionException:
        conn = duckdb.connect(str(db_path), read_only=True)

    try:
        conn.execute("SELECT 1 FROM snapshots LIMIT 0")
    except duckdb.CatalogException:
        conn.close()
        return init_db(db_path)
    return conn


def get_stock_quant_profile(
    ticker: str,
    as_of: date,
    db_path: Path = Path("data/arf.db"),
) -> dict[str, Any] | None:
    """Retrieve complete fundamental, valuation stretch, and technical metrics for a stock.
    
    Joins snapshots and technical_metrics in DuckDB for the given as_of date.
    """
    conn = _connect_db(db_path)
    try:
        query = """
        SELECT 
            s.ticker, s.name, s.leg, s.layer, s.as_of_date,
            s.price, s.market_cap_usd, s.arf, s.decile,
            s.e_score, s.v_score, s.froth_flag,
            s.roe, s.forward_pe, s.ps_ratio, s.gross_margin,
            s.revenue_yoy_growth, s.implied_growth, s.implied_growth_gap,
            t.technical_score, t.chip_profit_ratio, t.chip_avg_cost,
            t.ma_bullish_alignment AS ma_bullish, t.rsi
        FROM snapshots s
        LEFT JOIN technical_metrics t 
            ON s.ticker = t.ticker AND s.as_of_date = t.as_of_date
        WHERE s.ticker = ? AND s.as_of_date = ?
        """
        df = conn.execute(query, [ticker, as_of]).fetchdf()
        if df.empty:
            # Fallback: check most recent snapshot if exact as_of date is missing
            fallback_query = """
            SELECT 
                s.ticker, s.name, s.leg, s.layer, s.as_of_date,
                s.price, s.market_cap_usd, s.arf, s.decile,
                s.e_score, s.v_score, s.froth_flag,
                s.roe, s.forward_pe, s.ps_ratio, s.gross_margin,
                s.revenue_yoy_growth, s.implied_growth, s.implied_growth_gap,
                t.technical_score, t.chip_profit_ratio, t.chip_avg_cost,
                t.ma_bullish_alignment AS ma_bullish, t.rsi
            FROM snapshots s
            LEFT JOIN technical_metrics t 
                ON s.ticker = t.ticker AND s.as_of_date = t.as_of_date
            WHERE s.ticker = ?
            ORDER BY s.as_of_date DESC LIMIT 1
            """
            df = conn.execute(fallback_query, [ticker]).fetchdf()
            if df.empty:
                return None

        row = df.iloc[0].to_dict()
        # Clean NaNs to None and dates to strings
        for k, v in row.items():
            if pd.isna(v):
                row[k] = None
        if "as_of_date" in row and row["as_of_date"] is not None:
            row["as_of_date"] = str(row["as_of_date"])[:10]
        return row
    finally:
        conn.close()


def query_quant_database(
    sql_query: str,
    db_path: Path = Path("data/arf.db"),
    max_rows: int = 50,
) -> list[dict[str, Any]]:
    """Execute a safe, read-only SQL query against DuckDB and return rows as dicts."""
    clean_sql = sql_query.strip().rstrip(";")
    if not clean_sql.upper().startswith("SELECT"):
        raise ValueError("Only SELECT queries are permitted.")

    # Guard against mutations
    disallowed = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE"]
    upper_tokens = clean_sql.upper().split()
    for token in disallowed:
        if token in upper_tokens:
            raise ValueError(f"Disallowed DDL/DML keyword in query: {token}")

    conn = _connect_db(db_path)
    try:
        df = conn.execute(clean_sql).fetchdf()
        if max_rows and len(df) > max_rows:
            df = df.head(max_rows)
        return df.where(pd.notna(df), None).to_dict(orient="records")
    finally:
        conn.close()


def search_value_chain_layer(
    layer: str,
    leg: str | None = None,
    db_path: Path = Path("data/arf.db"),
) -> list[dict[str, Any]]:
    """Retrieve companies belonging to a specific AI value-chain layer (L1..L5)."""
    conn = _connect_db(db_path)
    try:
        clauses = ["layer = ?"]
        params: list[Any] = [layer.upper()]
        if leg:
            clauses.append("leg = ?")
            params.append(leg.upper())

        query = f"""
        SELECT ticker, name, leg, layer, arf, decile, e_score, v_score, roe, ps_ratio, market_cap_usd
        FROM snapshots
        WHERE {' AND '.join(clauses)}
          AND as_of_date = (SELECT MAX(as_of_date) FROM snapshots)
        ORDER BY arf DESC
        """
        df = conn.execute(query, params).fetchdf()
        return df.where(pd.notna(df), None).to_dict(orient="records")
    finally:
        conn.close()


def fetch_external_candidate(
    ticker: str,
    leg: str = "US",
    as_of: date | None = None,
) -> dict[str, Any] | None:
    """Fetch external fundamental data for a newly discovered ticker outside the core universe."""
    target_date = as_of or date.today()
    from arf.config import UniverseEntry
    entry = UniverseEntry(
        ticker=ticker,
        name=ticker,
        leg=leg,
        layer="L3",
        pure_play_pct=50.0,
        primary_exchange="",
        policy_premium=False,
    )
    try:
        if leg.upper() == "US":
            from arf.fetchers.us import fetch_us
            sd = fetch_us(entry, target_date)
        else:
            from arf.fetchers.china import fetch_china
            sd = fetch_china(entry, target_date)

        return {
            "ticker": sd.ticker,
            "name": sd.name,
            "leg": sd.leg,
            "price": sd.price,
            "market_cap_usd": sd.market_cap_usd,
            "revenue_ttm": sd.revenue_ttm,
            "revenue_yoy_growth": sd.revenue_yoy_growth,
            "gross_margin": sd.gross_margin,
            "roe": sd.roe,
            "forward_pe": sd.forward_pe,
            "ps_ratio": sd.ps_ratio,
        }
    except Exception as exc:
        log.warning("External fetch failed for candidate %s: %s", ticker, exc)
        return None
