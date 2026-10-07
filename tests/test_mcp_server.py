"""
test_mcp_server.py
------------------
Smoke-tests the MCP server over stdio, the way Claude Desktop runs it:
starts the server, lists the tools and calls them.
Requires OPENAI_API_KEY, FRED_API_KEY and EDGAR_USER_AGENT in .env.
  default: every data tool, one analyst and analyze_ticker (~1 min)
  --full:  also every analyst, review_portfolio (sample CSV) and discover_stocks (several minutes)
Run from project root:
    uv run python -m tests.test_mcp_server [TICKER] [--full]
"""

import asyncio
import json
import sys
import time
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).parents[1]
args = [a for a in sys.argv[1:] if not a.startswith("--")]
TICKER = args[0] if args else "AAPL"
FULL = "--full" in sys.argv

CALLS = [
    ("tool_market", {"symbol": TICKER}),
    ("tool_technical", {"symbol": TICKER}),
    ("tool_peers", {"symbol": TICKER}),
    ("tool_sector", {"symbol": TICKER}),
    ("tool_edgar", {"symbol": TICKER}),
    ("tool_edgar_search", {"symbol": TICKER, "question": "What drove revenue growth?"}),
    ("tool_news", {"symbol": TICKER}),
    ("tool_fred", {}),
    ("tool_stocktwits", {"symbol": TICKER}),
    ("tool_apewisdom", {"symbol": TICKER}),
    ("tool_polymarket", {"symbol": TICKER}),
    ("analyst_technical", {"symbol": TICKER}),
    ("analyze_ticker", {"symbol": TICKER}),
]
if FULL:
    CALLS += [
        (f"analyst_{name}", {"symbol": TICKER})
        for name in ("fundamentals", "peers", "sector", "earnings", "news", "sentiment", "macro")
    ]
    CALLS += [
        ("review_portfolio", {"csv_path": str(ROOT / "tests/data/sample_portfolio.csv")}),
        ("discover_stocks", {"limit": 3}),
    ]


async def main() -> None:
    server = StdioServerParameters(command="uv", args=["run", "python", "-m", "src.mcp.server"], cwd=ROOT)
    results = {}
    async with stdio_client(server) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        tools = {t.name for t in (await session.list_tools()).tools}
        print(f"\n== MCP server - {len(tools)} tools ==\n")
        for name, arguments in CALLS:
            start = time.time()
            result = await session.call_tool(name, arguments)
            text = result.content[0].text if result.content else ""
            results[name] = not result.isError
            preview = text if result.isError else json.dumps(result.structuredContent)[:120]
            print(f"  [{'PASS' if not result.isError else 'FAIL'}] {name:<22} {time.time() - start:5.1f}s  {preview}")

    print()
    expected = {name for name, _ in CALLS} | {"review_portfolio", "discover_stocks"}
    print(f"  [{'PASS' if expected <= tools else 'FAIL'}] All expected tools registered")
    print(f"  [{'PASS' if all(results.values()) else 'FAIL'}] All calls succeeded\n")


asyncio.run(main())
