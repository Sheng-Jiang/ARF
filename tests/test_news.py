"""Unit tests for the ARF Financial Press (WSJ & NYT) news intelligence pipeline."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import duckdb
import pytest

from arf.news.classifier import NewsClassifier
from arf.news.feeds import (
    _clean_text,
    _clean_url,
    _generate_article_id,
    _parse_pub_date,
)
from arf.news.schema import NewsArticle
from arf.news.storage import (
    init_news_table,
    query_news_signals,
    query_news_summary_by_layer,
    upsert_news_articles,
)
from arf.news.sync import sync_financial_press


class TestNewsSchema:
    def test_news_article_to_dict(self):
        now = datetime.now(UTC)
        art = NewsArticle(
            article_id="art-12345",
            source="WSJ",
            title="Nvidia's Big Earnings Surge Drives AI CapEx",
            summary="Strong datacenter demand drives higher revenue.",
            url="https://wsj.com/articles/nvidia-surge",
            published_at=now,
            fetched_at=now,
            tickers=["NVDA"],
            layers=["L2"],
            themes=["CapEx_Infrastructure"],
            relevance_score=0.95,
            sentiment_label="Bullish",
            sentiment_score=0.70,
        )
        d = art.to_dict()
        assert d["article_id"] == "art-12345"
        assert d["source"] == "WSJ"
        assert '"NVDA"' in d["tickers"]
        assert '"L2"' in d["layers"]
        assert '"CapEx_Infrastructure"' in d["themes"]
        assert d["relevance_score"] == 0.95
        assert d["sentiment_label"] == "Bullish"


class TestNewsClassifier:
    @pytest.fixture
    def classifier(self):
        return NewsClassifier()

    def test_classify_nvidia_capex(self, classifier):
        title = "Nvidia Soars as Big Tech CapEx Fuels Datacenter Buildout"
        summary = "Microsoft and Meta accelerate server buildout and liquid cooling adoption."
        res = classifier.classify(title, summary)

        assert "NVDA" in res["tickers"]
        assert "MSFT" in res["tickers"]
        assert "META" in res["tickers"]
        assert "L2" in res["layers"] or "L3" in res["layers"]
        assert "CapEx_Infrastructure" in res["themes"]
        assert res["sentiment_label"] == "Bullish"
        assert res["relevance_score"] >= 0.70

    def test_classify_china_export_controls(self, classifier):
        title = "US Expands Semiconductor Export Controls and Entity List Bans on SMIC"
        summary = "Bureau of Industry and Security targets domestic substitution and Big Fund subsidies."
        res = classifier.classify(title, summary)

        assert "688981.SH" in res["tickers"]
        assert "L1" in res["layers"]
        assert "Export_Controls_Policy" in res["themes"]
        assert res["sentiment_label"] == "Bearish"

    def test_classify_buybacks_capital_allocation(self, classifier):
        title = "Alibaba and Tencent Expand Share Buybacks to Counter Equity Dilution"
        summary = "Management commits record capital return via share repurchase and dividend payouts."
        res = classifier.classify(title, summary)

        assert "BABA" in res["tickers"]
        assert "0700.HK" in res["tickers"]
        assert "Buybacks_Capital_Allocation" in res["themes"]
        assert res["relevance_score"] >= 0.70

    def test_classify_valuation_bubble(self, classifier):
        title = "AI Bubble Warning: Froth in Tech Multiples Leads to Heavy Selloff"
        summary = "Investors worry about margin compression and high implied growth hurdles."
        res = classifier.classify(title, summary)

        assert "Valuation_Bubble_Froth" in res["themes"]
        assert res["sentiment_label"] == "Bearish"

    def test_classify_model_breakthrough(self, classifier):
        title = "DeepSeek Unveils New Open Source AI Reasoning Model"
        summary = "Distillation breakthrough challenges proprietary foundation models."
        res = classifier.classify(title, summary)

        assert "DEEPSEEK" in res["tickers"]
        assert "L4" in res["layers"]
        assert "Model_Breakthrough" in res["themes"]

    def test_generic_name_parts_do_not_resolve_to_tickers(self, classifier):
        """Corporate suffixes inside display names must not become aliases."""
        res = classifier.classify(
            "Banks route capital as companies cut technology spending",
            "The energy and digital networks group reports results.",
        )
        assert res["tickers"] == []
        assert res["layers"] == []

    @pytest.mark.parametrize(
        "title",
        [
            "The central bank reported quarterly results",
            "Logistics firms will route shipments through Asia",
            "Warner Bros Discovery scheduled an investor day",
            "Dropbox expanded its enterprise plan",
            "Routine maintenance is scheduled for the weekend",
        ],
    )
    def test_sentiment_has_no_substring_false_positives(self, classifier, title):
        assert classifier.classify(title)["sentiment_label"] == "Neutral"

    def test_sentiment_still_matches_inflections(self, classifier):
        res = classifier.classify("Nvidia shares surged as profits soared")
        assert res["sentiment_label"] == "Bullish"

    def test_cowos_tags_capex_and_foundry_layer(self, classifier):
        res = classifier.classify("TSMC Expands CoWoS Advanced Packaging Capacity")
        assert "CapEx_Infrastructure" in res["themes"]
        # TSMC is a known ticker, so its own layer assignment applies.
        assert "L1" in res["layers"]

    def test_livestock_is_not_a_capex_signal(self, classifier):
        res = classifier.classify("Dairy farm reports record milk output as cows graze")
        assert "CapEx_Infrastructure" not in res["themes"]


class TestNewsFeedsHelpers:
    def test_clean_text(self):
        html_input = "<p>Nvidia reported <b>strong</b> revenue &amp; earnings.</p>"
        assert _clean_text(html_input) == "Nvidia reported strong revenue & earnings."
        assert _clean_text("") == ""
        assert _clean_text(None) == ""

    def test_clean_url(self):
        raw = "https://www.wsj.com/articles/ai-boom-123?mod=rss_technology&utm_source=google"
        cleaned = _clean_url(raw)
        assert "mod" not in cleaned
        assert "utm_source" not in cleaned
        assert cleaned == "https://www.wsj.com/articles/ai-boom-123"

    def test_generate_article_id(self):
        url = "https://www.wsj.com/articles/nvidia"
        title = "Nvidia Soars on Q3 Beat"
        id1 = _generate_article_id(url, title)
        id2 = _generate_article_id(url, title)
        id3 = _generate_article_id(url, "Different Title")
        assert len(id1) == 24
        assert id1 == id2
        assert id1 != id3

    def test_parse_pub_date(self):
        rfc822 = "Mon, 03 Nov 2026 14:30:00 GMT"
        dt = _parse_pub_date(rfc822)
        assert dt.year == 2026
        assert dt.month == 11
        assert dt.day == 3
        assert dt.tzinfo is not None

        # Undated/invalid items must not be stamped with "now" — callers skip
        # them so they cannot linger in every rolling window forever.
        assert _parse_pub_date(None) is None
        assert _parse_pub_date("") is None
        assert _parse_pub_date("invalid-date") is None

        # ISO-8601 (Atom / Dublin Core) fallback
        iso = _parse_pub_date("2026-11-03T14:30:00Z")
        assert iso is not None
        assert (iso.year, iso.month, iso.day) == (2026, 11, 3)


class TestNewsDuckDBStorage:
    @pytest.fixture
    def conn(self):
        c = duckdb.connect(":memory:")
        init_news_table(c)
        yield c
        c.close()

    def test_upsert_and_query_articles(self, conn):
        now = datetime.now(UTC)
        articles = [
            NewsArticle(
                article_id="art-001",
                source="WSJ",
                title="Nvidia's Record Quarter",
                summary="GPU demand drives strong cash flow.",
                url="https://wsj.com/art-001",
                published_at=now - timedelta(days=1),
                fetched_at=now,
                tickers=["NVDA"],
                layers=["L2"],
                themes=["CapEx_Infrastructure"],
                relevance_score=0.90,
                sentiment_label="Bullish",
                sentiment_score=0.60,
            ),
            NewsArticle(
                article_id="art-002",
                source="NYT",
                title="TSMC Advanced Packaging Bottleneck",
                summary="CoWoS capacity remains tight.",
                url="https://nytimes.com/art-002",
                published_at=now - timedelta(days=2),
                fetched_at=now,
                tickers=["TSM"],
                layers=["L1"],
                themes=["CapEx_Infrastructure"],
                relevance_score=0.85,
                sentiment_label="Neutral",
                sentiment_score=0.0,
            ),
            NewsArticle(
                article_id="art-003",
                source="WSJ",
                title="BABA Share Repurchase Accelerates",
                summary="Alibaba completes record buyback.",
                url="https://wsj.com/art-003",
                published_at=now - timedelta(days=5),
                fetched_at=now,
                tickers=["BABA"],
                layers=["L3"],
                themes=["Buybacks_Capital_Allocation"],
                relevance_score=0.80,
                sentiment_label="Bullish",
                sentiment_score=0.50,
            ),
        ]

        count = upsert_news_articles(conn, articles)
        assert count == 3

        # Re-upserting same articles should update, not duplicate
        count2 = upsert_news_articles(conn, articles)
        assert count2 == 3
        df_all = query_news_signals(conn, days=10)
        assert len(df_all) == 3

        # Filter by ticker
        df_nvda = query_news_signals(conn, ticker="NVDA")
        assert len(df_nvda) == 1
        assert df_nvda.iloc[0]["title"] == "Nvidia's Record Quarter"

        # Filter by layer
        df_l1 = query_news_signals(conn, layer="L1")
        assert len(df_l1) == 1
        assert df_l1.iloc[0]["source"] == "NYT"

        # Filter by theme
        df_buybacks = query_news_signals(conn, theme="Buybacks_Capital_Allocation")
        assert len(df_buybacks) == 1
        assert df_buybacks.iloc[0]["tickers"] == '["BABA"]'

        # Filter by source
        df_wsj = query_news_signals(conn, source="WSJ")
        assert len(df_wsj) == 2

    def test_layer_summary_aggregation(self, conn):
        now = datetime.now(UTC)
        articles = [
            NewsArticle(
                article_id="art-l1",
                source="WSJ",
                title="TSMC Foundry Expansion",
                summary="Expanding CoWoS line.",
                url="https://wsj.com/l1",
                published_at=now - timedelta(days=1),
                fetched_at=now,
                tickers=["TSM"],
                layers=["L1"],
                themes=["CapEx_Infrastructure"],
                relevance_score=0.90,
                sentiment_label="Bullish",
                sentiment_score=0.80,
            ),
            NewsArticle(
                article_id="art-l2-a",
                source="NYT",
                title="AI Chip Demand Surges",
                summary="Nvidia and AMD accelerators.",
                url="https://nytimes.com/l2-a",
                published_at=now - timedelta(days=2),
                fetched_at=now,
                tickers=["NVDA", "AMD"],
                layers=["L2"],
                themes=["CapEx_Infrastructure"],
                relevance_score=0.95,
                sentiment_label="Bullish",
                sentiment_score=0.60,
            ),
        ]
        upsert_news_articles(conn, articles)

        agg = query_news_summary_by_layer(conn, days=7)
        assert not agg.empty
        assert set(agg["layer"]) == {"L1", "L2"}
        l1_row = agg[agg["layer"] == "L1"].iloc[0]
        assert l1_row["article_count"] == 1
        assert pytest.approx(l1_row["avg_sentiment"], 0.01) == 0.80

    def test_ticker_filter_accepts_partial_symbols(self, conn):
        now = datetime.now(UTC)
        articles = [
            NewsArticle(
                article_id="art-cambricon",
                source="WSJ",
                title="Cambricon AI Chip Demand",
                summary="",
                url="https://wsj.com/cambricon",
                published_at=now - timedelta(days=1),
                fetched_at=now,
                tickers=["688256.SH"],
                layers=["L1"],
                themes=["General_AI_Tech"],
                relevance_score=0.80,
            ),
            NewsArticle(
                article_id="art-tencent",
                source="NYT",
                title="Tencent Cloud Buyback",
                summary="",
                url="https://nytimes.com/tencent",
                published_at=now - timedelta(days=1),
                fetched_at=now,
                tickers=["0700.HK"],
                layers=["L3"],
                themes=["Buybacks_Capital_Allocation"],
                relevance_score=0.80,
            ),
        ]
        upsert_news_articles(conn, articles)

        assert len(query_news_signals(conn, ticker="688256")) == 1
        assert len(query_news_signals(conn, ticker="688256.SH")) == 1
        assert len(query_news_signals(conn, ticker="0700")) == 1
        assert len(query_news_signals(conn, ticker="0700.HK")) == 1
        assert len(query_news_signals(conn, ticker="NVDA")) == 0

    def test_as_of_bounds_window_to_that_date(self, conn):
        now = datetime.now(UTC)
        as_of = (now - timedelta(days=5)).date()
        articles = [
            NewsArticle(
                article_id="art-before",
                source="WSJ",
                title="Nvidia Results Before Snapshot",
                summary="",
                url="https://wsj.com/before",
                published_at=now - timedelta(days=6),
                fetched_at=now,
                tickers=["NVDA"],
                layers=["L2"],
                themes=["General_AI_Tech"],
                relevance_score=0.90,
            ),
            NewsArticle(
                article_id="art-after",
                source="WSJ",
                title="Nvidia Results After Snapshot",
                summary="",
                url="https://wsj.com/after",
                published_at=now - timedelta(days=1),
                fetched_at=now,
                tickers=["NVDA"],
                layers=["L2"],
                themes=["General_AI_Tech"],
                relevance_score=0.90,
            ),
        ]
        upsert_news_articles(conn, articles)

        df = query_news_signals(conn, days=30, as_of=as_of)
        assert list(df["article_id"]) == ["art-before"]


class TestSyncFinancialPress:
    @patch("arf.news.sync.fetch_all_active_feeds")
    def test_sync_financial_press_mocked(self, mock_fetch):
        now = datetime.now(UTC)
        mock_fetch.return_value = [
            {
                "article_id": "mock-001",
                "source": "WSJ",
                "title": "Nvidia Delivers Massive Datacenter Revenue Growth",
                "summary": "AI CapEx drives huge demand for GPUs and liquid cooling.",
                "url": "https://wsj.com/mock-001",
                "published_at": now,
            },
            {
                "article_id": "mock-002",
                "source": "NYT",
                "title": "Local Bakery Wins Pie Contest",
                "summary": "Apple and cherry pies top the state fair.",
                "url": "https://nytimes.com/mock-002",
                "published_at": now,
            },
        ]

        conn = duckdb.connect(":memory:")
        init_news_table(conn)

        count = sync_financial_press(conn=conn, min_relevance=0.20)
        # mock-001 should be saved; mock-002 (pie contest) should be discarded as irrelevant
        assert count == 1

        df = query_news_signals(conn)
        assert len(df) == 1
        assert df.iloc[0]["article_id"] == "mock-001"
        assert "NVDA" in df.iloc[0]["tickers"]
        conn.close()

    @patch("arf.news.sync.fetch_all_active_feeds")
    def test_sync_as_of_excludes_future_articles(self, mock_fetch):
        now = datetime.now(UTC)
        mock_fetch.return_value = [
            {
                "article_id": "mock-future",
                "source": "WSJ",
                "title": "Nvidia Datacenter Revenue Growth",
                "summary": "AI CapEx drives demand for GPUs.",
                "url": "https://wsj.com/mock-future",
                "published_at": now,
            },
        ]

        conn = duckdb.connect(":memory:")
        init_news_table(conn)

        past_as_of = (now - timedelta(days=30)).date()
        count = sync_financial_press(conn=conn, as_of=past_as_of)
        assert count == 0
        assert query_news_signals(conn, days=365).empty
        conn.close()

