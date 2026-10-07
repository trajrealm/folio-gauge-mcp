"""
test_tool_apewisdom.py
----------------------
Smoke-tests src/tools/apewisdom.py (Reddit mentions via ApeWisdom). No API key required.
Run from project root:
    uv run python -m tests.test_tool_apewisdom [TICKER]
"""

import sys

from src.tools.apewisdom import fetch_reddit_mentions, fetch_reddit_top

TICKER = sys.argv[1] if len(sys.argv) > 1 else "AAPL"

print(f"\n== apewisdom.py tool - {TICKER} ==\n")

mention = fetch_reddit_mentions(TICKER)
print(f"  {TICKER}: {mention}")
top = fetch_reddit_top(10)
print(f"  Top 10: {[m.symbol for m in top]}\n")

checks = {
    "Top list returned": len(top) == 10,
    "Ticker ranked (WARN only: small caps may not be)": mention is not None,
}
for label, ok in checks.items():
    print(f"  [{'PASS' if ok else 'WARN'}] {label}")
print()
