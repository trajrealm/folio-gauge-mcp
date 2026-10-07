"""
test_tool_stocktwits.py
-----------------------
Smoke-tests src/tools/stocktwits.py. No API key required.
StockTwits sometimes answers 403 (bot protection); retry later if so.
Run from project root:
    uv run python -m tests.test_tool_stocktwits [TICKER]
"""

import sys

from src.tools.stocktwits import fetch_stocktwits_sentiment, fetch_stocktwits_trending

TICKER = sys.argv[1] if len(sys.argv) > 1 else "AAPL"

print(f"\n== stocktwits.py tool - {TICKER} ==\n")

st = fetch_stocktwits_sentiment(TICKER)
print(f"  bullish={st.bullish} bearish={st.bearish} untagged={st.untagged}")
for m in st.messages[:5]:
    print(f"    - {m[:100]}")
trending = fetch_stocktwits_trending(10)
print(f"\n  Trending: {[t.symbol for t in trending]}\n")

checks = {
    "Posts returned": bool(st.messages),
    "Counts add up": st.bullish + st.bearish + st.untagged == len(st.messages),
    "Trending list returned": bool(trending),
}
for label, ok in checks.items():
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
print()
