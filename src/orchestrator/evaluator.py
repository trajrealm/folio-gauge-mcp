"""
src/orchestrator/evaluator.py
-----------------------------
Risk plan and investment thesis for one ticker. The decision itself comes
from the aggregator (horizons combined, minimum-confidence check applied).

Risk plan, in code (thresholds in config), BUY only:
  entry = last close
  size  = MAX_POSITION_SIZE x consensus confidence, cut when VIX is stressed
  stop  = entry - STOP_ATR_MULTIPLE x ATR; take-profit at REWARD_RISK_RATIO
  setup "accumulate" (long-term BUY, short-term SELL): a starter position of
      STARTER_SIZE_FRACTION of the size; add once the short term stabilizes
  setup "trade" (short-term BUY only): TRADE_SIZE_FRACTION of the size and a
      tighter stop of TRADE_STOP_ATR_MULTIPLE x ATR

The LLM (LLM_MODEL_EVALUATOR) writes the thesis from the two horizons, the
analysts' reasoning, conflicts and data gaps; it does not change the numbers.
"""

from __future__ import annotations

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from src import config
from src.agent.knowledge import load_prompt
from src.agent.scoring import Decision, OrchestratorResult, Setup
from src.tools.fred import get_macro_snapshot
from src.tools.technical import get_technical_snapshot


class Thesis(BaseModel):
    thesis: str = Field(description="3-5 sentence investment thesis")
    key_considerations: list[str]
    risks: list[str]


class RiskPlan(BaseModel):
    position_size_pct: float  # of portfolio; 0 unless BUY
    stop_loss: float | None
    take_profit: float | None
    note: str  # plain-language plan, e.g. that a starter position is intended


class EvaluatorDecision(BaseModel):
    symbol: str
    decision: Decision
    setup: Setup
    held_for_low_confidence: bool
    confidence: float
    price: float  # last close
    atr: float
    vix: float
    plan: RiskPlan
    thesis: str
    key_considerations: list[str]
    risks: list[str]


def _risk_plan(decision: Decision, setup: Setup, confidence: float, price: float, atr: float, vix: float) -> RiskPlan:
    if decision != "BUY":
        note = "Reduce or exit the position." if decision == "SELL" else "No new position."
        return RiskPlan(position_size_pct=0.0, stop_loss=None, take_profit=None, note=note)

    size = config.MAX_POSITION_SIZE * confidence
    if vix > config.MACRO_VIX_BANDS[1]:
        size *= 1 - config.STRESSED_VIX_SIZE_CUT
    stop_multiple = config.STOP_ATR_MULTIPLE
    note = "Full position: both horizons support it." if setup == "aligned" else "Full position on the long-term case."
    if setup == "accumulate":
        size *= config.STARTER_SIZE_FRACTION
        note = (
            f"Starter position only ({config.STARTER_SIZE_FRACTION:.0%} of a full position): the long-term case "
            "is a BUY but the short-term trend is still negative. Add once the short-term turns."
        )
    elif setup == "trade":
        size *= config.TRADE_SIZE_FRACTION
        stop_multiple = config.TRADE_STOP_ATR_MULTIPLE
        note = (
            f"Short-term trade, not an investment ({config.TRADE_SIZE_FRACTION:.0%} of a full position, "
            "tighter stop): momentum supports it but the long-term case does not."
        )

    stop_distance = stop_multiple * atr
    return RiskPlan(
        position_size_pct=round(size, 4),
        stop_loss=round(price - stop_distance, 2),
        take_profit=round(price + config.REWARD_RISK_RATIO * stop_distance, 2),
        note=note,
    )


def evaluate(consensus: OrchestratorResult) -> EvaluatorDecision:
    technical = get_technical_snapshot(consensus.symbol)
    if technical is None or technical.atr_14 is None:
        raise ValueError(f"No price history for {consensus.symbol}; cannot build a risk plan")
    vix = get_macro_snapshot().vix
    plan = _risk_plan(
        consensus.decision, consensus.setup, consensus.confidence, technical.price, technical.atr_14, vix
    )

    horizons = "\n".join(
        f"  {h.horizon}-term ({', '.join(config.HORIZONS[h.horizon])}): {h.decision}, "
        f"score {h.weighted_score:.2f}/5, confidence {h.confidence:.0%}, agreement {h.agreement:.0%}"
        for h in (consensus.short, consensus.long)
    )
    analysts = "\n".join(
        f"- {s.agent} ({s.decision}, score {s.score}, confidence {s.confidence:.0%}): {s.reasoning}"
        for s in consensus.agent_scores
    )
    levels = (
        f"size {plan.position_size_pct:.1%} of portfolio, stop {plan.stop_loss}, target {plan.take_profit}; "
        if consensus.decision == "BUY"
        else ""
    )
    held = (
        f" (held back as HOLD from setup {consensus.setup}: leading horizon confidence "
        f"{consensus.confidence:.0%} below {config.HORIZON_MIN_CONFIDENCE:.0%})"
    )
    user_prompt = f"""Write the investment thesis for {consensus.symbol}.

Horizons:
{horizons}
Final decision (facts): {consensus.decision}, setup {consensus.setup}{held if consensus.held_for_low_confidence else ""}
Risk plan (facts): price {technical.price:.2f}, ATR {technical.atr_14:.2f}, VIX {vix:.1f}; {levels}{plan.note}
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
        decision=consensus.decision,
        setup=consensus.setup,
        held_for_low_confidence=consensus.held_for_low_confidence,
        confidence=consensus.confidence,
        price=technical.price,
        atr=technical.atr_14,
        vix=vix,
        plan=plan,
        thesis=thesis.thesis,
        key_considerations=thesis.key_considerations,
        risks=thesis.risks,
    )


def format_decision(d: EvaluatorDecision) -> str:
    held = f", {d.setup} held back: low confidence {d.confidence:.0%}" if d.held_for_low_confidence else ""
    lines = [f"DECISION for {d.symbol}: {d.decision} (setup {d.setup}{held})"]
    if d.decision == "BUY":
        lines.append(
            f"Position {d.plan.position_size_pct:.1%} of portfolio; entry {d.price:.2f}, "
            f"stop {d.plan.stop_loss:.2f}, take-profit {d.plan.take_profit:.2f} (ATR {d.atr:.2f}, VIX {d.vix:.1f})"
        )
    lines += [f"Plan: {d.plan.note}", "", d.thesis, "", "Key considerations:"]
    lines += [f"  - {k}" for k in d.key_considerations]
    lines += ["Risks:"] + [f"  - {r}" for r in d.risks]
    return "\n".join(lines)
