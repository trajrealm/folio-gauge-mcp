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

import yfinance as yf
from pydantic import BaseModel

from .. import config
from .market import TickerSnapshot, get_ticker_snapshot

VALUATION_METRICS = ("pe_ratio", "forward_pe", "ev_to_ebitda", "price_to_book")
QUALITY_METRICS = ("return_on_equity", "operating_margin", "revenue_growth")


class PeerComparison(BaseModel):
    target: TickerSnapshot
    peers: list[TickerSnapshot]
    medians: dict[str, float | None]  # peer median per metric
    premiums: dict[str, float | None]  # valuation only: target / median - 1


def find_peers(target: TickerSnapshot, count: int = config.PEERS_COUNT) -> list[str]:
    """Pick peer symbols from the target's industry, filling from its sector."""
    symbol = target.profile.symbol
    weights = yf.Industry(target.profile.industry_key).top_companies["market weight"]
    threshold = weights.get(symbol, 0) * config.PEERS_MIN_WEIGHT_RATIO
    peers = [s for s, w in weights.items() if s != symbol and w >= threshold][:count]

    if len(peers) < config.PEERS_MIN_INDUSTRY:
        sector = yf.Sector(target.profile.sector_key).top_companies.index
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
