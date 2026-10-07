"""
test_tool_sector.py
-------------------
Smoke-tests src/tools/sector.py (yfinance). No API key required.
Run from project root:
    uv run python -m tests.test_tool_sector [TICKER]
"""

import sys

from src.analysts.sector import _format_trend
from src.tools.sector import get_sector_trend

TICKER = sys.argv[1] if len(sys.argv) > 1 else "AAPL"

print(f"\n== sector.py tool - {TICKER} ==\n")

trend = get_sector_trend(TICKER)
print(f"  Sector: {trend.sector} -> {trend.sector_etf}\n")
print(_format_trend(trend))
print()

checks = {
    "Sector ETF mapped": trend.sector_etf is not None,
    "3m sector vs market present": trend.sector_vs_market["return_3m"] is not None,
    "3m stock vs sector present": trend.stock_vs_sector["return_3m"] is not None,
}
for label, ok in checks.items():
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
print()
