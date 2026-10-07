"""
test_tool_market.py
-------------------
Smoke-tests src/tools/market.py (yfinance). No API key required.
Run from project root:
    uv run python -m tests.test_tool_market [TICKER]
"""

import sys

from src.tools.market import get_ticker_snapshot

TICKER = sys.argv[1] if len(sys.argv) > 1 else "AAPL"

print(f"\n== market.py tool - {TICKER} ==\n")

snapshot = get_ticker_snapshot(TICKER)

for section in ("profile", "price", "fundamentals", "analysts"):
    print(f"-- {section} --")
    for field, value in getattr(snapshot, section).model_dump().items():
        if field in ("symbol", "description"):
            continue
        print(f"  {field:<22} {value}")
    print()

f = snapshot.fundamentals
checks = {
    "Current price present": snapshot.price.current_price is not None,
    "P/E present": f.pe_ratio is not None,
    "Sector present": snapshot.profile.sector is not None,
    "Margins are fractions (< 1)": f.profit_margin is None or abs(f.profit_margin) < 1,
    "Debt/Equity is a multiple (< 20)": f.debt_to_equity is None or f.debt_to_equity < 20,
    "Dividend yield is a fraction (< 0.2)": (
        snapshot.price.dividend_yield is None or snapshot.price.dividend_yield < 0.2
    ),
}
for label, ok in checks.items():
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
print()
