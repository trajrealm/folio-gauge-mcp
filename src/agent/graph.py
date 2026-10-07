"""
agent/graph.py
--------------
Per-ticker pipeline as a LangGraph:

  START -> 8 analyst nodes (run in parallel) -> aggregate -> evaluate -> END

Each analyst node appends one AgentScore to state["scores"]. A failing
analyst is logged with its stack trace and recorded as a neutral score with
zero confidence, so it carries no weight in the consensus.

analyze_ticker() is the entry point for one ticker; analyze_tickers() runs
several (config.ANALYSIS_WORKERS at a time) for portfolio review and discovery.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from src import config
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


class BatchAnalysis(BaseModel):
    analyses: dict[str, TickerAnalysis]
    failed: dict[str, str]  # symbol -> error message (stack trace is logged)


def analyze_tickers(symbols: list[str]) -> BatchAnalysis:
    """Analyze several tickers; one failing ticker does not stop the others."""

    def run(symbol: str) -> TickerAnalysis | str:
        try:
            return analyze_ticker(symbol)
        except Exception as e:
            logger.exception(f"Analysis failed for {symbol}")
            return f"{type(e).__name__}: {e}"

    with ThreadPoolExecutor(config.ANALYSIS_WORKERS) as pool:
        results = dict(zip(symbols, pool.map(run, symbols)))
    return BatchAnalysis(
        analyses={s: r for s, r in results.items() if isinstance(r, TickerAnalysis)},
        failed={s: r for s, r in results.items() if isinstance(r, str)},
    )


def format_analysis(analysis: TickerAnalysis) -> str:
    return f"{format_consensus(analysis.consensus)}\n\n{format_decision(analysis.decision)}"
