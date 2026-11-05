"""Unit tests for IDC Market Intelligence & MarketScape Engine."""

import re
from datetime import date

import pandas as pd
import pytest

from arf.idc import (
    compute_ai_spending_tracker,
    compute_idc_marketscape,
    generate_idc_executive_briefing,
)


@pytest.fixture
def sample_snapshot_df():
    """Create a mock snapshot DataFrame representing AI vendors."""
    return pd.DataFrame([
        {
            "ticker": "NVDA", "as_of_date": date(2026, 6, 1), "leg": "US", "layer": "L2",
            "name": "NVIDIA", "price": 120.0, "market_cap_usd": 3e12,
            "revenue_ttm": 1e11, "revenue_yoy_growth": 0.80, "gross_margin": 0.75,
            "roe": 0.90, "e_score": 95.0, "v_score": 45.0, "arf": 65.4,
            "froth_flag": False, "ev_sales": 25.0, "ps_ratio": 24.0,
        },
        {
            "ticker": "MSFT", "as_of_date": date(2026, 6, 1), "leg": "US", "layer": "L3",
            "name": "Microsoft", "price": 450.0, "market_cap_usd": 3.2e12,
            "revenue_ttm": 2.5e11, "revenue_yoy_growth": 0.16, "gross_margin": 0.68,
            "roe": 0.38, "e_score": 88.0, "v_score": 42.0, "arf": 60.8,
            "froth_flag": False, "ev_sales": 13.0, "ps_ratio": 12.5,
        },
        {
            "ticker": "300308.SZ", "as_of_date": date(2026, 6, 1), "leg": "China", "layer": "L2",
            "name": "Innolight", "price": 140.0, "market_cap_usd": 1.5e10,
            "revenue_ttm": 2e9, "revenue_yoy_growth": 0.65, "gross_margin": 0.38,
            "roe": 0.28, "e_score": 90.0, "v_score": 50.0, "arf": 67.1,
            "froth_flag": False, "ev_sales": 8.0, "ps_ratio": 7.5,
        },
        {
            "ticker": "FROTH_CO", "as_of_date": date(2026, 6, 1), "leg": "US", "layer": "L5",
            "name": "Froth AI", "price": 80.0, "market_cap_usd": 2e10,
            "revenue_ttm": 1e8, "revenue_yoy_growth": 0.15, "gross_margin": 0.25,
            "roe": -0.05, "e_score": 92.0, "v_score": 95.0, "arf": 93.5,
            "froth_flag": True, "ev_sales": 50.0, "ps_ratio": 48.0,
        },
    ])


@pytest.fixture
def sample_forecast_df():
    """Create a mock forecast DataFrame."""
    return pd.DataFrame([
        {
            "ticker": "NVDA", "predicted_rev_growth": 0.50, "expected_beat_pct": 0.12,
            "revision_velocity_14d": 0.05,
        },
        {
            "ticker": "MSFT", "predicted_rev_growth": 0.18, "expected_beat_pct": 0.02,
            "revision_velocity_14d": 0.01,
        },
        {
            "ticker": "300308.SZ", "predicted_rev_growth": 0.45, "expected_beat_pct": 0.08,
            "revision_velocity_14d": 0.03,
        },
        {
            "ticker": "FROTH_CO", "predicted_rev_growth": 0.10, "expected_beat_pct": -0.05,
            "revision_velocity_14d": -0.02,
        },
    ])


def test_compute_idc_marketscape_empty():
    """Verify empty snapshot returns empty DataFrame."""
    empty_res = compute_idc_marketscape(pd.DataFrame())
    assert empty_res.empty


def test_compute_idc_marketscape(sample_snapshot_df, sample_forecast_df):
    """Verify capabilities and strategies scoring and categorization."""
    ms_df = compute_idc_marketscape(sample_snapshot_df, sample_forecast_df)
    assert not ms_df.empty
    assert len(ms_df) == 4

    expected_cols = [
        "ticker", "name", "leg", "layer", "capabilities_score",
        "strategies_score", "marketscape_category", "market_cap_b",
        "ai_revenue_est_b", "arf", "froth_flag",
    ]
    for col in expected_cols:
        assert col in ms_df.columns

    # NVDA should be in Leaders quadrant (high ROE, high E_score, high growth)
    nvda_row = ms_df[ms_df["ticker"] == "NVDA"].iloc[0]
    assert nvda_row["marketscape_category"] == "Leaders"
    assert nvda_row["capabilities_score"] >= 52.0
    assert nvda_row["strategies_score"] >= 55.0

    # FROTH_CO should have froth_flag == True
    froth_row = ms_df[ms_df["ticker"] == "FROTH_CO"].iloc[0]
    assert bool(froth_row["froth_flag"]) is True


def test_compute_ai_spending_tracker(sample_snapshot_df):
    """Verify AI spending tracker aggregation across layers and legs."""
    tracker = compute_ai_spending_tracker(sample_snapshot_df)
    assert "total_universe_mcap_t" in tracker
    assert "total_ai_revenue_b" in tracker
    assert "overall_bubble_multiple" in tracker
    assert tracker["total_universe_mcap_t"] > 0
    assert tracker["total_ai_revenue_b"] > 0
    assert tracker["overall_bubble_multiple"] > 0

    assert "layers" in tracker
    assert len(tracker["layers"]) > 0

    assert "legs" in tracker
    assert "US" in tracker["legs"]
    assert "China" in tracker["legs"]


def test_generate_idc_executive_briefing(sample_snapshot_df, sample_forecast_df):
    """Verify executive briefing generation in official IDC format (Chinese and English)."""
    as_of = date(2026, 6, 1)
    briefing = generate_idc_executive_briefing(as_of, sample_snapshot_df, sample_forecast_df, lang="zh")

    assert "IDC MarketScape" in briefing
    assert "Worldwide AI Spending Guide" in briefing
    assert "IDC Opinion" in briefing
    assert "Essential Guidance for Technology Buyers" in briefing
    assert "Essential Guidance for Technology Vendors" in briefing
    assert "Sheng Jiang" in briefing

    # Test English version
    briefing_en = generate_idc_executive_briefing(as_of, sample_snapshot_df, sample_forecast_df, lang="en")
    assert "IDC MarketScape" in briefing_en
    assert "Worldwide AI Spending Guide" in briefing_en
    assert "Leaders Quadrant" in briefing_en
    assert "Market Perspective" in briefing_en
    assert "Essential Guidance for Technology Buyers" in briefing_en
    assert "Sheng Jiang" in briefing_en


def test_generate_analyst_vendor_profile(sample_snapshot_df, sample_forecast_df):
    """Verify analyst vendor profile generation with IDC MarketScape scores (Chinese and English)."""
    from arf.idc import generate_analyst_vendor_profile

    links_df = pd.DataFrame([
        {
            "supplier_ticker": "300308.SZ",
            "customer_ticker": "NVDA",
            "revenue_share_pct": 40.0,
            "relationship_type": "optical",
        }
    ])

    profile = generate_analyst_vendor_profile(
        ticker="NVDA",
        snap_df=sample_snapshot_df,
        fc_df=sample_forecast_df,
        links_df=links_df,
        analyst_commentary="Strong supplier pricing power in 1.6T transceivers.",
        lang="zh",
    )

    assert "IDC Vendor Profile" in profile
    assert "NVIDIA" in profile
    assert "Capabilities Score" in profile
    assert "Strategies Score" in profile
    assert "Strong supplier pricing power" in profile

    # Test English version
    profile_en = generate_analyst_vendor_profile(
        ticker="NVDA",
        snap_df=sample_snapshot_df,
        fc_df=sample_forecast_df,
        links_df=links_df,
        analyst_commentary="Strong supplier pricing power in 1.6T transceivers.",
        lang="en",
    )
    assert "IDC Vendor Profile" in profile_en
    assert "Execution Quality & Margins" in profile_en
    assert "Supply Chain Topology" in profile_en
    assert "Key Direct Customers" in profile_en

    # Test unknown ticker
    unknown = generate_analyst_vendor_profile("UNKNOWN_TICKER", sample_snapshot_df)
    assert "not found" in unknown


def test_marketscape_drops_unscored_rows(sample_snapshot_df):
    """A vendor without a computed ARF must not receive invented scores."""
    df = sample_snapshot_df.copy()
    df.loc[df["ticker"] == "MSFT", ["e_score", "v_score", "arf"]] = None

    ms_df = compute_idc_marketscape(df)

    assert "MSFT" not in set(ms_df["ticker"])
    assert len(ms_df) == 3
    # Every surviving row carries its real score, never a 50.0 substitute.
    assert (ms_df["e_score"] != 50.0).all()


def test_marketscape_preserves_zero_forecast(sample_snapshot_df):
    """A genuine 0% forecast must not fall through to trailing growth."""
    fc_df = pd.DataFrame([
        {"ticker": "NVDA", "predicted_rev_growth": 0.0, "expected_beat_pct": 0.0},
    ])
    ms_df = compute_idc_marketscape(sample_snapshot_df, fc_df)
    nvda = ms_df[ms_df["ticker"] == "NVDA"].iloc[0]
    assert nvda["predicted_growth"] == 0.0


def test_generators_handle_empty_snapshot():
    """CLI/automation callers get a readable result instead of a KeyError."""
    empty = pd.DataFrame()
    briefing = generate_idc_executive_briefing(date(2026, 6, 1), empty)
    assert "尚无已完成评分" in briefing

    from arf.idc import generate_analyst_vendor_profile

    profile = generate_analyst_vendor_profile("NVDA", empty)
    assert "not found" in profile


def test_vendor_profile_renders_null_metrics_as_na(sample_snapshot_df, sample_forecast_df):
    """NULL metrics round-trip through a float column as NaN; never print 'nan'."""
    df = sample_snapshot_df.copy()
    df.loc[df["ticker"] == "NVDA", ["roe", "ps_ratio"]] = None
    df["implied_growth"] = None

    from arf.idc import generate_analyst_vendor_profile

    profile = generate_analyst_vendor_profile("NVDA", df, sample_forecast_df)

    assert "nan%" not in profile
    assert "nanx" not in profile
    assert "N/A" in profile


def test_spending_tracker_excludes_manual_rows_without_scores(sample_snapshot_df):
    """Pre-IPO / manual rows (no market cap, no score) must not enter the totals."""
    rows = sample_snapshot_df.to_dict("records")
    rows.append({
        "ticker": "OPENAI", "as_of_date": date(2026, 6, 1), "leg": "US",
        "layer": "L4", "name": "OpenAI", "market_cap_usd": None,
        "e_score": None, "ev_sales": None, "ps_ratio": None, "froth_flag": None,
    })
    df = pd.DataFrame(rows)

    tracker = compute_ai_spending_tracker(df)

    assert tracker["covered_count"] == len(sample_snapshot_df)


def test_spending_tracker_localizes_layer_names(sample_snapshot_df):
    """English reports must not inherit the Chinese-first layer labels."""
    zh = compute_ai_spending_tracker(sample_snapshot_df, lang="zh")
    en = compute_ai_spending_tracker(sample_snapshot_df, lang="en")

    assert any(re.search(r"[一-鿿]", s["layer_name"]) for s in zh["layers"])
    assert not any(re.search(r"[一-鿿]", s["layer_name"]) for s in en["layers"])
    assert [s["layer_code"] for s in zh["layers"]] == [s["layer_code"] for s in en["layers"]]


def test_english_briefing_has_no_chinese(sample_snapshot_df, sample_forecast_df):
    """Regression: the English briefing previously emitted Chinese layer labels."""
    briefing = generate_idc_executive_briefing(
        date(2026, 6, 1), sample_snapshot_df, sample_forecast_df, lang="en"
    )

    assert not re.search(r"[一-鿿]", briefing)


def test_briefing_and_vendor_profile_with_news_df(sample_snapshot_df, sample_forecast_df):
    """Ensure WSJ & NYT news intelligence seamlessly integrates into IDC briefing and vendor profile."""
    from datetime import UTC, datetime

    from arf.idc import generate_analyst_vendor_profile

    sample_news = pd.DataFrame([
        {
            "article_id": "art-wsj-1",
            "source": "WSJ",
            "title": "Nvidia Accelerates CoWoS Packaging Supply with TSMC",
            "summary": "Hyperscaler datacenter CapEx expands rapidly.",
            "url": "https://wsj.com/nvidia-cowos",
            "published_at": datetime.now(UTC),
            "tickers": '["NVDA", "TSM"]',
            "sentiment_label": "Bullish",
        },
        {
            "article_id": "art-nyt-1",
            "source": "NYT",
            "title": "Big Tech Share Buybacks Surpass Capital Expenditure",
            "summary": "Capital allocation shifts toward equity reduction.",
            "url": "https://nytimes.com/tech-buybacks",
            "published_at": datetime.now(UTC),
            "tickers": '["MSFT"]',
            "sentiment_label": "Neutral",
        },
    ])

    # 1. Executive briefing with news
    en_briefing = generate_idc_executive_briefing(
        date(2026, 6, 1),
        sample_snapshot_df,
        sample_forecast_df,
        news_df=sample_news,
        lang="en",
    )
    assert "Financial Press Wire & Narrative Velocity" in en_briefing
    assert "https://wsj.com/nvidia-cowos" in en_briefing

    zh_briefing = generate_idc_executive_briefing(
        date(2026, 6, 1),
        sample_snapshot_df,
        sample_forecast_df,
        news_df=sample_news,
        lang="zh",
    )
    assert "权威财经舆情前沿与叙事动能" in zh_briefing
    assert "https://wsj.com/nvidia-cowos" in zh_briefing

    # 2. Vendor profile with news
    en_profile = generate_analyst_vendor_profile(
        ticker="NVDA",
        snap_df=sample_snapshot_df,
        fc_df=sample_forecast_df,
        news_df=sample_news,
        lang="en",
    )
    assert "Financial Press Intelligence" in en_profile
    assert "https://wsj.com/nvidia-cowos" in en_profile

    zh_profile = generate_analyst_vendor_profile(
        ticker="NVDA",
        snap_df=sample_snapshot_df,
        fc_df=sample_forecast_df,
        news_df=sample_news,
        lang="zh",
    )
    assert "华尔街日报与纽时实时舆情追踪" in zh_profile
    assert "https://wsj.com/nvidia-cowos" in zh_profile

