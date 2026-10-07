"""
agent/graph.py
--------------
Per-ticker pipeline as a LangGraph:

  START -> 8 analyst nodes (run in parallel) -> aggregate -> evaluate -> END

Each analyst node appends one AgentScore to state["scores"]. A failing
analyst is logged with its stack trace and recorded as a neutral score with
zero confidence, so it carries no weight in the consensus.

analyze_ticker() is the single entry point.
"""

from __future__ import annotations

from typing import Callable

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from src.agent.scoring import AgentScore, OrchestratorResult
from src.agent.state import TickerState
from src.analysts import (
    analyze_earnings,
    analyze_fundamentals,
    analyze_macro,
    analyze_news,
    analyze_peers,
    analyze_sector,
    analyze_sentiment,
    analyze_technical,
)
from src.orchestrator.aggregator import aggregate, format_consensus
from src.orchestrator.evaluator import EvaluatorDecision, evaluate, format_decision
from src.utils.logger import get_logger

logger = get_logger(__name__)

ANALYSTS: dict[str, Callable[[str], AgentScore]] = {
    "technical": analyze_technical,
    "fundamentals": analyze_fundamentals,
    "sentiment": analyze_sentiment,
    "macro": analyze_macro,
    "peers": analyze_peers,
    "sector": analyze_sector,
    "earnings": analyze_earnings,
    "news": analyze_news,
}


class TickerAnalysis(BaseModel):
    consensus: OrchestratorResult
    decision: EvaluatorDecision


def _analyst_node(name: str, analyze: Callable[[str], AgentScore]):
    def node(state: TickerState) -> dict:
        symbol = state["symbol"]
        try:
            score = analyze(symbol)
        except Exception as e:
            logger.exception(f"{name} analyst failed for {symbol}")
            score = AgentScore(
                agent=name,
                symbol=symbol,
                decision="HOLD",
                score=3,
                timeframe="mid",
                reasoning=f"Analyst failed: {e}",
                confidence=0.0,
                data_gaps=[f"Analyst failed: {e}"],
            )
        return {"scores": [score]}

    return node


def _aggregate_node(state: TickerState) -> dict:
    return {"consensus": aggregate(state["symbol"], state["scores"])}


def _evaluate_node(state: TickerState) -> dict:
    return {"decision": evaluate(state["consensus"])}


def build_graph():
    graph = StateGraph(TickerState)
    for name, analyze in ANALYSTS.items():
        graph.add_node(name, _analyst_node(name, analyze))
        graph.add_edge(START, name)
        graph.add_edge(name, "aggregate")
    graph.add_node("aggregate", _aggregate_node)
    graph.add_node("evaluate", _evaluate_node)
    graph.add_edge("aggregate", "evaluate")
    graph.add_edge("evaluate", END)
    return graph.compile()


ticker_graph = build_graph()


def analyze_ticker(symbol: str) -> TickerAnalysis:
    state = ticker_graph.invoke({"symbol": symbol.upper(), "scores": [], "consensus": None, "decision": None})
    return TickerAnalysis(consensus=state["consensus"], decision=state["decision"])


def format_analysis(analysis: TickerAnalysis) -> str:
    return f"{format_consensus(analysis.consensus)}\n\n{format_decision(analysis.decision)}"
