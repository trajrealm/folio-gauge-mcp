"""
tools/news.py
-------------
News fetcher using free RSS feeds — no API key required.

Sources:
  - Yahoo Finance RSS        (per-ticker feed)
  - Google News RSS          (per-ticker search feed)
  - Reuters RSS              (general market/business feed)
  - Seeking Alpha RSS        (per-ticker feed)
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential


# ---------------------------------------------------------------------------
# Output models
# ---------------------------------------------------------------------------

class NewsArticle(BaseModel):
    title: str
    source: str
    url: str
    published: str | None           # ISO 8601
    summary: str | None             # RSS description snippet


class NewsFeed(BaseModel):
    symbol: str
    articles: list[NewsArticle]
    fetched_at: str                 # ISO 8601 UTC


# ---------------------------------------------------------------------------
# RSS feed URLs
# ---------------------------------------------------------------------------

def _yahoo_rss(symbol: str) -> str:
    return f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US"

def _google_news_rss(symbol: str) -> str:
    return f"https://news.google.com/rss/search?q={symbol}+stock&hl=en-US&gl=US&ceid=US:en"

def _seeking_alpha_rss(symbol: str) -> str:
    return f"https://seekingalpha.com/api/sa/combined/{symbol}.xml"

REUTERS_RSS = "https://feeds.reuters.com/reuters/businessNews"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_date(entry) -> str | None:
    """Extract and normalise publish date from an RSS entry."""
    for attr in ("published", "updated"):
        raw = getattr(entry, attr, None)
        if raw:
            try:
                return parsedate_to_datetime(raw).astimezone(timezone.utc).isoformat()
            except Exception:
                return raw
    return None


def _clean_summary(text: str | None, max_chars: int = 300) -> str | None:
    """Strip HTML tags and truncate summary text."""
    if not text:
        return None
    import re
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars] if len(text) > max_chars else text


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5))
def _fetch_feed(url: str) -> feedparser.FeedParserDict:
    time.sleep(0.1)
    feed = feedparser.parse(url)
    return feed


# ---------------------------------------------------------------------------
# Per-source fetchers
# ---------------------------------------------------------------------------

def _fetch_yahoo(symbol: str, limit: int) -> list[NewsArticle]:
    feed = _fetch_feed(_yahoo_rss(symbol))
    articles = []
    for entry in feed.entries[:limit]:
        articles.append(NewsArticle(
            title=entry.get("title", ""),
            source="Yahoo Finance",
            url=entry.get("link", ""),
            published=_parse_date(entry),
            summary=_clean_summary(entry.get("summary")),
        ))
    return articles


def _fetch_google_news(symbol: str, limit: int) -> list[NewsArticle]:
    feed = _fetch_feed(_google_news_rss(symbol))
    articles = []
    for entry in feed.entries[:limit]:
        articles.append(NewsArticle(
            title=entry.get("title", ""),
            source="Google News",
            url=entry.get("link", ""),
            published=_parse_date(entry),
            summary=_clean_summary(entry.get("summary")),
        ))
    return articles


def _fetch_seeking_alpha(symbol: str, limit: int) -> list[NewsArticle]:
    feed = _fetch_feed(_seeking_alpha_rss(symbol))
    articles = []
    for entry in feed.entries[:limit]:
        articles.append(NewsArticle(
            title=entry.get("title", ""),
            source="Seeking Alpha",
            url=entry.get("link", ""),
            published=_parse_date(entry),
            summary=_clean_summary(entry.get("summary")),
        ))
    return articles


def _fetch_reuters(limit: int) -> list[NewsArticle]:
    feed = _fetch_feed(REUTERS_RSS)
    articles = []
    for entry in feed.entries[:limit]:
        articles.append(NewsArticle(
            title=entry.get("title", ""),
            source="Reuters",
            url=entry.get("link", ""),
            published=_parse_date(entry),
            summary=_clean_summary(entry.get("summary")),
        ))
    return articles


# ---------------------------------------------------------------------------
# Dedup helper
# ---------------------------------------------------------------------------

def _dedup(articles: list[NewsArticle]) -> list[NewsArticle]:
    """Remove duplicate articles by URL, preserve order."""
    seen: set[str] = set()
    result = []
    for a in articles:
        if a.url not in seen:
            seen.add(a.url)
            result.append(a)
    return result


def _sort_by_date(articles: list[NewsArticle]) -> list[NewsArticle]:
    """Sort newest first, articles with no date go to the end."""
    def sort_key(a: NewsArticle):
        if a.published:
            try:
                return datetime.fromisoformat(a.published)
            except Exception:
                pass
        return datetime.min.replace(tzinfo=timezone.utc)

    return sorted(articles, key=sort_key, reverse=True)


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def get_ticker_news(
    symbol: str,
    per_source_limit: int = 5,
    include_reuters: bool = False,
) -> NewsFeed:
    """
    Fetch recent news for a ticker from Yahoo Finance, Google News,
    and Seeking Alpha. Deduplicates and sorts newest-first.

    Args:
        symbol:            Stock ticker (e.g. "AAPL")
        per_source_limit:  Max articles to pull from each source
        include_reuters:   Also include general Reuters business news
    """
    symbol = symbol.upper()
    articles: list[NewsArticle] = []

    articles += _fetch_yahoo(symbol, per_source_limit)
    articles += _fetch_google_news(symbol, per_source_limit)
    articles += _fetch_seeking_alpha(symbol, per_source_limit)

    if include_reuters:
        articles += _fetch_reuters(per_source_limit)

    articles = _dedup(articles)
    articles = _sort_by_date(articles)

    return NewsFeed(
        symbol=symbol,
        articles=articles,
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )


def get_portfolio_news(
    symbols: list[str],
    per_source_limit: int = 3,
) -> dict[str, NewsFeed]:
    """
    Fetch news for multiple tickers. Returns a dict keyed by symbol.
    Keeps per_source_limit low by default to avoid hammering feeds.
    """
    return {
        symbol: get_ticker_news(symbol, per_source_limit=per_source_limit)
        for symbol in symbols
    }


def format_news_for_llm(feed: NewsFeed, max_articles: int = 10) -> str:
    """
    Format a NewsFeed into a compact string suitable for LLM context.
    Each article is one line: [date] SOURCE: Title — Summary
    """
    lines = [f"Recent news for {feed.symbol} (as of {feed.fetched_at[:10]}):"]
    for article in feed.articles[:max_articles]:
        date = article.published[:10] if article.published else "unknown date"
        summary = f" — {article.summary}" if article.summary else ""
        lines.append(f"[{date}] {article.source}: {article.title}{summary}")
    return "\n".join(lines)