"""
src/tools/trends.py
-------------------
Trend detection using ApeWisdom (Reddit mentions) + StockTwits trending.

Sources:
  - ApeWisdom API: Reddit mention counts, upvotes, and rank changes across
    r/wallstreetbets, r/stocks, r/investing, r/options, and others.
    No API key required.
  - StockTwits /trending/symbols: tickers trending on StockTwits right now.
    No API key required.

No API key required for either source.
Replaces the previous pytrends + DuckDuckGo approach (pytrends was archived
and is unmaintained as of April 2025; DuckDuckGo HTML scraping is unreliable).
"""

from __future__ import annotations

import httpx
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential
from .. import config
from src.utils.logger import get_logger

logger = get_logger(__name__)

class RedditMention(BaseModel):
    """Reddit mention data for a single ticker from ApeWisdom."""

    symbol: str
    rank: int
    mentions: int
    upvotes: int
    mentions_24h_ago: int
    rank_24h_ago: int
    mention_delta: int


class StockTwitsTrending(BaseModel):
    """A ticker currently trending on StockTwits."""

    symbol: str
    watchlist_count: int


class TrendData(BaseModel):
    """
    Combined trend data for a ticker or set of tickers.
    Ready for agent consumption — no scoring or LLM calls.
    """

    reddit: Optional[RedditMention]
    stocktwits_trending: list[StockTwitsTrending]
    is_stocktwits_trending: bool
    fetched_at: str


class TrendingSnapshot(BaseModel):
    """
    Top trending tickers across Reddit + StockTwits.
    Useful for discovering what to analyse rather than scoring a known ticker.
    """

    reddit_top: list[RedditMention]
    stocktwits_top: list[StockTwitsTrending]
    fetched_at: str


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5))
def fetch_reddit_mentions(
    ticker: str, filter: str = config.REDDIT_FILTER
) -> Optional[RedditMention]:
    """
    Fetch Reddit mention data for a specific ticker from ApeWisdom.
    Searches the first two pages (200 results) of the ranked list.

    ApeWisdom aggregates r/wallstreetbets, r/stocks, r/investing, r/options,
    r/Daytrading, r/SPACs, and others. No API key required.

    """
    ticker = ticker.upper()

    for page in range(1, 3):  # Pages 1 and 2 = up to 200 results
        try:
            response = httpx.get(
                f"https://apewisdom.io/api/v1.0/filter/{filter}/page/{page}",
                timeout=10,
                headers={"User-Agent": "folio-gauge/1.0"},
            )
            response.raise_for_status()
            data = response.json()

            for item in data.get("results", []):
                if item.get("ticker", "").upper() == ticker:
                    mentions = int(item.get("mentions", 0))
                    mentions_ago = int(item.get("mentions_24h_ago", 0))
                    return RedditMention(
                        symbol=ticker,
                        rank=int(item.get("rank", 0)),
                        mentions=mentions,
                        upvotes=int(item.get("upvotes", 0)),
                        mentions_24h_ago=mentions_ago,
                        rank_24h_ago=int(item.get("rank_24h_ago", 0)),
                        mention_delta=mentions - mentions_ago,
                    )
        except Exception as e:
            logger.error(f"Error fetching Reddit mentions for {ticker}: {e}")

    return None


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5))
def fetch_reddit_top(
    limit: int = 25, filter: str = "all-stocks"
) -> list[RedditMention]:
    """
    Fetch the top Reddit-trending tickers from ApeWisdom.

    """
    try:
        response = httpx.get(
            f"https://apewisdom.io/api/v1.0/filter/{filter}/page/1",
            timeout=10,
            headers={"User-Agent": "folio-gauge/1.0"},
        )
        response.raise_for_status()
        data = response.json()

        results = []
        for item in data.get("results", [])[:limit]:
            mentions = int(item.get("mentions", 0))
            mentions_ago = int(item.get("mentions_24h_ago", 0))
            results.append(
                RedditMention(
                    symbol=item.get("ticker", "").upper(),
                    rank=int(item.get("rank", 0)),
                    mentions=mentions,
                    upvotes=int(item.get("upvotes", 0)),
                    mentions_24h_ago=mentions_ago,
                    rank_24h_ago=int(item.get("rank_24h_ago", 0)),
                    mention_delta=mentions - mentions_ago,
                )
            )
        return results

    except Exception as e:
        logger.error(f"Error fetching top Reddit mentions: {e}")
        return []


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5))
def fetch_stocktwits_trending(limit: int = 30) -> list[StockTwitsTrending]:
    """
    Fetch currently trending symbols from StockTwits.
    Uses the public /trending/symbols endpoint — no API key required.
    """
    try:
        response = httpx.get(
            "https://api.stocktwits.com/api/2/trending/symbols.json",
            headers={"User-Agent": "folio-gauge/1.0"},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        symbols = data.get("symbols", [])
        return [
            StockTwitsTrending(
                symbol=s.get("symbol", "").upper(),
                watchlist_count=int(s.get("watchlist_count", 0)),
            )
            for s in symbols[:limit]
        ]

    except Exception as e:
        logger.error(f"Error fetching StockTwits trending ")
        return []


def fetch_trend_data(ticker: str) -> TrendData:
    """
    Fetch all trend data for a single ticker.
    Checks Reddit mention rank (ApeWisdom) and whether it appears
    in StockTwits trending right now.
    No scoring or LLM calls — that is the responsibility of the calling agent.
    """
    ticker = ticker.upper()

    st_trending = fetch_stocktwits_trending()
    st_symbols = {t.symbol for t in st_trending}

    return TrendData(
        reddit=fetch_reddit_mentions(ticker),
        stocktwits_trending=st_trending,
        is_stocktwits_trending=ticker in st_symbols,
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )


def fetch_trending_snapshot(
    reddit_limit: int = 25, stocktwits_limit: int = 30
) -> TrendingSnapshot:
    """
    Fetch the top trending tickers across Reddit and StockTwits.
    Useful for discovering what to analyse rather than scoring a known ticker.
    No scoring or LLM calls — pure data collection.

    """
    return TrendingSnapshot(
        reddit_top=fetch_reddit_top(limit=reddit_limit),
        stocktwits_top=fetch_stocktwits_trending(limit=stocktwits_limit),
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )
