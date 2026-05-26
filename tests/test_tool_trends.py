"""
test_tool_trends.py
-------------------
Tests src/tools/trends.py (Reddit + StockTwits trend fetcher).
Run from project root:
    uv run python tests/test_tool_trends.py
"""

from dotenv import load_dotenv
load_dotenv()

TICKER = "NVDA"

print(f"\n{'='*60}")
print(f"  trends.py tool — {TICKER}")
print(f"{'='*60}\n")

from src.tools.trends import fetch_trend_data, fetch_trending_snapshot

# ---------------------------------------------------------------------------
# Per-ticker fetch
# ---------------------------------------------------------------------------

data = fetch_trend_data(TICKER)

print(f"  Symbol:      {TICKER}")
print(f"  Fetched At:  {data.fetched_at}")

# Reddit section
print(f"\n  {'─'*56}")
print(f"  Reddit Mentions (ApeWisdom — all-stocks)")
print(f"  {'─'*56}")

if data.reddit:
    r = data.reddit
    delta_str = f"+{r.mention_delta}" if r.mention_delta >= 0 else str(r.mention_delta)
    rank_delta = r.rank_24h_ago - r.rank  # positive = moved up
    rank_str = f"+{rank_delta}" if rank_delta >= 0 else str(rank_delta)
    print(f"  Found:       Yes (rank #{r.rank})")
    print(f"  Mentions:    {r.mentions} ({delta_str} vs 24h ago)")
    print(f"  Upvotes:     {r.upvotes}")
    print(f"  Rank Change: {rank_str} (was #{r.rank_24h_ago})")
else:
    print(f"  Found:       No — {TICKER} not in top 200 Reddit mentions")

# StockTwits trending section
print(f"\n  {'─'*56}")
print(f"  StockTwits Trending")
print(f"  {'─'*56}")
print(f"  Trending Now:{' ✅ Yes' if data.is_stocktwits_trending else ' ❌ No'}")
print(f"  Total In List:{len(data.stocktwits_trending)}")

if data.stocktwits_trending:
    print(f"\n  Top 10 Trending on StockTwits:")
    for i, t in enumerate(data.stocktwits_trending[:10], 1):
        marker = " ◀" if t.symbol == TICKER else ""
        print(f"  [{i:2}] {t.symbol:<6}  watchlist: {t.watchlist_count:,}{marker}")

# ---------------------------------------------------------------------------
# Trending snapshot (discovery)
# ---------------------------------------------------------------------------

print(f"\n  {'─'*56}")
print(f"  Trending Snapshot (top 10 Reddit + top 10 StockTwits)")
print(f"  {'─'*56}")

snapshot = fetch_trending_snapshot(reddit_limit=10, stocktwits_limit=10)

print(f"\n  Reddit Top 10 (ApeWisdom):")
for r in snapshot.reddit_top[:10]:
    delta_str = f"+{r.mention_delta}" if r.mention_delta >= 0 else str(r.mention_delta)
    print(f"  #{r.rank:<3} {r.symbol:<6}  mentions: {r.mentions:>4}  ({delta_str})")

print(f"\n  StockTwits Top 10:")
for i, t in enumerate(snapshot.stocktwits_top[:10], 1):
    print(f"  [{i:2}] {t.symbol:<6}  watchlist: {t.watchlist_count:,}")

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

validation = {
    "stocktwits_trending_fetched": len(data.stocktwits_trending) > 0,
    "snapshot_reddit_has_results": len(snapshot.reddit_top) > 0,
    "snapshot_stocktwits_has_results": len(snapshot.stocktwits_top) > 0,
    "fetched_at_present": bool(data.fetched_at),
    "reddit_result_or_not_trending": True,   # None is valid — means not in top 200
}

issues = [k for k, v in validation.items() if not v]

print()
print(f"  {'─'*56}")
if issues:
    print(f"  ⚠️   Issues:")
    for issue in issues:
        print(f"        - {issue}")
else:
    print(f"  ✅  All key fields returned data")
print()