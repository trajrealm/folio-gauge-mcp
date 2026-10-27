"""
src/analysts/earnings.py
Earnings Analyst Agent

Combines two SEC sources, each a tool the agent calls:
  1. Numbers from XBRL company facts: annual and quarterly EPS, revenue and
     net income with YoY growth, plus operating cash flow / net income.
  2. Narrative via RAG: MD&A of the latest 10-K and 10-Q and recent earnings
     press releases, for guidance, one-time items and management tone.

Filings do not contain analyst consensus estimates, so beat/miss versus
expectations is not assessed. Errors propagate to the caller.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.agent.scoring import AgentScore, compute_confidence, decision_from_score
from src.agent.tool_agent import run_tool_agent
from src.tools.edgar import EarningsFacts, get_earnings_facts, ingest_filings, query_filings

from .. import config

NARRATIVE_QUESTIONS = {
    "10-K": [
        "What does management expect for future revenue, margins and earnings, and what will drive them?",
        "Were there one-time, non-recurring or unusual items affecting reported earnings?",
    ],
    "10-Q": [
        "What drove the change in revenue, margins and net income versus the prior-year quarter?",
        "Were there one-time, non-recurring or unusual items affecting quarterly results?",
    ],
    "8-K": [
        "What guidance or outlook did the company give for the next quarter or fiscal year?",
    ],
}

QUARTERLY_METRICS = ("eps_diluted", "revenue", "net_income")

# not_stated guidance carries no signal and is left out.
SIGNALS = {
    "strong": 1, "solid": 1, "flat": 0, "declining": -1,
    "accelerating": 1, "steady": 0, "decelerating": -1,
    "raised": 1, "maintained": 0, "lowered": -1, "withdrawn": -1,
    "high": 1, "medium": 0, "low": -1,
}  # fmt: skip


class EarningsAnalysis(BaseModel):
    score: int = Field(ge=1, le=5, description="1=strong bearish, 3=neutral, 5=strong bullish")
    guidance_signal: Literal["raised", "maintained", "lowered", "withdrawn", "not_stated"]
    reasoning: str = Field(description="2-3 sentence explanation")
    key_signals: list[str]
    risk_flags: list[str]


def _fmt(metric: str, value: float) -> str:
    return f"{value:.2f}" if metric == "eps_diluted" else f"{value / 1e9:,.2f}B"


def _prior_year(frame: str) -> str:
    """CY2025 -> CY2024, CY2025Q3 -> CY2024Q3."""
    return f"CY{int(frame[2:6]) - 1}{frame[6:]}"


def _series_line(metric: str, series: dict[str, float], count: int = 4) -> str:
    parts = []
    for frame in sorted(series)[-count:]:
        part = f"{frame}={_fmt(metric, series[frame])}"
        prior = series.get(_prior_year(frame))
        if prior:
            part += f" ({(series[frame] - prior) / abs(prior):+.0%} YoY)"
        parts.append(part)
    return f"  {metric}: " + ", ".join(parts)


def _latest_yoy(series: dict[str, float]) -> float | None:
    latest = max(series, default=None)
    prior = series.get(_prior_year(latest)) if latest else None
    return (series[latest] - prior) / abs(prior) if prior else None


def _eps_trend(facts: EarningsFacts) -> str | None:
    """Latest annual diluted EPS YoY against config.EARNINGS_EPS_BANDS."""
    growth = _latest_yoy(facts.annual.get("eps_diluted", {}))
    if growth is None:
        return None
    strong, solid, flat = config.EARNINGS_EPS_BANDS
    return "strong" if growth > strong else "solid" if growth >= solid else "flat" if growth >= flat else "declining"


def _momentum(facts: EarningsFacts) -> str | None:
    """Latest quarterly EPS YoY vs latest annual EPS YoY (config.EARNINGS_MOMENTUM_BAND)."""
    annual = _latest_yoy(facts.annual.get("eps_diluted", {}))
    quarterly = _latest_yoy(facts.quarterly.get("eps_diluted", {}))
    if annual is None or quarterly is None:
        return None
    gap, band = quarterly - annual, config.EARNINGS_MOMENTUM_BAND
    return "accelerating" if gap > band else "decelerating" if gap < -band else "steady"


def _cash_quality(facts: EarningsFacts) -> str | None:
    """Latest annual operating cash flow / net income; None for financials."""
    if facts.is_financial:
        return None
    ocf = facts.annual.get("operating_cash_flow", {})
    net_income = facts.annual.get("net_income", {})
    latest = max(set(ocf) & set(net_income), default=None)
    if latest is None or net_income[latest] <= 0:
        return None
    ratio = ocf[latest] / net_income[latest]
    high, low = config.EARNINGS_CASH_CONVERSION
    return "high" if ratio >= high else "low" if ratio < low else "medium"


def _format_financials(facts: EarningsFacts) -> str:
    annual = facts.annual
    if facts.is_financial:
        annual = {m: s for m, s in annual.items() if m != "operating_cash_flow"}

    lines = ["Annual (fiscal years, labelled by nearest calendar year):"]
    lines += [_series_line(m, s) for m, s in annual.items() if s]

    ocf = annual.get("operating_cash_flow", {})
    net_income = annual.get("net_income", {})
    ratios = [
        f"{f}={ocf[f] / net_income[f]:.2f}"
        for f in sorted(net_income)[-4:]
        if f in ocf and net_income[f]
    ]
    if ratios:
        lines.append("  operating_cash_flow / net_income: " + ", ".join(ratios))

    lines.append("Quarterly (labelled by nearest calendar quarter):")
    lines += [
        _series_line(m, facts.quarterly[m]) for m in QUARTERLY_METRICS if facts.quarterly.get(m)
    ]
    if facts.is_financial:
        lines.append("Financial company: cash flow is omitted as not meaningful.")
    return "\n".join(lines)


def _retrieve_narrative(symbol: str) -> dict[str, str]:
    """
    Query the vector DB per filing type. Chunks already returned for an
    earlier question are not repeated. Returns {filing_type: section}.
    """
    sections: dict[str, str] = {}
    for filing_type, questions in NARRATIVE_QUESTIONS.items():
        seen: set[str] = set()
        parts: list[str] = []
        for question in questions:
            result = query_filings(symbol, question, filing_type=filing_type)
            chunks = [c for c in result.answer_chunks if c not in seen]
            seen.update(chunks)
            if chunks:
                dates = ", ".join(sorted(set(result.filed_dates)))
                parts.append(f"Q: {question}\nSources: {filing_type} ({dates})\n" + "\n---\n".join(chunks))
        if parts:
            sections[filing_type] = "\n\n".join(parts)
    return sections


@tool(response_format="content_and_artifact")
def get_reported_financials(ticker: str) -> tuple[str, dict]:
    """Fetch reported annual and quarterly EPS, revenue, net income (with YoY growth) and cash
    conversion from SEC XBRL filings for a stock ticker, oldest to newest, with EPS trend,
    quarterly momentum and earnings-quality labels computed in code. Treat all of it as facts."""
    facts = get_earnings_facts(ticker)
    eps_trend, momentum, quality = _eps_trend(facts), _momentum(facts), _cash_quality(facts)
    labels_text = (
        f"EPS trend (latest annual YoY): {eps_trend or 'not assessable'}; "
        f"quarterly momentum (latest quarter vs annual EPS YoY): {momentum or 'not assessable'}; "
        f"earnings quality (cash conversion): {quality or 'not assessable'}"
    )
    artifact = {
        "available": bool(facts.annual),
        "labels": (eps_trend, momentum, quality),
        "labels_text": labels_text,
    }
    if not facts.annual:
        return "No US-GAAP XBRL financials (foreign filers report IFRS on 20-F).", artifact
    content = f"""=== Reported financials (XBRL) ===
{_format_financials(facts)}

Computed assessment (facts): {labels_text}"""
    return content, artifact


@tool(response_format="content_and_artifact")
def get_filing_narrative(ticker: str) -> tuple[str, list[str]]:
    """Retrieve passages on guidance, drivers and one-time items from the latest 10-K and 10-Q
    MD&A and recent earnings press releases (8-K) for a stock ticker."""
    ingest_filings(ticker)
    narrative = _retrieve_narrative(ticker)
    missing = [f"No {t} narrative retrieved" for t in NARRATIVE_QUESTIONS if t not in narrative]
    sections = [f"=== {t} excerpts ===\n{section}" for t, section in narrative.items()]
    if missing:
        sections.append("Data gaps: " + ", ".join(missing))
    return "\n\n".join(sections), list(narrative)


def analyze_earnings(ticker: str) -> AgentScore:
    """
    Flow:
      1. Agent calls get_reported_financials (XBRL financials with YoY growth; EPS trend,
         quarterly momentum and cash-conversion quality labels in code)
      2. Agent calls get_filing_narrative (new filings ingested into Qdrant, then queried)
      3. LLM reads guidance from the narrative and scores; decision is derived from the score
      4. Confidence = source coverage x agreement of EPS trend, momentum, guidance and quality
    """
    analysis, artifacts = run_tool_agent(
        "earnings",
        [get_reported_financials, get_filing_narrative],
        EarningsAnalysis,
        f"Today is {date.today()}. Analyze {ticker}'s earnings performance and outlook from its SEC data.",
    )
    financials, narrative = artifacts["get_reported_financials"], artifacts["get_filing_narrative"]

    data_gaps: list[str] = []
    if not financials["available"]:
        data_gaps.append("No US-GAAP XBRL financials (foreign filers report IFRS on 20-F)")
    data_gaps += [f"No {t} narrative retrieved" for t in NARRATIVE_QUESTIONS if t not in narrative]

    if not financials["available"] and not narrative:
        return AgentScore(
            agent="earnings",
            symbol=ticker,
            decision="HOLD",
            score=3,
            timeframe="mid",
            reasoning="No SEC earnings data available",
            confidence=0.1,
            data_gaps=data_gaps,
        )

    sources = [financials["available"], *(t in narrative for t in NARRATIVE_QUESTIONS)]
    coverage = sum(sources) / len(sources)
    eps_trend, momentum, quality = financials["labels"]
    labels = (eps_trend, momentum, analysis.guidance_signal, quality)
    signals = [SIGNALS[v] for v in labels if v in SIGNALS]

    parts = [analysis.reasoning, f"{financials['labels_text']}; guidance: {analysis.guidance_signal}."]
    if analysis.key_signals:
        parts.append("Key signals: " + ", ".join(analysis.key_signals) + ".")
    if analysis.risk_flags:
        parts.append("Risks: " + ", ".join(analysis.risk_flags) + ".")

    return AgentScore(
        agent="earnings",
        symbol=ticker,
        decision=decision_from_score(analysis.score),
        score=analysis.score,
        timeframe="mid",
        reasoning="Earnings: " + " ".join(parts),
        confidence=compute_confidence(coverage, signals),
        data_gaps=data_gaps,
    )
