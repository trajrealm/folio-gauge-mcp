"""
tools/edgar.py
--------------
SEC EDGAR REST API client — no API key required.
Base URL: https://data.sec.gov

Endpoints used:
  - /submissions/{cik}.json        → company metadata + filing history
  - /api/xbrl/companyfacts/{cik}.json → structured financial facts

EDGAR rate limit: max 10 req/sec. We stay well below that with tenacity.

Vector DB:
  - ChromaDB (local, persistent) for storing filing chunks
  - OpenAI text-embedding-3-small for embeddings
  - query_filings() is the main entry point for the edgar analyst
"""

from __future__ import annotations

import os
import re
import time
from typing import Literal

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

from qdrant_client import QdrantClient
import hashlib
from qdrant_client.models import (
    Filter,
    FieldCondition,
    MatchValue,
    PointStruct,
    Distance,
    VectorParams,
)
from .. import config
from ..utils.logger import get_logger

logger = get_logger(__name__)

HEADERS = {
    "User-Agent": f"{config.EDGAR_USER_AGENT}",
    "Accept-Encoding": "gzip, deflate",
}
FILING_TYPES = Literal["10-K", "10-Q", "8-K"]


# Vector DB settings
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))


class FilingMeta(BaseModel):
    symbol: str
    cik: str
    filing_type: str
    filed_date: str
    report_date: str | None
    accession_number: str
    primary_document: str | None
    description: str | None


class FilingSummary(BaseModel):
    symbol: str
    cik: str
    company_name: str
    filing_type: str
    filed_date: str
    accession_number: str
    text_excerpt: str | None


class CompanyFilings(BaseModel):
    symbol: str
    cik: str
    company_name: str
    recent_10k: FilingMeta | None
    recent_10q: list[FilingMeta]
    recent_8k: list[FilingMeta]


class AllFilingsSummary(BaseModel):
    symbol: str
    cik: str
    company_name: str
    filing_10k: FilingSummary | None
    filing_10q: FilingSummary | None
    filings_8k: list[FilingSummary]


class FilingQueryResult(BaseModel):
    """Result of a vector DB query against filing chunks."""

    symbol: str
    question: str
    answer_chunks: list[str]
    filing_types: list[str]
    filed_dates: list[str]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
def _get(url: str) -> dict:
    """GET with retry and polite rate limiting."""
    time.sleep(0.15)  # stay well under 15 req/sec
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

    soup = BeautifulSoup(response.text, "xml")
    company_info = soup.find("company-info")
    if not company_info:
        # Fallback: if the search endpoint doesn't return company-info, try the ticker mapping JSON
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


def _build_filing_url(
    cik: str, accession_number: str, primary_doc: str | None
) -> str | None:
    if not primary_doc:
        return None
    acc_clean = accession_number.replace("-", "")
    cik_stripped = str(int(cik))
    return f"https://www.sec.gov/Archives/edgar/data/{cik_stripped}/{acc_clean}/{primary_doc}"


def get_company_filings(symbol: str) -> CompanyFilings:
    """
    Fetch recent 10-K, 10-Q, and 8-K filings for a ticker.
    Returns structured metadata — does NOT download full text.
    """
    cik = resolve_cik(symbol)
    data = _get(f"{config.EDGAR_BASE_URL}/submissions/CIK{cik}.json")

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
    Pass max_chars=0 for no truncation (used by vector DB ingestion).
    """
    if not filing.primary_document:
        return ""

    html = _get_text(filing.primary_document)
    soup = BeautifulSoup(html, "lxml-xml")

    for tag in soup(["script", "style", "table"]):
        tag.decompose()

    text = soup.get_text(separator=" ")

    text = re.sub(r"\s+", " ", text).strip()

    if max_chars and max_chars > 0:
        return text[:max_chars]
    return text


def get_latest_filing_summary(
    symbol: str, filing_type: config.FILING_TYPES = "10-K"
) -> FilingSummary | None:
    """
    Convenience: get the most recent filing of a given type + a text excerpt.
    This is the main function the legacy agent will call.
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

    excerpt = get_filing_text(filing)

    return FilingSummary(
        symbol=symbol.upper(),
        cik=filings.cik,
        company_name=filings.company_name,
        filing_type=filing_type,
        filed_date=filing.filed_date,
        accession_number=filing.accession_number,
        text_excerpt=excerpt or None,
    )


def get_all_recent_filings_summary(symbol: str) -> AllFilingsSummary:
    """
    Fetch text excerpts for:
      - Most recent 10-K
      - Most recent 10-Q
      - Last 3 8-Ks
    """
    filings = get_company_filings(symbol)

    def to_summary(filing: FilingMeta) -> FilingSummary:
        excerpt = get_filing_text(filing)
        return FilingSummary(
            symbol=symbol.upper(),
            cik=filings.cik,
            company_name=filings.company_name,
            filing_type=filing.filing_type,
            filed_date=filing.filed_date,
            accession_number=filing.accession_number,
            text_excerpt=excerpt or None,
        )

    # 10-K
    filing_10k = to_summary(filings.recent_10k) if filings.recent_10k else None

    # 10-Q
    filing_10q = to_summary(filings.recent_10q[0]) if filings.recent_10q else None

    # Last 3 8-Ks
    filings_8k = [to_summary(f) for f in filings.recent_8k[:3]]

    return AllFilingsSummary(
        symbol=symbol.upper(),
        cik=filings.cik,
        company_name=filings.company_name,
        filing_10k=filing_10k,
        filing_10q=filing_10q,
        filings_8k=filings_8k,
    )


def _get_qdrant_client():
    """
    Get a Qdrant client connected to the local self-hosted instance.
    Creates the collection if it doesn't exist yet.
    """
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

    # Create collection if it doesn't exist
    existing = [c.name for c in client.get_collections().collections]
    if config.EDGAR_QDRANT_COLLECTION not in existing:
        client.create_collection(
            collection_name=config.EDGAR_QDRANT_COLLECTION,
            vectors_config=VectorParams(
                size=config.EDGAR_EMBEDDING_DIMENSION,
                distance=Distance.COSINE,
            ),
        )

    return client


def _embed(texts: list[str]) -> list[list[float]]:
    """
    Embed a list of texts using OpenAI text-embedding-3-small.
    """
    from openai import OpenAI

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    response = client.embeddings.create(
        model=config.EDGAR_EMBEDDING_MODEL,
        input=texts,
    )

    return [item.embedding for item in response.data]


def _chunk_text(
    text: str, chunk_size: int = config.EDGAR_CHUNK_SIZE, overlap: int = config.EDGAR_CHUNK_OVERLAP
) -> list[str]:
    """
    Split text into overlapping chunks.
    """
    if not text:
        return []

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        # If not at the end, try to break at a sentence boundary
        if end < len(text):
            # Look for a period/newline within the last 100 chars of the chunk
            boundary = text.rfind(". ", start, end)
            if boundary != -1 and boundary > start + chunk_size // 2:
                end = boundary + 1  # include the period

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        # Move forward by chunk_size - overlap
        start += chunk_size - overlap

    return chunks


def ingest_filings(symbol: str) -> dict:
    """
    Download full text of recent filings for a ticker, chunk them,
    embed via OpenAI, and store in Qdrant.

    Ingests:
      - Most recent 10-K (full document)
      - Most recent 10-Q (full document)
      - Last 3 8-Ks (full documents)

    Points are upserted so re-ingesting the same filing is idempotent.
    """
    symbol = symbol.upper()
    client = _get_qdrant_client()
    filings = get_company_filings(symbol)

    to_ingest: list[FilingMeta] = []
    if filings.recent_10k:
        to_ingest.append(filings.recent_10k)
    if filings.recent_10q:
        to_ingest.append(filings.recent_10q[0])
    for f in filings.recent_8k[:3]:
        to_ingest.append(f)

    counts: dict[str, int] = {}
    total_chunks = 0

    for filing in to_ingest:
        full_text = get_filing_text(filing, max_chars=0)

        if not full_text:
            logger.warning(f"No text for {symbol} {filing.filing_type} ({filing.filed_date})")
            continue

        chunks = _chunk_text(full_text)
        if not chunks:
            continue

        acc_clean = filing.accession_number.replace("-", "")

        batch_size = 100
        for batch_start in range(0, len(chunks), batch_size):
            batch_chunks = chunks[batch_start : batch_start + batch_size]
            embeddings = _embed(batch_chunks)

            points = []
            for i, (chunk, vector) in enumerate(zip(batch_chunks, embeddings)):
                chunk_idx = batch_start + i

                # Deterministic integer ID from symbol+accession+chunk_idx
                id_str = f"{symbol}_{acc_clean}_{chunk_idx}"
                point_id = int(hashlib.md5(id_str.encode()).hexdigest()[:16], 16) % (
                    2**63
                )

                points.append(
                    PointStruct(
                        id=point_id,
                        vector=vector,
                        payload={
                            "symbol": symbol,
                            "filing_type": filing.filing_type,
                            "filed_date": filing.filed_date,
                            "accession_number": filing.accession_number,
                            "chunk_index": chunk_idx,
                            "text": chunk,
                        },
                    )
                )

            client.upsert(
                collection_name=config.EDGAR_QDRANT_COLLECTION,
                points=points,
            )

        filing_type = filing.filing_type
        counts[filing_type] = counts.get(filing_type, 0) + len(chunks)
        total_chunks += len(chunks)
        logger.info(
            f"Ingested {symbol} {filing_type} ({filing.filed_date}): {len(chunks)} chunks"
        )

    counts["total"] = total_chunks
    return counts


def query_filings(
    symbol: str, question: str, filing_type: str | None = None
) -> FilingQueryResult:
    """
    Query Qdrant for chunks relevant to a question about a ticker's filings.
    """

    symbol = symbol.upper()
    client = _get_qdrant_client()

    # Embed the question
    question_vector = _embed([question])[0]

    # Build metadata filter
    conditions = [FieldCondition(key="symbol", match=MatchValue(value=symbol))]
    if filing_type:
        conditions.append(
            FieldCondition(key="filing_type", match=MatchValue(value=filing_type))
        )

    results = client.query_points(
        collection_name=config.EDGAR_QDRANT_COLLECTION,
        query=question_vector,
        query_filter=Filter(must=conditions),
        limit=config.EDGAR_TOP_K_RESULTS,
        with_payload=True,
    )

    documents = [hit.payload["text"] for hit in results.points]
    filing_types = [hit.payload.get("filing_type", "") for hit in results.points]
    filed_dates = [hit.payload.get("filed_date", "") for hit in results.points]

    return FilingQueryResult(
        symbol=symbol,
        question=question,
        answer_chunks=documents,
        filing_types=filing_types,
        filed_dates=filed_dates,
    )


def is_ingested(symbol: str) -> bool:
    """
    Check whether a ticker has already been ingested into Qdrant.
    """
    try:
        client = _get_qdrant_client()
        results = client.scroll(
            collection_name=config.EDGAR_QDRANT_COLLECTION,
            scroll_filter=Filter(
                must=[
                    FieldCondition(key="symbol", match=MatchValue(value=symbol.upper()))
                ]
            ),
            limit=1,
        )
        return len(results[0]) > 0
    except Exception as e:
        logger.error(f"Error checking if {symbol} ingested: {e}")
        return False


def ingest_if_needed(symbol: str) -> dict:
    """
    Ingest filings only if not already in ChromaDB.
    Safe to call on every analysis run — skips if already done.
    """
    if is_ingested(symbol):
        logger.info(f"{symbol} already ingested — skipping")
        return {"skipped": True}
    return ingest_filings(symbol)
