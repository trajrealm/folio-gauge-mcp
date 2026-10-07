"""
src/orchestrator/aggregator.py
------------------------------
Consensus across the 8 per-ticker analysts, computed in code (no LLM).

  effective weight_i = AGENT_WEIGHTS[agent] x confidence_i
  weighted score     = sum(w_i x score_i) / sum(w_i)
  agreement          = 1 - weighted standard deviation of scores / 2
                       (scores span 1-5, so the deviation is at most 2)
  confidence         = mean analyst confidence (by AGENT_WEIGHTS) x agreement
  decision           = decision_from_score(weighted score)

A failed or no-data analyst has low confidence and so little influence.
"""

from __future__ import annotations

from collections import Counter
from math import sqrt

from src import config
from src.agent.scoring import AgentScore, OrchestratorResult, decision_from_score


def aggregate(symbol: str, scores: list[AgentScore]) -> OrchestratorResult:
    weights = [config.AGENT_WEIGHTS[s.agent] * s.confidence for s in scores]
    total = sum(weights)
    if total == 0:  # every analyst has zero confidence
        weighted, spread = 3.0, 0.0
    else:
        weighted = sum(w * s.score for w, s in zip(weights, scores)) / total
        spread = sqrt(sum(w * (s.score - weighted) ** 2 for w, s in zip(weights, scores)) / total)

    agreement = 1 - spread / 2
    mean_confidence = sum(config.AGENT_WEIGHTS[s.agent] * s.confidence for s in scores) / sum(
        config.AGENT_WEIGHTS[s.agent] for s in scores
    )
    decision = decision_from_score(weighted)

    return OrchestratorResult(
        symbol=symbol,
        decision=decision,
        weighted_score=round(weighted, 2),
        confidence=round(mean_confidence * agreement, 2),
        agreement=round(agreement, 2),
        timeframe=Counter(s.timeframe for s in scores).most_common(1)[0][0],
        agent_scores=scores,
        conflicts=[
            f"{a.agent}={a.decision} vs {b.agent}={b.decision}"
            for i, a in enumerate(scores)
            for b in scores[i + 1 :]
            if {a.decision, b.decision} == {"BUY", "SELL"}
        ],
        dissenting_agents=[s.agent for s in scores if s.decision != decision],
        data_gaps=[f"{s.agent}: {gap}" for s in scores for gap in s.data_gaps],
    )


def format_consensus(result: OrchestratorResult) -> str:
    lines = [
        f"CONSENSUS for {result.symbol}: {result.decision}",
        f"Weighted score {result.weighted_score:.2f}/5, confidence {result.confidence:.0%} "
        f"(agreement {result.agreement:.0%}), timeframe {result.timeframe}",
        "",
        "Analysts:",
    ]
    for s in sorted(result.agent_scores, key=lambda s: s.score, reverse=True):
        lines.append(f"  {s.agent:<13} {s.decision:<4} score {s.score}, confidence {s.confidence:.0%}")
        lines.append(f"    {s.reasoning}")
    if result.conflicts:
        lines += ["", "Conflicts: " + "; ".join(result.conflicts)]
    if result.data_gaps:
        lines += ["", "Data gaps: " + "; ".join(result.data_gaps)]
    return "\n".join(lines)
