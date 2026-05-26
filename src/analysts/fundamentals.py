"""
src/analysts/fundamentals.py
Fundamentals Analyst Agent

Evaluates financial health and valuation metrics.
Uses LLM with domain knowledge from skills/fundamentals.md and prompts/fundamentals.md to guide analysis.
Returns AgentScore with fundamental outlook.
"""

from __future__ import annotations

import json
from langchain_openai import ChatOpenAI
from src.agent.scoring import AgentScore
from src.agent.knowledge import get_system_message
from src.tools.market import get_fundamentals

from .. import config
from src.utils.logger import get_logger
import traceback

logger = get_logger(__name__)


def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(model=config.LLM_MODEL_AGENTS, temperature=config.LLM_TEMPERATURE_AGENTS)


def analyze_fundamentals(ticker: str) -> AgentScore:
    """
    Analyze fundamental metrics using LLM guided by domain knowledge.

    """

    data_gaps: list[str] = []

    try:
        fundamentals = get_fundamentals(ticker)

        if not fundamentals:
            data_gaps.append("No fundamentals data available")
            return AgentScore(
                agent="fundamentals",
                symbol=ticker,
                decision="HOLD",
                score=2,
                timeframe="long",
                reasoning="Insufficient fundamentals data",
                confidence=0.3,
                data_gaps=data_gaps,
            )

        fund_context = f"""
P/E Ratio: {f'{fundamentals.pe_ratio:.2f}' if fundamentals.pe_ratio is not None else 'N/A'}
P/B Ratio: {f'{fundamentals.price_to_book:.2f}' if fundamentals.price_to_book is not None else 'N/A'}
Debt/Equity: {f'{fundamentals.debt_to_equity:.2f}' if fundamentals.debt_to_equity is not None else 'N/A'}
ROE: {f'{fundamentals.return_on_equity:.2f}' if fundamentals.return_on_equity is not None else 'N/A'}%
Profit Margin: {f'{fundamentals.profit_margin:.2f}' if fundamentals.profit_margin is not None else 'N/A'}%
Current Ratio: {f'{fundamentals.current_ratio:.2f}' if fundamentals.current_ratio is not None else 'N/A'}
Revenue Growth: {f'{fundamentals.revenue_growth:.2f}' if fundamentals.revenue_growth is not None else 'N/A'}%
Earnings Growth: {f'{fundamentals.earnings_growth:.2f}' if fundamentals.earnings_growth is not None else 'N/A'}%
"""

        system_prompt = get_system_message("fundamentals", include_skill=True)

        user_message = f"""Analyze fundamental metrics for {ticker}:

{fund_context}

Based on valuation, profitability, cash flow, and financial health metrics, assess the fundamental attractiveness.

Return ONLY a JSON object with this exact structure, no preamble:
{{
  "score": <1-5, where 1=unattractive, 3=fairly valued, 5=attractive>,
  "decision": "<BUY|HOLD|SELL>",
  "confidence": <0.0-1.0>,
  "reasoning": "<2-3 sentence explanation>",
  "key_metrics": ["<metric1>", "<metric2>"]
}}"""

        try:
            llm = _get_llm()
            response = llm.invoke([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ], config={"run_name": "Fundamentals Agent"})

            result = json.loads(response.content)

            score = max(1.0, min(5.0, float(result.get("score", 3.0))))
            decision = result.get("decision", "HOLD").upper()
            confidence = max(0.0, min(1.0, float(result.get("confidence", 0.5))))
            reasoning = result.get("reasoning", "")

            return AgentScore(
                agent="fundamentals",
                symbol=ticker,
                decision=decision,
                score=int(round(score)),
                timeframe="long",
                reasoning=reasoning,
                confidence=confidence,
                data_gaps=data_gaps,
            )

        except json.JSONDecodeError:
            logger.error(f"Fundamentals JSON decode error: {response.content}") 
            traceback.print_exc()
            data_gaps.append("LLM response was not valid JSON")
            return AgentScore(
                agent="fundamentals",
                symbol=ticker,
                decision="HOLD",
                score=2,
                timeframe="long",
                reasoning="LLM analysis failed - invalid response format",
                confidence=0.2,
                data_gaps=data_gaps,
            )

    except Exception as e:
        logger.error(f"Fundamentals outer exception: {type(e).__name__}: {str(e)}")
        traceback.print_exc()
        data_gaps.append(f"Fundamentals analysis error: {str(e)}")
        return AgentScore(
            agent="fundamentals",
            symbol=ticker,
            decision="HOLD",
            score=2,
            timeframe="long",
            reasoning=f"Fundamentals analysis failed: {str(e)}",
            confidence=0.2,
            data_gaps=data_gaps,
        )
