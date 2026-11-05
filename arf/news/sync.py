"""Synchronization pipeline for financial press news signals."""

from __future__ import annotations

import argparse
import logging
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from arf.db import init_db
from arf.news.classifier import NewsClassifier
from arf.news.feeds import fetch_all_active_feeds
from arf.news.schema import NewsArticle
from arf.news.storage import upsert_news_articles

log = logging.getLogger(__name__)


def sync_financial_press(
    conn: duckdb.DuckDBPyConnection | None = None,
    max_items_per_feed: int = 25,
    min_relevance: float = 0.20,
    db_path: Path = Path("data/arf.db"),
) -> int:
    """Fetch recent WSJ and NYT articles, classify them against the ARF universe,
    and persist relevant signals to DuckDB.

    Returns:
        Number of articles inserted/updated.
    """
    should_close = False
    if conn is None:
        conn = init_db(db_path)
        should_close = True

    try:
        log.info("Fetching articles from WSJ, NYT, and syndication feeds...")
        raw_items = fetch_all_active_feeds(max_items_per_feed=max_items_per_feed)
        log.info("Fetched %d raw candidate items across feeds.", len(raw_items))

        classifier = NewsClassifier()
        classified_articles: list[NewsArticle] = []
        now = datetime.now(UTC)

        for item in raw_items:
            res = classifier.classify(
                title=item["title"],
                summary=item.get("summary", ""),
                url=item.get("url", ""),
            )

            # Filter out noise that is not relevant to AI stack / financial markets
            if res["relevance_score"] < min_relevance:
                continue

            article = NewsArticle(
                article_id=item["article_id"],
                source=item["source"],
                title=item["title"],
                summary=item["summary"],
                url=item["url"],
                published_at=item["published_at"],
                fetched_at=now,
                tickers=res["tickers"],
                layers=res["layers"],
                themes=res["themes"],
                relevance_score=res["relevance_score"],
                sentiment_label=res["sentiment_label"],
                sentiment_score=res["sentiment_score"],
            )
            classified_articles.append(article)

        log.info(
            "Classified %d relevant articles (min_relevance=%.2f). Upserting into DB...",
            len(classified_articles),
            min_relevance,
        )
        count = upsert_news_articles(conn, classified_articles)
        log.info("Successfully upserted %d news articles into news_signals.", count)
        return count
    finally:
        if should_close:
            conn.close()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description="Sync WSJ & NYT Financial Press News Signals into DuckDB")
    parser.add_argument("--max-items", type=int, default=25, help="Max items per feed (default: 25)")
    parser.add_argument("--min-relevance", type=float, default=0.20, help="Min relevance threshold (default: 0.20)")
    parser.add_argument("--db-path", type=str, default="data/arf.db", help="Path to DuckDB database")
    args = parser.parse_args()

    count = sync_financial_press(
        max_items_per_feed=args.max_items,
        min_relevance=args.min_relevance,
        db_path=Path(args.db_path),
    )
    print(f"Sync complete. Upserted {count} relevant articles.")


if __name__ == "__main__":
    main()
