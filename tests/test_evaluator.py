"""
test_evaluator.py
-----------------
Unit tests for the evaluator's risk plan. No network or API keys.
Run from project root:
    uv run pytest tests/test_evaluator.py
"""

from src import config
from src.orchestrator.evaluator import _risk_plan


def test_full_position_uses_atr_and_reward_risk():
    plan = _risk_plan("BUY", "aligned", confidence=0.8, price=100.0, atr=2.0, vix=15.0)
    stop_distance = config.STOP_ATR_MULTIPLE * 2.0
    assert plan.stop_loss == 100.0 - stop_distance
    assert plan.take_profit == 100.0 + config.REWARD_RISK_RATIO * stop_distance
    assert plan.position_size_pct == round(config.MAX_POSITION_SIZE * 0.8, 4)


def test_accumulate_is_an_explicit_starter_position():
    full = _risk_plan("BUY", "aligned", 0.8, 100.0, 2.0, 15.0)
    starter = _risk_plan("BUY", "accumulate", 0.8, 100.0, 2.0, 15.0)
    assert starter.position_size_pct == round(full.position_size_pct * config.STARTER_SIZE_FRACTION, 4)
    assert "Starter position" in starter.note


def test_trade_is_smaller_with_tighter_stop():
    plan = _risk_plan("BUY", "trade", 0.8, 100.0, 2.0, 15.0)
    assert plan.position_size_pct == round(config.MAX_POSITION_SIZE * 0.8 * config.TRADE_SIZE_FRACTION, 4)
    assert plan.stop_loss == 100.0 - config.TRADE_STOP_ATR_MULTIPLE * 2.0


def test_stressed_vix_cuts_size():
    calm = _risk_plan("BUY", "aligned", 0.8, 100.0, 2.0, vix=15.0).position_size_pct
    stressed = _risk_plan("BUY", "aligned", 0.8, 100.0, 2.0, vix=config.MACRO_VIX_BANDS[1] + 1).position_size_pct
    assert stressed == round(calm * (1 - config.STRESSED_VIX_SIZE_CUT), 4)


def test_no_position_unless_buy():
    for decision in ("HOLD", "SELL"):
        plan = _risk_plan(decision, "none", 0.9, 100.0, 2.0, 15.0)
        assert (plan.position_size_pct, plan.stop_loss, plan.take_profit) == (0.0, None, None)
