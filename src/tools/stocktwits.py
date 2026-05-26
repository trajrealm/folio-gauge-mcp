"""
src/tools/stocktwits.py
-----------------------
Fetches retail sentiment data from StockTwits for a given ticker.
Returns structured data only — no analysis or LLM calls.
"""

from __future__ import annotations

import httpx
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential
from typing import Optional
from ..utils.logger import get_logger

logger = get_logger(__name__)

class StockTwitsData(BaseModel):
    """Result from fetching StockTwits sentiment for a ticker."""

    success: bool
    symbol: str
    bullish: int
    bearish: int
    neutral: int
    total: int
    messages: list[str]  
    error: Optional[str] = None


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5))
def fetch_stocktwits_sentiment(ticker: str) -> StockTwitsData:
    """
    Fetch StockTwits sentiment data for a ticker.
    """
    ticker = ticker.upper()

    try:
        url = f"https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"
        response = httpx.get(
            url,
            headers={"User-Agent": "folio-gauge/1.0"},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        messages = data.get("messages", [])

        bullish_count = 0
        bearish_count = 0
        neutral_count = 0
        message_texts = []

        for m in messages:
            text = m.get("body", "")
            message_texts.append(text)

            sentiment = m.get("entities", {}).get("sentiment", {})
            if sentiment:
                basic = sentiment.get("basic")
                if basic == "Bullish":
                    bullish_count += 1
                elif basic == "Bearish":
                    bearish_count += 1
                else:
                    neutral_count += 1
            else:
                neutral_count += 1

        return StockTwitsData(
            success=True,
            symbol=ticker,
            bullish=bullish_count,
            bearish=bearish_count,
            neutral=neutral_count,
            total=len(messages),
            messages=message_texts[:20],
        )

    except Exception as e:
        logger.error(f"Error fetching StockTwits sentiment for {ticker}: {e}")
        return StockTwitsData(
            success=False,
            symbol=ticker,
            bullish=0,
            bearish=0,
            neutral=0,
            total=0,
            messages=[],
            error=str(e),
        )
