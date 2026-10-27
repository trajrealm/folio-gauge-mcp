"""
src/analysts/macro.py
Macro Analyst Agent

The macro regime (rates, inflation, labor, growth, yield curve, volatility)
is labelled in code from the FRED snapshot. The agent calls two tools, one
for these indicators and labels (facts) and one for the stock's sector. The
LLM judges how this backdrop affects that sector and scores. Errors propagate to the caller.
"""

from __future__ import annotations

import yfinance as yf
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.agent.scoring import AgentScore, compute_confidence, decision_from_score
from src.agent.tool_agent import run_tool_agent
from src.tools.fred import MacroSnapshot, get_macro_snapshot

from .. import config

# Signal for equities per label: rates, inflation, labor and growth drive
# confidence; curve and volatility are context only.
SIGNALS = {
    "easing": 1, "tightening": -1,
    "cooling": 1, "heating": -1,
    "solid": 1, "softening": 0, "recession signal": -1,
    "expanding": 1, "slow": 0, "contracting": -1,
    "stable": 0,
}  # fmt: skip


class MacroAnalysis(BaseModel):
    score: int = Field(ge=1, le=5, description="1=strong headwind for this sector, 3=neutral, 5=strong tailwind")
    reasoning: str = Field(description="2-3 sentence explanation")
    key_signals: list[str]
    risk_flags: list[str]


def _change(delta: float, band: float, up: str, down: str) -> str:
    return up if delta > band else down if delta < -band else "stable"


def _labels(m: MacroSnapshot) -> dict[str, str]:
    softening, recession = config.MACRO_SAHM_BANDS
    expanding, contracting = config.MACRO_GDP_BANDS
    normal, inverted = config.MACRO_CURVE_BANDS
    calm, stressed = config.MACRO_VIX_BANDS
    return {
        "rates": _change(m.fed_funds - m.fed_funds_6m_ago, config.MACRO_RATE_CHANGE_BAND, "tightening", "easing"),
        "inflation": _change(m.cpi_yoy - m.cpi_yoy_6m_ago, config.MACRO_INFLATION_CHANGE_BAND, "heating", "cooling"),
        "labor": "recession signal" if m.sahm >= recession else "softening" if m.sahm >= softening else "solid",
        "growth": "expanding" if m.gdp_growth > expanding else "contracting" if m.gdp_growth < contracting else "slow",
        "yield curve": "normal" if m.yield_curve > normal else "inverted" if m.yield_curve < inverted else "flat",
        "volatility": "calm" if m.vix < calm else "stressed" if m.vix > stressed else "normal",
    }


def _format_snapshot(m: MacroSnapshot) -> str:
    return "\n".join(
        [
            f"  Fed funds rate: {m.fed_funds:.2f}% (6 months ago: {m.fed_funds_6m_ago:.2f}%)",
            f"  CPI inflation YoY: {m.cpi_yoy:.2f}% (6 months earlier: {m.cpi_yoy_6m_ago:.2f}%), as of {m.cpi_as_of}",
            f"  Unemployment: {m.unemployment:.1f}%; Sahm indicator: {m.sahm:.2f} (>= 0.5 has signalled recessions)",
            f"  Real GDP growth (annualized): {m.gdp_growth:.1f}%, quarter starting {m.gdp_as_of}",
            f"  Yield curve 10Y-2Y: {m.yield_curve:+.2f} pts",
            f"  VIX: {m.vix:.1f}",
        ]
    )


@tool(response_format="content_and_artifact")
def get_macro_indicators() -> tuple[str, dict[str, str]]:
    """Fetch the US macro snapshot (fed funds, CPI, unemployment and Sahm, GDP growth,
    yield curve, VIX) with regime labels computed in code. Treat all of it as facts."""
    snapshot = get_macro_snapshot()
    labels = _labels(snapshot)
    labels_text = "; ".join(f"{k}: {v}" for k, v in labels.items())
    return f"{_format_snapshot(snapshot)}\n\nComputed assessment (facts): {labels_text}", labels


@tool(response_format="content_and_artifact")
def get_company_sector(ticker: str) -> tuple[str, str | None]:
    """Look up the sector of a stock ticker."""
    sector = yf.Ticker(ticker).info.get("sector")
    return f"{ticker} sector: {sector or 'unknown'}", sector


def analyze_macro(ticker: str) -> AgentScore:
    """
    Flow:
      1. Agent calls get_macro_indicators (FRED snapshot, cached per day; regime labels
         in code) and get_company_sector
      2. LLM judges the impact on this sector and scores; decision is derived from the score
      3. Confidence = agreement of rates, inflation, labor and growth labels
    """
    analysis, artifacts = run_tool_agent(
        "macro",
        [get_macro_indicators, get_company_sector],
        MacroAnalysis,
        f"Assess the macro backdrop for {ticker}.",
    )
    labels, sector = artifacts["get_macro_indicators"], artifacts["get_company_sector"]
    labels_text = "; ".join(f"{k}: {v}" for k, v in labels.items())
    signals = [SIGNALS[labels[k]] for k in ("rates", "inflation", "labor", "growth")]

    parts = [analysis.reasoning, labels_text[0].upper() + labels_text[1:] + "."]
    if analysis.key_signals:
        parts.append("Key signals: " + ", ".join(analysis.key_signals) + ".")
    if analysis.risk_flags:
        parts.append("Risks: " + ", ".join(analysis.risk_flags) + ".")

    return AgentScore(
        agent="macro",
        symbol=ticker,
        decision=decision_from_score(analysis.score),
        score=analysis.score,
        timeframe="mid",
        reasoning="Macro: " + " ".join(parts),
        confidence=compute_confidence(1.0 if sector else 0.5, signals),
        data_gaps=[] if sector else ["Sector unknown; macro judged market-wide"],
    )
