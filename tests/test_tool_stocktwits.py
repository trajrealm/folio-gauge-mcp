"""
test_tool_stocktwits.py
-----------------------
Tests src/tools/stocktwits.py (StockTwits retail sentiment fetcher).
Run from project root:
    uv run python tests/test_tool_stocktwits.py
"""

from dotenv import load_dotenv
load_dotenv()

TICKER = "AAPL"

print(f"\n{'='*60}")
print(f"  stocktwits.py tool — {TICKER}")
print(f"{'='*60}\n")

from src.tools.stocktwits import fetch_stocktwits_sentiment

data = fetch_stocktwits_sentiment(TICKER)

print(f"  Symbol:      {data.symbol}")
print(f"  Success:     {data.success}")
print(f"  Total Msgs:  {data.total}")

if data.error:
    print(f"  Error:       {data.error}")

# ---------------------------------------------------------------------------
# Sentiment breakdown
# ---------------------------------------------------------------------------

if data.total > 0:
    bullish_pct = (data.bullish / data.total) * 100
    bearish_pct = (data.bearish / data.total) * 100
    neutral_pct = (data.neutral / data.total) * 100

    print(f"\n  {'─'*56}")
    print(f"  Sentiment Breakdown")
    print(f"  {'─'*56}")
    print(f"  Bullish:     {bullish_pct:.0f}% ({data.bullish})")
    print(f"  Bearish:     {bearish_pct:.0f}% ({data.bearish})")
    print(f"  Neutral:     {neutral_pct:.0f}% ({data.neutral})")

# ---------------------------------------------------------------------------
# Recent messages
# ---------------------------------------------------------------------------

if data.messages:
    print(f"\n  {'─'*56}")
    print(f"  Recent Messages (up to 5 of {len(data.messages)})")
    print(f"  {'─'*56}")
    for i, msg in enumerate(data.messages[:5], 1):
        print(f"  [{i}] {msg[:100]}")

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

validation = {
    "success":           data.success,
    "messages_found":    data.total > 0,
    "has_message_texts": len(data.messages) > 0,
    "symbol_correct":    data.symbol == TICKER,
    "counts_add_up":     (data.bullish + data.bearish + data.neutral) == data.total,
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