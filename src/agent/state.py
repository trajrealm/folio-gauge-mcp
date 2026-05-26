"""
agent/state.py
--------------
Defines AgentState — the single shared object that flows through
every node in the LangGraph graph.
"""

from __future__ import annotations

from typing import Annotated
from typing_extensions import TypedDict

from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

from src.tools.market import TickerSnapshot
from src.tools.edgar import FilingSummary
from src.tools.news import NewsFeed


class AgentState(TypedDict):
    symbols: list[str]
    user_query: str

    messages: Annotated[list[BaseMessage], add_messages]

    market_data: dict[str, TickerSnapshot]
    filing_data: dict[str, FilingSummary]
    news_data: dict[str, NewsFeed]

    plan: str | None
    reflection: str | None
    needs_more_data: bool

    final_summary: str | None
    errors: list[str]
