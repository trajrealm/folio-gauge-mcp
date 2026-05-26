"""
src/orchestrator/aggregator.py
Orchestrator Agent

Calls all 11 specialist analysts, aggregates their scores into consensus,
and identifies conflicts/divergence.
Uses domain knowledge from skills/orchestrator.md to guide aggregation logic.
Returns OrchestratorResult with final weighted recommendation.

The 11 analysts:
  Core 9 analysts:
    1. technical      — technical indicators (SMA, RSI, MACD)
    2. fundamentals   — P/E, P/B, margins, debt
    3. sentiment      — Polymarket odds, StockTwits, news
    4. macro          — economic indicators (FRED)
    5. peers          — relative valuation vs peers
    6. trends         — Reddit mentions, StockTwits trending
    7. earnings       — EPS growth, guidance, beats/misses
    8. news           — article sentiment analysis
    9. price_volume   — 52-week range, volume, dividend
  Portfolio agents:
    10. discovery     — candidate discovery and shortlisting
    11. portfolio     — portfolio-level analysis and rebalancing
"""

from __future__ import annotations

import json
from typing import Optional
from langchain_openai import ChatOpenAI

from src.agent.scoring import AgentScore, OrchestratorResult
from src.agent.knowledge import get_system_message
from src.analysts import (
    analyze_technical,
    analyze_fundamentals,
    analyze_sentiment,
    analyze_macro,
    analyze_peers,
    analyze_trends,
    analyze_earnings,
    analyze_news,
    analyze_price_volume,
    analyze_portfolio,
)

from .. import config
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=config.LLM_MODEL_AGENTS, temperature=config.LLM_TEMPERATURE_AGENTS
    )


def orchestrate_analysis(
    ticker: str,
    weights: Optional[dict[str, float]] = None,
) -> OrchestratorResult:

    scores: list[AgentScore] = []
    analysts = [
        ("technical", analyze_technical),
        ("fundamentals", analyze_fundamentals),
        ("sentiment", analyze_sentiment),
        ("macro", analyze_macro),
        ("peers", analyze_peers),
        ("trends", analyze_trends),
        ("earnings", analyze_earnings),
        ("news", analyze_news),
        ("price_volume", analyze_price_volume),
    ]

    for analyst_name, analyst_func in analysts:
        try:
            score = analyst_func(ticker)
            scores.append(score)
        except Exception as e:
            logger.error(f"{analyst_name} analyst failed: {str(e)}")
            scores.append(
                AgentScore(
                    agent=analyst_name,
                    symbol=ticker,
                    decision="HOLD",
                    score=3,
                    timeframe="mid",
                    reasoning=f"Analyst error: {str(e)}",
                    confidence=0.1,
                    data_gaps=[f"Analyst failed: {str(e)}"],
                )
            )

    weights = weights or config.AGENT_WEIGHTS

    try:
        result = _aggregate_with_llm(ticker, scores, weights)
    except Exception as e:
        logger.error(
            f"LLM aggregation failed for {ticker}: {str(e)}, falling back to rule-based"
        )
        result = _aggregate_fallback(ticker, scores, weights)

    return result


def _aggregate_with_llm(
    ticker: str,
    scores: list[AgentScore],
    weights: dict[str, float],
) -> OrchestratorResult:

    analyst_breakdown = {}
    for score in scores:
        analyst_breakdown[score.agent] = {
            "score": score.score,
            "decision": score.decision,
            "confidence": score.confidence,
            "reasoning": score.reasoning,
        }

    context = f"""
Analyst Scores for {ticker}:
{json.dumps(analyst_breakdown, indent=2)}

Standard Weights:
{json.dumps(weights, indent=2)}
"""

    system_prompt = get_system_message("orchestrator", include_skill=True)

    user_message = f"""Aggregate these analyst scores into a consensus for {ticker}:

{context}

Analyze the consensus level, identify any divergences between bullish and bearish analysts, and calculate a weighted consensus score (1-5 scale).

Return ONLY a JSON object with this exact structure, no preamble:
{{
  "weighted_score": <1-5 scale, weighted average of analyst scores>,
  "decision": "<BUY|HOLD|SELL>",
  "confidence": <0.0-1.0, how certain is this consensus>,
  "reasoning": "<2-3 sentences on consensus and key divergences>",
  "consensus_type": "<HIGH_CONSENSUS|DIVIDED_OPINION|NEGATIVE_CONSENSUS>",
  "conflicts": ["<conflict1>", "<conflict2>"],
  "dissenting_agents": ["<agent1>", "<agent2>"]
}}"""

    llm = _get_llm()
    response = llm.invoke(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        config={"run_name": "Aggregator Agent"},
    )

    result = json.loads(response.content)

    weighted_score = max(1.0, min(5.0, float(result.get("weighted_score", 3.0))))
    decision = result.get("decision", "HOLD").upper()
    confidence = max(0.0, min(1.0, float(result.get("confidence", 0.5))))
    conflicts = result.get("conflicts", [])
    dissenting = result.get("dissenting_agents", [])

    return OrchestratorResult(
        symbol=ticker,
        weighted_score=weighted_score,
        decision=decision,
        confidence=confidence,
        agent_scores=scores,
        conflicts=conflicts,
        dissenting_agents=dissenting,
        timeframe="mid",
        data_gaps=[],
    )


def _aggregate_fallback(
    ticker: str,
    scores: list[AgentScore],
    weights: dict[str, float],
) -> OrchestratorResult:

    weighted_sum = 0.0
    total_weight = 0.0

    for score in scores:
        weight = weights.get(score.agent, 0.0)
        weighted_sum += score.score * weight
        total_weight += weight

    if total_weight > 0:
        weighted_score = weighted_sum / total_weight
    else:
        weighted_score = 3.0

    if weighted_score >= 4.0:
        decision = "BUY"
    elif weighted_score >= 3.0:
        decision = "HOLD"
    else:
        decision = "SELL"

    confidence = sum(s.confidence for s in scores) / len(scores) if scores else 0.5

    return OrchestratorResult(
        symbol=ticker,
        weighted_score=weighted_score,
        decision=decision,
        confidence=confidence,
        agent_scores=scores,
        conflicts=[],
        dissenting_agents=[],
        timeframe="mid",
        data_gaps=[],
    )


def format_orchestrator_summary(result: OrchestratorResult) -> str:

    lines = [
        f"ORCHESTRATOR SUMMARY for {result.symbol}",
        f"{'='* 60}",
        f"Consensus Decision: {result.decision}",
        f"Weighted Score:    {result.weighted_score:.2f} / 5.0",
        f"Confidence:        {result.confidence:.0%}",
        f"Timeframe:         {result.timeframe}",
        "",
        "Analyst Breakdown:",
    ]

    sorted_scores = sorted(result.agent_scores, key=lambda s: s.score, reverse=True)

    for s in sorted_scores:
        lines.append(
            f"  {s.agent:<15} → {s.decision:<4} (score={s.score}, confidence={s.confidence:.0%})"
        )
        lines.append(f"    {s.reasoning}")

    if result.conflicts:
        lines += ["", "Conflicts Detected:"]
        for c in result.conflicts:
            lines.append(f"  • {c}")

    if result.dissenting_agents:
        lines += ["", f"Dissenters: {', '.join(result.dissenting_agents)}"]

    if result.data_gaps:
        lines += ["", "Data Gaps:"]
        for gap in result.data_gaps[:3]:
            lines.append(f"  • {gap}")
        if len(result.data_gaps) > 3:
            lines.append(f"  ... and {len(result.data_gaps) - 3} more")

    return "\n".join(lines)


if __name__ == "__main__":
    # Test
    result = orchestrate_analysis("AAPL")
    print(format_orchestrator_summary(result))
    print("\n" + "=" * 60)
    print(f"Final consensus: {result.decision}")
