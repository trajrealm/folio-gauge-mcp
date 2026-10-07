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

from dotenv import load_dotenv
load_dotenv()

import asyncio
import os

import mcp.server.stdio
import mcp.types as types
from mcp.server import Server

from src.agent.graph import analyze_ticker, format_analysis
from src.orchestrator.aggregator import format_consensus
from src.orchestrator.evaluator import format_decision
from src.tools.edgar import get_latest_filing_summary


load_dotenv()

server = Server("folio-gauge")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="analyze_ticker",
            description=(
                "Analyze a single stock ticker using the 11-agent orchestrator system. "
                "Combines 8 core analysts (technical, fundamentals, sentiment, macro, peers, sector, "
                "earnings, news) plus orchestrator and evaluator consolidation layers."
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
                "Analyze a portfolio of stocks using the 11-agent orchestrator system. "
                "Combines analyst consensus for each ticker to identify cross-portfolio risks and themes."
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
        types.Tool(
            name="get_analyst_scores",
            description=(
                "Get individual analyst scores for a ticker. "
                "Returns scores from 8 core analysts: technical, fundamentals, sentiment, macro, "
                "peers, sector, earnings, and news."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Stock ticker symbol e.g. AAPL",
                    },
                },
                "required": ["symbol"],
            },
        ),
        types.Tool(
            name="get_orchestrator_consensus",
            description=(
                "Get aggregated orchestrator consensus for a ticker. "
                "Returns weighted score, decision, conflicts, dissenters, and data gaps."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Stock ticker symbol e.g. AAPL",
                    },
                },
                "required": ["symbol"],
            },
        ),
        types.Tool(
            name="get_evaluator_decision",
            description=(
                "Get the final decision with position size, ATR-based stop-loss and take-profit, "
                "and the investment thesis."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Stock ticker symbol e.g. AAPL",
                    },
                },
                "required": ["symbol"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:

    if name == "analyze_ticker":
        symbol = arguments["symbol"].upper()
        
        analysis = await asyncio.to_thread(analyze_ticker, symbol)
        return [types.TextContent(type="text", text=format_analysis(analysis))]

    elif name == "analyze_portfolio":
        symbols = [s.upper() for s in arguments["symbols"]]
        
        if not symbols:
            return [types.TextContent(type="text", text="Error: no symbols provided.")]

        if len(symbols) > 10:
            return [types.TextContent(
                type="text",
                text="Error: maximum 10 symbols per request to avoid rate limiting."
            )]
        
        # Analyze each symbol and aggregate results
        all_results = []
        for symbol in symbols:
            analysis = await asyncio.to_thread(analyze_ticker, symbol)
            all_results.append({
                "symbol": symbol,
                "orchestrator_summary": format_consensus(analysis.consensus),
                "evaluator_summary": format_decision(analysis.decision),
            })
        
        if not all_results:
            return [types.TextContent(type="text", text="Could not analyze portfolio")]
        
        # Format portfolio summary
        summary_lines = [f"📊 PORTFOLIO ANALYSIS ({len(symbols)} positions)\n"]
        for item in all_results:
            summary_lines.append(f"\n--- {item['symbol']} ---")
            summary_lines.append(item['orchestrator_summary'])
            summary_lines.append(item['evaluator_summary'])
        
        return [types.TextContent(type="text", text="\n".join(summary_lines))]

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

    elif name == "get_analyst_scores":
        symbol = arguments["symbol"].upper()
        
        analysis = await asyncio.to_thread(analyze_ticker, symbol)

        lines = [f"ANALYST SCORES for {symbol}\n"]
        sorted_scores = sorted(analysis.consensus.agent_scores, key=lambda s: s.score, reverse=True)
        
        for s in sorted_scores:
            lines.append(f"{s.agent:<15} {s.decision:<5} Score: {s.score}/5 (confidence: {s.confidence:.0%})")
            lines.append(f"  {s.reasoning}\n")
        
        return [types.TextContent(type="text", text="\n".join(lines))]

    elif name == "get_orchestrator_consensus":
        symbol = arguments["symbol"].upper()
        
        analysis = await asyncio.to_thread(analyze_ticker, symbol)
        return [types.TextContent(type="text", text=format_consensus(analysis.consensus))]

    elif name == "get_evaluator_decision":
        symbol = arguments["symbol"].upper()
        analysis = await asyncio.to_thread(analyze_ticker, symbol)
        return [types.TextContent(type="text", text=format_decision(analysis.decision))]

    else:
        return [types.TextContent(type="text", text=f"Unknown tool: {name}")]


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