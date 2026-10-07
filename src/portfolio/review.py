"""
src/portfolio/review.py
-----------------------
Portfolio review, run after the per-ticker analysis of each holding.
  - compute_facts: market value, weight of gross exposure, unrealized P&L,
    concentration (top weight, Herfindahl index), sector and long/short
    exposure. Computed in code from yfinance prices and sectors.
  - position_action: add / hold / trim / exit from each holding's consensus
    (decision, confidence) and concentration, in code. Unrealized P&L is
    deliberately not an input.
  - review_portfolio: the LLM writes the summary, risks and a reason for
    each computed action.
"""

from __future__ import annotations

from typing import Literal

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from src import config
from src.agent.graph import analyze_tickers
from src.agent.knowledge import load_prompt
from src.agent.scoring import OrchestratorResult
from src.portfolio.models import Holding
from src.tools.market import get_ticker_snapshot


class Position(BaseModel):
    symbol: str
    position_type: Literal["long", "short"]
    sector: str | None
    price: float
    market_value: float  # signed: negative for shorts
    weight: float  # |market value| / gross exposure
    unrealized_pnl: float
    unrealized_pnl_pct: float  # vs cost basis


class PortfolioFacts(BaseModel):
    positions: list[Position]  # largest weight first
    gross_exposure: float  # sum of |market value|
    net_exposure: float  # (long - short) / gross
    unrealized_pnl: float
    top_weight: float
    hhi: float  # sum of squared weights: 1/n when equal-weighted, 1 when a single position
    sector_weights: dict[str, float]  # of gross exposure, largest first
    concentrated_positions: list[str]  # weight > PORTFOLIO_MAX_WEIGHT
    concentrated_sectors: list[str]  # weight > PORTFOLIO_MAX_SECTOR_WEIGHT


Action = Literal["add", "hold", "trim", "exit"]


class PositionReason(BaseModel):
    symbol: str
    reason: str = Field(description="One sentence explaining the given action, citing the facts")


class PortfolioReview(BaseModel):
    summary: str = Field(description="2-3 sentences on overall portfolio health")
    risks: list[str]
    reasons: list[PositionReason]


class PositionAction(BaseModel):
    symbol: str
    action: Action
    reason: str


class PortfolioReport(BaseModel):
    facts: PortfolioFacts
    summary: str
    risks: list[str]
    actions: list[PositionAction]
    not_analyzed: dict[str, str] = {}  # symbol -> error (stack trace is logged)


def compute_facts(holdings: list[Holding]) -> PortfolioFacts:
    rows = []
    for h in holdings:
        snapshot = get_ticker_snapshot(h.symbol)
        price = snapshot.price.current_price
        sign = 1 if h.position_type == "long" else -1
        rows.append((h, snapshot.profile.sector, price, sign * h.qty * price, sign * h.qty * (price - h.avg_cost)))

    gross = sum(abs(value) for _, _, _, value, _ in rows)
    positions = sorted(
        (
            Position(
                symbol=h.symbol,
                position_type=h.position_type,
                sector=sector,
                price=price,
                market_value=value,
                weight=abs(value) / gross,
                unrealized_pnl=pnl,
                unrealized_pnl_pct=pnl / (h.qty * h.avg_cost),
            )
            for h, sector, price, value, pnl in rows
        ),
        key=lambda p: p.weight,
        reverse=True,
    )

    sectors: dict[str, float] = {}
    for p in positions:
        sectors[p.sector or "Unknown"] = sectors.get(p.sector or "Unknown", 0) + p.weight
    sectors = dict(sorted(sectors.items(), key=lambda kv: kv[1], reverse=True))

    return PortfolioFacts(
        positions=positions,
        gross_exposure=gross,
        net_exposure=sum(p.market_value for p in positions) / gross,
        unrealized_pnl=sum(p.unrealized_pnl for p in positions),
        top_weight=positions[0].weight,
        hhi=sum(p.weight**2 for p in positions),
        sector_weights=sectors,
        concentrated_positions=[p.symbol for p in positions if p.weight > config.PORTFOLIO_MAX_WEIGHT],
        concentrated_sectors=[s for s, w in sectors.items() if w > config.PORTFOLIO_MAX_SECTOR_WEIGHT],
    )


def position_action(position: Position, result: OrchestratorResult | None) -> Action:
    """
    Long: BUY -> add (hold if concentrated or low confidence); HOLD -> hold
    (trim if concentrated); SELL -> exit with high confidence, else trim.
    Shorts mirror it (a SELL rating supports the short). Not analyzed:
    trim if concentrated, else hold.
    """
    concentrated = position.weight > config.PORTFOLIO_MAX_WEIGHT
    if result is None:
        return "trim" if concentrated else "hold"
    favorable, unfavorable = ("BUY", "SELL") if position.position_type == "long" else ("SELL", "BUY")
    if result.decision == favorable:
        add = not concentrated and result.confidence >= config.PORTFOLIO_ADD_MIN_CONFIDENCE
        return "add" if add else "hold"
    if result.decision == unfavorable:
        return "exit" if result.confidence >= config.PORTFOLIO_EXIT_MIN_CONFIDENCE else "trim"
    return "trim" if concentrated else "hold"


def _format(
    facts: PortfolioFacts, results: dict[str, OrchestratorResult], actions: dict[str, Action]
) -> str:
    lines = ["Symbol | Type | Sector | Weight | Unrealized P&L | Consensus | Action"]
    for p in facts.positions:
        r = results.get(p.symbol)
        consensus = (
            f"{r.decision} ({r.setup}), short {r.short.weighted_score:.1f} / long {r.long.weighted_score:.1f}, "
            f"confidence {r.confidence:.0%}"
            if r
            else "not analyzed"
        )
        lines.append(
            f"{p.symbol} | {p.position_type} | {p.sector or 'Unknown'} | {p.weight:.1%} | "
            f"{p.unrealized_pnl_pct:+.1%} | {consensus} | {actions[p.symbol]}"
        )
    sectors = ", ".join(f"{s} {w:.0%}" for s, w in facts.sector_weights.items())
    lines += [
        "",
        f"Gross exposure: {facts.gross_exposure:,.0f}; net exposure: {facts.net_exposure:+.0%} of gross; "
        f"unrealized P&L: {facts.unrealized_pnl:+,.0f}",
        f"Top position weight: {facts.top_weight:.1%}; Herfindahl index: {facts.hhi:.2f} "
        f"(equal-weighted would be {1 / len(facts.positions):.2f})",
        f"Sectors: {sectors}",
        f"Concentrated positions (> {config.PORTFOLIO_MAX_WEIGHT:.0%}): {', '.join(facts.concentrated_positions) or 'none'}",
        f"Concentrated sectors (> {config.PORTFOLIO_MAX_SECTOR_WEIGHT:.0%}): {', '.join(facts.concentrated_sectors) or 'none'}",
    ]
    return "\n".join(lines)


def review_portfolio(holdings: list[Holding], results: dict[str, OrchestratorResult]) -> PortfolioReport:
    facts = compute_facts(holdings)
    actions = {p.symbol: position_action(p, results.get(p.symbol)) for p in facts.positions}

    llm = ChatOpenAI(model=config.LLM_MODEL_AGENTS, temperature=config.LLM_TEMPERATURE_AGENTS)
    review: PortfolioReview = llm.with_structured_output(PortfolioReview).invoke(
        [
            {"role": "system", "content": load_prompt("portfolio")},
            {"role": "user", "content": f"Review this portfolio:\n\n{_format(facts, results, actions)}"},
        ],
        config={"run_name": "Portfolio Review"},
    )

    reasons = {r.symbol: r.reason for r in review.reasons}
    return PortfolioReport(
        facts=facts,
        summary=review.summary,
        risks=review.risks,
        actions=[
            PositionAction(symbol=symbol, action=action, reason=reasons.get(symbol, ""))
            for symbol, action in actions.items()
        ],
    )


def run_portfolio_review(holdings: list[Holding]) -> PortfolioReport:
    """Analyze every holding with the full pipeline, then review the portfolio."""
    batch = analyze_tickers([h.symbol for h in holdings])
    report = review_portfolio(holdings, {s: a.consensus for s, a in batch.analyses.items()})
    report.not_analyzed = batch.failed
    return report
