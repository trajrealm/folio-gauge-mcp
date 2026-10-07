"""
src/tools/apewisdom.py
----------------------
Ticker mention counts from ApeWisdom (apewisdom.io, public API, no key).
ApeWisdom counts ticker mentions on stock discussion forums over a rolling
24h window. Results are ranked by mentions, 100 per page.
"""

from __future__ import annotations

from pydantic import BaseModel

from .. import config
from ..utils.http import get_json

_URL = "https://apewisdom.io/api/v1.0/filter/{filter}/page/{page}"


class ApeWisdomMention(BaseModel):
    symbol: str
    rank: int
    mentions: int
    mentions_24h_ago: int
    rank_24h_ago: int | None
    upvotes: int


def _page(page: int) -> dict:
    return get_json(_URL.format(filter=config.APEWISDOM_FILTER, page=page))


def _parse(item: dict) -> ApeWisdomMention:
    return ApeWisdomMention(
        symbol=item["ticker"].upper(),
        rank=item["rank"],
        mentions=item["mentions"],
        mentions_24h_ago=item["mentions_24h_ago"] or 0,
        rank_24h_ago=item["rank_24h_ago"],
        upvotes=item["upvotes"],
    )


def fetch_mentions(ticker: str) -> ApeWisdomMention | None:
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


def fetch_top(limit: int = 25) -> list[ApeWisdomMention]:
    """Most-mentioned tickers right now (first page)."""
    return [_parse(item) for item in _page(1)["results"][:limit]]
