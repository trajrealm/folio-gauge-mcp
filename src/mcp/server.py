"""
src/mcp/server.py
-----------------
folio-gauge MCP server (stdio). Three levels of tools:
  - tool_*     raw data from one source, no LLM
  - analyst_*  one analyst's score (1-5), decision, confidence and reasoning
  - workflows  analyze_ticker, review_portfolio, discover_stocks

Run:  uv run --directory <repo> python -m src.mcp.server
A failing tool logs its stack trace to stderr and returns the error to the client.
"""

from __future__ import annotations

import functools
from typing import Any, Callable

import anyio
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

from src import config
from src.agent.graph import TickerAnalysis, analyze_ticker
from src.agent.scoring import AgentScore
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
from src.discovery import DiscoveryReport, run_discovery
from src.portfolio.loader import load_portfolio_csv
from src.portfolio.models import Holding
from src.portfolio.review import PortfolioReport, run_portfolio_review
from src.tools.apewisdom import ApeWisdomMention, fetch_mentions
from src.tools.edgar import (
    CompanyFilings,
    EarningsFacts,
    FilingQueryResult,
    get_company_filings,
    get_earnings_facts,
    ingest_filings,
    query_filings,
)
from src.tools.fred import MacroSnapshot, get_macro_snapshot
from src.tools.market import TickerSnapshot, get_ticker_snapshot
from src.tools.news import NewsFeed, get_ticker_news
from src.tools.peers import PeerComparison, compare_to_peers
from src.tools.polymarket import PolymarketMarket, fetch_polymarket_markets
from src.tools.sector import SectorTrend, get_sector_trend
from src.tools.stocktwits import StockTwitsSentiment, fetch_stocktwits_sentiment, fetch_stocktwits_trending
from src.tools.technical import TechnicalSnapshot, get_technical_snapshot
from src.utils.logger import get_logger

logger = get_logger(__name__)
mcp = FastMCP("folio-gauge")


async def _run(fn: Callable[..., Any], *args: Any) -> Any:
    """Run blocking work in a thread; log the stack trace of any failure, then re-raise."""
    try:
        return await anyio.to_thread.run_sync(functools.partial(fn, *args))
    except Exception:
        logger.exception(f"MCP tool call {fn.__name__}{args} failed")
        raise


# --- Data tools ---------------------------------------------------------------


@mcp.tool()
async def tool_market(symbol: str) -> TickerSnapshot:
    """Company profile, price, valuation and profitability ratios, and analyst price targets (yfinance)."""
    return await _run(get_ticker_snapshot, symbol)


@mcp.tool()
async def tool_technical(symbol: str) -> TechnicalSnapshot | None:
    """Price and volume indicators from 2 years of daily history: SMA 50/200, RSI, MACD, 1/3/6-month returns,
    52-week range, volume balance, relative volume and ATR (yfinance)."""
    return await _run(get_technical_snapshot, symbol)


@mcp.tool()
async def tool_peers(symbol: str) -> PeerComparison:
    """The stock vs its 5 largest industry peers: their ratios, the peer median, and the stock's
    valuation premium or discount to that median (yfinance)."""
    return await _run(compare_to_peers, symbol)


@mcp.tool()
async def tool_sector(symbol: str) -> SectorTrend:
    """1/3/6-month returns of the stock, its SPDR sector ETF and SPY, with excess returns
    (sector vs market, stock vs sector)."""
    return await _run(get_sector_trend, symbol)


class EdgarData(BaseModel):
    filings: CompanyFilings
    financials: EarningsFacts


@mcp.tool()
async def tool_edgar(symbol: str) -> EdgarData:
    """SEC EDGAR: recent 10-K, 10-Q and earnings 8-K filings, plus reported annual and quarterly
    diluted EPS, revenue, net income and operating cash flow (XBRL)."""
    filings = await _run(get_company_filings, symbol)
    return EdgarData(filings=filings, financials=await _run(get_earnings_facts, symbol))


@mcp.tool()
async def tool_edgar_search(symbol: str, question: str) -> FilingQueryResult:
    """Search the latest 10-K and 10-Q MD&A and recent earnings press releases for passages answering
    a question (e.g. "what did management say about margins?"). Filings are indexed on first use."""
    await _run(ingest_filings, symbol)
    return await _run(query_filings, symbol, question)


@mcp.tool()
async def tool_news(symbol: str) -> NewsFeed:
    """Recent news articles (last 14 days) from Yahoo Finance, Google News and Seeking Alpha."""
    return await _run(get_ticker_news, symbol)


@mcp.tool()
async def tool_fred() -> MacroSnapshot:
    """U.S. macro snapshot from FRED: fed funds rate and 6-month change, CPI inflation and 6-month
    change, unemployment and Sahm indicator, real GDP growth, 10Y-2Y yield curve and VIX."""
    return await _run(get_macro_snapshot)


class StockTwitsData(BaseModel):
    sentiment: StockTwitsSentiment
    trending: bool


@mcp.tool()
async def tool_stocktwits(symbol: str) -> StockTwitsData:
    """StockTwits: latest posts with their bullish/bearish tags, and whether the ticker is trending now."""
    sentiment = await _run(fetch_stocktwits_sentiment, symbol)
    trending = await _run(fetch_stocktwits_trending)
    return StockTwitsData(sentiment=sentiment, trending=symbol.upper() in {t.symbol for t in trending})


@mcp.tool()
async def tool_apewisdom(symbol: str) -> ApeWisdomMention | None:
    """ApeWisdom mention rank and 24h mention counts on stock discussion forums; null if not ranked."""
    return await _run(fetch_mentions, symbol)


@mcp.tool()
async def tool_polymarket(symbol: str) -> list[PolymarketMarket]:
    """Open Polymarket prediction markets about the company (e.g. earnings beat, leadership), excluding
    price bets, with the probability of the stated outcome."""
    return await _run(fetch_polymarket_markets, symbol)


# --- Analyst tools ------------------------------------------------------------

_ANALYST_NOTE = " Returns score 1-5 (1 strongly bearish, 5 strongly bullish), decision, confidence and reasoning."


@mcp.tool(description="Technical analyst: price trend, momentum and volume confirmation (short term)." + _ANALYST_NOTE)
async def analyst_technical(symbol: str) -> AgentScore:
    return await _run(analyze_technical, symbol)


@mcp.tool(description="Fundamentals analyst: valuation, profitability and financial health (long term)." + _ANALYST_NOTE)
async def analyst_fundamentals(symbol: str) -> AgentScore:
    return await _run(analyze_fundamentals, symbol)


@mcp.tool(description="Peers analyst: valuation and quality vs the industry peer median." + _ANALYST_NOTE)
async def analyst_peers(symbol: str) -> AgentScore:
    return await _run(analyze_peers, symbol)


@mcp.tool(description="Sector analyst: sector ETF vs market, and the stock vs its sector." + _ANALYST_NOTE)
async def analyst_sector(symbol: str) -> AgentScore:
    return await _run(analyze_sector, symbol)


@mcp.tool(
    description="Earnings analyst: SEC-reported EPS trend, quarterly momentum, cash conversion and guidance."
    + _ANALYST_NOTE
)
async def analyst_earnings(symbol: str) -> AgentScore:
    return await _run(analyze_earnings, symbol)


@mcp.tool(description="News analyst: relevance, sentiment and materiality of recent articles." + _ANALYST_NOTE)
async def analyst_news(symbol: str) -> AgentScore:
    return await _run(analyze_news, symbol)


@mcp.tool(
    description="Sentiment analyst: StockTwits tags and tone, ApeWisdom attention, Polymarket." + _ANALYST_NOTE
)
async def analyst_sentiment(symbol: str) -> AgentScore:
    return await _run(analyze_sentiment, symbol)


@mcp.tool(description="Macro analyst: the FRED macro regime judged for the stock's sector." + _ANALYST_NOTE)
async def analyst_macro(symbol: str) -> AgentScore:
    return await _run(analyze_macro, symbol)


# --- Workflows ----------------------------------------------------------------


@mcp.tool(name="analyze_ticker")
async def analyze_ticker_tool(symbol: str) -> TickerAnalysis:
    """Full analysis (~15s): all 8 analysts, a short-term and a long-term consensus, the combined
    decision and setup (aligned, long_term, accumulate = starter position, trade), a risk plan
    (position size, ATR-based stop-loss and take-profit) and an investment thesis."""
    return await _run(analyze_ticker, symbol)


@mcp.tool()
async def review_portfolio(holdings: list[Holding] | None = None, csv_path: str | None = None) -> PortfolioReport:
    """Analyze every holding with the full analysis, then review the portfolio: weights, unrealized P&L,
    concentration, sector exposure, and an add/hold/trim/exit action per position with reasons.
    Give either holdings (symbol, qty, avg_cost, position_type long/short) or csv_path to a CSV on
    the server's machine with columns symbol,qty,avg_cost,type. Takes ~15s per 3 holdings."""
    if (holdings is None) == (csv_path is None):
        raise ValueError("Provide exactly one of holdings or csv_path")
    return await _run(run_portfolio_review, holdings or load_portfolio_csv(csv_path))


@mcp.tool()
async def discover_stocks(limit: int = config.DISCOVERY_LIMIT) -> DiscoveryReport:
    """Find trending common stocks (ApeWisdom mentions and StockTwits trending), run the full analysis
    on each, and rank them: research_further, watch or skip. Takes ~15s per 3 candidates."""
    return await _run(run_discovery, limit)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
