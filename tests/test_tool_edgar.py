"""
test_tool_edgar.py
------------------
Smoke-tests src/tools/edgar.py (SEC EDGAR client).
Run from project root:
    uv run python test_tool_edgar.py

No mocks — hits the real EDGAR API.
EDGAR is free and requires no API key.
Note: free tier is rate-limited; expect ~15-20s runtime.
"""

from dotenv import load_dotenv
load_dotenv()

TICKER = "AAPL"

print(f"\n{'='*60}")
print(f"  edgar.py tool — {TICKER}")
print(f"{'='*60}\n")

from src.tools.edgar import (
    resolve_cik,
    get_company_filings,
    get_latest_filing_summary,
    get_filing_text,
)

# ---------------------------------------------------------------------------
# 1. CIK resolution
# ---------------------------------------------------------------------------

print("── CIK Resolution ──────────────────────────────────────")
cik = resolve_cik(TICKER)
print(f"  CIK ({TICKER}):       {cik}")
print()

# ---------------------------------------------------------------------------
# 2. Company filings metadata
# ---------------------------------------------------------------------------

print("── Company Filings ─────────────────────────────────────")
filings = get_company_filings(TICKER)

print(f"  Company:             {filings.company_name}")
print(f"  CIK:                 {filings.cik}")
print(f"  Symbol:              {filings.symbol}")
print()

if filings.recent_10k:
    print(f"  Latest 10-K:")
    print(f"    Filed:           {filings.recent_10k.filed_date}")
    print(f"    Report Date:     {filings.recent_10k.report_date}")
    print(f"    Accession #:     {filings.recent_10k.accession_number}")
    print(f"    Document URL:    {filings.recent_10k.primary_document}")
else:
    print("  Latest 10-K:       None ⚠️")

print()
print(f"  10-Q filings ({len(filings.recent_10q)} returned, expect up to 4):")
for q in filings.recent_10q:
    print(f"    {q.filed_date}  —  {q.accession_number}")

print()
print(f"  8-K filings ({len(filings.recent_8k)} returned, expect up to 5):")
for k in filings.recent_8k:
    print(f"    {k.filed_date}  —  {k.accession_number}")

print()

# ---------------------------------------------------------------------------
# 3. Latest 10-K summary (metadata + text excerpt)
# ---------------------------------------------------------------------------

print("── Latest 10-K Summary ─────────────────────────────────")
summary_10k = get_latest_filing_summary(TICKER, filing_type="10-K")

if summary_10k:
    print(f"  Company:             {summary_10k.company_name}")
    print(f"  Filing Type:         {summary_10k.filing_type}")
    print(f"  Filed Date:          {summary_10k.filed_date}")
    print(f"  Accession #:         {summary_10k.accession_number}")
    excerpt = summary_10k.text_excerpt or ""
    print(f"  Text Excerpt ({len(excerpt)} chars):")
    print(f"    {excerpt[:300].strip()}...")
else:
    print("  10-K summary:        None ⚠️")

print()

# ---------------------------------------------------------------------------
# 4. Latest 10-Q summary
# ---------------------------------------------------------------------------

print("── Latest 10-Q Summary ─────────────────────────────────")
summary_10q = get_latest_filing_summary(TICKER, filing_type="10-Q")

if summary_10q:
    print(f"  Filed Date:          {summary_10q.filed_date}")
    excerpt = summary_10q.text_excerpt or ""
    print(f"  Text Excerpt ({len(excerpt)} chars):")
    print(f"    {excerpt[:200].strip()}...")
else:
    print("  10-Q summary:        None ⚠️")

print()

# ---------------------------------------------------------------------------
# 5. Filing text extraction (raw)
# ---------------------------------------------------------------------------

print("── Filing Text Extraction ──────────────────────────────")
if filings.recent_10k:
    text = get_filing_text(filings.recent_10k, max_chars=500)
    print(f"  Extracted text ({len(text)} chars, truncated to 500):")
    print(f"    {text[:300].strip()}...")
else:
    print("  Skipped — no 10-K available ⚠️")

print()

# ---------------------------------------------------------------------------
# Quick validation
# ---------------------------------------------------------------------------

none_fields = [
    k for k, v in {
        "cik":                  cik,
        "company_name":         filings.company_name,
        "recent_10k":           filings.recent_10k,
        "recent_10q (count>0)": filings.recent_10q or None,
        "recent_8k (count>0)":  filings.recent_8k or None,
        "10k_filed_date":       filings.recent_10k.filed_date if filings.recent_10k else None,
        "10k_text_excerpt":     summary_10k.text_excerpt if summary_10k else None,
    }.items() if v is None
]

if none_fields:
    print(f"  ⚠️   None / empty fields (data gaps): {none_fields}")
else:
    print(f"  ✅  All key fields returned data")

print()