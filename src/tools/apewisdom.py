"""
src/tools/apewisdom.py
----------------------
Reddit mention counts via ApeWisdom (no API key). ApeWisdom aggregates
r/wallstreetbets, r/stocks, r/investing, r/options and others; Reddit's own
API is not used. Results are ranked by mentions, 100 per page.
"""

from __future__ import annotations

from pydantic import BaseModel

from .. import config
from ..utils.http import get_json

_URL = "https://apewisdom.io/api/v1.0/filter/{filter}/page/{page}"


class RedditMention(BaseModel):
    symbol: str
    rank: int
    mentions: int
    mentions_24h_ago: int
    rank_24h_ago: int | None
    upvotes: int


def _page(page: int) -> dict:
    return get_json(_URL.format(filter=config.REDDIT_FILTER, page=page))


def _parse(item: dict) -> RedditMention:
    return RedditMention(
        symbol=item["ticker"].upper(),
        rank=item["rank"],
        mentions=item["mentions"],
        mentions_24h_ago=item["mentions_24h_ago"] or 0,
        rank_24h_ago=item["rank_24h_ago"],
        upvotes=item["upvotes"],
    )


def fetch_reddit_mentions(ticker: str) -> RedditMention | None:
    """Mentions for one ticker, searching every page. None if it is not ranked."""
    ticker = ticker.upper()
    page, pages = 1, 1
    while page <= pages:
        data = _page(page)
        pages = data["pages"]
        for item in data["results"]:
            if item["ticker"].upper() == ticker:
                return _parse(item)
        page += 1
    return None


def fetch_reddit_top(limit: int = 25) -> list[RedditMention]:
    """Most-mentioned tickers right now (first page)."""
    return [_parse(item) for item in _page(1)["results"][:limit]]
