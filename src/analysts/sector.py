"""
src/analysts/sector.py
Sector Analyst Agent

Judges sector tailwinds and the stock's position within its sector from
relative returns (tools/sector.py). The agent calls get_sector_trend_facts,
which returns the returns and labels computed in code (facts); the LLM judges the combination and scores.
Errors propagate to the caller.
"""

from __future__ import annotations

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.agent.scoring import AgentScore, compute_confidence, decision_from_score
from src.agent.tool_agent import run_tool_agent
from src.tools.sector import SectorTrend, get_sector_trend

from .. import config

# Label names for a signal of +1 / 0 / -1.
LABELS = {
    "sector_vs_market": ("tailwind", "neutral", "headwind"),
    "stock_vs_sector": ("leading", "in_line", "lagging"),
}


class SectorAnalysis(BaseModel):
    score: int = Field(ge=1, le=5, description="1=strong headwind, 3=neutral, 5=strong tailwind")
    reasoning: str = Field(description="2-3 sentence explanation")
    key_signals: list[str]
    risk_flags: list[str]


def _signal(excess: dict[str, float | None]) -> int | None:
    """Mean vote of excess returns beyond config.SECTOR_RELATIVE_BANDS per window."""
    votes = [
        1 if value > band else -1 if value < -band else 0
        for key, band in config.SECTOR_RELATIVE_BANDS.items()
        if (value := excess[key]) is not None
    ]
    if not votes:
        return None
    mean = sum(votes) / len(votes)
    return 1 if mean > config.LABEL_VOTE_BAND else -1 if mean < -config.LABEL_VOTE_BAND else 0


def _format_trend(t: SectorTrend) -> str:
    def row(label: str, values: dict[str, float | None]) -> str:
        cells = ["n/a" if v is None else f"{v:+.1%}" for v in values.values()]
        return " | ".join([label] + cells)

    return "\n".join(
        [
            "Series | 1m | 3m | 6m",
            row(t.symbol, t.stock_returns),
            row(f"Sector ({t.sector_etf})", t.sector_returns),
            row(f"Market ({config.MARKET_ETF})", t.market_returns),
            row("Sector vs market", t.sector_vs_market),
            row(f"{t.symbol} vs sector", t.stock_vs_sector),
        ]
    )


@tool(response_format="content_and_artifact")
def get_sector_trend_facts(ticker: str) -> tuple[str, dict | None]:
    """Fetch 1/3/6-month returns of a stock, its sector ETF and the market, with
    sector-vs-market and stock-vs-sector labels computed in code. Treat all of it as facts."""
    trend = get_sector_trend(ticker)
    if trend.sector_etf is None:
        return f"No sector ETF mapped for sector '{trend.sector}'.", {"no_etf_sector": trend.sector}

    signals = {
        "sector_vs_market": _signal(trend.sector_vs_market),
        "stock_vs_sector": _signal(trend.stock_vs_sector),
    }
    labels = {k: "not assessable" if v is None else LABELS[k][1 - v] for k, v in signals.items()}
    labels_text = (
        f"sector vs market: {labels['sector_vs_market']}; "
        f"stock vs sector: {labels['stock_vs_sector']}"
    )
    content = f"""{ticker} (sector: {trend.sector})

{_format_trend(trend)}

Computed assessment (facts): {labels_text}"""
    return content, {"signals": signals, "labels_text": labels_text}


def analyze_sector(ticker: str) -> AgentScore:
    """
    Flow:
      1. Agent calls get_sector_trend_facts (stock, sector ETF and market returns from
         tools/sector.py; sector-vs-market and stock-vs-sector labels in code)
      2. LLM judges the combination and scores; decision is derived from the score
      3. Confidence = label coverage x agreement of the two labels
    """
    analysis, artifacts = run_tool_agent(
        "sector", [get_sector_trend_facts], SectorAnalysis, f"Assess the sector trend for {ticker}."
    )
    artifact = artifacts["get_sector_trend_facts"]
    if "no_etf_sector" in artifact:
        sector = artifact["no_etf_sector"]
        return AgentScore(
            agent="sector",
            symbol=ticker,
            decision="HOLD",
            score=3,
            timeframe="mid",
            reasoning=f"No sector ETF for sector '{sector}'",
            confidence=0.1,
            data_gaps=[f"No sector ETF mapped for '{sector}'"],
        )

    signals, labels_text = artifact["signals"], artifact["labels_text"]
    available = [v for v in signals.values() if v is not None]
    data_gaps = [f"{k} not assessable (short history)" for k, v in signals.items() if v is None]

    parts = [analysis.reasoning, labels_text[0].upper() + labels_text[1:] + "."]
    if analysis.key_signals:
        parts.append("Key signals: " + ", ".join(analysis.key_signals) + ".")
    if analysis.risk_flags:
        parts.append("Risks: " + ", ".join(analysis.risk_flags) + ".")

    return AgentScore(
        agent="sector",
        symbol=ticker,
        decision=decision_from_score(analysis.score),
        score=analysis.score,
        timeframe="mid",
        reasoning="Sector: " + " ".join(parts),
        confidence=compute_confidence(len(available) / len(signals), available),
        data_gaps=data_gaps,
    )
