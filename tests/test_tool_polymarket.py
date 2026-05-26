"""
test_tool_polymarket.py
-----------------------
Tests src/tools/polymarket.py (prediction markets from Polymarket).
Run from project root:
    uv run python tests/test_tool_polymarket.py
"""

from dotenv import load_dotenv
load_dotenv()

TICKER = "AAPL"

print(f"\n{'='*60}")
print(f"  polymarket.py tool — {TICKER}")
print(f"{'='*60}\n")

from src.tools.polymarket import fetch_polymarket_events

data = fetch_polymarket_events(TICKER, limit=5)

print(f"  Symbol:      {data.symbol}")
print(f"  Success:     {data.success}")
print(f"  Total Events:{data.count}")

if data.error:
    print(f"  Error:       {data.error}")

if data.events:
    print()
    print(f"  {'─'*56}")
    print(f"  Events (Latest First):")
    print(f"  {'─'*56}")

    for i, event in enumerate(data.events[:5], 1):
        print(f"\n  [{i}] {event.title}")
        print(f"      Slug:         {event.slug}")
        print(f"      Open Interest:{event.open_interest:,.2f}")
        print(f"      Updated:      {event.updated_at}")
        print(f"      Markets:      {len(event.markets)} market(s)")

        if event.description:
            desc_preview = event.description[:60].replace("\n", " ")
            print(f"      Desc:         {desc_preview}...")

        if event.markets:
            print(f"\n      {'·'*52}")
            print(f"      Markets:")
            print(f"      {'·'*52}")
            for j, market in enumerate(event.markets, 1):
                print(f"\n      [{i}.{j}] {market.question}")
                outcomes_str = " / ".join(market.outcomes) if market.outcomes else "Yes / No"
                print(f"             Outcomes:    {outcomes_str}")
                print(f"             Prob Yes:    {market.prob_yes:.1%}")
                print(f"             Prob No:     {market.prob_no:.1%}")
                print(f"             Volume:      {market.volume:,.2f}")
                print(f"             Open Int:    {market.open_interest:,.2f}")
                print(f"             Liquidity:   {market.liquidity:,.2f}")
                print(f"             Confidence:  {market.confidence:.2%}")

# Quick validation
first_event = data.events[0] if data.events else None
first_market = first_event.markets[0] if first_event and first_event.markets else None

validation = {
    "success": data.success,
    "events_found": len(data.events) > 0,
    "first_event_title": first_event.title if first_event else None,
    "first_market_question": first_market.question if first_market else None,
    "first_market_confidence": first_market.confidence if first_market else None,
    "first_market_prob_yes": first_market.prob_yes if first_market else None,
}

none_fields = [
    k for k, v in validation.items()
    if not v and k not in ["first_market_confidence", "first_market_prob_yes"]
]

print()
if data.error or none_fields:
    if data.error:
        print(f"  ⚠️   Error: {data.error}")
    if none_fields:
        print(f"  ⚠️   Issues: {none_fields}")
else:
    print(f"  ✅  All key fields returned data")
print()