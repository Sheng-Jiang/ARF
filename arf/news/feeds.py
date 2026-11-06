"""Feed fetcher and parser for The Wall Street Journal and The New York Times."""

from __future__ import annotations

import email.utils
import hashlib
import html
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any

from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

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
    # NOTE (2026-11): these public endpoints currently serve a frozen snapshot
    # (Jan 2025; Opinion goes back to Feb 2023), so their items are dropped by
    # sync's 30-day age filter. Kept registered in case WSJ restores them;
    # recent WSJ coverage comes from the Google News site:wsj.com queries.
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


def _parse_pub_date(pub_date_str: str | None) -> datetime | None:
    """Parse RFC 822 / ISO-8601 date string to timezone-aware UTC datetime.

    Returns ``None`` when the date is missing or unparseable. Stamping such
    items with the sync time would make them look freshly published forever,
    so callers skip undated items instead.
    """
    if not pub_date_str:
        return None
    try:
        dt = email.utils.parsedate_to_datetime(pub_date_str)
    except Exception:
        try:
            dt = datetime.fromisoformat(pub_date_str.replace("Z", "+00:00"))
        except Exception:
            return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _first_text(item: ET.Element, tags: tuple[str, ...]) -> str | None:
    """First non-empty child text among *tags* (Atom and RSS 2.0 variants)."""
    for tag in tags:
        elem = item.find(tag)
        if elem is not None and elem.text:
            return elem.text
    return None


def _is_retryable(exc: BaseException) -> bool:
    """Retry transient network/parse failures, not permanent HTTP 4xx."""
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code == 429 or exc.code >= 500
    return isinstance(exc, (urllib.error.URLError, TimeoutError, ConnectionError, ET.ParseError))


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception(_is_retryable),
    reraise=True,
)
def _read_feed(url: str, timeout_sec: int) -> bytes:
    """Download a feed with retry + exponential backoff (repo-wide rule)."""
    req = urllib.request.Request(url, headers=_DEFAULT_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
        return resp.read()


def _normalize_title(title: str) -> str:
    """Lower-case and strip punctuation so syndicated copies collide."""
    normalized = title.lower()
    normalized = re.sub(r"[^a-z0-9一-鿿]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _generate_article_id(title: str, published_at: datetime) -> str:
    """Deterministic story ID: normalized title + publication day.

    Google News copies of an NYT/WSJ story have a different URL from the
    original, so a URL-based hash stored the same story twice. Including the
    day keeps recurring columns (e.g. the daily "Market Talk" roundup) as
    separate articles while collapsing same-day syndication duplicates.
    """
    clean = f"{_normalize_title(title)}::{published_at.astimezone(UTC).date().isoformat()}"
    return hashlib.sha256(clean.encode("utf-8")).hexdigest()[:24]


def fetch_feed_items(
    url: str,
    source_label: SourceOutlet,
    timeout_sec: int = 12,
) -> list[dict[str, Any]]:
    """Fetch and parse RSS XML items from a given URL."""
    items_out = []
    try:
        content = _read_feed(url, timeout_sec)
        root = ET.fromstring(content)
        for item in root.findall(".//item"):
            title = _clean_text(_first_text(item, ("title",)))
            link = (_first_text(item, ("link",)) or "").strip()
            summary = _clean_text(_first_text(item, ("description", "summary", "content")))
            pub_str = _first_text(
                item,
                ("pubDate", "published", "updated", "{http://purl.org/dc/elements/1.1/}date"),
            )

            if not title or not link:
                continue

            published_at = _parse_pub_date(pub_str)
            if published_at is None:
                # Can't place the item in time; a fabricated "now" date would
                # keep it in every rolling window forever.
                log.debug("Skipping undated feed item: %s", title)
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
            art_id = _generate_article_id(title, published_at)

            items_out.append({
                "article_id": art_id,
                "source": actual_source,
                "title": title,
                "summary": summary,
                "url": clean_link,
                "published_at": published_at,
            })
    except Exception as exc:
        log.warning("Failed to fetch RSS feed from %s: %s", url, exc)

    return items_out


def fetch_all_active_feeds(
    max_items_per_feed: int = 25,
    max_workers: int = 6,
) -> list[dict[str, Any]]:
    """Fetch items across both WSJ, NYT, and targeted Google News queries.

    Feeds are fetched concurrently: with 13 endpoints and a 12 s timeout,
    serial fetching can add ~156 s to every pipeline run / sync click.
    """
    feed_specs: list[tuple[str, SourceOutlet]] = [
        (feed["url"], feed["source"]) for feed in FEED_REGISTRY
    ]
    feed_specs.extend(
        (_build_google_news_rss_url(q), "WSJ/NYT Syndication")
        for q in TARGETED_SEARCH_QUERIES
    )

    with ThreadPoolExecutor(max_workers=min(max_workers, len(feed_specs))) as pool:
        # map preserves submission order, so dedup stays deterministic.
        results = list(
            pool.map(lambda spec: fetch_feed_items(spec[0], spec[1]), feed_specs)
        )

    seen_ids: set[str] = set()
    aggregated_items: list[dict[str, Any]] = []
    for items in results:
        for it in items[:max_items_per_feed]:
            if it["article_id"] not in seen_ids:
                seen_ids.add(it["article_id"])
                aggregated_items.append(it)

    return aggregated_items
