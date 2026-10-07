"""
agent/state.py
--------------
State flowing through the per-ticker LangGraph. Only declared keys survive
node updates, so every key a node writes must be listed here.
`scores` has a reducer: the parallel analyst nodes each append one score.
"""

from __future__ import annotations

import operator
from typing import Annotated

from typing_extensions import TypedDict

from src.agent.scoring import AgentScore, OrchestratorResult
from src.orchestrator.evaluator import EvaluatorDecision


class TickerState(TypedDict):
    symbol: str
    scores: Annotated[list[AgentScore], operator.add]
    consensus: OrchestratorResult | None
    decision: EvaluatorDecision | None
