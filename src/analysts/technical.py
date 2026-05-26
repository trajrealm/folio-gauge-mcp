"""
src/analysts/technical.py
Technical Analyst Agent

Evaluates price action and momentum using technical indicators.
Uses LLM with domain knowledge from skills/technical.md and prompts/technical.md to guide analysis.
Returns AgentScore with technical outlook.
"""

from __future__ import annotations

import os

import json
from langchain_openai import ChatOpenAI

from src.agent.scoring import AgentScore
from src.agent.knowledge import get_system_message
from src.tools.technical import get_technical_snapshot

from .. import config
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(model=config.LLM_MODEL_AGENTS, temperature=config.LLM_TEMPERATURE_AGENTS)


def analyze_technical(ticker: str) -> AgentScore:
    """
    Analyze technical indicators using LLM guided by domain knowledge.
    """
    
    data_gaps: list[str] = []
    
    try:
        snapshot = get_technical_snapshot(ticker)
        
        if not snapshot or snapshot.price is None:
            data_gaps.append("No technical data available")
            return AgentScore(
                agent="technical",
                symbol=ticker,
                decision="HOLD",
                score=2,
                timeframe="short",
                reasoning="Insufficient technical data",
                confidence=0.3,
                data_gaps=data_gaps,
            )
        
        tech_context = f"""
Current Price: ${snapshot.price:.2f}
SMA 20: ${snapshot.sma_20:.2f}
SMA 50: ${snapshot.sma_50:.2f}
SMA 200: ${snapshot.sma_200:.2f}
RSI 14: {snapshot.rsi_14:.1f}
MACD Value: {snapshot.macd_value:.4f}
MACD Signal: {snapshot.macd_signal:.4f}
MACD Histogram: {snapshot.macd_histogram:.4f}
"""
        
        system_prompt = get_system_message("technical", include_skill=True)
        
        user_message = f"""Analyze technical setup for {ticker}:

{tech_context}

Based on price action, moving averages, momentum indicators, and your domain knowledge, assess the technical outlook.

Return ONLY a JSON object with this exact structure, no preamble:
{{
  "score": <1-5, where 1=strong bearish, 3=neutral, 5=strong bullish>,
  "decision": "<BUY|HOLD|SELL>",
  "confidence": <0.0-1.0>,
  "reasoning": "<2-3 sentence explanation>",
  "key_signals": ["<signal1>", "<signal2>"]
}}"""
        
        try:
            llm = _get_llm()
            response = llm.invoke([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ], config={"run_name": "Technical Agent"})

            result = json.loads(response.content)

            score = max(1.0, min(5.0, float(result.get("score", 3.0))))
            decision = result.get("decision", "HOLD").upper()
            confidence = max(0.0, min(1.0, float(result.get("confidence", 0.5))))
            reasoning = result.get("reasoning", "")

            return AgentScore(
                agent="technical",
                symbol=ticker,
                decision=decision,
                score=int(round(score)),
                timeframe="short",
                reasoning=reasoning,
                confidence=confidence,
                data_gaps=data_gaps,
            )

        except json.JSONDecodeError:
            logger.error(f"Technical JSON decode error: {response.content}")
            data_gaps.append("LLM response was not valid JSON")
            return AgentScore(
                agent="technical",
                symbol=ticker,
                decision="HOLD",
                score=2,
                timeframe="short",
                reasoning="LLM analysis failed - invalid response format",
                confidence=0.2,
                data_gaps=data_gaps,
            )

    except Exception as e:
        logger.error(f"Technical outer exception: {type(e).__name__}: {str(e)}")
        data_gaps.append(f"Technical analysis error: {str(e)}")
        return AgentScore(
            agent="technical",
            symbol=ticker,
            decision="HOLD",
            score=2,
            timeframe="short",
            reasoning=f"Technical analysis failed: {str(e)}",
            confidence=0.2,
            data_gaps=data_gaps,
        )
