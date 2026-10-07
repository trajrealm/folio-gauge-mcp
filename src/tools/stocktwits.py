"""
src/tools/stocktwits.py
-----------------------
StockTwits public API (no key): recent posts for a ticker with their
bullish/bearish tags, and the currently trending symbols.
StockTwits sometimes answers 403 (bot protection); that error is raised.
"""

from __future__ import annotations

from pydantic import BaseModel

from ..utils.http import get_json

_BASE = "https://api.stocktwits.com/api/2"


class StockTwitsSentiment(BaseModel):
    symbol: str
    bullish: int  # posts tagged Bullish by their author
    bearish: int
    untagged: int
    messages: list[str]  # newest first


class StockTwitsTrending(BaseModel):
    symbol: str
    watchlist_count: int


def fetch_stocktwits_sentiment(ticker: str) -> StockTwitsSentiment:
    """Latest posts (up to 30) for a ticker and their tag counts."""
    ticker = ticker.upper()
    messages = get_json(f"{_BASE}/streams/symbol/{ticker}.json")["messages"]
    tags = [((m.get("entities") or {}).get("sentiment") or {}).get("basic") for m in messages]
    return StockTwitsSentiment(
        symbol=ticker,
        bullish=tags.count("Bullish"),
        bearish=tags.count("Bearish"),
        untagged=sum(t not in ("Bullish", "Bearish") for t in tags),
        messages=[m["body"] for m in messages],
    )


def fetch_stocktwits_trending(limit: int = 30) -> list[StockTwitsTrending]:
    """Symbols trending on StockTwits right now."""
    symbols = get_json(f"{_BASE}/trending/symbols.json")["symbols"]
    return [
        StockTwitsTrending(symbol=s["symbol"].upper(), watchlist_count=s["watchlist_count"])
        for s in symbols[:limit]
    ]
