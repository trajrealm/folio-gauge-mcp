"""
src/orchestrator/aggregator.py
------------------------------
Consensus across the 8 per-ticker analysts, computed in code (no LLM).

Analysts are split by horizon (config.HORIZONS): short = price and news flow
(technical, sentiment, news, sector); long = business and valuation
(fundamentals, earnings, peers, macro). The two often disagree (a cheap stock
in a downtrend); a single average hid that and produced HOLD.

Per horizon:
  effective weight_i = AGENT_WEIGHTS[agent] x confidence_i
  weighted score     = sum(w_i x score_i) / sum(w_i)
  agreement          = 1 - weighted standard deviation of scores / 2
  confidence         = mean analyst confidence x agreement
  decision           = decision_from_score(weighted score)

Combined (long horizon leads when the short one is neutral):
  long \\ short   BUY             HOLD             SELL
  BUY           BUY aligned     BUY long_term    BUY accumulate (starter position)
  HOLD          BUY trade       HOLD             HOLD
  SELL          BUY trade       SELL long_term   SELL aligned

Gate: BUY/SELL becomes HOLD when the leading horizon (short for "trade",
else long) has confidence below HORIZON_MIN_CONFIDENCE.
"""

from __future__ import annotations

from math import sqrt

from src import config
from src.agent.scoring import (
    AgentScore,
    Decision,
    HorizonConsensus,
    OrchestratorResult,
    Setup,
    decision_from_score,
)


def horizon_consensus(horizon: str, scores: list[AgentScore]) -> HorizonConsensus:
    weights = [config.AGENT_WEIGHTS[s.agent] * s.confidence for s in scores]
    total = sum(weights)
    if total == 0:  # every analyst has zero confidence
        weighted, spread = 3.0, 0.0
    else:
        weighted = sum(w * s.score for w, s in zip(weights, scores)) / total
        spread = sqrt(sum(w * (s.score - weighted) ** 2 for w, s in zip(weights, scores)) / total)
    agreement = 1 - spread / 2
    mean_confidence = sum(config.AGENT_WEIGHTS[s.agent] * s.confidence for s in scores) / sum(
        config.AGENT_WEIGHTS[s.agent] for s in scores
    )
    return HorizonConsensus(
        horizon=horizon,
        decision=decision_from_score(weighted),
        weighted_score=round(weighted, 2),
        confidence=round(mean_confidence * agreement, 2),
        agreement=round(agreement, 2),
    )


def combine(short: Decision, long: Decision) -> tuple[Decision, Setup, str]:
    """(decision, setup, leading horizon) from the two horizon decisions."""
    if long == short and long != "HOLD":
        return long, "aligned", "long"
    if long != "HOLD" and short == "HOLD":
        return long, "long_term", "long"
    if long == "BUY" and short == "SELL":
        return "BUY", "accumulate", "long"
    if short == "BUY":
        return "BUY", "trade", "short"
    return "HOLD", "none", "long"


def aggregate(symbol: str, scores: list[AgentScore]) -> OrchestratorResult:
    by_agent = {s.agent: s for s in scores}
    horizons = {
        name: horizon_consensus(name, [by_agent[a] for a in agents])
        for name, agents in config.HORIZONS.items()
    }
    decision, setup, lead = combine(horizons["short"].decision, horizons["long"].decision)
    confidence = horizons[lead].confidence
    gated = decision != "HOLD" and confidence < config.HORIZON_MIN_CONFIDENCE

    return OrchestratorResult(
        symbol=symbol,
        decision="HOLD" if gated else decision,
        setup=setup,
        gated=gated,
        confidence=confidence,
        short=horizons["short"],
        long=horizons["long"],
        agent_scores=scores,
        conflicts=[
            f"{a.agent}={a.decision} vs {b.agent}={b.decision}"
            for i, a in enumerate(scores)
            for b in scores[i + 1 :]
            if {a.decision, b.decision} == {"BUY", "SELL"}
        ],
        data_gaps=[f"{s.agent}: {gap}" for s in scores for gap in s.data_gaps],
    )


def format_consensus(result: OrchestratorResult) -> str:
    gate = f" (gated from {result.setup}: confidence below {config.HORIZON_MIN_CONFIDENCE:.0%})" if result.gated else ""
    lines = [f"CONSENSUS for {result.symbol}: {result.decision}, setup {result.setup}{gate}"]
    for h in (result.short, result.long):
        lines.append(
            f"  {h.horizon:<5} term: {h.decision:<4} score {h.weighted_score:.2f}/5, "
            f"confidence {h.confidence:.0%}, agreement {h.agreement:.0%} "
            f"({', '.join(config.HORIZONS[h.horizon])})"
        )
    lines += ["", "Analysts:"]
    for s in sorted(result.agent_scores, key=lambda s: s.score, reverse=True):
        lines.append(f"  {s.agent:<13} {s.decision:<4} score {s.score}, confidence {s.confidence:.0%}")
        lines.append(f"    {s.reasoning}")
    if result.conflicts:
        lines += ["", "Conflicts: " + "; ".join(result.conflicts)]
    if result.data_gaps:
        lines += ["", "Data gaps: " + "; ".join(result.data_gaps)]
    return "\n".join(lines)
