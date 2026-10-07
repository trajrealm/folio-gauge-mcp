"""
test_aggregator.py
------------------
Unit tests for the consensus math and horizon combination. No network or API keys.
Run from project root:
    uv run pytest tests/test_aggregator.py
"""

import pytest

from src import config
from src.agent.scoring import AgentScore
from src.orchestrator.aggregator import aggregate, combine, horizon_consensus


def _score(agent: str, score: int, confidence: float = 0.8) -> AgentScore:
    decision = "BUY" if score >= 4 else "SELL" if score <= 2 else "HOLD"
    return AgentScore(
        agent=agent, symbol="TEST", decision=decision, score=score,
        timeframe="mid", reasoning="test", confidence=confidence,
    )


def _all(short: int, long: int, confidence: float = 0.8) -> list[AgentScore]:
    return [_score(a, short, confidence) for a in config.HORIZONS["short"]] + [
        _score(a, long, confidence) for a in config.HORIZONS["long"]
    ]


def test_unanimous_horizon():
    h = horizon_consensus("long", [_score(a, 4) for a in config.HORIZONS["long"]])
    assert (h.weighted_score, h.agreement, h.confidence, h.decision) == (4.0, 1.0, 0.8, "BUY")


def test_zero_confidence_analyst_has_no_weight():
    scores = [_score(a, 4) for a in config.HORIZONS["long"][:-1]] + [_score(config.HORIZONS["long"][-1], 1, 0.0)]
    assert horizon_consensus("long", scores).weighted_score == 4.0


def test_disagreement_lowers_confidence():
    agents = config.HORIZONS["short"]
    h = horizon_consensus("short", [_score(a, 5 if i % 2 else 1) for i, a in enumerate(agents)])
    assert h.agreement < 0.2 and h.confidence < 0.2


@pytest.mark.parametrize(
    "short,long,expected",
    [
        ("BUY", "BUY", ("BUY", "aligned", "long")),
        ("HOLD", "BUY", ("BUY", "long_term", "long")),
        ("SELL", "BUY", ("BUY", "accumulate", "long")),
        ("BUY", "HOLD", ("BUY", "trade", "short")),
        ("BUY", "SELL", ("BUY", "trade", "short")),
        ("HOLD", "HOLD", ("HOLD", "none", "long")),
        ("SELL", "HOLD", ("HOLD", "none", "long")),
        ("HOLD", "SELL", ("SELL", "long_term", "long")),
        ("SELL", "SELL", ("SELL", "aligned", "long")),
    ],
)
def test_combine_table(short, long, expected):
    assert combine(short, long) == expected


def test_accumulate_when_value_meets_downtrend():
    result = aggregate("TEST", _all(short=1, long=4))
    assert (result.decision, result.setup, result.held_for_low_confidence) == ("BUY", "accumulate", False)


def test_held_for_low_leading_horizon_confidence():
    result = aggregate("TEST", _all(short=1, long=4, confidence=0.3))
    assert (result.decision, result.setup, result.held_for_low_confidence) == ("HOLD", "accumulate", True)
