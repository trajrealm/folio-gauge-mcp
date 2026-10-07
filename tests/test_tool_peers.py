"""
test_tool_peers.py
------------------
Smoke-tests src/tools/peers.py (yfinance). No API key required.
Run from project root:
    uv run python -m tests.test_tool_peers [TICKER]
"""

import sys

from src.analysts.peers import _format_comparison
from src.tools.peers import compare_to_peers

TICKER = sys.argv[1] if len(sys.argv) > 1 else "AAPL"

print(f"\n== peers.py tool - {TICKER} ==\n")

comparison = compare_to_peers(TICKER)
profile = comparison.target.profile
print(f"  {profile.name} | sector: {profile.sector} | industry: {profile.industry}\n")
print(_format_comparison(comparison))
print()

checks = {
    "Peers found": bool(comparison.peers),
    "Target not in peers": all(p.profile.symbol != profile.symbol for p in comparison.peers),
    "P/E median present": comparison.medians["pe_ratio"] is not None,
}
for label, ok in checks.items():
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
print()
