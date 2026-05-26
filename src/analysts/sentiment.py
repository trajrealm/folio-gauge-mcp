"""
src/analysts/sentiment.py
-------------------------
Sentiment Analyst Agent

Evaluates market psychology by combining three data sources:
  1. Polymarket prediction markets  (src/tools/polymarket.py)
  2. StockTwits retail sentiment    (src/tools/stocktwits.py)
  3. RSS news feed                  (src/tools/news.py)

Passes combined context to OpenAI gpt-4o-mini for analysis.
Uses skill and prompt from markdown files to guide reasoning.
Returns AgentScore with sentiment outlook.
"""

from __future__ import annotations

import os

import json
from datetime import datetime, timezone

from langchain_openai import ChatOpenAI
from src.agent.scoring import AgentScore
from src.agent.knowledge import load_skill, get_system_message
from src.tools.polymarket import fetch_polymarket_events, PolymarketData
from src.tools.stocktwits import fetch_stocktwits_sentiment, StockTwitsData
from src.tools.news import get_ticker_news, NewsFeed
from src.utils.logger import get_logger

from .. import config

logger = get_logger(__name__)


def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(model=config.LLM_MODEL_AGENTS, temperature=config.LLM_TEMPERATURE_AGENTS)


def _format_polymarket(data: PolymarketData) -> str:
    if not data.success or not data.events:
        return "No Polymarket data available."

    lines = [f"Polymarket events ({data.count} found):"]
    for event in data.events[:5]:
        title = event.title
        volume = event.open_interest
        desc = (event.description or "")[:100]
        lines.append(f"- {title} (open interest: ${volume:,.0f})\n  {desc}")
    return "\n".join(lines)


def _format_stocktwits(data: StockTwitsData) -> str:
    if not data.success or data.total == 0:
        return "No StockTwits data available."

    bullish_pct = (data.bullish / data.total) * 100
    bearish_pct = (data.bearish / data.total) * 100

    lines = [
        f"StockTwits sentiment ({data.total} recent messages):",
        f"- Bullish: {bullish_pct:.0f}% ({data.bullish} messages)",
        f"- Bearish: {bearish_pct:.0f}% ({data.bearish} messages)",
        "Recent messages:",
    ]
    for msg in data.messages[:5]:
        lines.append(f"  • {msg[:100]}")
    return "\n".join(lines)


def _format_news(feed: NewsFeed, max_articles: int = 8) -> str:
    if not feed.articles:
        return "No recent news available."

    lines = [f"Recent news (as of {feed.fetched_at[:10]}):"]
    for article in feed.articles[:max_articles]:
        date = article.published[:10] if article.published else "unknown date"
        summary = f" — {article.summary}" if article.summary else ""
        lines.append(f"[{date}] {article.source}: {article.title}{summary}")
    return "\n".join(lines)


def _analyze_with_llm(
    ticker: str,
    polymarket_data: PolymarketData,
    stocktwits_data: StockTwitsData,
    news_feed: NewsFeed,
) -> tuple[float, str, float, str, list[str]]:
    """
    Call OpenAI gpt-4o-mini with combined context from all three sources.
    Uses sentiment skill and prompt to guide analysis.
    """
    system_prompt = get_system_message("sentiment", include_skill=True)
    
    user_message = f"""Analyze sentiment for {ticker} based on the following market data:

{_format_polymarket(polymarket_data)}

{_format_stocktwits(stocktwits_data)}

{_format_news(news_feed)}

Return ONLY a JSON object with this exact structure, no preamble:
{{
  "score": <1-5, where 1=strong bearish, 3=neutral, 5=strong bullish>,
  "decision": "<BUY|HOLD|SELL>",
  "confidence": <0.0-1.0>,
  "reasoning": "<2-3 sentence explanation>",
  "key_signals": ["<signal1>", "<signal2>", ...]
}}"""

    try:
        llm = _get_llm()
        response = llm.invoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ], config={"run_name": "Sentiment Agent"})

        result = json.loads(response.content)

        score = max(1.0, min(5.0, float(result.get("score", 3.0))))
        decision = result.get("decision", "HOLD").upper()
        confidence = max(0.0, min(1.0, float(result.get("confidence", 0.5))))
        reasoning = result.get("reasoning", "")
        signals = result.get("key_signals", [])

        return score, decision, confidence, reasoning, signals

    except Exception as e:
        logger.error(f"OpenAI analysis failed: {e}, falling back to heuristic")
        return _fallback_analysis(ticker, polymarket_data, stocktwits_data)



def _fallback_analysis(
    ticker: str,
    polymarket_data: PolymarketData,
    stocktwits_data: StockTwitsData,
) -> tuple[float, str, float, str, list[str]]:
    """
    Heuristic fallback if the OpenAI call fails.
    News is excluded here since it requires LLM to interpret.
    """
    signals = []
    score_components = []

    if stocktwits_data.success and stocktwits_data.total > 0:
        bullish_pct = (stocktwits_data.bullish / stocktwits_data.total) * 100
        bearish_pct = (stocktwits_data.bearish / stocktwits_data.total) * 100

        if bullish_pct > 60:
            signals.append(f"StockTwits bullish ({bullish_pct:.0f}%)")
            score_components.append(4)
        elif bearish_pct > 60:
            signals.append(f"StockTwits bearish ({bearish_pct:.0f}%)")
            score_components.append(2)
        else:
            signals.append("StockTwits mixed sentiment")
            score_components.append(3)

    if polymarket_data.success and polymarket_data.events:
        total_volume = sum(e.open_interest for e in polymarket_data.events)
        signals.append(f"Polymarket open interest: ${total_volume:,.0f}")
        score_components.append(4 if total_volume > 100000 else 2 if total_volume < 10000 else 3)

    score = max(1.0, min(5.0, round(
        sum(score_components) / len(score_components) if score_components else 3.0, 1
    )))

    if score >= 4.0:
        decision, confidence = "BUY", 0.65
    elif score >= 3.0:
        decision, confidence = "HOLD", 0.55
    else:
        decision, confidence = "SELL", 0.65

    return score, decision, confidence, f"Based on {len(signals)} sentiment signals", signals


def analyze_sentiment(ticker: str) -> AgentScore:
    """
    Analyze sentiment signals for a ticker using Polymarket, StockTwits, and News.
    """
    ticker = ticker.upper()
    data_gaps: list[str] = []

    # Fetch from all three tools
    polymarket_data = fetch_polymarket_events(ticker)
    stocktwits_data = fetch_stocktwits_sentiment(ticker)
    news_feed = get_ticker_news(ticker)

    # Track data gaps
    if not polymarket_data.success:
        data_gaps.append(f"Polymarket data unavailable: {polymarket_data.error}")
    if not stocktwits_data.success:
        data_gaps.append(f"StockTwits data unavailable: {stocktwits_data.error}")
    if not news_feed.articles:
        data_gaps.append("No news articles found")

    try:
        score, decision, confidence, reasoning, signals = _analyze_with_llm(
            ticker, polymarket_data, stocktwits_data, news_feed
        )

        reasoning_full = f"{reasoning}\nSignals: {', '.join(signals) if signals else 'None identified'}"

        return AgentScore(
            agent="sentiment",
            symbol=ticker,
            decision=decision,
            score=int(round(score)),
            timeframe="short",
            reasoning=reasoning_full,
            confidence=confidence,
            data_gaps=data_gaps,
        )

    except Exception as e:
        logger.error(f"Sentiment analysis error: {str(e)}")
        data_gaps.append(f"Sentiment analysis error: {str(e)}")
        return AgentScore(
            agent="sentiment",
            symbol=ticker,
            decision="HOLD",
            score=3,
            timeframe="short",
            reasoning=f"Sentiment analysis failed: {str(e)}. Defaulting to neutral.",
            confidence=0.2,
            data_gaps=data_gaps,
        )