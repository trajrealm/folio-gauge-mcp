"""
test_tool_technical.py
----------------------
Smoke-tests src/tools/technical.py (yfinance). No API key required.
Run from project root:
    uv run python -m tests.test_tool_technical [TICKER]
"""

import sys

from src.tools.technical import get_technical_snapshot

TICKER = sys.argv[1] if len(sys.argv) > 1 else "AAPL"

print(f"\n== technical.py tool - {TICKER} ==\n")

snapshot = get_technical_snapshot(TICKER)
for field, value in snapshot.model_dump().items():
    print(f"  {field:<16} {value}")
print()

checks = {
    "SMA 200 present (enough history)": snapshot.sma_200 is not None,
    "RSI in 0-100": snapshot.rsi_14 is not None and 0 <= snapshot.rsi_14 <= 100,
    "Range position in 0-1": 0 <= snapshot.range_position <= 1,
    "Volume balance in -1..1": snapshot.volume_balance is not None and -1 <= snapshot.volume_balance <= 1,
}
for label, ok in checks.items():
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
print()
