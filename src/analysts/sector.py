"""
src/analysts/sector.py
Sector Analyst Agent

Judges sector tailwinds and the stock's position within its sector from
relative returns (tools/sector.py). Labels are computed in code and given
to the LLM as facts; the LLM judges the combination and scores.
Errors propagate to the caller.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.agent.knowledge import load_prompt
from src.agent.scoring import AgentScore, compute_confidence, decision_from_score
from src.tools.sector import SectorTrend, get_sector_trend
from src.utils.llm import get_llm

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


def analyze_sector(ticker: str) -> AgentScore:
    """
    Flow:
      1. Fetch stock, sector ETF and market returns (tools/sector.py)
      2. Compute sector-vs-market and stock-vs-sector labels in code
      3. LLM judges the combination and scores; decision is derived from the score
      4. Confidence = label coverage x agreement of the two labels
    """
    trend = get_sector_trend(ticker)
    if trend.sector_etf is None:
        return AgentScore(
            agent="sector",
            symbol=ticker,
            decision="HOLD",
            score=3,
            timeframe="mid",
            reasoning=f"No sector ETF for sector '{trend.sector}'",
            confidence=0.1,
            data_gaps=[f"No sector ETF mapped for '{trend.sector}'"],
        )

    signals = {
        "sector_vs_market": _signal(trend.sector_vs_market),
        "stock_vs_sector": _signal(trend.stock_vs_sector),
    }
    labels = {k: "not assessable" if v is None else LABELS[k][1 - v] for k, v in signals.items()}
    labels_text = (
        f"sector vs market: {labels['sector_vs_market']}; "
        f"stock vs sector: {labels['stock_vs_sector']}"
    )

    user_prompt = f"""Assess the sector trend for {ticker} (sector: {trend.sector}).

{_format_trend(trend)}

Computed assessment (facts): {labels_text}"""

    llm = get_llm(config.LLM_MODEL_AGENTS, config.LLM_TEMPERATURE_AGENTS)
    analysis: SectorAnalysis = llm.with_structured_output(SectorAnalysis).invoke(
        [
            {"role": "system", "content": load_prompt("sector")},
            {"role": "user", "content": user_prompt},
        ],
        config={"run_name": "Sector Agent"},
    )

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
