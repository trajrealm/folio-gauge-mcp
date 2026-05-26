"""
src/analysts/news.py
News Analyst Agent

Evaluates sentiment from recent news and company announcements.
Uses LLM with domain knowledge from skills/news.md and prompts/news.md to guide analysis.
Returns AgentScore with news sentiment outlook.
"""

from __future__ import annotations

import json
from langchain_openai import ChatOpenAI
from src.agent.scoring import AgentScore
from src.agent.knowledge import get_system_message
from src.tools.news import get_ticker_news
import traceback

from .. import config
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(model=config.LLM_MODEL_AGENTS, temperature=config.LLM_TEMPERATURE_AGENTS)


def analyze_news(ticker: str) -> AgentScore:
    """
    Analyze recent news sentiment using LLM guided by domain knowledge.
    """

    data_gaps: list[str] = []

    try:
        news_items = get_ticker_news(ticker, per_source_limit=10)

        if not news_items:
            data_gaps.append("No recent news available")
            return AgentScore(
                agent="news",
                symbol=ticker,
                decision="HOLD",
                score=2,
                timeframe="short",
                reasoning="Insufficient news data",
                confidence=0.3,
                data_gaps=data_gaps,
            )

        news_summary = "\n".join([f"- {item.title}" for item in news_items.articles[:5]])

        news_context = f"""
Recent News (Last 10 items): {len(news_items.articles)} found
Recent Headlines:
{news_summary}
"""

        system_prompt = get_system_message("news", include_skill=True)

        user_message = f"""Analyze recent news sentiment for {ticker}:

{news_context}

Based on recent news coverage and sentiment, assess the sentiment direction and impact.

Return ONLY a JSON object with this exact structure, no preamble:
{{
  "score": <1-5, where 1=very negative news, 3=neutral, 5=very positive news>,
  "decision": "<BUY|HOLD|SELL>",
  "confidence": <0.0-1.0>,
  "reasoning": "<2-3 sentence explanation>",
  "key_stories": ["<story1>", "<story2>"]
}}"""

        try:
            llm = _get_llm()
            response = llm.invoke([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ], config={"run_name": "News Agent"})

            result = json.loads(response.content)

            score = max(1.0, min(5.0, float(result.get("score", 3.0))))
            decision = result.get("decision", "HOLD").upper()
            confidence = max(0.0, min(1.0, float(result.get("confidence", 0.5))))
            reasoning = result.get("reasoning", "")

            return AgentScore(
                agent="news",
                symbol=ticker,
                decision=decision,
                score=int(round(score)),
                timeframe="short",
                reasoning=reasoning,
                confidence=confidence,
                data_gaps=data_gaps,
            )

        except json.JSONDecodeError:
            traceback.print_exc()
            logger.error(f"News JSON decode error: {response.content}")
            data_gaps.append("LLM response was not valid JSON")
            return AgentScore(
                agent="news",
                symbol=ticker,
                decision="HOLD",
                score=2,
                timeframe="short",
                reasoning="LLM analysis failed - invalid response format",
                confidence=0.2,
                data_gaps=data_gaps,
            )

    except Exception as e:
        traceback.print_exc()
        logger.error(f"News analysis error: {str(e)}")
        data_gaps.append(f"News analysis error: {str(e)}")
        return AgentScore(
            agent="news",
            symbol=ticker,
            decision="HOLD",
            score=2,
            timeframe="short",
            reasoning=f"News analysis failed: {str(e)}",
            confidence=0.2,
            data_gaps=data_gaps,
        )
