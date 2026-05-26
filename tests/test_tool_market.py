"""
test_tool_market.py
-------------------
Tests src/tools/market.py (yfinance).
Run from project root:
    uv run python test_tool_market.py
"""

from dotenv import load_dotenv
load_dotenv()

TICKER = "AAPL"

print(f"\n{'='*60}")
print(f"  market.py tool — {TICKER}")
print(f"{'='*60}\n")

from src.tools.market import get_ticker_snapshot

snapshot = get_ticker_snapshot(TICKER)

print(f"  Company:         {snapshot.profile.name}")
print(f"  Sector:          {snapshot.profile.sector}")
print(f"  Industry:        {snapshot.profile.industry}")
print(f"  Market Cap:      {snapshot.profile.market_cap:,.0f}" if snapshot.profile.market_cap else "  Market Cap:      None")

print()
print(f"  Current Price:   {snapshot.price.current_price}")
print(f"  Previous Close:  {snapshot.price.previous_close}")
print(f"  52w High:        {snapshot.price.week_52_high}")
print(f"  52w Low:         {snapshot.price.week_52_low}")
print(f"  Avg Volume:      {snapshot.price.average_volume}")
print(f"  Dividend Yield:  {snapshot.price.dividend_yield}")

print()
print(f"  PE Ratio:        {snapshot.fundamentals.pe_ratio}")
print(f"  Forward PE:      {snapshot.fundamentals.forward_pe}")
print(f"  Price/Book:      {snapshot.fundamentals.price_to_book}")
print(f"  Debt/Equity:     {snapshot.fundamentals.debt_to_equity}")
print(f"  ROE:             {snapshot.fundamentals.return_on_equity}")
print(f"  Profit Margin:   {snapshot.fundamentals.profit_margin}")
print(f"  Revenue Growth:  {snapshot.fundamentals.revenue_growth}")
print(f"  Earnings Growth: {snapshot.fundamentals.earnings_growth}")
print(f"  Current Ratio:   {snapshot.fundamentals.current_ratio}")
print(f"  Quick Ratio:     {snapshot.fundamentals.quick_ratio}")

print()
print(f"  Recommendation:  {snapshot.analysts.recommendation}")
print(f"  Target Mean:     {snapshot.analysts.target_mean_price}")
print(f"  Target High:     {snapshot.analysts.target_high_price}")
print(f"  Target Low:      {snapshot.analysts.target_low_price}")
print(f"  # Analysts:      {snapshot.analysts.number_of_analysts}")

# Quick validation
none_fields = [
    k for k, v in {
        "current_price": snapshot.price.current_price,
        "pe_ratio": snapshot.fundamentals.pe_ratio,
        "recommendation": snapshot.analysts.recommendation,
        "52w_high": snapshot.price.week_52_high,
    }.items() if v is None
]

print()
if none_fields:
    print(f"  ⚠️   None fields (data gaps): {none_fields}")
else:
    print(f"  ✅  All key fields returned data")
print()