"""
src/orchestrator/evaluator.py
Evaluator Agent

Takes the orchestrator consensus and makes final buy/hold/sell decision.
Uses domain knowledge from skills/evaluator.md to guide final decision logic.
Handles trade execution logic (position sizing, stops, targets, risk management).
"""

from __future__ import annotations

import os
import json
from datetime import datetime
from dataclasses import dataclass
from typing import Optional
from langchain_openai import ChatOpenAI

from src.agent.scoring import OrchestratorResult
from src.agent.knowledge import get_system_message

from .. import config
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=config.LLM_MODEL_AGENTS, temperature=config.LLM_TEMPERATURE_AGENTS
    )


@dataclass
class EvaluatorDecision:
    """
    Final decision from the evaluator.
    Includes position sizing, risk management (stops/targets), and execution guidance.
    """

    ticker: str
    decision: str
    position_size_pct: float
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    stop_loss_pct: float = 0.0
    take_profit_pct: float = 0.0
    reasoning: str = ""
    confidence: float = 0.5
    risk_level: str = "MEDIUM"
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


def evaluate_consensus(
    result: OrchestratorResult,
    current_price: float,
    portfolio_context: Optional[dict] = None,
) -> EvaluatorDecision:

    portfolio_context = portfolio_context or {}

    try:
        decision = _evaluate_with_llm(result, current_price, portfolio_context)
    except Exception as e:
        logger.error(f"LLM evaluation failed: {str(e)}, falling back to rule-based")
        decision = _evaluate_fallback(result, current_price, portfolio_context)

    return decision


def _evaluate_with_llm(
    result: OrchestratorResult,
    current_price: float,
    portfolio_context: dict,
) -> EvaluatorDecision:

    vix = portfolio_context.get("vix", 15)
    portfolio_concentration = portfolio_context.get("top_1_pct", 0.05)

    analyst_summary = "\n".join(
        [
            f"  {s.agent}: score={s.score}, decision={s.decision}, confidence={s.confidence:.0%}"
            for s in sorted(result.agent_scores, key=lambda x: x.score, reverse=True)
        ]
    )

    context = f"""
Orchestrator Consensus for {result.symbol}:
Weighted Score: {result.weighted_score:.2f}/5.0
Decision: {result.decision}
Confidence: {result.confidence:.0%}

Analyst Breakdown:
{analyst_summary}

Current Price: ${current_price:.2f}
VIX: {vix:.1f}
Portfolio Concentration: {portfolio_concentration:.1%}

Conflicts: {', '.join(result.conflicts) if result.conflicts else 'None'}
Dissenting Agents: {', '.join(result.dissenting_agents) if result.dissenting_agents else 'None'}
"""

    system_prompt = get_system_message("evaluator", include_skill=True)

    user_message = f"""Make a final investment decision for {result.symbol}:

{context}

Based on the orchestrator consensus and market context, decide whether to BUY, HOLD, or SELL with appropriate position sizing and risk management.

Return ONLY a JSON object with this exact structure, no preamble:
{{
  "decision": "<BUY|HOLD|SELL>",
  "position_size_pct": <0.0-0.15, position as % of portfolio>,
  "stop_loss_pct": <percentage below entry, 0 if not applicable>,
  "take_profit_pct": <percentage above entry, 0 if not applicable>,
  "risk_level": "<LOW|MEDIUM|HIGH>",
  "confidence": <0.5-1.0>,
  "reasoning": "<2-3 sentence explanation>",
  "key_considerations": ["<factor1>", "<factor2>"]
}}"""

    llm = _get_llm()
    response = llm.invoke(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        config={"run_name": "Evaluator Agent"},
    )

    llm_result = json.loads(response.content)

    decision_str = llm_result.get("decision", "HOLD").upper()
    position_size = max(0.0, min(0.15, float(llm_result.get("position_size_pct", 0.0))))
    stop_loss_pct = max(0.0, float(llm_result.get("stop_loss_pct", 0.0)))
    take_profit_pct = max(0.0, float(llm_result.get("take_profit_pct", 0.0)))
    risk_level = llm_result.get("risk_level", "MEDIUM")
    confidence = max(0.5, min(1.0, float(llm_result.get("confidence", 0.6))))
    reasoning = llm_result.get("reasoning", "")

    entry_price = current_price if decision_str == "BUY" else None
    stop_loss = (
        (current_price * (1 - stop_loss_pct))
        if (stop_loss_pct > 0 and decision_str == "BUY")
        else None
    )
    take_profit = (
        (current_price * (1 + take_profit_pct))
        if (take_profit_pct > 0 and decision_str == "BUY")
        else None
    )

    return EvaluatorDecision(
        ticker=result.symbol,
        decision=decision_str,
        position_size_pct=position_size,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        stop_loss_pct=stop_loss_pct,
        take_profit_pct=take_profit_pct,
        reasoning=reasoning,
        confidence=confidence,
        risk_level=risk_level,
    )


def _evaluate_fallback(
    result: OrchestratorResult,
    current_price: float,
    portfolio_context: dict,
) -> EvaluatorDecision:

    vix = portfolio_context.get("vix", 15)
    portfolio_concentration = portfolio_context.get("top_1_pct", 0.05)

    score = result.weighted_score

    if score >= 4.0:
        decision = "BUY"
        confidence = 0.85
        base_position_size = 0.10
        risk_level = "MEDIUM"
        stop_loss_pct = 0.10
        take_profit_pct = 0.25
    elif score >= 3.5:
        decision = "BUY"
        confidence = 0.75
        base_position_size = 0.06
        risk_level = "MEDIUM"
        stop_loss_pct = 0.12
        take_profit_pct = 0.20
    elif score >= 3.0:
        decision = "HOLD"
        confidence = 0.60
        base_position_size = 0.03
        risk_level = "LOW"
        stop_loss_pct = 0.15
        take_profit_pct = 0.15
    elif score >= 2.5:
        decision = "HOLD"
        confidence = 0.55
        base_position_size = 0.00
        risk_level = "LOW"
        stop_loss_pct = 0.20
        take_profit_pct = 0.10
    elif score >= 2.0:
        decision = "SELL"
        confidence = 0.65
        base_position_size = 0.00
        risk_level = "MEDIUM"
        stop_loss_pct = 0.00
        take_profit_pct = 0.00
    else:
        decision = "SELL"
        confidence = 0.75
        base_position_size = 0.00
        risk_level = "HIGH"
        stop_loss_pct = 0.00
        take_profit_pct = 0.00

    if vix > 25:
        position_size_pct = base_position_size * 0.7
        risk_level = "HIGH"
    elif vix < 12:
        position_size_pct = base_position_size * 1.1
    else:
        position_size_pct = base_position_size

    if portfolio_concentration + position_size_pct > 0.15:
        position_size_pct = max(0, 0.15 - portfolio_concentration)
        if position_size_pct > 0:
            risk_level = "MEDIUM"

    entry_price = current_price if decision == "BUY" else None
    stop_loss = (
        (entry_price * (1 - stop_loss_pct))
        if (stop_loss_pct > 0 and decision == "BUY")
        else None
    )
    take_profit = (
        (entry_price * (1 + take_profit_pct))
        if (take_profit_pct > 0 and decision == "BUY")
        else None
    )

    reasoning_parts = [
        f"Score: {result.weighted_score:.2f}/5 ({result.decision})",
        f"Confidence: {result.confidence:.0%}",
    ]

    if result.conflicts:
        reasoning_parts.append(f"{len(result.conflicts)} conflicts")

    if result.data_gaps:
        reasoning_parts.append(f"{len(result.data_gaps)} data gaps")

    reasoning = " | ".join(reasoning_parts)

    return EvaluatorDecision(
        ticker=result.symbol,
        decision=decision,
        position_size_pct=position_size_pct,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        stop_loss_pct=stop_loss_pct,
        take_profit_pct=take_profit_pct,
        reasoning=reasoning,
        confidence=confidence,
        risk_level=risk_level,
    )


def format_evaluator_decision(decision: EvaluatorDecision) -> str:

    lines = [
        f"EVALUATOR DECISION for {decision.ticker}",
        f"{'='*60}",
        f"Decision:       {decision.decision}",
        f"Confidence:     {decision.confidence:.0%}",
        f"Risk Level:     {decision.risk_level}",
        "",
    ]

    if decision.decision == "BUY":
        lines += [
            f"Position Size:  {decision.position_size_pct:.1%} of portfolio",
            (
                f"Entry:          ${decision.entry_price:.2f}"
                if decision.entry_price
                else "Entry: N/A"
            ),
            (
                f"Stop Loss:      ${decision.stop_loss:.2f} ({decision.stop_loss_pct:.1%} below entry)"
                if decision.stop_loss
                else "Stop: N/A"
            ),
            (
                f"Take Profit:    ${decision.take_profit:.2f} ({decision.take_profit_pct:.1%} above entry)"
                if decision.take_profit
                else "Target: N/A"
            ),
            "",
        ]
    elif decision.decision == "SELL":
        lines += [
            f"Action:         Reduce or exit position",
            "",
        ]
    else:
        lines += [
            f"Action:         Hold existing position",
            "",
        ]

    lines.append(f"Reasoning:      {decision.reasoning}")

    return "\n".join(lines)


if __name__ == "__main__":
    # Test (requires orchestrator result)
    from src.orchestrator.aggregator import orchestrate_analysis

    result = orchestrate_analysis("AAPL")
    decision = evaluate_consensus(result, current_price=150.0)
    print(format_evaluator_decision(decision))
