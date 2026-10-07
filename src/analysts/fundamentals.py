"""
src/analysts/fundamentals.py
Fundamentals Analyst Agent

Scores valuation, profitability and financial health from yfinance ratios,
in the context of the company's sector. Growth is used only to judge
valuation; the growth trend and earnings quality belong to the earnings
analyst. Errors propagate to the caller.
"""

from __future__ import annotations

from typing import Literal

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from src.agent.knowledge import load_prompt
from src.agent.scoring import AgentScore, compute_confidence, decision_from_score
from src.tools.market import Fundamentals, get_ticker_snapshot

from .. import config

# (field, label, format): "x" = multiple, "pct" = fraction shown as percent
METRICS: list[tuple[str, str, str]] = [
    ("pe_ratio", "P/E (trailing)", "x"),
    ("forward_pe", "P/E (forward)", "x"),
    ("peg_ratio", "PEG", "x"),
    ("price_to_book", "P/B", "x"),
    ("ev_to_ebitda", "EV/EBITDA", "x"),
    ("free_cash_flow_yield", "FCF yield", "pct"),
    ("return_on_equity", "ROE", "pct"),
    ("return_on_assets", "ROA", "pct"),
    ("operating_margin", "Operating margin", "pct"),
    ("profit_margin", "Net margin", "pct"),
    ("debt_to_equity", "Debt/Equity", "x"),
    ("current_ratio", "Current ratio", "x"),
    ("quick_ratio", "Quick ratio", "x"),
    ("revenue_growth", "Revenue growth (latest quarter YoY)", "pct"),
    ("earnings_growth", "Earnings growth (latest quarter YoY)", "pct"),
]


class FundamentalsAnalysis(BaseModel):
    score: int = Field(ge=1, le=5, description="1=unattractive, 3=fairly valued, 5=attractive")
    valuation: Literal["cheap", "fair", "expensive"]
    profitability: Literal["strong", "average", "weak"]
    financial_health: Literal["strong", "adequate", "weak"]
    reasoning: str = Field(description="2-3 sentence explanation")
    key_signals: list[str]
    risk_flags: list[str]

SIGNALS = {
    "cheap": 1, "fair": 0, "expensive": -1,
    "strong": 1, "average": 0, "adequate": 0, "weak": -1,
}  # fmt: skip


def _format_metrics(fundamentals: Fundamentals) -> str:
    lines = []
    for field, label, fmt in METRICS:
        value = getattr(fundamentals, field)
        if value is None:
            text = "n/a"
        elif fmt == "pct":
            text = f"{value:.1%}"
        else:
            text = f"{value:.2f}x"
        lines.append(f"  {label}: {text}")
    return "\n".join(lines)


def analyze_fundamentals(ticker: str) -> AgentScore:
    """
    Flow:
      1. Fetch the yfinance snapshot (profile + fundamentals)
      2. LLM produces a structured score; decision is derived from the score
      3. Confidence = metric coverage x agreement of the three sub-assessments
    """
    snapshot = get_ticker_snapshot(ticker)
    fundamentals = snapshot.fundamentals

    data_gaps = [label for field, label, _ in METRICS if getattr(fundamentals, field) is None]
    if len(data_gaps) == len(METRICS):
        return AgentScore(
            agent="fundamentals",
            symbol=ticker,
            decision="HOLD",
            score=3,
            timeframe="long",
            reasoning="No fundamentals data available",
            confidence=0.1,
            data_gaps=["No fundamentals data from yfinance"],
        )

    profile = snapshot.profile
    market_cap = f"{profile.market_cap / 1e9:,.1f}B" if profile.market_cap else "n/a"
    user_prompt = f"""Analyze the fundamentals of {ticker} ({profile.name}).
Sector: {profile.sector or "n/a"}; industry: {profile.industry or "n/a"}; market cap: {market_cap}

{_format_metrics(fundamentals)}"""

    llm = ChatOpenAI(model=config.LLM_MODEL_AGENTS, temperature=config.LLM_TEMPERATURE_AGENTS)
    analysis: FundamentalsAnalysis = llm.with_structured_output(FundamentalsAnalysis).invoke(
        [
            {"role": "system", "content": load_prompt("fundamentals")},
            {"role": "user", "content": user_prompt},
        ],
        config={"run_name": "Fundamentals Agent"},
    )

    coverage = 1 - len(data_gaps) / len(METRICS)
    signals = [SIGNALS[analysis.valuation], SIGNALS[analysis.profitability], SIGNALS[analysis.financial_health]]

    parts = [
        analysis.reasoning,
        f"Valuation: {analysis.valuation}; profitability: {analysis.profitability}; "
        f"financial health: {analysis.financial_health}.",
    ]
    if analysis.key_signals:
        parts.append("Key signals: " + ", ".join(analysis.key_signals) + ".")
    if analysis.risk_flags:
        parts.append("Risks: " + ", ".join(analysis.risk_flags) + ".")

    return AgentScore(
        agent="fundamentals",
        symbol=ticker,
        decision=decision_from_score(analysis.score),
        score=analysis.score,
        timeframe="long",
        reasoning="Fundamentals: " + " ".join(parts),
        confidence=compute_confidence(coverage, signals),
        data_gaps=[f"Missing: {', '.join(data_gaps)}"] if data_gaps else [],
    )
