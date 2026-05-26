"""
tools/peers.py
--------------
Peer discovery and comparison logic.

Uses:
  - yfinance: Get sector/industry info, fundamental ratios
  - Polygon.io: Fetch related/similar companies

Requires: POLYGON_API_KEY environment variable
"""

from __future__ import annotations

import os
import time
from typing import Optional

import yfinance as yf
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential
import httpx
from .. import config
from ..utils.logger import get_logger

from src.tools.market import get_ticker_snapshot, TickerSnapshot

logger = get_logger(__name__)

class PeerMetrics(BaseModel):
    """Comparison metrics for a peer vs target."""

    symbol: str
    name: str
    sector: str | None
    industry: str | None
    market_cap: float | None
    pe_ratio: float | None
    price_to_book: float | None
    debt_to_equity: float | None
    profit_margin: float | None
    revenue_growth: float | None
    roe: float | None


class PeerComparison(BaseModel):
    """Comparison between target and peers."""

    target_symbol: str
    target_metrics: PeerMetrics
    peers: list[PeerMetrics]
    peer_avg_pe: float | None
    peer_avg_pb: float | None
    peer_avg_debt_equity: float | None
    target_vs_peer_pe: float | None 
    target_vs_peer_pb: float | None
    target_vs_peer_de: float | None


class PeerGroup(BaseModel):
    """Group of peer companies."""

    symbol: str
    sector: str | None
    industry: str | None
    peer_symbols: list[str]
    peer_count: int


def get_sector_industry(symbol: str) -> tuple[str | None, str | None]:
    """
    Get sector and industry for a ticker.
    """
    try:
        ticker = yf.Ticker(symbol.upper())
        info = ticker.info
        return (info.get("sector"), info.get("industry"))
    except Exception as e:
        logger.error(f"Error fetching sector/industry for {symbol}: {e}")
        return (None, None)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5))
def _fetch_polygon_related(symbol: str, limit: int = config.PEERS_LOOKUP_LIMIT) -> list[str]:
    """
    Fetch related/similar companies from Polygon.io API.

    """
    try:
       api_key = os.getenv("POLYGON_API_KEY")
       if not api_key:
           return []

       time.sleep(0.5)

       url = f"https://api.polygon.io/v1/related-companies/{symbol}"
       params = {"apiKey": api_key}

       response = httpx.get(url, params=params, timeout=10)
       response.raise_for_status()

       data = response.json()
       results = data.get("results", [])

       tickers = [item.get("ticker") for item in results if item.get("ticker")]
       return tickers[:limit]
    except Exception as e:
       logger.error(f"Error fetching related companies for {symbol}: {e}")
       return []


def search_competitors(symbol: str, count: int = 5) -> list[str]:
    """
    Search for competitors/related companies using Polygon.io API.
    """
    try:
        # Use Polygon API for related companies
       symbols = _fetch_polygon_related(symbol, limit=count * 2)

       # Filter out the search symbol itself
       symbols = [s for s in symbols if s != symbol.upper()]

       return symbols[:count]
    except Exception as e:
       logger.error(f"Error searching competitors for {symbol}: {e}")
       return []


def get_peer_group(symbol: str, count: int = 5) -> PeerGroup:
    """
    Get a peer group for a ticker using Polygon.io related companies API.
    """
    symbol = symbol.upper()
    sector, industry = get_sector_industry(symbol)

    # Fallback peer lists for well-known tickers
    fallback_peers = {
        "AAPL": ["MSFT", "GOOGL", "AMZN", "NVDA", "META"],
        "MSFT": ["AAPL", "GOOGL", "AMZN", "NVDA", "META"],
        "GOOGL": ["AAPL", "MSFT", "AMZN", "META", "NVDA"],
        "AMZN": ["AAPL", "MSFT", "GOOGL", "NVDA", "META"],
        "NVDA": ["AMD", "QCOM", "INTC", "ASML", "TSM"],
    }

    # Fetch peers from Polygon.io API
    peers = search_competitors(symbol, count=count)

    # Use fallback if no peers found
    if len(peers) < count and symbol in fallback_peers:
        fallback = fallback_peers[symbol]
        peers.extend([p for p in fallback if p not in peers])

    # Deduplicate and limit
    peers = list(dict.fromkeys(peers))[:count]  # Preserve order while deduping

    return PeerGroup(
        symbol=symbol,
        sector=sector,
        industry=industry,
        peer_symbols=peers,
        peer_count=len(peers),
    )

def _extract_peer_metrics(snapshot: TickerSnapshot) -> PeerMetrics:
    """Convert a TickerSnapshot to PeerMetrics."""
    return PeerMetrics(
        symbol=snapshot.profile.symbol,
        name=snapshot.profile.name,
        sector=snapshot.profile.sector,
        industry=snapshot.profile.industry,
        market_cap=snapshot.profile.market_cap,
        pe_ratio=snapshot.fundamentals.pe_ratio,
        price_to_book=snapshot.fundamentals.price_to_book,
        debt_to_equity=snapshot.fundamentals.debt_to_equity,
        profit_margin=snapshot.fundamentals.profit_margin,
        revenue_growth=snapshot.fundamentals.revenue_growth,
        roe=snapshot.fundamentals.return_on_equity,
    )


def get_peer_metrics(peer_symbols: list[str]) -> list[PeerMetrics]:
    """
    Fetch metrics for a list of peer symbols.
    """
    metrics = []

    for symbol in peer_symbols:
        try:
            snapshot = get_ticker_snapshot(symbol)
            metrics.append(_extract_peer_metrics(snapshot))
        except Exception as e:
            logger.error(f"Error fetching metrics for peer {symbol}: {e}")

    return metrics


def _avg_metric(metrics: list[PeerMetrics], attribute: str) -> float | None:
    """
    Calculate average of a metric across peers.
    Ignores None values.
    """
    values = [
        getattr(m, attribute) for m in metrics if getattr(m, attribute) is not None
    ]

    if not values:
        return None

    return sum(values) / len(values)


def compare_to_peers(symbol: str, peer_count: int = 5) -> PeerComparison:
    """
    Compare target company to its peers.

    """
    symbol = symbol.upper()

    # Get target metrics
    target_snapshot = get_ticker_snapshot(symbol)
    target_metrics = _extract_peer_metrics(target_snapshot)

    # Get peer group
    peer_group = get_peer_group(symbol, count=peer_count)

    # Get peer metrics
    peer_metrics = get_peer_metrics(peer_group.peer_symbols)

    # Calculate averages
    peer_avg_pe = _avg_metric(peer_metrics, "pe_ratio")
    peer_avg_pb = _avg_metric(peer_metrics, "price_to_book")
    peer_avg_de = _avg_metric(peer_metrics, "debt_to_equity")

    # Calculate differences (target vs peer avg)
    target_vs_peer_pe = None
    if target_metrics.pe_ratio is not None and peer_avg_pe is not None:
        target_vs_peer_pe = target_metrics.pe_ratio - peer_avg_pe

    target_vs_peer_pb = None
    if target_metrics.price_to_book is not None and peer_avg_pb is not None:
        target_vs_peer_pb = target_metrics.price_to_book - peer_avg_pb

    target_vs_peer_de = None
    if target_metrics.debt_to_equity is not None and peer_avg_de is not None:
        target_vs_peer_de = target_metrics.debt_to_equity - peer_avg_de

    return PeerComparison(
        target_symbol=symbol,
        target_metrics=target_metrics,
        peers=peer_metrics,
        peer_avg_pe=peer_avg_pe,
        peer_avg_pb=peer_avg_pb,
        peer_avg_debt_equity=peer_avg_de,
        target_vs_peer_pe=target_vs_peer_pe,
        target_vs_peer_pb=target_vs_peer_pb,
        target_vs_peer_de=target_vs_peer_de,
    )


def score_peer_position(comparison: PeerComparison) -> dict:
    """
    Score how a company is positioned vs its peers.

    Returns dict with:
      - valuation_score: 1-5 (1=expensive, 5=cheap vs peers)
      - quality_score: 1-5 (1=weak, 5=strong fundamentals vs peers)
      - overall_score: 1-5

    """
    scores = []

    # Valuation: if PE is lower than peers, that's better (cheaper)
    if comparison.target_vs_peer_pe is not None:
        # Positive value means expensive vs peers
        valuation_score = max(1, min(5, 3 - (comparison.target_vs_peer_pe / 10)))
        scores.append(("valuation", valuation_score))

    # Quality: ROE, profit margin, revenue growth
    target = comparison.target_metrics
    peers = comparison.peers

    if target.roe is not None and peers:
        peer_roes = [p.roe for p in peers if p.roe is not None]
        if peer_roes:
            avg_roe = sum(peer_roes) / len(peer_roes)
            # Higher ROE is better
            if target.roe > avg_roe:
                quality_score = min(5, 2.5 + (target.roe - avg_roe) / avg_roe)
            else:
                quality_score = max(1, 2.5 - (avg_roe - target.roe) / avg_roe)
            scores.append(("quality", quality_score))

    if not scores:
        return {
            "valuation_score": None,
            "quality_score": None,
            "overall_score": None,
        }

    avg_score = sum(s[1] for s in scores) / len(scores)

    result = {s[0] + "_score": s[1] for s in scores}
    result["overall_score"] = avg_score

    return result
