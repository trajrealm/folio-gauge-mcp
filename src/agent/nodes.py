"""
agent/nodes.py
--------------
Individual node functions for the folio-gauge LangGraph agent.

Node execution order:
  planner → tool_caller → reflect → summarizer
                 ↑____________|  (if needs_more_data — future extension)

Each node receives the full AgentState and returns a partial dict
of keys to update. LangGraph merges these back into the state.
"""

from __future__ import annotations

import os
from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI

from src.agent.state import AgentState
from src.agent.prompts import (
    PLANNER_PROMPT,
    REFLECTION_PROMPT,
    SUMMARIZER_PROMPT,
    format_market_data,
    format_filing_data,
    format_news_data,
)
from src.tools.market import get_ticker_snapshot, TickerSnapshot
from src.tools.edgar import get_latest_filing_summary, FilingSummary
from src.tools.news import get_ticker_news, NewsFeed


# ---------------------------------------------------------------------------
# LLM setup
# ---------------------------------------------------------------------------

def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        temperature=float(os.getenv("LLM_TEMPERATURE", "0.2")),
        api_key=os.getenv("OPENAI_API_KEY"),
    )


# ---------------------------------------------------------------------------
# Node: planner
# ---------------------------------------------------------------------------

def planner_node(state: AgentState) -> dict:
    """
    Reads user query + symbols, produces a brief analysis plan.
    This gives the LLM a chance to reason about what to look for
    before data is fetched.
    """
    llm = _get_llm()
    chain = PLANNER_PROMPT | llm

    response = chain.invoke({
        "symbols": ", ".join(state["symbols"]),
        "user_query": state["user_query"],
    })

    plan = response.content

    return {
        "plan": plan,
        "messages": [
            HumanMessage(content=state["user_query"]),
            AIMessage(content=f"[Plan]\n{plan}"),
        ],
    }


# ---------------------------------------------------------------------------
# Node: tool_caller
# ---------------------------------------------------------------------------

def tool_caller_node(state: AgentState) -> dict:
    """
    Fetches market data, SEC filings, and news for every symbol.
    Errors are caught per-ticker so one failure doesn't abort everything.
    """
    symbols = state["symbols"]
    errors: list[str] = list(state.get("errors", []))

    market_data: dict[str, TickerSnapshot] = {}
    filing_data: dict[str, FilingSummary] = {}
    news_data: dict[str, NewsFeed] = {}

    for symbol in symbols:
        # Market data
        try:
            market_data[symbol] = get_ticker_snapshot(symbol)
        except Exception as e:
            errors.append(f"{symbol} market data: {e}")

        # SEC filing — try 10-K first, fall back to 10-Q
        try:
            filing = get_latest_filing_summary(symbol, "10-K")
            if not filing:
                filing = get_latest_filing_summary(symbol, "10-Q")
            if filing:
                filing_data[symbol] = filing
            else:
                errors.append(f"{symbol} SEC filing: no 10-K or 10-Q found")
        except Exception as e:
            errors.append(f"{symbol} SEC filing: {e}")

        # News
        try:
            news_data[symbol] = get_ticker_news(symbol, per_source_limit=5)
        except Exception as e:
            errors.append(f"{symbol} news: {e}")

    return {
        "market_data": market_data,
        "filing_data": filing_data,
        "news_data": news_data,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Node: reflect
# ---------------------------------------------------------------------------

def reflect_node(state: AgentState) -> dict:
    """
    Checks whether we have enough data to answer the user's question.
    Sets needs_more_data=True to trigger a retry loop (future extension),
    or False to proceed to the summarizer.

    For now: if we have market data for at least half the symbols,
    we proceed. The LLM reflection is logged but the decision is
    also made programmatically to avoid unnecessary LLM calls.
    """
    llm = _get_llm()
    chain = REFLECTION_PROMPT | llm

    symbols = state["symbols"]
    market_symbols = list(state.get("market_data", {}).keys())
    filing_symbols = list(state.get("filing_data", {}).keys())
    news_symbols = list(state.get("news_data", {}).keys())
    errors = state.get("errors", [])

    response = chain.invoke({
        "symbols": ", ".join(symbols),
        "market_symbols": ", ".join(market_symbols) or "none",
        "filing_symbols": ", ".join(filing_symbols) or "none",
        "news_symbols": ", ".join(news_symbols) or "none",
        "errors": "\n".join(errors) if errors else "none",
        "plan": state.get("plan", ""),
        "user_query": state["user_query"],
        "market_data_text": format_market_data(state.get("market_data", {})),
        "filing_data_text": format_filing_data(state.get("filing_data", {})),
        "news_data_text": format_news_data(state.get("news_data", {})),
    })

    reflection = response.content

    # Programmatic decision — proceed if we have market data for ≥50% of symbols
    coverage = len(market_symbols) / max(len(symbols), 1)
    needs_more_data = coverage < 0.5

    return {
        "reflection": reflection,
        "needs_more_data": needs_more_data,
        "messages": [AIMessage(content=f"[Reflection]\n{reflection}")],
    }


# ---------------------------------------------------------------------------
# Node: summarizer
# ---------------------------------------------------------------------------

def summarizer_node(state: AgentState) -> dict:
    """
    Synthesizes all fetched data into a final structured analysis.
    This is the main LLM call the user actually sees.
    """
    llm = _get_llm()
    chain = SUMMARIZER_PROMPT | llm

    response = chain.invoke({
        "symbols": ", ".join(state["symbols"]),
        "user_query": state["user_query"],
        "market_data_text": format_market_data(state.get("market_data", {})),
        "filing_data_text": format_filing_data(state.get("filing_data", {})),
        "news_data_text": format_news_data(state.get("news_data", {})),
        "plan": state.get("plan", ""),
    })

    summary = response.content

    return {
        "final_summary": summary,
        "messages": [AIMessage(content=summary)],
    }


# ---------------------------------------------------------------------------
# Conditional edge function (used in graph.py)
# ---------------------------------------------------------------------------

def should_retry(state: AgentState) -> str:
    """
    LangGraph conditional edge — called after reflect_node.
    Returns the name of the next node to execute.

    Currently: always go to summarizer (retry loop is a future extension).
    When you add retry logic, check state["needs_more_data"] here.
    """
    # Future: if state["needs_more_data"]: return "tool_caller"
    return "summarizer"