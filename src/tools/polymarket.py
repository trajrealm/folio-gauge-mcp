"""
src/tools/polymarket.py
-----------------------
Polymarket prediction markets for a ticker (gamma API, no key), via the
/events endpoint with tag_slug = ticker, latest first.

Only open markets that are not price bets are kept: any question with a
dollar price level ("closes above $X", "hit $X") or "Up or Down" mirrors the
current price and carries no sentiment. Placeholder outcomes ("Candidate A",
"Other") are dropped too (config.POLY_SKIP_PATTERN).
"""

from __future__ import annotations

import json
import re

from pydantic import BaseModel

from .. import config
from ..utils.http import get_json


class PolymarketMarket(BaseModel):
    event: str
    question: str
    outcome: str  # first outcome, usually "Yes"
    probability: float  # market price of that outcome, 0-1
    volume: float | None
    end_date: str | None


def fetch_polymarket_markets(
    ticker: str, limit: int = config.POLY_DEFAULT_EVENT_LIMIT
) -> list[PolymarketMarket]:
    events = get_json(
        "https://gamma-api.polymarket.com/events",
        params={
            "tag_slug": ticker.lower(),
            "limit": limit,
            "order": "updatedAt",
            "ascending": False,
            "related_tags": True,
            "closed": False,
        },
    )
    skip = re.compile(config.POLY_SKIP_PATTERN, re.IGNORECASE)

    markets = []
    for event in events:
        for m in event["markets"]:
            if m.get("closed") or skip.search(m["question"]) or skip.search(event["title"]):
                continue
            markets.append(
                PolymarketMarket(
                    event=event["title"],
                    question=m["question"],
                    outcome=json.loads(m["outcomes"])[0],
                    probability=float(json.loads(m["outcomePrices"])[0]),
                    volume=m.get("volume"),
                    end_date=m.get("endDate"),
                )
            )
    return markets
