"""
tools/peers.py
--------------
Peer discovery and comparison via yfinance. No API key required.

Peers are the largest companies in the target's industry (yf.Industry)
whose market weight is at least PEERS_MIN_WEIGHT_RATIO of the target's.
If fewer than PEERS_MIN_INDUSTRY qualify (e.g. AAPL dominates
consumer electronics), the list is filled from the sector's top companies.

The target is compared to the peer median: valuation multiples as a
% premium/discount, quality metrics as values next to the median.
"""

from __future__ import annotations

from statistics import median

import pandas as pd
import yfinance as yf
from pydantic import BaseModel
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .. import config
from .market import TickerSnapshot, get_ticker_snapshot

VALUATION_METRICS = ("pe_ratio", "forward_pe", "ev_to_ebitda", "price_to_book")
QUALITY_METRICS = ("return_on_equity", "operating_margin", "revenue_growth")


class PeerComparison(BaseModel):
    target: TickerSnapshot
    peers: list[TickerSnapshot]
    medians: dict[str, float | None]  # peer median per metric
    premiums: dict[str, float | None]  # valuation only: target / median - 1


class YahooDataUnavailable(Exception):
    """yfinance returned no data (it logs Yahoo errors such as HTTP 401 and returns None)."""


@retry(
    retry=retry_if_exception_type(YahooDataUnavailable),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)
def _top_companies(kind: str, key: str) -> pd.DataFrame:
    """Top companies of a yfinance Industry or Sector; retried when Yahoo returns nothing."""
    data = (yf.Industry(key) if kind == "industry" else yf.Sector(key)).top_companies
    if data is None:
        raise YahooDataUnavailable(f"No top companies for {kind} '{key}' from Yahoo")
    return data


def find_peers(target: TickerSnapshot, count: int = config.PEERS_COUNT) -> list[str]:
    """Pick peer symbols from the target's industry, filling from its sector."""
    symbol = target.profile.symbol
    weights = _top_companies("industry", target.profile.industry_key)["market weight"]
    threshold = weights.get(symbol, 0) * config.PEERS_MIN_WEIGHT_RATIO
    peers = [s for s, w in weights.items() if s != symbol and w >= threshold][:count]

    if len(peers) < config.PEERS_MIN_INDUSTRY:
        sector = _top_companies("sector", target.profile.sector_key).index
        peers += [s for s in sector if s != symbol and s not in peers][: count - len(peers)]

    return peers


def _median(peers: list[TickerSnapshot], metric: str) -> float | None:
    values = [getattr(p.fundamentals, metric) for p in peers]
    values = [v for v in values if v is not None]
    return median(values) if values else None


def compare_to_peers(symbol: str, count: int = config.PEERS_COUNT) -> PeerComparison:
    """Compare a company's valuation and quality to its peer median."""
    target = get_ticker_snapshot(symbol)
    peers = [get_ticker_snapshot(s) for s in find_peers(target, count)]

    medians = {m: _median(peers, m) for m in VALUATION_METRICS + QUALITY_METRICS}
    premiums = {}
    for metric in VALUATION_METRICS:
        value, mid = getattr(target.fundamentals, metric), medians[metric]
        # Multiples are meaningless when negative (losses), so no premium.
        positive = value is not None and value > 0 and mid is not None and mid > 0
        premiums[metric] = value / mid - 1 if positive else None

    return PeerComparison(target=target, peers=peers, medians=medians, premiums=premiums)
