"""
src/agent/scoring.py
--------------------
Shared scoring models and helpers.
  - AgentScore: what every per-ticker analyst returns
  - OrchestratorResult: the consensus across analysts (built by the aggregator)
  - decision_from_score, compute_confidence
Field constraints replace manual validation: an invalid score cannot be built.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .. import config

Decision = Literal["BUY", "HOLD", "SELL"]
Timeframe = Literal["short", "mid", "long"]


class AgentScore(BaseModel):
    agent: str
    symbol: str = Field(min_length=1)
    decision: Decision
    score: int = Field(ge=config.SCORE_MIN, le=config.SCORE_MAX)
    timeframe: Timeframe
    reasoning: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    data_gaps: list[str] = []


class OrchestratorResult(BaseModel):
    symbol: str
    decision: Decision
    weighted_score: float  # confidence-weighted mean of analyst scores, 1-5
    confidence: float  # mean analyst confidence x agreement
    agreement: float  # 1 = all analysts give the same score, 0 = maximal spread
    timeframe: Timeframe  # most common analyst timeframe
    agent_scores: list[AgentScore]
    conflicts: list[str]  # analyst pairs with opposing BUY / SELL decisions
    dissenting_agents: list[str]  # analysts whose decision differs from the consensus
    data_gaps: list[str]  # "agent: gap"


def decision_from_score(score: float) -> Decision:
    """BUY >= 3.5, SELL < 2.5, else HOLD."""
    if score >= 3.5:
        return "BUY"
    if score < 2.5:
        return "SELL"
    return "HOLD"


def compute_confidence(coverage: float, signals: list[int]) -> float:
    """
    Confidence from data coverage (0-1) and agreement of an analyst's
    sub-assessments, each mapped to -1 (bearish), 0 or +1 (bullish).
    Agreement is 1 when all signals match, 0.5 one step apart, 0 when opposed
    or when there are no signals. LLM self-reported confidence is not used:
    it anchors to a constant.
    """
    agreement = 1 - (max(signals) - min(signals)) / 2 if signals else 0
    return round(coverage * (0.5 + 0.5 * agreement), 2)
