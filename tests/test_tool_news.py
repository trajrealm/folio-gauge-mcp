"""
test_tool_news.py
-----------------
Smoke-tests src/tools/news.py (Yahoo Finance, Google News, Seeking Alpha RSS).
No API key required.
Run from project root:
    uv run python -m tests.test_tool_news [TICKER]
"""

import sys
from datetime import datetime, timedelta, timezone

from src import config
from src.tools.news import get_ticker_news

TICKER = sys.argv[1] if len(sys.argv) > 1 else "AAPL"

print(f"\n== news.py tool - {TICKER} ==\n")

feed = get_ticker_news(TICKER)
for a in feed.articles:
    print(f"  {a.published:%Y-%m-%d} | {a.source:<20.20} | {a.title[:80]}")
print(f"\n  Failed feeds: {feed.failed_sources or 'none'}\n")

cutoff = datetime.now(timezone.utc) - timedelta(days=config.NEWS_MAX_AGE_DAYS)
checks = {
    "Articles returned": bool(feed.articles),
    "All feeds succeeded": not feed.failed_sources,
    "Newest first": all(a.published >= b.published for a, b in zip(feed.articles, feed.articles[1:])),
    "Within age window": all(a.published >= cutoff for a in feed.articles),
    "Capped": len(feed.articles) <= config.NEWS_MAX_ARTICLES,
}
for label, ok in checks.items():
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
print()
