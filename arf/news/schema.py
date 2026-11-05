"""Data schemas and types for the ARF Financial Press (WSJ & NYT) intelligence module."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

SourceOutlet = Literal["WSJ", "NYT", "WSJ/NYT Syndication"]
SentimentLabel = Literal["Bullish", "Bearish", "Neutral"]

# Thematic tags bridging ARF factor research and reference papers:
# - CapEx_Infrastructure: Hyperscaler CapEx, power grid, nuclear PPAs, CoWoS packaging, optical transceivers
# - Export_Controls_Policy: BIS sanctions, chip bans, Big Fund III subsidies, CSRC reforms, policy premiums
# - Buybacks_Capital_Allocation: Share repurchases, dividend payouts, dilution vs accretion, corporate governance
# - Valuation_Bubble_Froth: Valuation multiples, bubble de-rating, earnings beat/miss, implied growth gap
# - Model_Breakthrough: Foundation models, open-source weights, distillation, reasoning architectures
# - General_AI_Tech: Broad enterprise AI adoption, corporate partnerships
ThemeTag = Literal[
    "CapEx_Infrastructure",
    "Export_Controls_Policy",
    "Buybacks_Capital_Allocation",
    "Valuation_Bubble_Froth",
    "Model_Breakthrough",
    "General_AI_Tech",
]


@dataclass
class NewsArticle:
    """Standardized news article entity extracted from financial press feeds."""

    article_id: str
    source: SourceOutlet
    title: str
    summary: str
    url: str
    published_at: datetime
    fetched_at: datetime
    tickers: list[str] = field(default_factory=list)
    layers: list[str] = field(default_factory=list)
    themes: list[str] = field(default_factory=list)
    relevance_score: float = 0.0
    sentiment_label: SentimentLabel = "Neutral"
    sentiment_score: float = 0.0

    def to_dict(self) -> dict:
        """Convert entity to a dictionary for DataFrame / database insertion."""
        import json

        return {
            "article_id": self.article_id,
            "source": str(self.source),
            "title": self.title,
            "summary": self.summary,
            "url": self.url,
            "published_at": self.published_at,
            "fetched_at": self.fetched_at,
            "tickers": json.dumps(self.tickers),
            "layers": json.dumps(self.layers),
            "themes": json.dumps(self.themes),
            "relevance_score": self.relevance_score,
            "sentiment_label": str(self.sentiment_label),
            "sentiment_score": self.sentiment_score,
        }

