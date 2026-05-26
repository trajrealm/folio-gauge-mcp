"""
src/analysts/peers.py
Peers Analyst Agent

Evaluates relative valuation and competitive positioning.
Uses LLM with domain knowledge from skills/peers.md and prompts/peers.md to guide analysis.
Returns AgentScore with peer comparison outlook.
"""

from __future__ import annotations

import json
from langchain_openai import ChatOpenAI

from src.agent.scoring import AgentScore
from src.agent.knowledge import get_system_message
from src.tools.peers import compare_to_peers
import traceback

from .. import config
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(model=config.LLM_MODEL_AGENTS, temperature=config.LLM_TEMPERATURE_AGENTS)


def analyze_peers(ticker: str) -> AgentScore:
    """
    Analyze relative valuation versus peers using LLM guided by domain knowledge.
    """

    data_gaps: list[str] = []

    try:
        comparison = compare_to_peers(ticker)

        if not comparison or not comparison.peers:
            data_gaps.append("No peer comparison data available")
            return AgentScore(
                agent="peers",
                symbol=ticker,
                decision="HOLD",
                score=2,
                timeframe="mid",
                reasoning="Insufficient peer data",
                confidence=0.3,
                data_gaps=data_gaps,
            )

        # Format peer comparison data for LLM
        peers_context = f"""
Ticker: {ticker}
Target P/E: {f'{comparison.target_metrics.pe_ratio:.2f}' if comparison.target_metrics.pe_ratio is not None else 'N/A'}
Peer Avg P/E: {f'{comparison.peer_avg_pe:.2f}' if comparison.peer_avg_pe is not None else 'N/A'}
Target P/B: {f'{comparison.target_metrics.price_to_book:.2f}' if comparison.target_metrics.price_to_book is not None else 'N/A'}
Peer Avg P/B: {f'{comparison.peer_avg_pb:.2f}' if comparison.peer_avg_pb is not None else 'N/A'}
Target vs Peers P/E Ratio: {f'{comparison.target_vs_peer_pe:.2f}' if comparison.target_vs_peer_pe is not None else 'N/A'}
Target vs Peers P/B Ratio: {f'{comparison.target_vs_peer_pb:.2f}' if comparison.target_vs_peer_pb is not None else 'N/A'}
Number of Peers Analyzed: {len(comparison.peers)}
"""

        # Call LLM with system message containing skill + prompt
        system_prompt = get_system_message("peers", include_skill=True)

        user_message = f"""Analyze peer valuation for {ticker}:

{peers_context}

Based on relative valuation metrics compared to industry peers, assess whether the stock is trading at a discount or premium.

Return ONLY a JSON object with this exact structure, no preamble:
{{
  "score": <1-5, where 1=expensive vs peers, 3=in line with peers, 5=cheap vs peers>,
  "decision": "<BUY|HOLD|SELL>",
  "confidence": <0.0-1.0>,
  "reasoning": "<2-3 sentence explanation>",
  "valuation_signals": ["<signal1>", "<signal2>"]
}}"""

        try:
            llm = _get_llm()
            response = llm.invoke([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ], config={"run_name": "Peers Agent"})

            result = json.loads(response.content)

            score = max(1.0, min(5.0, float(result.get("score", 3.0))))
            decision = result.get("decision", "HOLD").upper()
            confidence = max(0.0, min(1.0, float(result.get("confidence", 0.5))))
            reasoning = result.get("reasoning", "")

            return AgentScore(
                agent="peers",
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
            logger.error(f"Peers JSON decode error: {response.content}")
            data_gaps.append("LLM response was not valid JSON")
            return AgentScore(
                agent="peers",
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
        logger.error(f"Peers analysis error: {str(e)}")
        data_gaps.append(f"Peers analysis error: {str(e)}")
        return AgentScore(
            agent="peers",
            symbol=ticker,
            decision="HOLD",
            score=2,
            timeframe="mid",
            reasoning=f"Peers analysis failed: {str(e)}",
            confidence=0.2,
            data_gaps=data_gaps,
        )
