"""
test_portfolio_review.py
------------------------
Smoke-tests src/portfolio (CSV loader, facts, review) on tests/data/sample_portfolio.csv.
Requires OPENAI_API_KEY in .env for the review.
Without --analyze, holdings are reviewed without per-ticker analysis (fast).
With --analyze, every holding runs the full per-ticker analysis first (slow).
Run from project root:
    uv run python -m tests.test_portfolio_review [--analyze]
"""

import sys

from dotenv import load_dotenv

load_dotenv()

from src.orchestrator.aggregator import orchestrate_analysis  # noqa: E402
from src.portfolio.loader import load_portfolio_csv  # noqa: E402
from src.portfolio.review import review_portfolio  # noqa: E402

print("\n== portfolio review ==\n")

holdings = load_portfolio_csv("tests/data/sample_portfolio.csv")
results = {h.symbol: orchestrate_analysis(h.symbol) for h in holdings} if "--analyze" in sys.argv else {}
report = review_portfolio(holdings, results)
facts = report.facts

for p in facts.positions:
    print(f"  {p.symbol:<5} {p.position_type:<5} {p.sector or 'Unknown':<24} {p.weight:6.1%}  P&L {p.unrealized_pnl_pct:+.1%}")
print(f"\n  Net exposure {facts.net_exposure:+.0%}, top weight {facts.top_weight:.1%}, HHI {facts.hhi:.2f}")
print(f"  Sectors: {facts.sector_weights}")
print(f"  Concentrated: positions {facts.concentrated_positions}, sectors {facts.concentrated_sectors}\n")
print(f"  Summary: {report.summary}")
print(f"  Risks: {report.risks}")
for a in report.actions:
    print(f"    {a.symbol:<5} {a.action:<5} {a.reason}")
print()

checks = {
    "All holdings loaded": len(holdings) == 6,
    "Weights sum to 1": abs(sum(p.weight for p in facts.positions) - 1) < 1e-9,
    "Short has negative value": all((p.market_value < 0) == (p.position_type == "short") for p in facts.positions),
    "Action per position": {a.symbol for a in report.actions} == {h.symbol for h in holdings},
    "Reason per action": all(a.reason for a in report.actions),
}
for label, ok in checks.items():
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
print()
