"""
test_aggregator.py
------------------
Unit tests for the consensus math. No network or API keys.
Run from project root:
    uv run pytest tests/test_aggregator.py
"""

from src import config
from src.agent.scoring import AgentScore
from src.orchestrator.aggregator import aggregate


def _score(agent: str, score: int, confidence: float, decision: str = "HOLD") -> AgentScore:
    return AgentScore(
        agent=agent, symbol="TEST", decision=decision, score=score,
        timeframe="mid", reasoning="test", confidence=confidence,
    )


def test_unanimous_scores():
    result = aggregate("TEST", [_score(a, 4, 0.8, "BUY") for a in config.AGENT_WEIGHTS])
    assert result.weighted_score == 4.0
    assert result.agreement == 1.0
    assert result.confidence == 0.8
    assert result.decision == "BUY"
    assert result.conflicts == []


def test_zero_confidence_analyst_has_no_weight():
    scores = [_score(a, 4, 0.8, "BUY") for a in config.AGENT_WEIGHTS if a != "macro"]
    scores.append(_score("macro", 1, 0.0, "SELL"))
    result = aggregate("TEST", scores)
    assert result.weighted_score == 4.0
    assert any("macro=SELL" in c for c in result.conflicts)


def test_disagreement_lowers_confidence():
    agents = list(config.AGENT_WEIGHTS)
    split = [_score(a, 5 if i % 2 else 1, 0.8, "BUY" if i % 2 else "SELL") for i, a in enumerate(agents)]
    result = aggregate("TEST", split)
    assert result.agreement < 0.2
    assert result.confidence < 0.2
