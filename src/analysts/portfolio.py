"""
src/analysts/portfolio.py
Portfolio Analyst Agent

Evaluates portfolio composition, risk, and concentration metrics.
Uses LLM with domain knowledge from skills/portfolio.md and prompts/portfolio.md to guide analysis.
Returns AgentScore with portfolio health assessment.
"""

from __future__ import annotations

import os

import json
from langchain_openai import ChatOpenAI
from src.agent.scoring import AgentScore
from src.agent.knowledge import get_system_message
from src.tools.market import get_portfolio_snapshots

from .. import config
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(model=config.LLM_MODEL_AGENTS, temperature=config.LLM_TEMPERATURE_AGENTS)


def analyze_portfolio(holdings: list[dict]) -> AgentScore:
    """
    Analyze portfolio composition and risk using LLM guided by domain knowledge.
    """
    
    data_gaps: list[str] = []
    
    try:
        if not holdings:
            data_gaps.append("No portfolio holdings provided")
            return AgentScore(
                agent="portfolio",
                symbol="PORTFOLIO",
                decision="HOLD",
                score=2,
                timeframe="mid",
                reasoning="Empty portfolio",
                confidence=0.3,
                data_gaps=data_gaps,
            )
        
        # Get snapshots for all holdings
        tickers = [h['symbol'] for h in holdings]
        snapshots = get_portfolio_snapshots(tickers)
        
        if not snapshots:
            data_gaps.append("No portfolio analysis data available")
            return AgentScore(
                agent="portfolio",
                symbol="PORTFOLIO",
                decision="HOLD",
                score=2,
                timeframe="mid",
                reasoning="Portfolio analysis failed",
                confidence=0.3,
                data_gaps=data_gaps,
            )
        
        # Format portfolio data for LLM
        holdings_list = "\n".join([
            f"- {h['symbol']}: {h.get('weight', 'N/A')}"
            for h in holdings[:10]
        ])
        
        portfolio_context = f"""
Number of Holdings: {len(holdings)}
Top Holdings:
{holdings_list}

Portfolio Diversification:
Total Tickers: {len(holdings)}
Number with Data: {len(snapshots)}
Average Price: ${sum(s.price for s in snapshots)/len(snapshots) if snapshots else 0:.2f}
"""
        
        # Call LLM with system message containing skill + prompt
        system_prompt = get_system_message("portfolio", include_skill=True)
        
        user_message = f"""Analyze portfolio composition and risk:

{portfolio_context}

Based on diversification, concentration, correlation, and sector exposure, assess portfolio health and balance.

Return ONLY a JSON object with this exact structure, no preamble:
{{
  "score": <1-5, where 1=poorly diversified/high risk, 3=balanced, 5=well-diversified/low risk>,
  "decision": "<BUY|HOLD|SELL>",
  "confidence": <0.0-1.0>,
  "reasoning": "<2-3 sentence explanation>",
  "portfolio_insights": ["<insight1>", "<insight2>"]
}}"""
        
        try:
            llm = _get_llm()
            response = llm.invoke([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ], config={"run_name": "Portfolio Agent"})
            

            result = json.loads(response.content)

            score = max(1.0, min(5.0, float(result.get("score", 3.0))))
            decision = result.get("decision", "HOLD").upper()
            confidence = max(0.0, min(1.0, float(result.get("confidence", 0.5))))
            reasoning = result.get("reasoning", "")

            return AgentScore(
                agent="portfolio",
                symbol="PORTFOLIO",
                decision=decision,
                score=int(round(score)),
                timeframe="mid",
                reasoning=reasoning,
                confidence=confidence,
                data_gaps=data_gaps,
            )

        except json.JSONDecodeError:
            logger.error(f"Portfolio JSON decode error: {response.content}")
            data_gaps.append("LLM response was not valid JSON")
            return AgentScore(
                agent="portfolio",
                symbol="PORTFOLIO",
                decision="HOLD",
                score=2,
                timeframe="mid",
                reasoning="LLM analysis failed - invalid response format",
                confidence=0.2,
                data_gaps=data_gaps,
            )

    except Exception as e:
        logger.error(f"Portfolio analysis error: {str(e)}")
        data_gaps.append(f"Portfolio analysis error: {str(e)}")
        return AgentScore(
            agent="portfolio",
            symbol="PORTFOLIO",
            decision="HOLD",
            score=2,
            timeframe="mid",
            reasoning=f"Portfolio analysis failed: {str(e)}",
            confidence=0.2,
            data_gaps=data_gaps,
        )
