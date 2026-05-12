"""
agent/graph.py
--------------
Wires all nodes into a LangGraph StateGraph.

Flow:
  START → planner → tool_caller → reflect → [conditional] → summarizer → END

The conditional edge after reflect currently always goes to summarizer.
To enable retry: uncomment the line in nodes.should_retry.
"""

from __future__ import annotations

from langgraph.graph import StateGraph, START, END

from dotenv import load_dotenv
load_dotenv()

from src.agent.state import AgentState
from src.agent.nodes import (
    planner_node,
    tool_caller_node,
    reflect_node,
    summarizer_node,
    should_retry,
)


# ---------------------------------------------------------------------------
# Build graph
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    # Register nodes
    graph.add_node("planner", planner_node)
    graph.add_node("tool_caller", tool_caller_node)
    graph.add_node("reflect", reflect_node)
    graph.add_node("summarizer", summarizer_node)

    # Edges
    graph.add_edge(START, "planner")
    graph.add_edge("planner", "tool_caller")
    graph.add_edge("tool_caller", "reflect")

    # Conditional edge after reflect
    graph.add_conditional_edges(
        "reflect",
        should_retry,
        {
            "summarizer": "summarizer",
            "tool_caller": "tool_caller",   # retry path (future)
        },
    )

    graph.add_edge("summarizer", END)

    return graph


# ---------------------------------------------------------------------------
# Compiled graph (singleton — import this in server.py and tests)
# ---------------------------------------------------------------------------

compiled_graph = build_graph().compile()


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

def run_analysis(symbols: list[str], user_query: str) -> str:
    """
    Run the full agent pipeline and return the final summary as a string.

    Args:
        symbols:    List of ticker symbols e.g. ["AAPL", "MSFT"]
        user_query: The user's question e.g. "What are the main risks?"

    Returns:
        Final analysis string from the summarizer node.
    """
    initial_state: AgentState = {
        "symbols": [s.upper() for s in symbols],
        "user_query": user_query,
        "messages": [],
        "market_data": {},
        "filing_data": {},
        "news_data": {},
        "plan": None,
        "reflection": None,
        "needs_more_data": False,
        "final_summary": None,
        "errors": [],
    }

    final_state = compiled_graph.invoke(initial_state)

    return final_state.get("final_summary") or "Analysis could not be completed."