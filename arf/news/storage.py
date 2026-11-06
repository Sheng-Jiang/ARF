"""DuckDB persistence and query operations for financial press signals."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

import duckdb
import pandas as pd

from arf.news.schema import NewsArticle

_SCHEMA_NEWS_SIGNALS = """
CREATE TABLE IF NOT EXISTS news_signals (
    article_id       TEXT PRIMARY KEY,
    source           TEXT NOT NULL,
    title            TEXT NOT NULL,
    summary          TEXT,
    url              TEXT NOT NULL,
    published_at     TIMESTAMP WITH TIME ZONE NOT NULL,
    fetched_at       TIMESTAMP WITH TIME ZONE NOT NULL,
    tickers          TEXT,        -- JSON array e.g. ["NVDA", "TSM"]
    layers           TEXT,        -- JSON array e.g. ["L1", "L2"]
    themes           TEXT,        -- JSON array e.g. ["CapEx_Infrastructure"]
    relevance_score  DOUBLE,
    sentiment_label  TEXT,
    sentiment_score  DOUBLE
);

CREATE INDEX IF NOT EXISTS idx_news_published ON news_signals(published_at DESC);
"""


def init_news_table(conn: duckdb.DuckDBPyConnection) -> None:
    """Ensure the news_signals table exists."""
    conn.execute(_SCHEMA_NEWS_SIGNALS)


def upsert_news_articles(
    conn: duckdb.DuckDBPyConnection,
    articles: list[NewsArticle],
) -> int:
    """Upsert a list of NewsArticle objects into DuckDB.
    
    Returns:
        Number of articles inserted/updated.
    """
    if not articles:
        return 0

    init_news_table(conn)

    rows = []
    for a in articles:
        rows.append((
            a.article_id,
            a.source,
            a.title,
            a.summary,
            a.url,
            a.published_at,
            a.fetched_at,
            json.dumps(a.tickers),
            json.dumps(a.layers),
            json.dumps(a.themes),
            float(a.relevance_score),
            a.sentiment_label,
            float(a.sentiment_score),
        ))

    insert_sql = """
    INSERT OR REPLACE INTO news_signals (
        article_id, source, title, summary, url, published_at, fetched_at,
        tickers, layers, themes, relevance_score, sentiment_label, sentiment_score
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    conn.executemany(insert_sql, rows)
    return len(rows)


def _escape_like(term: str) -> str:
    """Escape LIKE metacharacters so a ticker search is a literal match."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def query_news_signals(
    conn: duckdb.DuckDBPyConnection,
    ticker: str | None = None,
    layer: str | None = None,
    theme: str | None = None,
    source: str | None = None,
    days: int = 14,
    min_relevance: float = 0.20,
    limit: int = 50,
    as_of: date | None = None,
) -> pd.DataFrame:
    """Query recent news signals with multi-dimensional filtering.

    When *as_of* is given the window is point-in-time: it ends at the close of
    that date rather than at "now", so a historical snapshot's briefing never
    cites articles published after it.
    """
    init_news_table(conn)

    upper = (
        datetime.combine(as_of + timedelta(days=1), time.min, tzinfo=UTC)
        if as_of is not None
        else datetime.now(UTC)
    )
    cutoff = upper - timedelta(days=days)
    conditions = ["published_at >= ?", "published_at <= ?", "relevance_score >= ?"]
    params: list[Any] = [cutoff, upper, min_relevance]

    if ticker:
        # Allow partial symbols: "688256" and "0700" should match the stored
        # "688256.SH" / "0700.HK" JSON values, not only the exact full code.
        conditions.append("tickers LIKE ? ESCAPE '\\'")
        params.append(f'%"{_escape_like(ticker.strip().upper())}%')

    if layer:
        conditions.append("layers LIKE ?")
        params.append(f'%"{layer.strip().upper()}"%')

    if theme:
        conditions.append("themes LIKE ?")
        params.append(f'%"{theme.strip()}"%')

    if source:
        conditions.append("source = ?")
        params.append(source.strip())

    where_clause = " AND ".join(conditions)
    sql = f"""
    SELECT
        article_id,
        source,
        title,
        summary,
        url,
        published_at,
        tickers,
        layers,
        themes,
        relevance_score,
        sentiment_label,
        sentiment_score
    FROM news_signals
    WHERE {where_clause}
    ORDER BY published_at DESC
    LIMIT {int(limit)}
    """
    return conn.execute(sql, params).df()


def query_news_summary_by_layer(
    conn: duckdb.DuckDBPyConnection,
    days: int = 14,
) -> pd.DataFrame:
    """Aggregate article volume and average sentiment per stack layer."""
    init_news_table(conn)
    cutoff = datetime.now(UTC) - timedelta(days=days)

    sql = """
    SELECT
        layers,
        sentiment_label,
        sentiment_score,
        relevance_score
    FROM news_signals
    WHERE published_at >= ? AND relevance_score >= 0.25
    """
    df = conn.execute(sql, [cutoff]).df()
    if df.empty:
        return pd.DataFrame(columns=["layer", "article_count", "avg_sentiment"])

    # Explode layers JSON array
    expanded = []
    for _, row in df.iterrows():
        try:
            layer_list = json.loads(row["layers"]) if isinstance(row["layers"], str) else []
            for l_code in layer_list:
                expanded.append({
                    "layer": l_code,
                    "sentiment_score": row["sentiment_score"],
                })
        except Exception:
            continue

    if not expanded:
        return pd.DataFrame(columns=["layer", "article_count", "avg_sentiment"])

    exp_df = pd.DataFrame(expanded)
    agg = exp_df.groupby("layer").agg(
        article_count=("sentiment_score", "count"),
        avg_sentiment=("sentiment_score", "mean"),
    ).reset_index().sort_values("layer")

    return agg
