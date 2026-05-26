"""
src/analysts/price_volume.py
Price Volume Analyst Agent

Evaluates volume trends, liquidity, and price action patterns.
Uses LLM with domain knowledge from skills/price_volume.md and prompts/price_volume.md to guide analysis.
Returns AgentScore with price-volume outlook.
"""

from __future__ import annotations

import os

import json
from langchain_openai import ChatOpenAI
from src.agent.scoring import AgentScore
from src.agent.knowledge import get_system_message
from src.tools.market import get_ticker_snapshot

from .. import config
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(model=config.LLM_MODEL_AGENTS, temperature=config.LLM_TEMPERATURE_AGENTS)


def analyze_price_volume(ticker: str) -> AgentScore:
    """
    Analyze price and volume patterns using LLM guided by domain knowledge.

    """
    
    data_gaps: list[str] = []
    
    try:
        snapshot = get_ticker_snapshot(ticker)
        
        if not snapshot or snapshot.price is None:
            data_gaps.append("No price/volume data available")
            return AgentScore(
                agent="price_volume",
                symbol=ticker,
                decision="HOLD",
                score=2,
                timeframe="short",
                reasoning="Insufficient price/volume data",
                confidence=0.3,
                data_gaps=data_gaps,
            )
        
        pv_context = f"""
Current Price: ${f'{snapshot.price.current_price:.2f}' if snapshot.price.current_price is not None else 'N/A'}
Average Volume: {f'{snapshot.price.average_volume:,.0f}' if snapshot.price.average_volume is not None else 'N/A'}
52-Week High: ${f'{snapshot.price.week_52_high:.2f}' if snapshot.price.week_52_high is not None else 'N/A'}
52-Week Low: ${f'{snapshot.price.week_52_low:.2f}' if snapshot.price.week_52_low is not None else 'N/A'}
Previous Close: ${f'{snapshot.price.previous_close:.2f}' if snapshot.price.previous_close is not None else 'N/A'}
"""
        
        system_prompt = get_system_message("price_volume", include_skill=True)
        
        user_message = f"""Analyze price and volume patterns for {ticker}:

{pv_context}

Based on volume trends, liquidity, price patterns, and OBV, assess the price-volume setup.

Return ONLY a JSON object with this exact structure, no preamble:
{{
  "score": <1-5, where 1=weak price-volume, 3=neutral, 5=strong price-volume setup>,
  "decision": "<BUY|HOLD|SELL>",
  "confidence": <0.0-1.0>,
  "reasoning": "<2-3 sentence explanation>",
  "volume_signals": ["<signal1>", "<signal2>"]
}}"""
        
        try:
            llm = _get_llm()
            response = llm.invoke([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ], config={"run_name": "Price Volume Agent"})

            result = json.loads(response.content)

            score = max(1.0, min(5.0, float(result.get("score", 3.0))))
            decision = result.get("decision", "HOLD").upper()
            confidence = max(0.0, min(1.0, float(result.get("confidence", 0.5))))
            reasoning = result.get("reasoning", "")

            return AgentScore(
                agent="price_volume",
                symbol=ticker,
                decision=decision,
                score=int(round(score)),
                timeframe="short",
                reasoning=reasoning,
                confidence=confidence,
                data_gaps=data_gaps,
            )

        except json.JSONDecodeError:
            logger.error(f"Price/Volume JSON decode error: {response.content}")
            data_gaps.append("LLM response was not valid JSON")
            return AgentScore(
                agent="price_volume",
                symbol=ticker,
                decision="HOLD",
                score=2,
                timeframe="short",
                reasoning="LLM analysis failed - invalid response format",
                confidence=0.2,
                data_gaps=data_gaps,
            )

    except Exception as e:
        logger.error(f"Price/Volume analysis error: {str(e)}")
        data_gaps.append(f"Price/Volume analysis error: {str(e)}")
        return AgentScore(
            agent="price_volume",
            symbol=ticker,
            decision="HOLD",
            score=2,
            timeframe="short",
            reasoning=f"Price/Volume analysis failed: {str(e)}",
            confidence=0.2,
            data_gaps=data_gaps,
        )
