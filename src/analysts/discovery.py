"""
src/analysts/discovery.py
Discovery Agent

Identifies trending stock candidates based on social sentiment and market trends.
Does NOT evaluate specific tickers - instead returns a list of candidates for further analysis.
Uses LLM with domain knowledge from skills/discovery.md and prompts/discovery.md.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from src.agent.knowledge import get_system_message
from src.tools.trends import fetch_reddit_mentions, fetch_stocktwits_trending
from src.utils.logger import get_logger
from langchain_openai import ChatOpenAI

from .. import config

logger = get_logger(__name__)


def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(model=config.LLM_MODEL_AGENTS, temperature=config.LLM_TEMPERATURE_AGENTS)


def _is_valid_us_symbol(symbol: str) -> bool:
    """Check if symbol format is valid for US ticker."""
    if not symbol or not isinstance(symbol, str):
        return False
    
    symbol = symbol.strip().upper()
    
    if len(symbol) > 5 or len(symbol) < 1:
        return False
    
    if '.' in symbol or ',' in symbol:
        return False
    
    if not all(c.isalpha() or c == '-' for c in symbol):
        return False
    

    return True


@dataclass
class DiscoveryResult:
    candidates: list[str]
    reasoning: str
    confidence: float
    sources: dict
    timestamp: str


def discover_candidates(limit: int = 5) -> DiscoveryResult:
    """
    Discover trending stock candidates based on social sentiment and market trends.
    
    Returns:
        DiscoveryResult with list of candidate tickers
    """
    
    try:
        candidates = _discover_with_llm(limit)
    except Exception as e:
        logger.warning(f"LLM discovery failed: {str(e)}, falling back to rule-based")
        candidates = _discover_fallback(limit)
    
    return candidates


def _discover_with_llm(limit: int) -> DiscoveryResult:
    
    reddit_data = []
    stocktwits_data = []
    
    try:
        reddit_trending = fetch_reddit_mentions("all-stocks")
        if reddit_trending:
            reddit_data = [reddit_trending.ticker]
    except Exception as e:
        logger.warning(f"Reddit fetch failed: {e}")
    
    try:
        stocktwits_trending = fetch_stocktwits_trending(limit=10)
        stocktwits_data = [item.symbol for item in stocktwits_trending[:5]]
        stocktwits_data = [s for s in stocktwits_data if _is_valid_us_symbol(s)]
        logger.debug(f"StockTwits fetched (after validation): {stocktwits_data}")
    except Exception as e:
        logger.warning(f"StockTwits error: {e}")
    
    all_candidates = list(set(reddit_data + stocktwits_data))[:10]
    logger.debug(f"All candidates before LLM: {all_candidates}")
    
    context = f"""
Current Trending Candidates (by social volume):
Reddit mentions: {', '.join(reddit_data) if reddit_data else 'None'}
StockTwits trending: {', '.join(stocktwits_data) if stocktwits_data else 'None'}

Total candidates identified: {len(all_candidates)}
"""
    
    system_prompt = get_system_message("discovery", include_skill=True)
    
    user_message = f"""Identify the most promising stock discovery candidates based on trending data:

{context}

From the trending stocks shown, select the top {limit} most likely to be worth further analysis.
Consider social momentum, volume, and market interest. Return strong candidates that justify deeper research.

Return ONLY a JSON object with this exact structure, no preamble:
{{
  "top_candidates": ["TICKER1", "TICKER2", "TICKER3"],
  "reasoning": "<Why these were selected>",
  "confidence": <0.5-1.0, confidence in discovery>,
  "rationale": ["<reason1>", "<reason2>"]
}}"""
    
    llm = _get_llm()
    response = llm.invoke([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},        
    ], config={"run_name": "Discovery Agent"})
    
    result = json.loads(response.content)
    
    candidates = result.get("top_candidates", [])[:limit]
    logger.debug(f"LLM returned candidates: {candidates}")
    
    valid_candidates = candidates
    logger.debug(f"After validation: {valid_candidates}")
    
    reasoning = result.get("reasoning", "")
    confidence = max(0.5, min(1.0, float(result.get("confidence", 0.6))))
    
    return DiscoveryResult(
        candidates=valid_candidates,
        reasoning=reasoning,
        confidence=confidence,
        sources={
            "reddit": reddit_data,
            "stocktwits": stocktwits_data,
        },
        timestamp="",
    )


def _discover_fallback(limit: int) -> DiscoveryResult:
    
    reddit_data = []
    stocktwits_data = []
    
    try:
        reddit_trending = fetch_reddit_mentions("all-stocks")
        if reddit_trending:
            reddit_data = [reddit_trending.ticker]
    except:
        logger.warning("Reddit fetch failed in fallback")
        pass
    
    try:
        stocktwits_trending = fetch_stocktwits_trending(limit=10)
        stocktwits_data = [item.symbol for item in stocktwits_trending[:5]]
        stocktwits_data = [s for s in stocktwits_data if _is_valid_us_symbol(s)]
    except:
        logger.warning("StockTwits fetch failed in fallback")
        pass
    
    all_candidates = list(set(reddit_data + stocktwits_data))[:limit]
    valid_candidates = all_candidates
    
    return DiscoveryResult(
        candidates=valid_candidates,
        reasoning=f"Rule-based discovery: top {limit} valid US trading symbols from trending",
        confidence=0.6,
        sources={
            "reddit": reddit_data,
            "stocktwits": stocktwits_data,
        },
        timestamp="",
    )
