"""
tools/edgar.py
--------------
SEC EDGAR REST API client — no API key required.
Base URL: https://data.sec.gov

Endpoints used:
  - /submissions/{cik}.json        → company metadata + filing history
  - /api/xbrl/companyfacts/{cik}.json → structured financial facts

EDGAR rate limit: max 10 req/sec. We stay well below that with tenacity.
"""

from __future__ import annotations

import re
import time
from typing import Literal

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "https://data.sec.gov"
SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
HEADERS = {
    # EDGAR requires a descriptive User-Agent with contact info
    "User-Agent": "folio-gauge-mcp contact@example.com",
    "Accept-Encoding": "gzip, deflate",
}
FILING_TYPES = Literal["10-K", "10-Q", "8-K"]


# ---------------------------------------------------------------------------
# Output models
# ---------------------------------------------------------------------------

class FilingMeta(BaseModel):
    symbol: str
    cik: str
    filing_type: str
    filed_date: str
    report_date: str | None
    accession_number: str
    primary_document: str | None        # URL to the actual filing document
    description: str | None


class FilingSummary(BaseModel):
    symbol: str
    cik: str
    company_name: str
    filing_type: str
    filed_date: str
    accession_number: str
    text_excerpt: str | None            # first ~2000 chars of filing text


class CompanyFilings(BaseModel):
    symbol: str
    cik: str
    company_name: str
    recent_10k: FilingMeta | None
    recent_10q: list[FilingMeta]        # last 4 quarters
    recent_8k: list[FilingMeta]         # last 5 material events


# ---------------------------------------------------------------------------
# Internal HTTP helpers
# ---------------------------------------------------------------------------

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
def _get(url: str) -> dict:
    """GET with retry and polite rate limiting."""
    time.sleep(0.15)  # stay well under 10 req/sec
    response = httpx.get(url, headers=HEADERS, timeout=15)
    response.raise_for_status()
    return response.json()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
def _get_text(url: str) -> str:
    """GET raw text (for HTML filing docs)."""
    time.sleep(0.15)
    response = httpx.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()
    return response.text


# ---------------------------------------------------------------------------
# CIK resolution
# ---------------------------------------------------------------------------

_cik_cache: dict[str, str] = {}

def resolve_cik(symbol: str) -> str:
    """
    Convert ticker symbol to zero-padded 10-digit CIK.
    Uses EDGAR's company search endpoint — no key needed.
    """
    symbol = symbol.upper()
    if symbol in _cik_cache:
        return _cik_cache[symbol]

    url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company=&CIK={symbol}&type=10-K&dateb=&owner=include&count=5&search_text=&output=atom"
    time.sleep(0.15)
    response = httpx.get(url, headers=HEADERS, timeout=15)
    response.raise_for_status()

    # Parse CIK from the atom feed
    soup = BeautifulSoup(response.text, "xml")
    company_info = soup.find("company-info")
    if not company_info:
        # Fallback: try the ticker→CIK JSON map EDGAR provides
        ticker_data = _get("https://www.sec.gov/files/company_tickers.json")
        for entry in ticker_data.values():
            if entry.get("ticker", "").upper() == symbol:
                cik = str(entry["cik_str"]).zfill(10)
                _cik_cache[symbol] = cik
                return cik
        raise ValueError(f"Could not resolve CIK for symbol: {symbol}")

    cik_tag = company_info.find("cik")
    if not cik_tag:
        raise ValueError(f"CIK tag not found for symbol: {symbol}")

    cik = cik_tag.text.strip().zfill(10)
    _cik_cache[symbol] = cik
    return cik


# ---------------------------------------------------------------------------
# Filing retrieval
# ---------------------------------------------------------------------------

def _build_filing_url(cik: str, accession_number: str, primary_doc: str | None) -> str | None:
    if not primary_doc:
        return None
    acc_clean = accession_number.replace("-", "")
    # Correct EDGAR Archives path — cik without leading zeros
    cik_stripped = str(int(cik))
    return f"https://www.sec.gov/Archives/edgar/data/{cik_stripped}/{acc_clean}/{primary_doc}"


def get_company_filings(symbol: str) -> CompanyFilings:
    """
    Fetch recent 10-K, 10-Q, and 8-K filings for a ticker.
    Returns structured metadata — does NOT download full text.
    """
    cik = resolve_cik(symbol)
    data = _get(f"{BASE_URL}/submissions/CIK{cik}.json")

    company_name = data.get("name", symbol)
    recent = data.get("filings", {}).get("recent", {})

    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    report_dates = recent.get("reportDate", [])
    accessions = recent.get("accessionNumber", [])
    descriptions = recent.get("primaryDocument", [])

    def build_meta(i: int) -> FilingMeta:
        acc = accessions[i]
        primary_doc = descriptions[i] if descriptions else None
        return FilingMeta(
            symbol=symbol.upper(),
            cik=cik,
            filing_type=forms[i],
            filed_date=dates[i],
            report_date=report_dates[i] if report_dates else None,
            accession_number=acc,
            primary_document=_build_filing_url(cik, acc, primary_doc),
            description=None,
        )

    recent_10k: FilingMeta | None = None
    recent_10q: list[FilingMeta] = []
    recent_8k: list[FilingMeta] = []

    for i, form in enumerate(forms):
        if form == "10-K" and recent_10k is None:
            recent_10k = build_meta(i)
        elif form == "10-Q" and len(recent_10q) < 4:
            recent_10q.append(build_meta(i))
        elif form == "8-K" and len(recent_8k) < 5:
            recent_8k.append(build_meta(i))

        # Stop early once we have everything we need
        if recent_10k and len(recent_10q) >= 4 and len(recent_8k) >= 5:
            break

    return CompanyFilings(
        symbol=symbol.upper(),
        cik=cik,
        company_name=company_name,
        recent_10k=recent_10k,
        recent_10q=recent_10q,
        recent_8k=recent_8k,
    )


def get_filing_text(filing: FilingMeta, max_chars: int = 4000) -> str:
    """
    Download and extract plain text from a filing's primary document.
    Strips HTML tags, collapses whitespace, truncates to max_chars.
    Used to feed filing content to the LLM.
    """
    if not filing.primary_document:
        return ""

    html = _get_text(filing.primary_document)
    soup = BeautifulSoup(html, "lxml-xml")

    # Remove noise tags
    for tag in soup(["script", "style", "table"]):
        tag.decompose()

    text = soup.get_text(separator=" ")
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text[:max_chars]


def get_latest_filing_summary(symbol: str, filing_type: FILING_TYPES = "10-K") -> FilingSummary | None:
    """
    Convenience: get the most recent filing of a given type + a text excerpt.
    This is the main function the agent will call.
    """
    filings = get_company_filings(symbol)

    filing: FilingMeta | None = None
    if filing_type == "10-K":
        filing = filings.recent_10k
    elif filing_type == "10-Q":
        filing = filings.recent_10q[0] if filings.recent_10q else None
    elif filing_type == "8-K":
        filing = filings.recent_8k[0] if filings.recent_8k else None

    if not filing:
        return None

    excerpt = get_filing_text(filing, max_chars=3000)

    return FilingSummary(
        symbol=symbol.upper(),
        cik=filings.cik,
        company_name=filings.company_name,
        filing_type=filing_type,
        filed_date=filing.filed_date,
        accession_number=filing.accession_number,
        text_excerpt=excerpt or None,
    )