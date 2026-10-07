"""
test_tool_polymarket.py
-----------------------
Smoke-tests src/tools/polymarket.py. No API key required.
Most tickers have no non-price markets; JPM or META usually do.
Run from project root:
    uv run python -m tests.test_tool_polymarket [TICKER]
"""

import re
import sys

from src import config
from src.tools.polymarket import fetch_polymarket_markets

TICKER = sys.argv[1] if len(sys.argv) > 1 else "JPM"

print(f"\n== polymarket.py tool - {TICKER} ==\n")

markets = fetch_polymarket_markets(TICKER)
for m in markets:
    print(f"  {m.probability:>5.0%}  {m.question}")
print()

skip = re.compile(config.POLY_SKIP_PATTERN, re.IGNORECASE)
checks = {
    "No price bets kept": not any(skip.search(m.question) for m in markets),
    "Probabilities in 0-1": all(0 <= m.probability <= 1 for m in markets),
}
for label, ok in checks.items():
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
print()
