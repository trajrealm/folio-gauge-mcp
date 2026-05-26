"""
agent/graph.py
--------------
Wires all nodes into a LangGraph StateGraph.
The orchestrator calls all 9 core specialist analysts and aggregates their scores.
"""

from __future__ import annotations

from langgraph.graph import StateGraph, START, END

from src.agent.state import AgentState
from src.orchestrator.aggregator import (
    orchestrate_analysis,
    format_orchestrator_summary,
)
from src.orchestrator.evaluator import evaluate_consensus, format_evaluator_decision
from src.tools.market import get_ticker_snapshot
from src.utils.logger import get_logger

logger = get_logger(__name__)

def build_analyst_graph() -> StateGraph:
    """
    Build analyst pipeline: calls 9 analysts -> orchestrator -> evaluator.
    Each ticker is analyzed by all 9 core agents, scores are aggregated.
    """
    graph = StateGraph(AgentState)

    def orchestrator_node(state: AgentState) -> AgentState:
        """Call orchestrator for first symbol."""
        symbols = state.get("symbols", [])
        if not symbols:
            return state

        ticker = symbols[0]
        orchestrator_result = orchestrate_analysis(ticker)
        orchestrator_summary = format_orchestrator_summary(orchestrator_result)

        state["orchestrator_result"] = orchestrator_result
        state["orchestrator_summary"] = orchestrator_summary

        state["messages"] = state.get("messages", []) + [
            {"role": "system", "content": orchestrator_summary}
        ]

        return state

    def evaluator_node(state: AgentState) -> AgentState:
        """Call evaluator based on orchestrator result."""
        orchestrator_result = state.get("orchestrator_result")

        if not orchestrator_result:
            return state

        ticker = orchestrator_result.ticker
        try:
            snapshot = get_ticker_snapshot(ticker)
            current_price = snapshot.price.current_price
            if current_price is None:
                # Fallback if price data unavailable (150.0 is arbitrary placeholder)
                current_price = 150.0
                state.setdefault("errors", []).append(
                    f"Could not fetch price for {ticker}, using placeholder"
                )
                logger.warning(f"Could not fetch price for {ticker}, using placeholder")
        except Exception as e:
            logger.error(f"Error fetching price for {ticker}: {str(e)}. Default price is being used.")
            current_price = 150.0
            state.setdefault("errors", []).append(
                f"Error fetching price for {ticker}: {str(e)}"
            )

        portfolio_context = state.get("portfolio_context", {"vix": 15})

        evaluator_decision = evaluate_consensus(
            orchestrator_result,
            current_price=current_price,
            portfolio_context=portfolio_context,
        )

        evaluator_summary = format_evaluator_decision(evaluator_decision)

        state["evaluator_decision"] = evaluator_decision
        state["evaluator_summary"] = evaluator_summary
        state["final_summary"] = (
            f"{state.get('orchestrator_summary', '')}\n\n{evaluator_summary}"
        )

        return state

    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("evaluator", evaluator_node)

    graph.add_edge(START, "orchestrator")
    graph.add_edge("orchestrator", "evaluator")
    graph.add_edge("evaluator", END)

    return graph


# Compiled analyst graph
analyst_graph = build_analyst_graph().compile()

# Public Entry point
def run_analysis_with_analysts(symbols: list[str]) -> dict:
    """
    Run 9-agent analyst pipeline with orchestrator and evaluator.
    """
    initial_state: AgentState = {
        "symbols": [s.upper() for s in symbols],
        "user_query": f"Analyze {', '.join(symbols)}",
        "messages": [],
        "market_data": {},
        "filing_data": {},
        "news_data": {},
        "plan": None,
        "reflection": None,
        "needs_more_data": False,
        "final_summary": None,
        "errors": [],
        "orchestrator_result": None,
        "orchestrator_summary": None,
        "evaluator_decision": None,
        "evaluator_summary": None,
    }

    final_state = analyst_graph.invoke(initial_state)

    return {
        "symbol": final_state["symbols"][0] if final_state.get("symbols") else None,
        "orchestrator_result": final_state.get("orchestrator_result"),
        "evaluator_decision": final_state.get("evaluator_decision"),
        "orchestrator_summary": final_state.get("orchestrator_summary"),
        "evaluator_summary": final_state.get("evaluator_summary"),
        "final_summary": final_state.get("final_summary"),
    }
