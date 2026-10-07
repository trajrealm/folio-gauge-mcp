"""
src/analysts/technical.py
Technical Analyst Agent (price and volume)

Trend, momentum and volume labels are computed in code from the technical
snapshot and given to the LLM as facts; the LLM judges the overall setup
(e.g. whether a move is confirmed by volume, or stretched) and scores.
Errors propagate to the caller.
"""

from __future__ import annotations

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from src.agent.knowledge import load_prompt
from src.agent.scoring import AgentScore, compute_confidence, decision_from_score
from src.tools.technical import TechnicalSnapshot, get_technical_snapshot

from .. import config

# Label names for a signal of +1 / 0 / -1.
LABELS = {
    "trend": ("uptrend", "mixed", "downtrend"),
    "momentum": ("bullish", "neutral", "bearish"),
    "volume": ("accumulation", "neutral", "distribution"),
}


class TechnicalAnalysis(BaseModel):
    score: int = Field(ge=1, le=5, description="1=strong bearish, 3=neutral, 5=strong bullish")
    reasoning: str = Field(description="2-3 sentence explanation")
    key_signals: list[str]
    risk_flags: list[str]


def _band(value: float, band: float) -> int:
    return 1 if value > band else -1 if value < -band else 0


def _trend(s: TechnicalSnapshot) -> int | None:
    """Price above both SMA 50 and 200 = uptrend, below both = downtrend, else mixed.
    The SMA 50/200 cross is not required: it lags price by weeks."""
    if s.sma_50 is None or s.sma_200 is None:
        return None
    if s.price > max(s.sma_50, s.sma_200):
        return 1
    if s.price < min(s.sma_50, s.sma_200):
        return -1
    return 0


def _momentum(s: TechnicalSnapshot) -> int | None:
    """Mean vote of the MACD histogram sign and 1/3/6-month returns."""
    votes = [_band(s.macd_histogram, 0)] if s.macd_histogram is not None else []
    for key, band in config.TECHNICAL_RETURN_BANDS.items():
        value = getattr(s, key)
        if value is not None:
            votes.append(_band(value, band))
    return _band(sum(votes) / len(votes), config.LABEL_VOTE_BAND) if votes else None


def _volume(s: TechnicalSnapshot) -> int | None:
    if s.volume_balance is None:
        return None
    return _band(s.volume_balance, config.TECHNICAL_VOLUME_BALANCE_BAND)


def _rsi_zone(s: TechnicalSnapshot) -> str:
    if s.rsi_14 is None:
        return "not assessable"
    overbought, oversold = config.TECHNICAL_RSI_BANDS
    return "overbought" if s.rsi_14 > overbought else "oversold" if s.rsi_14 < oversold else "neutral"


def _fmt(value: float | None, kind: str) -> str:
    if value is None:
        return "n/a"
    return {"pct": f"{value:+.1%}", "price": f"{value:,.2f}", "num": f"{value:.2f}"}[kind]


def _format_snapshot(s: TechnicalSnapshot) -> str:
    rows = [
        ("Price", s.price, "price"),
        ("SMA 50", s.sma_50, "price"),
        ("SMA 200", s.sma_200, "price"),
        ("RSI 14", s.rsi_14, "num"),
        ("MACD histogram", s.macd_histogram, "num"),
        ("Return 1m", s.return_1m, "pct"),
        ("Return 3m", s.return_3m, "pct"),
        ("Return 6m", s.return_6m, "pct"),
        ("52-week high", s.week_52_high, "price"),
        ("52-week low", s.week_52_low, "price"),
        ("Position in 52-week range (0=low, 1=high)", s.range_position, "num"),
        ("Volume balance 20d (-1 selling to +1 buying)", s.volume_balance, "num"),
        ("Relative volume (20d / 3m average)", s.relative_volume, "num"),
    ]
    return "\n".join(f"  {label}: {_fmt(value, kind)}" for label, value, kind in rows)


def analyze_technical(ticker: str) -> AgentScore:
    """
    Flow:
      1. Fetch price/volume history and compute indicators (tools/technical.py)
      2. Compute trend, momentum and volume labels in code
      3. LLM judges the setup and scores; decision is derived from the score
      4. Confidence = label coverage x agreement of trend, momentum and volume
    """
    snapshot = get_technical_snapshot(ticker)
    if snapshot is None:
        return AgentScore(
            agent="technical",
            symbol=ticker,
            decision="HOLD",
            score=3,
            timeframe="short",
            reasoning="No price history available",
            confidence=0.1,
            data_gaps=["No price history from yfinance"],
        )

    signals = {"trend": _trend(snapshot), "momentum": _momentum(snapshot), "volume": _volume(snapshot)}
    labels = {k: "not assessable" if v is None else LABELS[k][1 - v] for k, v in signals.items()}
    labels_text = "; ".join(f"{k}: {v}" for k, v in labels.items()) + f"; RSI zone: {_rsi_zone(snapshot)}"

    user_prompt = f"""Assess the technical setup of {ticker} ({snapshot.trading_days} trading days of history).

{_format_snapshot(snapshot)}

Computed assessment (facts): {labels_text}"""

    llm = ChatOpenAI(model=config.LLM_MODEL_AGENTS, temperature=config.LLM_TEMPERATURE_AGENTS)
    analysis: TechnicalAnalysis = llm.with_structured_output(TechnicalAnalysis).invoke(
        [
            {"role": "system", "content": load_prompt("technical")},
            {"role": "user", "content": user_prompt},
        ],
        config={"run_name": "Technical Agent"},
    )

    available = [v for v in signals.values() if v is not None]
    data_gaps = [f"{k} not assessable (short history)" for k, v in signals.items() if v is None]

    parts = [analysis.reasoning, labels_text[0].upper() + labels_text[1:] + "."]
    if analysis.key_signals:
        parts.append("Key signals: " + ", ".join(analysis.key_signals) + ".")
    if analysis.risk_flags:
        parts.append("Risks: " + ", ".join(analysis.risk_flags) + ".")

    return AgentScore(
        agent="technical",
        symbol=ticker,
        decision=decision_from_score(analysis.score),
        score=analysis.score,
        timeframe="short",
        reasoning="Technical: " + " ".join(parts),
        confidence=compute_confidence(len(available) / len(signals), available),
        data_gaps=data_gaps,
    )
