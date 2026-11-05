"""ARF Financial Press Intelligence (WSJ & NYT) module."""

from arf.news.classifier import NewsClassifier
from arf.news.feeds import fetch_all_active_feeds, fetch_feed_items
from arf.news.schema import NewsArticle, SentimentLabel, SourceOutlet, ThemeTag
from arf.news.storage import (
    init_news_table,
    query_news_signals,
    query_news_summary_by_layer,
    upsert_news_articles,
)
from arf.news.sync import sync_financial_press

__all__ = [
    "NewsArticle",
    "NewsClassifier",
    "SentimentLabel",
    "SourceOutlet",
    "ThemeTag",
    "fetch_all_active_feeds",
    "fetch_feed_items",
    "init_news_table",
    "query_news_signals",
    "query_news_summary_by_layer",
    "sync_financial_press",
    "upsert_news_articles",
]

