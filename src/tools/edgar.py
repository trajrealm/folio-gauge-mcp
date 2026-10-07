"""
tools/edgar.py
--------------
SEC EDGAR client - no API key required (a contact User-Agent is).

Endpoints used:
  - /files/company_tickers.json            -> ticker to CIK mapping
  - /submissions/CIK{cik}.json             -> filing history
  - /api/xbrl/companyfacts/CIK{cik}.json   -> structured financials (XBRL)
  - Archives/.../{accession}-index.htm     -> filing index (exhibit lookup)

EDGAR rate limit: max 10 req/sec. Requests are spaced 0.15s apart.

Numbers come from XBRL (get_earnings_facts). Narrative text - MD&A from the
latest 10-K and 10-Q, and the press release (Exhibit 99.1) of recent
earnings 8-Ks - is embedded into a local Qdrant index (ingest_filings) and
searched with query_filings.
"""

from __future__ import annotations

import atexit
import re
import time
import uuid
import warnings
from functools import lru_cache
from typing import Literal

import httpx
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from openai import OpenAI
from pydantic import BaseModel
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchAny,
    MatchValue,
    PointStruct,
    VectorParams,
)
from .. import config
from ..utils.http import retry_transient
from ..utils.logger import get_logger

logger = get_logger(__name__)

FILING_TYPES = Literal["10-K", "10-Q", "8-K"]

_http = httpx.Client(
    headers={"User-Agent": config.EDGAR_USER_AGENT, "Accept-Encoding": "gzip, deflate"},
    timeout=20,
)

# MD&A start and end headings per filing type.
_MDNA_PATTERNS = {
    "10-K": (
        r"item\s*7\.?\s*management.{0,3}s\s+discussion",
        r"item\s*7a\.?\s*quantitative",
    ),
    "10-Q": (
        r"item\s*2\.?\s*management.{0,3}s\s+discussion",
        r"item\s*3\.?\s*quantitative|item\s*4\.?\s*controls",
    ),
}
# A shorter match is a cross-reference (banks often put MD&A in an exhibit).
_MIN_MDNA_CHARS = 2000


class FilingMeta(BaseModel):
    symbol: str
    cik: str
    filing_type: str
    filed_date: str
    report_date: str | None
    accession_number: str
    url: str


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
    recent_8k: list[FilingMeta]  # earnings releases only (8-K item 2.02)


class EarningsFacts(BaseModel):
    """XBRL values keyed by metric, then by SEC frame (CY2025 or CY2025Q3)."""

    symbol: str
    company_name: str
    is_financial: bool  # bank, broker or insurer: cash flow ratios not meaningful
    annual: dict[str, dict[str, float]]
    quarterly: dict[str, dict[str, float]]


class FilingQueryResult(BaseModel):
    """Result of a vector DB query against filing chunks."""

    symbol: str
    question: str
    answer_chunks: list[str]
    filing_types: list[str]
    filed_dates: list[str]


@retry_transient
def _get(url: str) -> dict:
    """GET JSON with retry on transient errors and polite rate limiting."""
    time.sleep(0.15)
    response = _http.get(url)
    response.raise_for_status()
    return response.json()


@retry_transient
def _get_text(url: str) -> str:
    """GET raw text (for HTML filing docs)."""
    time.sleep(0.15)
    response = _http.get(url)
    response.raise_for_status()
    return response.text


@lru_cache(maxsize=1)
def _ticker_map() -> dict[str, str]:
    data = _get("https://www.sec.gov/files/company_tickers.json")
    return {e["ticker"].upper(): str(e["cik_str"]).zfill(10) for e in data.values()}


def resolve_cik(symbol: str) -> str:
    """
    Convert ticker symbol to zero-padded 10-digit CIK using EDGAR's ticker mapping.
    """
    cik = _ticker_map().get(symbol.upper().replace(".", "-"))
    if cik is None:
        raise ValueError(f"Could not resolve CIK for symbol: {symbol}")
    return cik


def get_company_filings(symbol: str) -> CompanyFilings:
    """
    Fetch recent 10-K, 10-Q, and earnings 8-K filings for a ticker.
    Returns structured metadata - does NOT download full text.
    """
    symbol = symbol.upper()
    cik = resolve_cik(symbol)
    data = _get(f"{config.EDGAR_BASE_URL}/submissions/CIK{cik}.json")
    recent = data["filings"]["recent"]

    def build_meta(i: int) -> FilingMeta:
        acc = recent["accessionNumber"][i]
        return FilingMeta(
            symbol=symbol,
            cik=cik,
            filing_type=recent["form"][i],
            filed_date=recent["filingDate"][i],
            report_date=recent["reportDate"][i] or None,
            accession_number=acc,
            url=f"{config.EDGAR_ARCHIVES_URL}/{int(cik)}/{acc.replace('-', '')}/"
            f"{recent['primaryDocument'][i]}",
        )

    recent_10k: FilingMeta | None = None
    recent_10q: list[FilingMeta] = []
    recent_8k: list[FilingMeta] = []

    for i, form in enumerate(recent["form"]):
        if form == "10-K" and recent_10k is None:
            recent_10k = build_meta(i)
        elif form == "10-Q" and len(recent_10q) < config.EDGAR_RECENT_10Q_COUNT:
            recent_10q.append(build_meta(i))
        elif (
            form == "8-K"
            and "2.02" in recent["items"][i]
            and len(recent_8k) < config.EDGAR_RECENT_8K_COUNT
        ):
            recent_8k.append(build_meta(i))

    return CompanyFilings(
        symbol=symbol,
        cik=cik,
        company_name=data["name"],
        recent_10k=recent_10k,
        recent_10q=recent_10q,
        recent_8k=recent_8k,
    )


def get_earnings_facts(symbol: str) -> EarningsFacts:
    """
    Fetch annual and quarterly EPS, revenue, net income and operating cash
    flow from XBRL company facts. SEC frames give one value per period.
    SIC 6000-6499 (banks, brokers, insurers) marks the company as financial.
    Foreign filers (IFRS, 20-F) have no us-gaap facts and return empty dicts.
    """
    symbol = symbol.upper()
    cik = resolve_cik(symbol)
    sic = _get(f"{config.EDGAR_BASE_URL}/submissions/CIK{cik}.json")["sic"]
    data = _get(f"{config.EDGAR_BASE_URL}/api/xbrl/companyfacts/CIK{cik}.json")
    gaap = data["facts"].get("us-gaap", {})

    annual: dict[str, dict[str, float]] = {}
    quarterly: dict[str, dict[str, float]] = {}
    for metric, concepts in config.EDGAR_FACT_CONCEPTS.items():
        candidates = [next(iter(gaap[c]["units"].values())) for c in concepts if c in gaap]
        if not candidates:
            continue
        rows = max(candidates, key=lambda rows: max(r["end"] for r in rows))
        framed = {r["frame"]: r["val"] for r in rows if "frame" in r}
        annual[metric] = {f: v for f, v in framed.items() if re.fullmatch(r"CY\d{4}", f)}
        quarterly[metric] = {f: v for f, v in framed.items() if re.fullmatch(r"CY\d{4}Q\d", f)}

    return EarningsFacts(
        symbol=symbol,
        company_name=data["entityName"],
        is_financial=sic.isdigit() and 6000 <= int(sic) < 6500,
        annual=annual,
        quarterly=quarterly,
    )


def _document_text(url: str) -> str:
    """
    Download an HTML filing document and return plain text.
    Table rows are kept as pipe-delimited text so financial statements survive.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
        soup = BeautifulSoup(_get_text(url), "lxml")

    for tag in soup(["script", "style", "ix:header"]):
        tag.extract()

    for row in reversed(soup.find_all("tr")):
        cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
        cells = [c for c in cells if c]
        row.replace_with(" | ".join(cells) + " ; " if cells else "")

    return re.sub(r"\s+", " ", soup.get_text(separator=" ")).strip()


def get_filing_text(filing: FilingMeta, max_chars: int = config.EDGAR_MAX_CHARS) -> str:
    """
    Plain text of a filing's primary document, truncated to max_chars.
    Pass max_chars=0 for no truncation.
    """
    text = _document_text(filing.url)
    return text[:max_chars] if max_chars else text


def _mdna_section(text: str, filing_type: str) -> str:
    """
    Cut the MD&A section out of 10-K/10-Q text. The last start heading that
    has an end heading after it is the real one (earlier ones are the table
    of contents or cross-references). Falls back to the full text.
    """
    start_re, end_re = _MDNA_PATTERNS[filing_type]
    ends = [m.start() for m in re.finditer(end_re, text, re.I)]
    starts = [m.start() for m in re.finditer(start_re, text, re.I)]
    starts = [s for s in starts if any(e > s for e in ends)]

    if starts:
        start = starts[-1]
        end = next(e for e in ends if e > start)
        if end - start >= _MIN_MDNA_CHARS:
            return text[start:end]

    logger.info(f"MD&A section not found in {filing_type}, using full document")
    return text


def _exhibit_99_1_url(filing: FilingMeta) -> str | None:
    """Find the Exhibit 99.1 (press release) document in a filing's index."""
    index_url = filing.url.rsplit("/", 1)[0] + f"/{filing.accession_number}-index.htm"
    soup = BeautifulSoup(_get_text(index_url), "lxml")
    cell = soup.find("td", string="EX-99.1")
    if cell is None:
        return None
    return "https://www.sec.gov" + cell.find_parent("tr").find("a")["href"]


def _narrative_text(filing: FilingMeta) -> str:
    """MD&A for 10-K/10-Q; the earnings press release for 8-K."""
    if filing.filing_type == "8-K":
        return _document_text(_exhibit_99_1_url(filing) or filing.url)
    return _mdna_section(_document_text(filing.url), filing.filing_type)


def get_latest_filing_summary(
    symbol: str, filing_type: FILING_TYPES = "10-K"
) -> FilingSummary | None:
    """
    Convenience: get the most recent filing of a given type + a text excerpt.
    """
    filings = get_company_filings(symbol)

    filing = {
        "10-K": filings.recent_10k,
        "10-Q": filings.recent_10q[0] if filings.recent_10q else None,
        "8-K": filings.recent_8k[0] if filings.recent_8k else None,
    }[filing_type]
    if not filing:
        return None

    return FilingSummary(
        symbol=filings.symbol,
        cik=filings.cik,
        company_name=filings.company_name,
        filing_type=filing_type,
        filed_date=filing.filed_date,
        accession_number=filing.accession_number,
        text_excerpt=get_filing_text(filing) or None,
    )


@lru_cache(maxsize=1)
def _get_qdrant_client() -> QdrantClient:
    """Local (on-disk) Qdrant client; the collection is created on first use."""
    client = QdrantClient(path=config.QDRANT_PATH)
    # Close before interpreter shutdown; closing in __del__ at exit fails.
    atexit.register(client.close)
    if not client.collection_exists(config.EDGAR_QDRANT_COLLECTION):
        client.create_collection(
            collection_name=config.EDGAR_QDRANT_COLLECTION,
            vectors_config=VectorParams(
                size=config.EDGAR_EMBEDDING_DIMENSION,
                distance=Distance.COSINE,
            ),
        )
    return client


@lru_cache(maxsize=1)
def _get_openai_client() -> OpenAI:
    return OpenAI(max_retries=4)


def _embed(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts using the configured OpenAI embedding model."""
    response = _get_openai_client().embeddings.create(
        model=config.EDGAR_EMBEDDING_MODEL,
        input=texts,
    )
    return [item.embedding for item in response.data]


def _chunk_text(
    text: str,
    chunk_size: int = config.EDGAR_CHUNK_SIZE,
    overlap: int = config.EDGAR_CHUNK_OVERLAP,
) -> list[str]:
    """
    Split text into overlapping chunks, preferring sentence boundaries.
    Each chunk starts `overlap` characters before the previous chunk ended.
    """
    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        if end < len(text):
            boundary = text.rfind(". ", start, end)
            if boundary > start + chunk_size // 2:
                end = boundary + 1

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break

        start = max(end - overlap, start + 1)

    return chunks


def _symbol_filter(symbol: str, **match: str) -> Filter:
    conditions = [FieldCondition(key="symbol", match=MatchValue(value=symbol))]
    conditions += [FieldCondition(key=k, match=MatchValue(value=v)) for k, v in match.items()]
    return Filter(must=conditions)


def _filing_ingested(client: QdrantClient, filing: FilingMeta) -> bool:
    points, _ = client.scroll(
        collection_name=config.EDGAR_QDRANT_COLLECTION,
        scroll_filter=_symbol_filter(filing.symbol, accession_number=filing.accession_number),
        limit=1,
    )
    return len(points) > 0


def _prune_stale_filings(client: QdrantClient, symbol: str, keep_accessions: list[str]) -> None:
    client.delete(
        collection_name=config.EDGAR_QDRANT_COLLECTION,
        points_selector=FilterSelector(
            filter=Filter(
                must=[FieldCondition(key="symbol", match=MatchValue(value=symbol))],
                must_not=[
                    FieldCondition(key="accession_number", match=MatchAny(any=keep_accessions))
                ],
            )
        ),
    )


def ingest_filings(symbol: str) -> int:
    """
    Embed the narrative of recent filings into Qdrant:
      - MD&A of the most recent 10-K and 10-Q
      - press release of the latest earnings 8-Ks (config.EDGAR_NUMBER_8K_IN_SUMMARY)

    Filings already stored are skipped; stored filings no longer in the
    current set are removed. Safe to call on every analysis run.
    Returns the number of filings in the current set.
    """
    symbol = symbol.upper()
    client = _get_qdrant_client()
    filings = get_company_filings(symbol)

    to_ingest = [
        f
        for f in (
            filings.recent_10k,
            filings.recent_10q[0] if filings.recent_10q else None,
            *filings.recent_8k[: config.EDGAR_NUMBER_8K_IN_SUMMARY],
        )
        if f
    ]

    for filing in to_ingest:
        if _filing_ingested(client, filing):
            continue

        chunks = _chunk_text(_narrative_text(filing))
        for batch_start in range(0, len(chunks), config.EDGAR_BATCH_SIZE):
            batch = chunks[batch_start : batch_start + config.EDGAR_BATCH_SIZE]
            client.upsert(
                collection_name=config.EDGAR_QDRANT_COLLECTION,
                points=[
                    PointStruct(
                        id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{filing.accession_number}/{idx}")),
                        vector=vector,
                        payload={
                            "symbol": symbol,
                            "filing_type": filing.filing_type,
                            "filed_date": filing.filed_date,
                            "accession_number": filing.accession_number,
                            "chunk_index": idx,
                            "text": chunk,
                        },
                    )
                    for idx, chunk, vector in zip(
                        range(batch_start, batch_start + len(batch)), batch, _embed(batch)
                    )
                ],
            )
        logger.info(
            f"Ingested {symbol} {filing.filing_type} ({filing.filed_date}): {len(chunks)} chunks"
        )

    if to_ingest:
        _prune_stale_filings(client, symbol, [f.accession_number for f in to_ingest])

    return len(to_ingest)


def query_filings(
    symbol: str, question: str, filing_type: str | None = None
) -> FilingQueryResult:
    """
    Query Qdrant for chunks relevant to a question about a ticker's filings.
    """
    symbol = symbol.upper()
    match = {"filing_type": filing_type} if filing_type else {}

    results = _get_qdrant_client().query_points(
        collection_name=config.EDGAR_QDRANT_COLLECTION,
        query=_embed([question])[0],
        query_filter=_symbol_filter(symbol, **match),
        limit=config.EDGAR_TOP_K_RESULTS,
        with_payload=True,
    )

    return FilingQueryResult(
        symbol=symbol,
        question=question,
        answer_chunks=[hit.payload["text"] for hit in results.points],
        filing_types=[hit.payload["filing_type"] for hit in results.points],
        filed_dates=[hit.payload["filed_date"] for hit in results.points],
    )
