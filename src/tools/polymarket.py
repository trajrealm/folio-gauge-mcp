"""
src/tools/polymarket.py
-----------------------
Fetches prediction market data from Polymarket for a given ticker.
Returns structured data with probabilities and confidence scores.

Polymarket /events endpoint with tag_slug parameter to get ticker-specific markets.
Orders by updatedAt to get latest predictions first.

Confidence metric combines volume, open interest, and liquidity per market:
    confidence = 0.4 * log1p(volume) + 0.3 * log1p(open_interest) + 0.3 * log1p(liquidity)
"""

from __future__ import annotations

import json
import math
import httpx
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential
from typing import Optional
import traceback
from .. import config
from ..utils.logger import get_logger

logger = get_logger(__name__)


class PolymarketMarket(BaseModel):
    """A single market within a Polymarket event."""

    id: str
    question: str
    outcomes: list[str]  # e.g. ["Yes", "No"] or ["Up", "Down"]
    prob_yes: float  # probability for outcome[0]
    prob_no: float  # probability for outcome[1]
    volume: float
    open_interest: float
    liquidity: float
    confidence: float  # 0-1 score based on volume, open_interest, liquidity


class PolymarketEvent(BaseModel):
    """A Polymarket event containing one or more individual markets."""

    id: str
    title: str
    slug: str
    description: Optional[str] = None
    open_interest: float  # event-level open interest from API
    updated_at: str
    markets: list[PolymarketMarket]


class PolymarketData(BaseModel):
    """Result from fetching Polymarket events for a ticker."""

    success: bool
    symbol: str
    count: int
    events: list[PolymarketEvent]
    error: Optional[str] = None


def _calculate_confidence(
    volume: float, open_interest: float, liquidity: float
) -> float:
    """
    Calculate confidence score based on market metrics.

    Formula: 0.4 * log1p(volume) + 0.3 * log1p(open_interest) + 0.3 * log1p(liquidity)
    Normalized to 0-1 range using a sigmoid-like function.
    """
    try:
        volume = float(volume or 0)
        open_interest = float(open_interest or 0)
        liquidity = float(liquidity or 0)

        score = (
            config.POLY_CONFIDENCE_CALC_WEIGHT[0] * math.log1p(volume)
            + config.POLY_CONFIDENCE_CALC_WEIGHT[1] * math.log1p(open_interest)
            + config.POLY_CONFIDENCE_CALC_WEIGHT[2] * math.log1p(liquidity)
        )

        # Normalize to 0-1 using sigmoid-like transformation
        normalized = 1.0 / (1.0 + math.exp(-score / config.POLY_NORMALIZATION_DIVISOR))
        return min(1.0, max(0.0, normalized))
    except Exception as e:
        logger.error(f"Error calculating confidence score: {e}")
        return 0.5


def _extract_outcome_prices(market: dict) -> list[float]:
    """
    Extract outcome prices from a market object as floats.
    """
    try:
        prices_raw = market.get("outcomePrices", "[]")
        if isinstance(prices_raw, str):
            prices_raw = json.loads(prices_raw)
        if isinstance(prices_raw, list):
            return [float(p) for p in prices_raw]
        return []
    except Exception as e:
        logger.error(f"Error extracting outcome prices: {e}")
        return []


def _extract_outcomes(market: dict) -> list[str]:
    """
    Extract outcome labels from a market object.
    """
    try:
        outcomes_raw = market.get("outcomes", '["Yes", "No"]')
        if isinstance(outcomes_raw, str):
            outcomes_raw = json.loads(outcomes_raw)
        if isinstance(outcomes_raw, list):
            return [str(o) for o in outcomes_raw]
        return ["Yes", "No"]
    except Exception as e:
        logger.error(f"Error extracting outcomes: {e}")
        return ["Yes", "No"]


def _parse_market(
    raw_market: dict, open_interest: float = 0.0
) -> Optional[PolymarketMarket]:
    """
    Parse a raw market dict into a PolymarketMarket.
    Returns None if parsing fails or prices are unavailable.
    """
    try:
        prices = _extract_outcome_prices(raw_market)
        if len(prices) < 2:
            return None

        liquidity = float(raw_market.get("liquidity", 0) or 0)
        volume = float(raw_market.get("volume", 0) or 0)

        return PolymarketMarket(
            id=raw_market.get("id", ""),
            question=raw_market.get("question", ""),
            outcomes=_extract_outcomes(raw_market),
            prob_yes=prices[0],
            prob_no=prices[1],
            volume=volume,
            open_interest=open_interest,
            liquidity=liquidity,
            confidence=_calculate_confidence(volume, open_interest, liquidity),
        )
    except Exception as e:
        logger.error(f"Error parsing market: {e}")
        return None

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5))
def fetch_polymarket_events(ticker: str, limit: int = config.POLY_DEFAULT_EVENT_LIMIT) -> PolymarketData:
    """
    Fetch Polymarket /events for a ticker using tag_slug.
    Orders by updatedAt descending to get latest predictions first.
    Each event contains its markets individually with per-market
    probabilities and confidence scores.
    """
    base_url = "https://gamma-api.polymarket.com"
    ticker = ticker.upper()

    try:
        response = httpx.get(
            f"{base_url}/events",
            params={
                "tag_slug": ticker.lower(),
                "limit": limit,
                "order": "updatedAt",
                "ascending": False,
                "related_tags": True,
                "closed": False,
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        events = []
        if isinstance(data, list):
            for raw_event in data:
                try:
                    raw_markets = raw_event.get("markets", [])

                    # Parse each market individually — no aggregation
                    markets = []
                    if isinstance(raw_markets, list):
                        for raw_market in raw_markets:
                            event_open_interest = float(
                                raw_event.get("openInterest", 0) or 0
                            )
                            market = _parse_market(
                                raw_market, open_interest=event_open_interest
                            )
                            if market is not None:
                                markets.append(market)

                    event = PolymarketEvent(
                        id=raw_event.get("id", ""),
                        title=raw_event.get("title", ""),
                        slug=raw_event.get("slug", ""),
                        description=raw_event.get("description"),
                        open_interest=float(raw_event.get("openInterest", 0) or 0),
                        updated_at=raw_event.get("updatedAt", ""),
                        markets=markets,
                    )
                    events.append(event)
                except Exception as e:
                    logger.error(f"Error parsing polymarket event: {e}")

        return PolymarketData(
            success=True,
            symbol=ticker,
            count=len(events),
            events=events,
        )

    except Exception as e:
        logger.error(f"Error fetching polymarket events for {ticker}: {e}")
        traceback.print_exc()
        return PolymarketData(
            success=False,
            symbol=ticker,
            count=0,
            events=[],
            error=str(e),
        )
