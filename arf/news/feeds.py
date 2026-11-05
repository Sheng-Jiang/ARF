"""Feed fetcher and parser for The Wall Street Journal and The New York Times."""

from __future__ import annotations

import email.utils
import hashlib
import html
import logging
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from typing import Any

from arf.news.schema import SourceOutlet

log = logging.getLogger(__name__)

# Standard Browser User-Agent to avoid generic bot 403 blocks
_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}

# Curated Feeds Registry
FEED_REGISTRY: list[dict[str, str]] = [
    # NYT Feeds
    {
        "name": "NYT Technology",
        "source": "NYT",
        "url": "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
    },
    {
        "name": "NYT Business",
        "source": "NYT",
        "url": "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
    },
    {
        "name": "NYT Economy",
        "source": "NYT",
        "url": "https://rss.nytimes.com/services/xml/rss/nyt/Economy.xml",
    },
    {
        "name": "NYT DealBook",
        "source": "NYT",
        "url": "https://rss.nytimes.com/services/xml/rss/nyt/Dealbook.xml",
    },
    # WSJ Feeds
    {
        "name": "WSJ Technology",
        "source": "WSJ",
        "url": "https://feeds.a.dj.com/rss/RSSWSJD.xml",
    },
    {
        "name": "WSJ Markets",
        "source": "WSJ",
        "url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
    },
    {
        "name": "WSJ US Business",
        "source": "WSJ",
        "url": "https://feeds.a.dj.com/rss/WSJcomUSBusiness.xml",
    },
    {
        "name": "WSJ Opinion & Markets",
        "source": "WSJ",
        "url": "https://feeds.a.dj.com/rss/RSSOpinion.xml",
    },
    {
        "name": "WSJ World & China",
        "source": "WSJ",
        "url": "https://feeds.a.dj.com/rss/RSSWorldNews.xml",
    },
]

# Targeted Google News queries searching specifically for WSJ and NYT reporting
TARGETED_SEARCH_QUERIES = [
    '(site:wsj.com OR site:nytimes.com) ("artificial intelligence" OR "AI" OR "Nvidia" OR "chips" OR "semiconductor") when:7d',
    '(site:wsj.com OR site:nytimes.com) ("CapEx" OR "datacenter" OR "data center" OR "power grid" OR "CoWoS") when:7d',
    '(site:wsj.com OR site:nytimes.com) ("China tech" OR "DeepSeek" OR "export control" OR "TSMC" OR "SMIC") when:7d',
    '(site:wsj.com OR site:nytimes.com) ("buyback" OR "share repurchase" OR "dilution" OR "dividend") when:7d',
]


def _build_google_news_rss_url(query: str) -> str:
    """Encode targeted query into Google News RSS endpoint."""
    encoded = urllib.parse.quote(query)
    return f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"


def _clean_text(raw_html: str | None) -> str:
    """Strip HTML tags and unescape entities."""
    if not raw_html:
        return ""
    clean = re.sub(r"<[^>]+>", " ", raw_html)
    clean = html.unescape(clean)
    return re.sub(r"\s+", " ", clean).strip()


def _clean_url(raw_url: str) -> str:
    """Remove tracking parameters like ?mod=rss or ?utm_* from URLs."""
    parsed = urllib.parse.urlparse(raw_url)
    qs = urllib.parse.parse_qs(parsed.query)
    filtered_qs = {k: v for k, v in qs.items() if not k.startswith("utm_") and k != "mod"}
    new_query = urllib.parse.urlencode(filtered_qs, doseq=True)
    return urllib.parse.urlunparse(parsed._replace(query=new_query, fragment=""))


def _parse_pub_date(pub_date_str: str | None) -> datetime:
    """Parse RFC 822 date string to timezone-aware UTC datetime."""
    if not pub_date_str:
        return datetime.now(UTC)
    try:
        dt = email.utils.parsedate_to_datetime(pub_date_str)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except Exception:
        return datetime.now(UTC)


def _generate_article_id(url: str, title: str) -> str:
    """Generate a deterministic hash ID for deduplication."""
    clean = f"{_clean_url(url)}::{title.strip().lower()}"
    return hashlib.sha256(clean.encode("utf-8")).hexdigest()[:24]


def fetch_feed_items(
    url: str,
    source_label: SourceOutlet,
    timeout_sec: int = 12,
) -> list[dict[str, Any]]:
    """Fetch and parse RSS XML items from a given URL."""
    req = urllib.request.Request(url, headers=_DEFAULT_HEADERS)
    items_out = []
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            content = resp.read()
            root = ET.fromstring(content)
            for item in root.findall(".//item"):
                title_elem = item.find("title")
                link_elem = item.find("link")
                desc_elem = item.find("description")
                pub_elem = item.find("pubDate")

                title = _clean_text(title_elem.text if title_elem is not None else "")
                link = (link_elem.text if link_elem is not None else "").strip()
                summary = _clean_text(desc_elem.text if desc_elem is not None else "")
                pub_str = pub_elem.text if pub_elem is not None else None

                if not title or not link:
                    continue

                # Determine source outlet if from syndication
                actual_source = source_label
                if "wsj.com" in link.lower() or title.endswith("- WSJ"):
                    actual_source = "WSJ"
                    title = re.sub(r"\s*-\s*WSJ$", "", title).strip()
                elif "nytimes.com" in link.lower() or title.endswith("- The New York Times"):
                    actual_source = "NYT"
                    title = re.sub(r"\s*-\s*The New York Times$", "", title).strip()

                clean_link = _clean_url(link)
                art_id = _generate_article_id(clean_link, title)

                items_out.append({
                    "article_id": art_id,
                    "source": actual_source,
                    "title": title,
                    "summary": summary,
                    "url": clean_link,
                    "published_at": _parse_pub_date(pub_str),
                })
    except Exception as exc:
        log.warning("Failed to fetch RSS feed from %s: %s", url, exc)

    return items_out


def fetch_all_active_feeds(max_items_per_feed: int = 25) -> list[dict[str, Any]]:
    """Fetch items across both WSJ, NYT, and targeted Google News queries."""
    seen_ids: set[str] = set()
    aggregated_items: list[dict[str, Any]] = []

    # 1. Fetch from direct editorial feeds
    for feed in FEED_REGISTRY:
        items = fetch_feed_items(feed["url"], feed["source"])
        for it in items[:max_items_per_feed]:
            if it["article_id"] not in seen_ids:
                seen_ids.add(it["article_id"])
                aggregated_items.append(it)

    # 2. Fetch from targeted Google News search queries for WSJ / NYT
    for q in TARGETED_SEARCH_QUERIES:
        query_url = _build_google_news_rss_url(q)
        items = fetch_feed_items(query_url, "WSJ/NYT Syndication")
        for it in items[:max_items_per_feed]:
            if it["article_id"] not in seen_ids:
                seen_ids.add(it["article_id"])
                aggregated_items.append(it)

    return aggregated_items
