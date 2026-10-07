"""
src/discovery.py
----------------
Discovery mode, in two steps:
  1. find_candidates: rank trending tickers in code (no LLM). Pool: ApeWisdom
     most-mentioned tickers and StockTwits trending. Order: on both sources
     first, then ApeWisdom 24h mention growth, then mentions. Only common stocks are kept
     (yfinance quoteType EQUITY), checked in rank order until the limit is met.
  2. review_candidates: after each candidate has been through the per-ticker
     analysis, the LLM compares them and recommends which to pursue.

A failing source is logged with its stack trace and recorded as a data gap.
"""

from __future__ import annotations

from typing import Literal

import yfinance as yf
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from src import config
from src.agent.knowledge import load_prompt
from src.agent.scoring import OrchestratorResult
from src.tools.apewisdom import ApeWisdomMention, fetch_top
from src.tools.stocktwits import StockTwitsTrending, fetch_stocktwits_trending
from src.utils.logger import get_logger

logger = get_logger(__name__)


class Candidate(BaseModel):
    symbol: str
    sources: list[str]  # "apewisdom", "stocktwits"
    apewisdom_rank: int | None
    mentions: int | None  # ApeWisdom mentions, last 24h
    mention_growth: float | None  # vs the prior 24h (fraction)
    stocktwits_watchlist: int | None


class DiscoveryResult(BaseModel):
    candidates: list[Candidate]  # ranked
    data_gaps: list[str]


class CandidateView(BaseModel):
    symbol: str
    action: Literal["research_further", "watch", "skip"]
    reason: str = Field(description="One sentence citing the analysis")


class DiscoveryReview(BaseModel):
    summary: str = Field(description="2-3 sentences comparing the candidates")
    candidates: list[CandidateView] = Field(description="Best first")


def _growth(m: ApeWisdomMention) -> float:
    return (m.mentions - m.mentions_24h_ago) / max(m.mentions_24h_ago, 1)


def find_candidates(limit: int = config.DISCOVERY_LIMIT) -> DiscoveryResult:
    data_gaps: list[str] = []
    apewisdom: dict[str, ApeWisdomMention] = {}
    trending: dict[str, StockTwitsTrending] = {}
    try:
        apewisdom = {m.symbol: m for m in fetch_top(config.DISCOVERY_POOL)}
    except Exception as e:
        logger.exception("ApeWisdom top list failed")
        data_gaps.append(f"ApeWisdom unavailable: {e}")
    try:
        trending = {t.symbol: t for t in fetch_stocktwits_trending(config.DISCOVERY_POOL)}
    except Exception as e:
        logger.exception("StockTwits trending failed")
        data_gaps.append(f"StockTwits unavailable: {e}")

    pool = [
        Candidate(
            symbol=symbol,
            sources=[s for s, d in (("apewisdom", apewisdom), ("stocktwits", trending)) if symbol in d],
            apewisdom_rank=apewisdom[symbol].rank if symbol in apewisdom else None,
            mentions=apewisdom[symbol].mentions if symbol in apewisdom else None,
            mention_growth=_growth(apewisdom[symbol]) if symbol in apewisdom else None,
            stocktwits_watchlist=trending[symbol].watchlist_count if symbol in trending else None,
        )
        for symbol in apewisdom.keys() | trending.keys()
    ]
    pool.sort(key=lambda c: (-len(c.sources), -(c.mention_growth or 0), -(c.mentions or 0)))

    candidates = []
    for c in pool:
        if len(candidates) == limit:
            break
        if yf.Ticker(c.symbol).info.get("quoteType") == "EQUITY":
            candidates.append(c)
    return DiscoveryResult(candidates=candidates, data_gaps=data_gaps)


def _format(c: Candidate, result: OrchestratorResult | None) -> str:
    attention = f"sources: {', '.join(c.sources)}"
    if c.mentions is not None:
        attention += f"; ApeWisdom rank {c.apewisdom_rank}, {c.mentions} mentions ({c.mention_growth:+.0%} vs prior 24h)"
    if result is None:
        return f"{c.symbol} | {attention} | analysis: not available"
    scores = ", ".join(f"{s.agent} {s.score}" for s in result.agent_scores)
    return (
        f"{c.symbol} | {attention} | consensus {result.decision}, score {result.weighted_score:.2f}/5, "
        f"confidence {result.confidence:.0%} | analysts: {scores}"
    )


def review_candidates(
    discovery: DiscoveryResult, results: dict[str, OrchestratorResult]
) -> DiscoveryReview:
    """LLM compares analyzed candidates and recommends which to pursue."""
    lines = "\n".join(_format(c, results.get(c.symbol)) for c in discovery.candidates)
    llm = ChatOpenAI(model=config.LLM_MODEL_AGENTS, temperature=config.LLM_TEMPERATURE_AGENTS)
    return llm.with_structured_output(DiscoveryReview).invoke(
        [
            {"role": "system", "content": load_prompt("discovery")},
            {"role": "user", "content": f"Trending candidates and their analysis:\n\n{lines}"},
        ],
        config={"run_name": "Discovery Review"},
    )
