"""
src/tools/news.py
-----------------
Recent news for a ticker from free RSS feeds (no API key): Yahoo Finance,
Google News and Seeking Alpha.

Articles older than NEWS_MAX_AGE_DAYS, without a date, or that are option
quote pages are dropped; the rest are de-duplicated by URL and normalized
title, sorted newest first and capped at NEWS_MAX_ARTICLES. A failing feed is logged with its stack trace
and listed in failed_sources; the other feeds are still used.
"""

from __future__ import annotations

import re
from calendar import timegm
from datetime import datetime, timedelta, timezone

import feedparser
from pydantic import BaseModel

from .. import config
from ..utils.http import get_text
from ..utils.logger import get_logger

logger = get_logger(__name__)

FEEDS = {
    "Yahoo Finance": "https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US",
    "Google News": "https://news.google.com/rss/search?q={symbol}+stock&hl=en-US&gl=US&ceid=US:en",
    "Seeking Alpha": "https://seekingalpha.com/api/sa/combined/{symbol}.xml",
}


class NewsArticle(BaseModel):
    title: str
    source: str  # publisher when the feed names it, else the feed
    url: str
    published: datetime
    summary: str | None


class NewsFeed(BaseModel):
    symbol: str
    articles: list[NewsArticle]  # newest first
    failed_sources: list[str]


# Option quote pages ("CLS Oct 2026 365.000 call (CLS261023C00365000)") are not
# news; they carry an OCC option symbol: ticker + YYMMDD + C/P + 8-digit strike.
_OPTION_QUOTE = re.compile(r"[A-Z]{1,6}\d{6}[CP]\d{8}")


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _clean(text: str | None) -> str | None:
    if not text:
        return None
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).strip()
    return text[: config.NEWS_SUMMARY_CHARS] or None


def _parse_entry(entry: feedparser.FeedParserDict, feed: str) -> NewsArticle | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed is None or _OPTION_QUOTE.search(entry["title"]):
        return None
    title = entry["title"]
    source = (entry.get("source") or {}).get("title") or feed
    # Google News appends " - Publisher" to titles.
    title = title.removesuffix(f" - {source}")
    summary = _clean(entry.get("summary"))
    # Google News summaries only repeat the title.
    if summary and _normalize(title) in _normalize(summary):
        summary = None
    return NewsArticle(
        title=title,
        source=source,
        url=entry["link"],
        published=datetime.fromtimestamp(timegm(parsed), tz=timezone.utc),
        summary=summary,
    )


def fetch_feed(feed: str, symbol: str) -> list[NewsArticle]:
    """All dated articles from one feed."""
    parsed = feedparser.parse(get_text(FEEDS[feed].format(symbol=symbol)))
    return [a for e in parsed.entries if (a := _parse_entry(e, feed))]


def get_ticker_news(symbol: str) -> NewsFeed:
    symbol = symbol.upper()
    articles: list[NewsArticle] = []
    failed: list[str] = []
    for feed in FEEDS:
        try:
            articles += fetch_feed(feed, symbol)
        except Exception:
            logger.exception(f"News feed {feed} failed for {symbol}")
            failed.append(feed)

    cutoff = datetime.now(timezone.utc) - timedelta(days=config.NEWS_MAX_AGE_DAYS)
    seen: set[str] = set()
    unique = []
    for a in sorted(articles, key=lambda a: a.published, reverse=True):
        keys = {a.url, _normalize(a.title)}
        if a.published >= cutoff and not keys & seen:
            seen |= keys
            unique.append(a)

    return NewsFeed(symbol=symbol, articles=unique[: config.NEWS_MAX_ARTICLES], failed_sources=failed)
