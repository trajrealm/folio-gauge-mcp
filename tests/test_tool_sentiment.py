"""
test_tool_sentiment.py
----------------------
Tests src/tools/sentiment.py (Polymarket + StockTwits data fetcher).
Run from project root:
    uv run python tests/test_tool_sentiment.py
"""

from dotenv import load_dotenv
load_dotenv()

TICKER = "AAPL"

print(f"\n{'='*60}")
print(f"  sentiment.py tool — {TICKER}")
print(f"{'='*60}\n")

from src.tools.sentiment import fetch_sentiment_data
# polymarket: PolymarketData  (from src.tools.polymarket)
# stocktwits: StockTwitsData  (from src.tools.stocktwits)

data = fetch_sentiment_data(TICKER)

print(f"  Symbol:      {data.symbol}")
print(f"  Fetched At:  {data.fetched_at}")

# ---------------------------------------------------------------------------
# Polymarket section
# ---------------------------------------------------------------------------

pm = data.polymarket
print(f"\n  {'─'*56}")
print(f"  Polymarket")
print(f"  {'─'*56}")
print(f"  Success:     {pm.success}")
print(f"  Events Found:{pm.count}")

if pm.error:
    print(f"  Error:       {pm.error}")

if pm.events:
    print()
    for i, event in enumerate(pm.events[:5], 1):
        print(f"  [{i}] {event.title}")
        print(f"       Open Interest: {event.open_interest:,.2f}")
        print(f"       Updated:       {event.updated_at}")
        print(f"       Markets:       {len(event.markets)} market(s)")

        if event.markets:
            for j, market in enumerate(event.markets[:2], 1):
                outcomes_str = " / ".join(market.outcomes) if market.outcomes else "Yes / No"
                print(f"\n       [{i}.{j}] {market.question}")
                print(f"              Outcomes:   {outcomes_str}")
                print(f"              Prob Yes:   {market.prob_yes:.1%}")
                print(f"              Prob No:    {market.prob_no:.1%}")
                print(f"              Volume:     {market.volume:,.2f}")
                print(f"              Liquidity:  {market.liquidity:,.2f}")
                print(f"              Confidence: {market.confidence:.2%}")
        print()

# ---------------------------------------------------------------------------
# StockTwits section
# ---------------------------------------------------------------------------

st = data.stocktwits
print(f"  {'─'*56}")
print(f"  StockTwits")
print(f"  {'─'*56}")
print(f"  Success:     {st.success}")
print(f"  Total Msgs:  {st.total}")

if st.error:
    print(f"  Error:       {st.error}")

if st.total > 0:
    bullish_pct = (st.bullish / st.total) * 100
    bearish_pct = (st.bearish / st.total) * 100
    neutral_pct  = (st.neutral / st.total) * 100
    print(f"  Bullish:     {bullish_pct:.0f}% ({st.bullish})")
    print(f"  Bearish:     {bearish_pct:.0f}% ({st.bearish})")
    print(f"  Neutral:     {neutral_pct:.0f}% ({st.neutral})")

if st.messages:
    print(f"\n  Recent Messages (up to 5):")
    for msg in st.messages[:5]:
        print(f"    • {msg[:100]}")

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

first_event  = pm.events[0] if pm.events else None
first_market = first_event.markets[0] if first_event and first_event.markets else None

validation = {
    "success_polymarket":        pm.success,
    "success_stocktwits":        st.success,
    "polymarket_events_found":   pm.count > 0,
    "stocktwits_messages_found": st.total > 0,
    "first_market_has_probs":    first_market is not None and first_market.prob_yes > 0,
    "first_market_has_confidence": first_market is not None and first_market.confidence > 0,
    "fetched_at_present":        bool(data.fetched_at),
    "symbol_correct":            data.symbol == TICKER,
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