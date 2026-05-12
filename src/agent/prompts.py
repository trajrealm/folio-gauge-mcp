"""
agent/prompts.py
----------------
All prompt templates for the folio-gauge agent.
Keeping prompts in one place makes them easy to tune without
touching node logic.
"""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate


# ---------------------------------------------------------------------------
# System prompt — shared across all nodes
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are folio-gauge, an AI portfolio analyst.

Your job is to analyze stock portfolios based on:
  - SEC filings (10-K annual reports, 10-Q quarterly reports, 8-K material events)
  - Recent news and market sentiment
  - Key fundamental metrics (P/E, debt-to-equity, margins, growth)

You do NOT rely on price momentum, technical indicators, or volatility signals.
Your analysis is grounded in what companies actually report and what credible
news sources are saying right now.

Guidelines:
  - Be specific — cite filing dates, actual numbers, and news headlines
  - Be balanced — flag both risks and strengths
  - Be honest about uncertainty — if data is missing or stale, say so
  - Keep language clear — avoid jargon where plain English works
  - Never give explicit buy/sell advice — present findings, not orders
"""


# ---------------------------------------------------------------------------
# Planner node
# ---------------------------------------------------------------------------

PLANNER_PROMPT = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate.from_template(SYSTEM_PROMPT),
    HumanMessagePromptTemplate.from_template("""
The user wants to analyze the following portfolio: {symbols}

Their specific question is: "{user_query}"

Create a brief analysis plan. List:
1. What data you need for each ticker (market data / SEC filings / news)
2. What specific risks or themes to look for given the user's question
3. Any tickers that may need special attention

Keep the plan concise — 5 to 8 bullet points.
""")
])


# ---------------------------------------------------------------------------
# Reflection node
# ---------------------------------------------------------------------------

REFLECTION_PROMPT = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate.from_template(SYSTEM_PROMPT),
    HumanMessagePromptTemplate.from_template("""
You have fetched the following data for the portfolio {symbols}:

Market data available for: {market_symbols}
SEC filings available for: {filing_symbols}
News available for: {news_symbols}

Errors encountered: {errors}

Fetched market data:
{market_data_text}

Fetched filing data:
{filing_data_text}

Fetched news data:
{news_data_text}

Original plan:
{plan}

User question: "{user_query}"

Assess whether you have enough data to answer the user's question well.

Rules:
- If market data, filing data, AND news data are all present, respond SUFFICIENT: yes
- Only respond SUFFICIENT: no if one of those three is completely missing
- Do NOT ask for data beyond what was fetched (e.g. competitive analysis, additional filings)
- Do NOT second-guess the data quality

Respond with:
SUFFICIENT: [yes/no]
REASON: [one sentence explaining why]
MISSING: [what is completely absent, or "nothing" if all three data types are present]
""")
])


# ---------------------------------------------------------------------------
# Summarizer node
# ---------------------------------------------------------------------------

SUMMARIZER_PROMPT = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate.from_template(SYSTEM_PROMPT),
    HumanMessagePromptTemplate.from_template("""
Analyze the following portfolio and answer the user's question.

Portfolio: {symbols}
User question: "{user_query}"

--- MARKET DATA ---
{market_data_text}

--- SEC FILINGS ---
{filing_data_text}

--- RECENT NEWS ---
{news_data_text}

--- ANALYSIS PLAN ---
{plan}

Write a clear, structured analysis with these sections:

## Portfolio Overview
Brief snapshot of what this portfolio holds and its general character.

## Company-by-Company Findings
For each ticker: key fundamental signals, what the latest filing reveals,
and what recent news is saying. Flag any red flags or notable positives.

## Cross-Portfolio Risks
Concentration risks, shared exposures, or macro themes affecting multiple holdings.

## Summary
2-3 sentence bottom line answering the user's specific question.

Be specific. Cite filing dates and news headlines where relevant.
Do not give explicit buy/sell recommendations.
""")
])


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def format_market_data(market_data: dict) -> str:
    """Flatten market snapshots into LLM-readable text."""
    if not market_data:
        return "No market data available."

    lines = []
    for symbol, snap in market_data.items():
        p = snap.price
        f = snap.fundamentals
        a = snap.analysts
        pr = snap.profile

        lines.append(f"\n{symbol} — {pr.name}")
        lines.append(f"  Sector: {pr.sector or 'N/A'} | Industry: {pr.industry or 'N/A'}")
        lines.append(f"  Price: ${p.current_price or 'N/A'} | 52w High: ${p.week_52_high or 'N/A'} | 52w Low: ${p.week_52_low or 'N/A'}")
        lines.append(f"  Market Cap: ${pr.market_cap:,.0f}" if pr.market_cap else "  Market Cap: N/A")
        lines.append(f"  P/E: {f.pe_ratio or 'N/A'} | Fwd P/E: {f.forward_pe or 'N/A'} | P/B: {f.price_to_book or 'N/A'}")
        lines.append(f"  Debt/Equity: {f.debt_to_equity or 'N/A'} | ROE: {f.return_on_equity or 'N/A'}")
        lines.append(f"  Profit Margin: {f.profit_margin or 'N/A'} | Revenue Growth: {f.revenue_growth or 'N/A'}")
        lines.append(f"  Analyst: {a.recommendation or 'N/A'} | Target: ${a.target_mean_price or 'N/A'} ({a.number_of_analysts or 0} analysts)")

    return "\n".join(lines)


def format_filing_data(filing_data: dict) -> str:
    """Flatten SEC filing summaries into LLM-readable text."""
    if not filing_data:
        return "No SEC filing data available."

    lines = []
    for symbol, filing in filing_data.items():
        lines.append(f"\n{symbol} — {filing.filing_type} filed {filing.filed_date}")
        if filing.text_excerpt:
            lines.append(f"  Excerpt: {filing.text_excerpt[:1500]}")
        else:
            lines.append("  No text excerpt available.")

    return "\n".join(lines)


def format_news_data(news_data: dict) -> str:
    """Flatten news feeds into LLM-readable text."""
    if not news_data:
        return "No news data available."

    lines = []
    for symbol, feed in news_data.items():
        lines.append(f"\n{symbol} — {len(feed.articles)} articles (as of {feed.fetched_at[:10]})")
        for article in feed.articles[:6]:
            date = article.published[:10] if article.published else "?"
            summary = f" — {article.summary}" if article.summary else ""
            lines.append(f"  [{date}] {article.source}: {article.title}{summary}")

    return "\n".join(lines)