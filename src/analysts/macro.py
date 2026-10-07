"""
src/analysts/macro.py
Macro Analyst Agent

The macro regime (rates, inflation, labor, growth, yield curve, volatility)
is labelled in code from the FRED snapshot and given to the LLM as facts,
with the stock's sector. The LLM judges how this backdrop affects that
sector and scores. Errors propagate to the caller.
"""

from __future__ import annotations

import yfinance as yf
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from src.agent.knowledge import load_prompt
from src.agent.scoring import AgentScore, compute_confidence, decision_from_score
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


def analyze_macro(ticker: str) -> AgentScore:
    """
    Flow:
      1. Fetch the FRED macro snapshot (cached per day) and the stock's sector
      2. Compute regime labels in code
      3. LLM judges the impact on this sector and scores; decision is derived from the score
      4. Confidence = agreement of rates, inflation, labor and growth labels
    """
    snapshot = get_macro_snapshot()
    sector = yf.Ticker(ticker).info.get("sector")
    labels = _labels(snapshot)
    labels_text = "; ".join(f"{k}: {v}" for k, v in labels.items())

    user_prompt = f"""Assess the macro backdrop for {ticker} (sector: {sector or "unknown"}).

{_format_snapshot(snapshot)}

Computed assessment (facts): {labels_text}"""

    llm = ChatOpenAI(model=config.LLM_MODEL_AGENTS, temperature=config.LLM_TEMPERATURE_AGENTS)
    analysis: MacroAnalysis = llm.with_structured_output(MacroAnalysis).invoke(
        [
            {"role": "system", "content": load_prompt("macro")},
            {"role": "user", "content": user_prompt},
        ],
        config={"run_name": "Macro Agent"},
    )

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
