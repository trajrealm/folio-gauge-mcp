"""
src/analysts/trends.py
Trends Analyst Agent

Evaluates industry and sector trends and relative momentum.
Uses LLM with domain knowledge from skills/trends.md and prompts/trends.md to guide analysis.
Returns AgentScore with trends outlook.
"""

from __future__ import annotations


import json
from langchain_openai import ChatOpenAI
from src.agent.scoring import AgentScore
from src.agent.knowledge import get_system_message
from src.tools.trends import fetch_trend_data

from .. import config
from src.utils.logger import get_logger
import traceback

logger = get_logger(__name__)


def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(model=config.LLM_MODEL_AGENTS, temperature=config.LLM_TEMPERATURE_AGENTS)

def analyze_trends(ticker: str) -> AgentScore:
    """
    Analyze sector trends and relative momentum using LLM guided by domain knowledge.
    """
    
    data_gaps: list[str] = []
    
    try:
        snapshot = fetch_trend_data(ticker)
        
        if not snapshot:
            data_gaps.append("No trends data available")
            return AgentScore(
                agent="trends",
                symbol=ticker,
                decision="HOLD",
                score=2,
                timeframe="mid",
                reasoning="Insufficient trends data",
                confidence=0.3,
                data_gaps=data_gaps,
            )
        
        trends_context = f"""
Ticker: {ticker}
Reddit Mentions: {snapshot.reddit.mentions if snapshot.reddit else 0}
Reddit Mention Delta (24h): {snapshot.reddit.mention_delta if snapshot.reddit else 0}
StockTwits Trending: {len(snapshot.stocktwits_trending) if snapshot.stocktwits_trending else 0}
"""
        
        system_prompt = get_system_message("trends", include_skill=True)
        
        user_message = f"""Analyze sector and market trends for {ticker}:

{trends_context}

Based on sector momentum, relative strength, and industry positioning, assess the tailwinds or headwinds.

Return ONLY a JSON object with this exact structure, no preamble:
{{
  "score": <1-5, where 1=strong headwinds, 3=neutral, 5=strong tailwinds>,
  "decision": "<BUY|HOLD|SELL>",
  "confidence": <0.0-1.0>,
  "reasoning": "<2-3 sentence explanation>",
  "trend_signals": ["<signal1>", "<signal2>"]
}}"""
        
        try:
            llm = _get_llm()
            response = llm.invoke([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ], config={"run_name": "Trends Agent"})
            result = json.loads(response.content)

            score = max(1.0, min(5.0, float(result.get("score", 3.0))))
            decision = result.get("decision", "HOLD").upper()
            confidence = max(0.0, min(1.0, float(result.get("confidence", 0.5))))
            reasoning = result.get("reasoning", "")

            return AgentScore(
                agent="trends",
                symbol=ticker,
                decision=decision,
                score=int(round(score)),
                timeframe="mid",
                reasoning=reasoning,
                confidence=confidence,
                data_gaps=data_gaps,
            )

        except json.JSONDecodeError:
            traceback.print_exc()
            logger.error(f"Trends JSON decode error: {response.content}")
            data_gaps.append("LLM response was not valid JSON")
            return AgentScore(
                agent="trends",
                symbol=ticker,
                decision="HOLD",
                score=2,
                timeframe="mid",
                reasoning="LLM analysis failed - invalid response format",
                confidence=0.2,
                data_gaps=data_gaps,
            )

    except Exception as e:
        traceback.print_exc()
        logger.error(f"Trends analysis error: {type(e).__name__}: {str(e)}")
        data_gaps.append(f"Trends analysis error: {str(e)}")
        return AgentScore(
            agent="trends",
            symbol=ticker,
            decision="HOLD",
            score=2,
            timeframe="mid",
            reasoning=f"Trends analysis failed: {str(e)}",
            confidence=0.2,
            data_gaps=data_gaps,
        )
