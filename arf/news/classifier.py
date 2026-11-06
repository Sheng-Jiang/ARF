"""Classifier for mapping financial press news to ARF universe tickers, layers, and themes."""

from __future__ import annotations

import re
from typing import Any

from arf.config import UniverseEntry, load_universe
from arf.news.schema import SentimentLabel, ThemeTag

# Core keyword sets for thematic tagging
_THEME_KEYWORDS: dict[ThemeTag, list[str]] = {
    "CapEx_Infrastructure": [
        "capex", "capital expenditure", "capital spending", "datacenter", "data center",
        "power grid", "nuclear power", "smr", "small modular reactor", "cooling", "liquid cooling",
        "cowos", "advanced packaging", "optical transceiver", "800g", "1.6t", "hbm",
        "high-bandwidth memory", "server buildout", "megawatt", "gigawatt",
    ],
    "Export_Controls_Policy": [
        "export control", "export restriction", "sanction", "bis", "bureau of industry and security",
        "entity list", "chip ban", "semiconductor ban", "tariff", "national security",
        "big fund", "state subsidy", "csrc", "nine guidelines", "新国九条",
        "domestic substitution", "self-reliance", "tech war",
    ],
    "Buybacks_Capital_Allocation": [
        "buyback", "share repurchase", "share buyback", "repurchased shares",
        "dividend", "capital return", "dilution", "share dilution", "stock dilution",
        "equity offering", "capital allocation", "shareholder return", "payout ratio",
    ],
    "Valuation_Bubble_Froth": [
        "bubble", "froth", "valuation", "multiple", "pe ratio", "p/s ratio",
        "selloff", "rout", "meltdown", "overvalued", "de-rating", "derating",
        "earnings beat", "earnings miss", "margin compression", "implied growth",
        "correction", "tech tumble", "investor fatigue", "capex fatigue",
    ],
    "Model_Breakthrough": [
        "deepseek", "gpt-4", "gpt-5", "claude", "gemini", "llama", "qwen", "ernie",
        "reasoning model", "open source ai", "distillation", "foundation model",
        "large language model", "llm", "agentic ai", "superintelligence", "agi",
    ],
}

# Positive / Bullish lexicon for tech journalism. Patterns are word-bounded so
# that e.g. "surge" cannot match "surgeon"; inflections are spelled out rather
# than matched as substrings.
_BULLISH_PATTERNS = [
    r"soar\w*",
    r"surge\w*",
    r"record profits?",
    r"record revenues?",
    r"beats? estimates?",
    r"exceed(?:s|ed)?",
    r"rall(?:y|ies|ied)",
    r"breakthrough\w*",
    r"expansion\w*",
    r"accelerat\w*",
    r"boom\w*",
    r"upgrade\w*",
    r"outperform\w*",
    r"milestone\w*",
    r"huge demand",
    r"strong guidance",
]

# Negative / Bearish lexicon. Deliberately keeps short stems out of prefix
# matching: "ban" must not match bank, "rout" must not match route, "warn"
# must not match Warner, "drop" must not match Dropbox.
_BEARISH_PATTERNS = [
    r"rout\b",
    r"tumbl\w*",
    r"slump\w*",
    r"fall(?:s|ing|en)?",
    r"drops?|dropped|dropping",
    r"sink\w*|sank",
    r"selloffs?",
    r"meltdown\w*",
    r"miss(?:ed|es)? estimates?",
    r"weak guidance",
    r"scrutin\w*",
    r"bans?",
    r"curb\w*",
    r"halt\w*",
    r"bubbl\w*",
    r"froth\w*",
    r"warns?|warned|warning",
    r"plung\w*",
    r"investigat\w*",
    r"decelerat\w*",
    r"loss(?:es)?",
]

_BULLISH_RE = [re.compile(rf"\b(?:{p})\b") for p in _BULLISH_PATTERNS]
_BEARISH_RE = [re.compile(rf"\b(?:{p})\b") for p in _BEARISH_PATTERNS]

# Corporate suffixes and bare industry words that appear inside universe display
# names. Registering them as ticker aliases turns ordinary headlines into
# matches ("companies" → WMB, "technology" → MRVL), so name parts are only
# registered when they are distinctive.
_GENERIC_NAME_TOKENS = {
    "adr", "and", "black", "capital", "co", "companies", "company", "corp",
    "corporation", "digital", "electric", "energy", "enterprise", "enterprises",
    "financial", "fourth", "ge", "global", "group", "holding", "holdings",
    "horizon", "inc", "industries", "industry", "information", "international",
    "labs", "limited", "ltd", "micro", "motors", "network", "networks",
    "platform", "platforms", "plc", "power", "robotics", "semiconductor",
    "semiconductors", "serve", "services", "solutions", "super", "system",
    "systems", "tech", "technologies", "technology", "the",
}


class NewsClassifier:
    """Classifies news articles against the ARF universe and thematic dimensions."""

    def __init__(self, universe: list[UniverseEntry] | None = None) -> None:
        if universe is None:
            try:
                universe = load_universe()
            except Exception:
                universe = []
        self.universe = universe
        self._ticker_map: dict[str, tuple[str, str]] = {}
        self._build_ticker_map()

    def _build_ticker_map(self) -> None:
        """Construct a lookup map of lower-cased aliases to (ticker, layer)."""
        # 1. First merge universe entries
        for u in self.universe:
            layer_val = u.layer or "L2"
            t_upper = u.ticker.upper()
            self._ticker_map[t_upper.lower()] = (t_upper, layer_val)
            name_clean = u.name.lower().strip()
            if name_clean and len(name_clean) > 2:
                self._ticker_map[name_clean] = (t_upper, layer_val)
                # Split English and Chinese parts if present. Bare corporate /
                # industry words ("technology", "companies", "networks") are
                # skipped: as aliases they would tag unrelated headlines.
                for part in re.split(r"[\s/()（）]+", name_clean):
                    if part in _GENERIC_NAME_TOKENS:
                        continue
                    has_cjk = any("一" <= ch <= "鿿" for ch in part)
                    if (has_cjk and len(part) >= 2) or len(part) >= 3:
                        self._ticker_map[part] = (t_upper, layer_val)

        # 2. Hardcoded high-frequency aliases for major companies (override / take precedence)
        custom_aliases = {
            "nvidia": ("NVDA", "L2"),
            "nvda": ("NVDA", "L2"),
            "microsoft": ("MSFT", "L3"),
            "msft": ("MSFT", "L3"),
            "google": ("GOOGL", "L3"),
            "alphabet": ("GOOGL", "L3"),
            "googl": ("GOOGL", "L3"),
            "meta": ("META", "L3"),
            "facebook": ("META", "L3"),
            "apple": ("AAPL", "L5"),
            "aapl": ("AAPL", "L5"),
            "amazon": ("AMZN", "L3"),
            "aws": ("AMZN", "L3"),
            "amd": ("AMD", "L2"),
            "intel": ("INTC", "L2"),
            "broadcom": ("AVGO", "L2"),
            "avgo": ("AVGO", "L2"),
            "marvell": ("MRVL", "L2"),
            "tsmc": ("TSM", "L1"),
            "taiwan semiconductor": ("TSM", "L1"),
            "asml": ("ASML", "L1"),
            "smic": ("688981.SH", "L1"),  # Prefer A-share (688981.SH) per AGENTS.md §Critical Implementation Notes #4
            "中芯国际": ("688981.SH", "L1"),
            "cambricon": ("688256.SH", "L1"),
            "寒武纪": ("688256.SH", "L1"),
            "innolight": ("300308.SZ", "L2"),
            "中际旭创": ("300308.SZ", "L2"),
            "eoptolink": ("300502.SZ", "L2"),
            "新易盛": ("300502.SZ", "L2"),
            "supermicro": ("SMCI", "L2"),
            "super micro": ("SMCI", "L2"),
            "smci": ("SMCI", "L2"),
            "vertiv": ("VRT", "L2"),
            "palantir": ("PLTR", "L5"),
            "pltr": ("PLTR", "L5"),
            "servicenow": ("NOW", "L5"),
            "salesforce": ("CRM", "L5"),
            "constellation energy": ("CEG", "L3"),
            "constellation": ("CEG", "L3"),
            "vistra": ("VST", "L3"),
            "openai": ("OPENAI", "L4"),
            "anthropic": ("ANTHROPIC", "L4"),
            "deepseek": ("DEEPSEEK", "L4"),
            "alibaba": ("BABA", "L3"),
            "aliyun": ("BABA", "L3"),
            "baba": ("BABA", "L3"),
            "tencent": ("0700.HK", "L3"),
            "baidu": ("BIDU", "L4"),
            "bidu": ("BIDU", "L4"),
            "micron": ("MU", "L2"),
            "qualcomm": ("QCOM", "L2"),
            "cohere": ("COHERE", "L4"),
        }
        self._ticker_map.update(custom_aliases)

    def classify(self, title: str, summary: str = "", url: str = "") -> dict[str, Any]:
        """Classify article into tickers, layers, themes, and sentiment."""
        full_text = f"{title} {summary}".lower()

        # 1. Ticker and Layer Extraction
        matched_tickers: set[str] = set()
        matched_layers: set[str] = set()

        has_tech_context = bool(
            re.search(
                r"\b(tech|technology|ai|artificial intelligence|chips?|semiconductors?|"
                r"cloud|software|shares|stock|nasdaq|earnings|revenue|datacenters?|"
                r"data centers?|investors?|iphone|ipad|mac)\b",
                full_text,
            )
        )

        for alias, (tk, layer) in self._ticker_map.items():
            # Disambiguate common English everyday words
            if alias in ("apple", "arm", "now", "open") and not has_tech_context:
                continue

            # Use whole-word boundary matching
            pattern = rf"\b{re.escape(alias)}\b"
            if re.search(pattern, full_text):
                matched_tickers.add(tk)
                matched_layers.add(layer)

        # 2. Theme Tagging
        matched_themes: list[ThemeTag] = []
        for theme, kw_list in _THEME_KEYWORDS.items():
            if any(re.search(rf"\b{re.escape(kw)}\b", full_text) for kw in kw_list):
                matched_themes.append(theme)

        # Fallback theme if generic AI news
        if not matched_themes and re.search(r"\b(ai|artificial intelligence|tech|technology|chips?|semiconductor)\b", full_text):
            matched_themes.append("General_AI_Tech")

        # Fallback layer inference from text if no ticker matched directly
        if not matched_layers:
            if re.search(r"\b(foundry|wafer|lithography|euv|packaging|cowos)\b", full_text):
                matched_layers.add("L1")
            elif re.search(r"\b(gpus?|opticals?|transceivers?|accelerators?|servers?|liquid cooling)\b", full_text):
                matched_layers.add("L2")
            elif re.search(r"\b(datacenters?|data centers?|cloud|power grid|nuclear|utility)\b", full_text):
                matched_layers.add("L3")
            elif re.search(r"\b(llms?|large language models?|foundation models?|deepseek|chatgpt)\b", full_text):
                matched_layers.add("L4")
            elif re.search(r"\b(software seats?|saas|enterprise apps?|agentic workflows?)\b", full_text):
                matched_layers.add("L5")

        # 3. Sentiment Analysis — word-bounded, not substring matching
        bull_count = sum(1 for rx in _BULLISH_RE if rx.search(full_text))
        bear_count = sum(1 for rx in _BEARISH_RE if rx.search(full_text))

        sentiment_score = 0.0
        if bull_count > bear_count:
            sentiment_label: SentimentLabel = "Bullish"
            sentiment_score = min(1.0, 0.25 + 0.15 * (bull_count - bear_count))
        elif bear_count > bull_count:
            sentiment_label = "Bearish"
            sentiment_score = max(-1.0, -0.25 - 0.15 * (bear_count - bull_count))
        else:
            sentiment_label = "Neutral"
            sentiment_score = 0.0

        # 4. Relevance Score (0.0 to 1.0)
        has_ai_context = bool(
            re.search(
                r"\b(ai|artificial intelligence|nvidia|chips?|semiconductors?|datacenters?|data centers?)\b",
                full_text,
            )
        )
        relevance = 0.0
        if matched_themes:
            relevance += 0.40
        if has_ai_context:
            relevance += 0.30
        if matched_tickers:
            if matched_themes or has_ai_context:
                relevance += 0.30
            else:
                relevance += 0.10
        relevance = min(1.0, relevance)

        return {
            "tickers": sorted(matched_tickers),
            "layers": sorted(matched_layers),
            "themes": matched_themes,
            "relevance_score": round(relevance, 2),
            "sentiment_label": sentiment_label,
            "sentiment_score": round(sentiment_score, 2),
        }
