"""
test_tool_edgar.py
------------------
Smoke-tests src/tools/edgar.py against the real SEC EDGAR API.
Requires EDGAR_USER_AGENT and OPENAI_API_KEY (ingest/query) in .env.
Run from project root:
    uv run python -m tests.test_tool_edgar [TICKER]
"""

import sys

from dotenv import load_dotenv

load_dotenv()

from src.tools.edgar import (  # noqa: E402
    get_company_filings,
    get_earnings_facts,
    get_latest_filing_summary,
    ingest_filings,
    query_filings,
    resolve_cik,
)

TICKER = sys.argv[1] if len(sys.argv) > 1 else "AAPL"

print(f"\n== edgar.py tool - {TICKER} ==\n")

print("-- CIK --")
cik = resolve_cik(TICKER)
print(f"  {cik}\n")

print("-- Filings --")
filings = get_company_filings(TICKER)
print(f"  Company: {filings.company_name}")
if filings.recent_10k:
    print(f"  10-K: {filings.recent_10k.filed_date}  {filings.recent_10k.url}")
for q in filings.recent_10q:
    print(f"  10-Q: {q.filed_date}  {q.accession_number}")
for k in filings.recent_8k:
    print(f"  8-K (earnings): {k.filed_date}  {k.accession_number}")
print()

print("-- XBRL earnings facts (last 4 periods) --")
facts = get_earnings_facts(TICKER)
for label, data in (("annual", facts.annual), ("quarterly", facts.quarterly)):
    for metric, series in data.items():
        print(f"  {label:<9} {metric:<20} {dict(sorted(series.items())[-4:])}")
print()

print("-- Latest 10-K excerpt --")
summary = get_latest_filing_summary(TICKER, "10-K")
excerpt = (summary.text_excerpt or "") if summary else ""
print(f"  {len(excerpt)} chars: {excerpt[:200]}...\n")

print("-- Ingest (MD&A + earnings press releases) --")
print(f"  Filings in index: {len(ingest_filings(TICKER))}\n")

print("-- Query --")
for filing_type in ("10-K", "10-Q", "8-K"):
    result = query_filings(TICKER, "What is the outlook for revenue and margins?", filing_type)
    first = result.answer_chunks[0][:150] if result.answer_chunks else ""
    print(f"  {filing_type}: {len(result.answer_chunks)} chunks  {sorted(set(result.filed_dates))}")
    print(f"    {first}...")
print()

checks = {
    "10-K found": filings.recent_10k is not None,
    "10-Q found": bool(filings.recent_10q),
    "Earnings 8-K found": bool(filings.recent_8k),
    "Annual EPS present": bool(facts.annual.get("eps_diluted")),
    "Quarterly revenue present": bool(facts.quarterly.get("revenue")),
    "10-K excerpt present": bool(excerpt),
}
for label, ok in checks.items():
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
print()
