"""
src/analysts/peers.py
Peers Analyst Agent

Compares a company with named competitors (peer median from tools/peers.py).
Relative valuation and quality labels are computed in code and given to the
LLM as facts; the LLM judges whether a premium is justified and scores.
Errors propagate to the caller.
"""

from __future__ import annotations

from statistics import median

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from src.agent.knowledge import load_prompt
from src.agent.scoring import AgentScore, compute_confidence, decision_from_score
from src.tools.market import Fundamentals
from src.tools.peers import QUALITY_METRICS, PeerComparison, compare_to_peers

from .. import config

LABELS = {
    "pe_ratio": "P/E",
    "forward_pe": "Fwd P/E",
    "ev_to_ebitda": "EV/EBITDA",
    "price_to_book": "P/B",
    "return_on_equity": "ROE",
    "operating_margin": "Op margin",
    "revenue_growth": "Rev growth",
}

SIGNALS = {"discount": 1, "in_line": 0, "premium": -1, "stronger": 1, "weaker": -1}


class PeersAnalysis(BaseModel):
    score: int = Field(ge=1, le=5, description="1=unattractive vs peers, 3=in line, 5=attractive vs peers")
    reasoning: str = Field(description="2-3 sentence explanation")
    key_signals: list[str]
    risk_flags: list[str]


def _cell(metric: str, value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.1%}" if metric in QUALITY_METRICS else f"{value:.1f}x"


def _row(label: str, values: dict[str, float | None]) -> str:
    return " | ".join([label] + [_cell(m, values[m]) for m in LABELS])


def _metrics(fundamentals: Fundamentals) -> dict[str, float | None]:
    return {m: getattr(fundamentals, m) for m in LABELS}


def _relative_valuation(comparison: PeerComparison) -> str | None:
    """Median of the target's valuation premiums vs config.PEERS_PREMIUM_BAND."""
    premiums = [p for p in comparison.premiums.values() if p is not None]
    if not premiums:
        return None
    mid, band = median(premiums), config.PEERS_PREMIUM_BAND
    return "premium" if mid > band else "discount" if mid < -band else "in_line"


def _relative_quality(comparison: PeerComparison) -> str | None:
    """Quality metrics above the peer median minus those below, vs config.PEERS_QUALITY_NET."""
    pairs = [
        (getattr(comparison.target.fundamentals, m), comparison.medians[m]) for m in QUALITY_METRICS
    ]
    pairs = [(v, mid) for v, mid in pairs if v is not None and mid is not None]
    if not pairs:
        return None
    net = sum(v > mid for v, mid in pairs) - sum(v < mid for v, mid in pairs)
    threshold = config.PEERS_QUALITY_NET
    return "stronger" if net >= threshold else "weaker" if net <= -threshold else "in_line"


def _format_comparison(comparison: PeerComparison) -> str:
    target = comparison.target.profile.symbol
    lines = [" | ".join(["Company"] + list(LABELS.values()))]
    lines.append(_row(f"{target} (target)", _metrics(comparison.target.fundamentals)))
    lines += [_row(p.profile.symbol, _metrics(p.fundamentals)) for p in comparison.peers]
    lines.append(_row("Peer median", comparison.medians))
    premiums = [
        f"{LABELS[m]} {p:+.0%}" for m, p in comparison.premiums.items() if p is not None
    ]
    lines.append(f"\n{target} valuation vs peer median: {', '.join(premiums) or 'n/a'}")
    return "\n".join(lines)


def analyze_peers(ticker: str) -> AgentScore:
    """
    Flow:
      1. Find peers and compute the peer median (tools/peers.py)
      2. Compute relative valuation and quality labels in code
      3. LLM judges whether a premium is justified and scores; decision is derived from the score
      4. Confidence = peer coverage x agreement of valuation and quality
    """
    comparison = compare_to_peers(ticker)

    if not comparison.peers:
        return AgentScore(
            agent="peers",
            symbol=ticker,
            decision="HOLD",
            score=3,
            timeframe="mid",
            reasoning="No peers found",
            confidence=0.1,
            data_gaps=["No peers found"],
        )

    valuation, quality = _relative_valuation(comparison), _relative_quality(comparison)
    labels_text = (
        f"valuation vs peers: {valuation or 'not assessable'}; "
        f"quality vs peers: {quality or 'not assessable'}"
    )

    profile = comparison.target.profile
    user_prompt = f"""Compare {ticker} ({profile.name}) with its peers.
Sector: {profile.sector or "n/a"}; industry: {profile.industry or "n/a"}

{_format_comparison(comparison)}

Computed assessment (facts): {labels_text}"""

    llm = ChatOpenAI(model=config.LLM_MODEL_AGENTS, temperature=config.LLM_TEMPERATURE_AGENTS)
    analysis: PeersAnalysis = llm.with_structured_output(PeersAnalysis).invoke(
        [
            {"role": "system", "content": load_prompt("peers")},
            {"role": "user", "content": user_prompt},
        ],
        config={"run_name": "Peers Agent"},
    )

    coverage = len(comparison.peers) / config.PEERS_COUNT
    signals = [SIGNALS[v] for v in (valuation, quality) if v is not None]

    parts = [
        analysis.reasoning,
        f"Peers: {', '.join(p.profile.symbol for p in comparison.peers)}. "
        f"{labels_text[0].upper() + labels_text[1:]}.",
    ]
    if analysis.key_signals:
        parts.append("Key signals: " + ", ".join(analysis.key_signals) + ".")
    if analysis.risk_flags:
        parts.append("Risks: " + ", ".join(analysis.risk_flags) + ".")

    data_gaps = []
    if len(comparison.peers) < config.PEERS_COUNT:
        data_gaps.append(f"Only {len(comparison.peers)} peers found")

    return AgentScore(
        agent="peers",
        symbol=ticker,
        decision=decision_from_score(analysis.score),
        score=analysis.score,
        timeframe="mid",
        reasoning="Peers: " + " ".join(parts),
        confidence=compute_confidence(coverage, signals),
        data_gaps=data_gaps,
    )
