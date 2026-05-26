"""
src/analysts/macro.py
Macro Analyst Agent

Evaluates macroeconomic conditions and policy impact on equities.
Uses LLM with domain knowledge from skills/macro.md and prompts/macro.md to guide analysis.
Returns AgentScore with macro outlook.
"""

from __future__ import annotations

import os

import json
from langchain_openai import ChatOpenAI
from src.agent.scoring import AgentScore
from src.agent.knowledge import get_system_message
from src.tools.fred import get_economic_indicators

from .. import config
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(model=config.LLM_MODEL_AGENTS, temperature=config.LLM_TEMPERATURE_AGENTS)


def analyze_macro(ticker: str) -> AgentScore:
    """
    Analyze macro indicators using LLM guided by domain knowledge.
    """
    
    data_gaps: list[str] = []
    
    try:
        # Fetch macro indicators
        indicators = get_economic_indicators()
        
        if not indicators:
            data_gaps.append("No macro data available from FRED")
            return AgentScore(
                agent="macro",
                symbol=ticker,
                decision="HOLD",
                score=2,
                timeframe="mid",
                reasoning="Insufficient macro data",
                confidence=0.3,
                data_gaps=data_gaps,
            )
        
        # Format macro data for LLM
        macro_context = f"""
Federal Reserve Rate: {indicators.fed_funds_rate:.2f}% (neutral ~3.5%)
CPI YoY Change: {indicators.cpi_yoy_change:.2f}%
Unemployment Rate: {indicators.unemployment_rate:.2f}%
Yield Curve (10Y-2Y): {indicators.yield_spread_10y2y:.2f}%
VIX Index: {indicators.vix_index:.1f}
"""
        
        # Call LLM with system message containing skill + prompt
        system_prompt = get_system_message("macro", include_skill=True)
        
        user_message = f"""Analyze macro conditions for equity analysis of {ticker}:

{macro_context}

Based on these macro indicators and your domain knowledge, assess the macro environment outlook.

Return ONLY a JSON object with this exact structure, no preamble:
{{
  "score": <1-5, where 1=very bearish, 3=neutral, 5=very bullish>,
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
            ], config={"run_name": "Macro Agent"})

            result = json.loads(response.content)

            score = max(1.0, min(5.0, float(result.get("score", 3.0))))
            decision = result.get("decision", "HOLD").upper()
            confidence = max(0.0, min(1.0, float(result.get("confidence", 0.5))))
            reasoning = result.get("reasoning", "")

            return AgentScore(
                agent="macro",
                symbol=ticker,
                decision=decision,
                score=int(round(score)),
                timeframe="mid",
                reasoning=reasoning,
                confidence=confidence,
                data_gaps=data_gaps,
            )

        except json.JSONDecodeError:
            logger.error(f"Macro JSON decode error: {response.content}")
            data_gaps.append("LLM response was not valid JSON")
            return AgentScore(
                agent="macro",
                symbol=ticker,
                decision="HOLD",
                score=2,
                timeframe="mid",
                reasoning="LLM analysis failed - invalid response format",
                confidence=0.2,
                data_gaps=data_gaps,
            )

    except Exception as e:
        logger.error(f"Macro analysis error: {str(e)}")
        data_gaps.append(f"Macro analysis error: {str(e)}")
        return AgentScore(
            agent="macro",
            symbol=ticker,
            decision="HOLD",
            score=2,
            timeframe="mid",
            reasoning=f"Macro analysis failed: {str(e)}",
            confidence=0.2,
            data_gaps=data_gaps,
        )
