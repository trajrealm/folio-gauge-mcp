"""
src/orchestrator/evaluator.py
-----------------------------
Final decision and risk plan for one ticker.

In code (thresholds in config):
  - decision: the consensus decision; BUY/SELL becomes HOLD when consensus
    confidence is below EVALUATOR_MIN_CONFIDENCE
  - BUY only: entry = last close; stop = entry - STOP_ATR_MULTIPLE x ATR;
    take-profit = entry + REWARD_RISK_RATIO x stop distance;
    size = MAX_POSITION_SIZE x confidence, cut when VIX is stressed

The LLM (LLM_MODEL_EVALUATOR) writes the investment thesis from the
analysts' reasoning, conflicts and data gaps; it does not change the numbers.
"""

from __future__ import annotations

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from src import config
from src.agent.knowledge import load_prompt
from src.agent.scoring import Decision, OrchestratorResult
from src.tools.fred import get_macro_snapshot
from src.tools.technical import get_technical_snapshot


class Thesis(BaseModel):
    thesis: str = Field(description="3-5 sentence investment thesis")
    key_considerations: list[str]
    risks: list[str]


class EvaluatorDecision(BaseModel):
    symbol: str
    decision: Decision
    gated: bool  # consensus BUY/SELL turned into HOLD for low confidence
    confidence: float  # consensus confidence
    price: float  # last close
    atr: float
    vix: float
    position_size_pct: float  # of portfolio; 0 unless BUY
    stop_loss: float | None  # BUY only
    take_profit: float | None  # BUY only
    thesis: str
    key_considerations: list[str]
    risks: list[str]


def _risk_plan(decision: Decision, confidence: float, price: float, atr: float, vix: float) -> dict:
    if decision != "BUY":
        return {"position_size_pct": 0.0, "stop_loss": None, "take_profit": None}
    stop_distance = config.STOP_ATR_MULTIPLE * atr
    size = config.MAX_POSITION_SIZE * confidence
    if vix > config.MACRO_VIX_BANDS[1]:
        size *= 1 - config.STRESSED_VIX_SIZE_CUT
    return {
        "position_size_pct": round(size, 4),
        "stop_loss": round(price - stop_distance, 2),
        "take_profit": round(price + config.REWARD_RISK_RATIO * stop_distance, 2),
    }


def evaluate(consensus: OrchestratorResult) -> EvaluatorDecision:
    technical = get_technical_snapshot(consensus.symbol)
    if technical is None or technical.atr_14 is None:
        raise ValueError(f"No price history for {consensus.symbol}; cannot build a risk plan")
    vix = get_macro_snapshot().vix

    gated = consensus.decision != "HOLD" and consensus.confidence < config.EVALUATOR_MIN_CONFIDENCE
    decision: Decision = "HOLD" if gated else consensus.decision
    plan = _risk_plan(decision, consensus.confidence, technical.price, technical.atr_14, vix)

    analysts = "\n".join(
        f"- {s.agent} ({s.decision}, score {s.score}, confidence {s.confidence:.0%}): {s.reasoning}"
        for s in consensus.agent_scores
    )
    risk_plan = (
        f"position {plan['position_size_pct']:.1%} of portfolio, stop {plan['stop_loss']}, "
        f"target {plan['take_profit']}"
        if decision == "BUY"
        else "no new position"
    )
    user_prompt = f"""Write the investment thesis for {consensus.symbol}.

Consensus: {consensus.decision}, weighted score {consensus.weighted_score:.2f}/5, confidence {consensus.confidence:.0%}, agreement {consensus.agreement:.0%}
Final decision (facts): {decision}{" (gated from " + consensus.decision + ": confidence below " + f"{config.EVALUATOR_MIN_CONFIDENCE:.0%})" if gated else ""}
Risk plan (facts): price {technical.price:.2f}, ATR {technical.atr_14:.2f}, VIX {vix:.1f}; {risk_plan}
Conflicts: {"; ".join(consensus.conflicts) or "none"}
Data gaps: {"; ".join(consensus.data_gaps) or "none"}

Analysts:
{analysts}"""

    llm = ChatOpenAI(model=config.LLM_MODEL_EVALUATOR, temperature=config.LLM_TEMPERATURE_EVALUATOR)
    thesis: Thesis = llm.with_structured_output(Thesis).invoke(
        [
            {"role": "system", "content": load_prompt("evaluator")},
            {"role": "user", "content": user_prompt},
        ],
        config={"run_name": "Evaluator"},
    )

    return EvaluatorDecision(
        symbol=consensus.symbol,
        decision=decision,
        gated=gated,
        confidence=consensus.confidence,
        price=technical.price,
        atr=technical.atr_14,
        vix=vix,
        **plan,
        thesis=thesis.thesis,
        key_considerations=thesis.key_considerations,
        risks=thesis.risks,
    )


def format_decision(d: EvaluatorDecision) -> str:
    lines = [f"DECISION for {d.symbol}: {d.decision}" + (" (gated: low confidence)" if d.gated else "")]
    if d.decision == "BUY":
        lines.append(
            f"Position {d.position_size_pct:.1%} of portfolio; entry {d.price:.2f}, "
            f"stop {d.stop_loss:.2f}, take-profit {d.take_profit:.2f} (ATR {d.atr:.2f}, VIX {d.vix:.1f})"
        )
    lines += ["", d.thesis, "", "Key considerations:"]
    lines += [f"  - {k}" for k in d.key_considerations]
    lines += ["Risks:"] + [f"  - {r}" for r in d.risks]
    return "\n".join(lines)
