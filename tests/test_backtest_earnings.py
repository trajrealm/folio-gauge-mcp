"""
test_backtest_earnings.py
-------------------------
Smoke-tests src/backtest/earnings.py end to end on a few tickers since 2025:
build, score and evaluate into data/backtest/smoke (cleared first), then
checks that no prompt cites a filing dated after its as_of date.
Requires EDGAR_USER_AGENT and an LLM / embedding key in .env (~3 min, a few cents).
Run from project root:
    uv run python -m tests.test_backtest_earnings [TICKERS]
"""

import re
import shutil
import sys
from datetime import date
from pathlib import Path

from src import config
from src.backtest.earnings import _latest, _read_csv, _read_jsonl, build, evaluate, parse_tickers, score

TICKERS = parse_tickers(sys.argv[1] if len(sys.argv) > 1 else "AAPL,JPM,NVDA")
OUT = Path("data/backtest/smoke")

shutil.rmtree(OUT, ignore_errors=True)
OUT.mkdir(parents=True)

print(f"\n== earnings backtest - {', '.join(TICKERS)} since 2025-01-01 ==\n")
build(TICKERS, date(2025, 1, 1), OUT, workers=3)
score(OUT, workers=8)
evaluate(OUT)

contexts = list(_latest(_read_jsonl(OUT / "contexts.jsonl")).values())
scores = list(_latest(_read_csv(OUT / f"scores_{config.LLM_MODEL_AGENTS.replace('/', '_')}.csv")).values())
built = [c for c in contexts if not c.get("error")]
leaks = [
    (c["symbol"], c["as_of"], cited)
    for c in built
    for cited in re.findall(r"\d{4}-\d{2}-\d{2}", " ".join(re.findall(r"Sources: .*", c["prompt"] or "")))
    if cited > c["as_of"]
]

print(f"  contexts: {len(contexts)} ({len(contexts) - len(built)} failed); scores: {len(scores)}")
print(f"  [{'PASS' if built and len(built) == len(contexts) else 'FAIL'}] Every context built")
print(f"  [{'PASS' if all(c['prompt'] is None or c['prompt'].startswith(f'Today is {c['as_of']}.') for c in built) else 'FAIL'}] Prompt dated as_of")
print(f"  [{'PASS' if not leaks else 'FAIL'}] No filing after as_of cited {leaks[:3]}")
print(f"  [{'PASS' if scores and all(not s['error'] for s in scores) else 'FAIL'}] Every context scored")
print(f"  [{'PASS' if (OUT / f'outcomes_{config.LLM_MODEL_AGENTS.replace("/", "_")}.csv').exists() else 'FAIL'}] Outcomes written")
print()
