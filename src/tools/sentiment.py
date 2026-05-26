"""
src/tools/sentiment.py
----------------------
Sentiment data fetcher using Polymarket + StockTwits.

Fetches:
  1. Polymarket /events via src.tools.polymarket (per-market probabilities,
     confidence scores, open interest, and liquidity)
  2. StockTwits sentiment via src.tools.stocktwits (bullish/bearish counts
     and recent messages)

Returns:
  SentimentData object ready to be passed to a sentiment analysis agent.
  No scoring, no LLM calls — pure data collection.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pydantic import BaseModel

from src.tools.polymarket import PolymarketData, fetch_polymarket_events
from src.tools.stocktwits import StockTwitsData, fetch_stocktwits_sentiment


class SentimentData(BaseModel):
    """
    Combined sentiment data for a ticker, ready for agent analysis.
    Contains raw Polymarket and StockTwits data — no scoring or decisions.

    polymarket: full PolymarketData with per-market probabilities,
                confidence scores, open interest, and liquidity.
    stocktwits: full StockTwitsData with bullish/bearish counts and
                raw message texts.
    """
    symbol: str
    polymarket: PolymarketData
    stocktwits: StockTwitsData
    fetched_at: str           


def fetch_sentiment_data(ticker: str) -> SentimentData:
    """
    Fetch all sentiment data for a ticker.
    Delegates to src.tools.polymarket and src.tools.stocktwits — no
    duplicate fetching logic lives here.
    No scoring or LLM calls — that is the responsibility of the calling agent.
    """
    ticker = ticker.upper()

    return SentimentData(
        symbol=ticker,
        polymarket=fetch_polymarket_events(ticker),
        stocktwits=fetch_stocktwits_sentiment(ticker),
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )