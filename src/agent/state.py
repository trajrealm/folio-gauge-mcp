"""
agent/state.py
--------------
Defines AgentState — the single shared object that flows through
every node in the LangGraph graph.

LangGraph passes this state between nodes and merges updates
returned by each node back into it.
"""

from __future__ import annotations

from typing import Annotated, Any
from typing_extensions import TypedDict

from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

from src.tools.market import TickerSnapshot
from src.tools.edgar import FilingSummary
from src.tools.news import NewsFeed


# ---------------------------------------------------------------------------
# AgentState
# ---------------------------------------------------------------------------

class AgentState(TypedDict):
    # ── Input ────────────────────────────────────────────────────────────────
    symbols: list[str]                          # tickers to analyze e.g. ["AAPL", "MSFT"]
    user_query: str                             # original user question

    # ── Conversation / LLM messages ──────────────────────────────────────────
    # add_messages is a LangGraph reducer — it appends instead of replacing
    messages: Annotated[list[BaseMessage], add_messages]

    # ── Fetched data (populated by tool-caller node) ──────────────────────────
    market_data: dict[str, TickerSnapshot]      # keyed by symbol
    filing_data: dict[str, FilingSummary]       # keyed by symbol
    news_data: dict[str, NewsFeed]              # keyed by symbol

    # ── Agent reasoning ───────────────────────────────────────────────────────
    plan: str | None                            # planner node output
    reflection: str | None                      # reflect node output — "do I have enough?"
    needs_more_data: bool                       # reflect node decision to loop or continue

    # ── Final output ──────────────────────────────────────────────────────────
    final_summary: str | None                   # summarizer node output
    errors: list[str]                           # non-fatal errors collected during fetch