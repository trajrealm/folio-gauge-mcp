"""
src/agent/scoring.py
--------------------
AgentScore dataclass — the standardised output every analyst agent returns.
Aggregation logic used by the orchestrator to consolidate all agent scores.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .. import config

@dataclass
class AgentScore:
    agent: str
    symbol: str
    decision: str
    score: int
    timeframe: str
    reasoning: str
    confidence: float
    data_gaps: list[str] = field(default_factory=list)

    def validate(self) -> list[str]:
        """
        Validate this score's fields.
        Returns list of error strings; empty means valid.
        """
        errors: list[str] = []

        if self.decision not in config.VALID_DECISIONS:
            errors.append(
                f"[{self.agent}] Invalid decision '{self.decision}'. "
                f"Must be one of {config.VALID_DECISIONS}."
            )

        if not (config.SCORE_MIN <= self.score <= config.SCORE_MAX):
            errors.append(
                f"[{self.agent}] Score {self.score} out of range "
                f"[{config.SCORE_MIN}, {config.SCORE_MAX}]."
            )

        if self.timeframe not in config.VALID_TIMEFRAMES:
            errors.append(
                f"[{self.agent}] Invalid timeframe '{self.timeframe}'. "
                f"Must be one of {config.VALID_TIMEFRAMES}."
            )

        if not (0.0 <= self.confidence <= 1.0):
            errors.append(
                f"[{self.agent}] Confidence {self.confidence} out of range [0.0, 1.0]."
            )

        if not self.reasoning.strip():
            errors.append(f"[{self.agent}] Reasoning must not be empty.")

        if not self.symbol.strip():
            errors.append(f"[{self.agent}] Symbol must not be empty.")

        return errors


@dataclass
class OrchestratorResult:
    symbol: str
    decision: str
    weighted_score: float
    confidence: float
    timeframe: str
    agent_scores: list[AgentScore]
    conflicts: list[str]
    dissenting_agents: list[str]
    data_gaps: list[str]


def _decision_from_score(weighted_score: float) -> str:
    """
    Map a weighted average score to a BUY / SELL / HOLD decision.

    Score bands:
      3.5 – 5.0  → BUY
      2.5 – 3.49 → HOLD
      1.0 – 2.49 → SELL
    """
    if weighted_score >= 3.5:
        return "BUY"
    elif weighted_score >= 2.5:
        return "HOLD"
    else:
        return "SELL"


def _majority_timeframe(scores: list[AgentScore]) -> str:
    """Return the most common timeframe across all agent scores."""
    counts: dict[str, int] = {}
    for s in scores:
        counts[s.timeframe] = counts.get(s.timeframe, 0) + 1
    return max(counts, key=lambda k: counts[k])


def _find_conflicts(scores: list[AgentScore]) -> list[str]:
    """
    Identify pairs of agents with opposing decisions (BUY vs SELL).
    HOLD vs BUY or HOLD vs SELL are noted as mild conflicts.
    """
    conflicts: list[str] = []
    for i, a in enumerate(scores):
        for b in scores[i + 1 :]:
            if a.decision == "BUY" and b.decision == "SELL":
                conflicts.append(f"{a.agent}=BUY vs {b.agent}=SELL")
            elif a.decision == "SELL" and b.decision == "BUY":
                conflicts.append(f"{a.agent}=SELL vs {b.agent}=BUY")
    return conflicts


def _find_dissenters(scores: list[AgentScore], majority_decision: str) -> list[str]:
    """Return agent names whose decision differs from the majority decision."""
    return [s.agent for s in scores if s.decision != majority_decision]


def _all_data_gaps(scores: list[AgentScore]) -> list[str]:
    """Collect and deduplicate data gaps reported across all agents."""
    seen: set[str] = set()
    gaps: list[str] = []
    for s in scores:
        for gap in s.data_gaps:
            if gap not in seen:
                seen.add(gap)
                gaps.append(gap)
    return gaps


def aggregate_scores(
    symbol: str,
    scores: list[AgentScore],
    weights: Optional[dict[str, float]] = None,
) -> OrchestratorResult:
    """
    Aggregate a list of AgentScores into an OrchestratorResult.
    """
    if not scores:
        raise ValueError(f"Cannot aggregate empty scores list for {symbol}.")

    weights = weights or config.AGENT_WEIGHTS

    all_errors: list[str] = []
    for s in scores:
        all_errors.extend(s.validate())
    if all_errors:
        raise ValueError(
            f"Invalid agent scores for {symbol}:\n" + "\n".join(all_errors)
        )

    fallback_weight = 1.0 / len(scores)
    total_weight = 0.0
    weighted_score_sum = 0.0
    weighted_confidence_sum = 0.0

    for s in scores:
        w = weights.get(s.agent, fallback_weight)
        weighted_score_sum += s.score * w
        weighted_confidence_sum += s.confidence * w
        total_weight += w

    weighted_score = weighted_score_sum / total_weight
    weighted_confidence = weighted_confidence_sum / total_weight

    decision = _decision_from_score(weighted_score)
    timeframe = _majority_timeframe(scores)
    conflicts = _find_conflicts(scores)
    dissenters = _find_dissenters(scores, decision)
    data_gaps = _all_data_gaps(scores)

    return OrchestratorResult(
        symbol=symbol,
        decision=decision,
        weighted_score=round(weighted_score, 3),
        confidence=round(weighted_confidence, 3),
        timeframe=timeframe,
        agent_scores=scores,
        conflicts=conflicts,
        dissenting_agents=dissenters,
        data_gaps=data_gaps,
    )


def format_orchestrator_result(result: OrchestratorResult) -> str:
    """
    Format an OrchestratorResult as a human-readable string
    for passing into the final evaluator agent prompt.
    """
    lines = [
        f"Symbol: {result.symbol}",
        f"Draft Decision: {result.decision}",
        f"Weighted Score: {result.weighted_score} / {config.SCORE_MAX}",
        f"Confidence: {result.confidence:.0%}",
        f"Timeframe: {result.timeframe}",
        "",
        "Agent Scores:",
    ]

    for s in result.agent_scores:
        lines.append(
            f"  {s.agent:<15} {s.decision:<4}  score={s.score}  "
            f"timeframe={s.timeframe}  confidence={s.confidence:.0%}"
        )
        lines.append(f"    Reasoning: {s.reasoning}")
        if s.data_gaps:
            lines.append(f"    Data gaps: {', '.join(s.data_gaps)}")

    if result.conflicts:
        lines += ["", "Conflicts detected:"]
        for c in result.conflicts:
            lines.append(f"  - {c}")

    if result.dissenting_agents:
        lines += ["", f"Dissenting agents: {', '.join(result.dissenting_agents)}"]

    if result.data_gaps:
        lines += ["", f"Overall data gaps: {', '.join(result.data_gaps)}"]

    return "\n".join(lines)
