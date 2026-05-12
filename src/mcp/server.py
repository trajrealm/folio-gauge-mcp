"""
mcp/server.py
-------------
MCP server for folio-gauge.
Exposes three tools that any MCP client (Claude Desktop, etc.) can call:

  - analyze_ticker(symbol)
  - analyze_portfolio(symbols)
  - get_sec_filing(symbol, filing_type)

Start with:
  folio-gauge          (via pyproject.toml entry point)
  or
  python -m src.mcp.server
"""

from __future__ import annotations

import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

import mcp.server.stdio
import mcp.types as types
from mcp.server import Server

from src.agent.graph import run_analysis
from src.tools.edgar import get_latest_filing_summary
from src.tools.market import get_ticker_snapshot
from src.tools.news import get_ticker_news, format_news_for_llm


# ---------------------------------------------------------------------------
# Server instance
# ---------------------------------------------------------------------------

server = Server("folio-gauge")


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="analyze_ticker",
            description=(
                "Analyze a single stock ticker using SEC filings, recent news, "
                "and fundamental market data. Returns a structured analysis."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Stock ticker symbol e.g. AAPL",
                    },
                    "question": {
                        "type": "string",
                        "description": "Optional specific question about the ticker",
                        "default": "Give me a comprehensive analysis of this stock.",
                    },
                },
                "required": ["symbol"],
            },
        ),
        types.Tool(
            name="analyze_portfolio",
            description=(
                "Analyze a portfolio of stocks using SEC filings, recent news, "
                "and fundamental data. Identifies cross-portfolio risks and themes."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "symbols": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of stock ticker symbols e.g. ['AAPL', 'MSFT', 'NVDA']",
                    },
                    "question": {
                        "type": "string",
                        "description": "Optional specific question about the portfolio",
                        "default": "What are the main risks and opportunities in this portfolio?",
                    },
                },
                "required": ["symbols"],
            },
        ),
        types.Tool(
            name="get_sec_filing",
            description=(
                "Fetch the latest SEC filing for a ticker. "
                "Supports 10-K (annual), 10-Q (quarterly), and 8-K (material events)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Stock ticker symbol e.g. AAPL",
                    },
                    "filing_type": {
                        "type": "string",
                        "enum": ["10-K", "10-Q", "8-K"],
                        "description": "Type of SEC filing to retrieve",
                        "default": "10-K",
                    },
                },
                "required": ["symbol"],
            },
        ),
    ]


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:

    if name == "analyze_ticker":
        symbol = arguments["symbol"].upper()
        question = arguments.get("question", "Give me a comprehensive analysis of this stock.")

        result = await asyncio.to_thread(run_analysis, [symbol], question)

        return [types.TextContent(type="text", text=result)]

    elif name == "analyze_portfolio":
        symbols = [s.upper() for s in arguments["symbols"]]
        question = arguments.get(
            "question",
            "What are the main risks and opportunities in this portfolio?"
        )

        if not symbols:
            return [types.TextContent(type="text", text="Error: no symbols provided.")]

        if len(symbols) > 10:
            return [types.TextContent(
                type="text",
                text="Error: maximum 10 symbols per request to avoid rate limiting."
            )]

        result = await asyncio.to_thread(run_analysis, symbols, question)

        return [types.TextContent(type="text", text=result)]

    elif name == "get_sec_filing":
        symbol = arguments["symbol"].upper()
        filing_type = arguments.get("filing_type", "10-K")

        filing = await asyncio.to_thread(
            get_latest_filing_summary, symbol, filing_type
        )

        if not filing:
            return [types.TextContent(
                type="text",
                text=f"No {filing_type} filing found for {symbol}."
            )]

        text = (
            f"{symbol} — {filing.filing_type}\n"
            f"Company: {filing.company_name}\n"
            f"Filed: {filing.filed_date}\n"
            f"Accession: {filing.accession_number}\n\n"
            f"--- Excerpt ---\n{filing.text_excerpt or 'No text available.'}"
        )

        return [types.TextContent(type="text", text=text)]

    else:
        return [types.TextContent(type="text", text=f"Unknown tool: {name}")]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def _main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main():
    """Entry point registered in pyproject.toml."""
    asyncio.run(_main())


if __name__ == "__main__":
    main()