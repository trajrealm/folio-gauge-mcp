"""
test_tool_news.py
-----------------
Tests src/tools/news.py (RSS feed parser).
Run from project root:
    uv run python tests/test_tool_news.py
"""

from dotenv import load_dotenv
load_dotenv()

TICKER = "AAPL"

print(f"\n{'='*60}")
print(f"  news.py tool — {TICKER}")
print(f"{'='*60}\n")

from src.tools.news import get_ticker_news

feed = get_ticker_news(TICKER, per_source_limit=3, include_reuters=True)

print(f"  Symbol:        {feed.symbol}")
print(f"  Total Articles: {len(feed.articles)}")
print(f"  Fetched At:     {feed.fetched_at}")

print()
print(f"  {'─'*56}")
print(f"  Articles:")
print(f"  {'─'*56}")

for i, article in enumerate(feed.articles[:5], 1):
    print(f"\n  [{i}] {article.title[:55]}...")
    print(f"      Source:     {article.source}")
    print(f"      Published:  {article.published}")
    print(f"      URL:        {article.url[:50]}...")
    if article.summary:
        summary_preview = article.summary[:60].replace("\n", " ")
        print(f"      Summary:    {summary_preview}...")

# Quick validation
none_fields = [
    k for k, v in {
        "articles_exist": len(feed.articles) > 0,
        "fetched_at": feed.fetched_at,
        "first_article_title": feed.articles[0].title if feed.articles else None,
        "first_article_source": feed.articles[0].source if feed.articles else None,
    }.items() if not v
]

print()
if none_fields:
    print(f"  ⚠️   Issues: {none_fields}")
else:
    print(f"  ✅  All key fields returned data")
print()
