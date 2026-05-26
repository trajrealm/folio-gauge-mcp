"""
tests/test_config.py
--------------------
Tests for config.py.
Run with: pytest tests/test_config.py -v
"""

import pytest
import config



# ---------------------------------------------------------------------------
# Agent weights
# ---------------------------------------------------------------------------


def test_agent_weights_sum_to_one():
    total = sum(config.AGENT_WEIGHTS.values())
    assert round(total, 10) == 1.0, f"AGENT_WEIGHTS sum to {total}, expected 1.0"


def test_agent_weights_all_positive():
    for agent, weight in config.AGENT_WEIGHTS.items():
        assert weight > 0, f"Weight for '{agent}' must be positive, got {weight}"


def test_agent_weights_contains_all_agents():
    expected_agents = {
        "technical",
        "fundamentals",
        "price_volume",
        "news",
        "trend",
        "earnings",
        "peers",
        "industry",
        "sector",
        "macro",
    }
    assert set(config.AGENT_WEIGHTS.keys()) == expected_agents


# ---------------------------------------------------------------------------
# Scoring range
# ---------------------------------------------------------------------------


def test_score_range_valid():
    assert config.SCORE_MIN < config.SCORE_MAX


def test_score_min_is_positive():
    assert config.SCORE_MIN >= 1


def test_valid_decisions_not_empty():
    assert len(config.VALID_DECISIONS) > 0


def test_valid_decisions_contains_expected():
    assert "BUY" in config.VALID_DECISIONS
    assert "SELL" in config.VALID_DECISIONS
    assert "HOLD" in config.VALID_DECISIONS


def test_valid_timeframes_contains_expected():
    assert "short" in config.VALID_TIMEFRAMES
    assert "mid" in config.VALID_TIMEFRAMES
    assert "long" in config.VALID_TIMEFRAMES


# ---------------------------------------------------------------------------
# Counts
# ---------------------------------------------------------------------------


def test_peers_count_positive():
    assert config.PEERS_COUNT >= 1


def test_trending_stocks_count_positive():
    assert config.TRENDING_STOCKS_COUNT >= 1


# ---------------------------------------------------------------------------
# LLM config
# ---------------------------------------------------------------------------


def test_llm_temperature_in_range():
    assert 0.0 <= config.LLM_TEMPERATURE <= 1.0


def test_llm_max_tokens_positive():
    assert config.LLM_MAX_TOKENS > 0


def test_llm_models_not_empty():
    assert config.LLM_MODEL_AGENTS
    assert config.LLM_MODEL_ORCHESTRATOR
    assert config.LLM_MODEL_FINAL


# ---------------------------------------------------------------------------
# Rate limits
# ---------------------------------------------------------------------------


def test_rate_limits_positive():
    assert config.POLYGON_CALLS_PER_MINUTE > 0
    assert config.FRED_CALLS_PER_MINUTE > 0
    assert config.YFINANCE_CALLS_PER_MINUTE > 0


# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------


def test_portfolio_csv_columns_not_empty():
    assert len(config.PORTFOLIO_CSV_COLUMNS) > 0


def test_portfolio_csv_columns_contains_required():
    for col in ("symbol", "qty", "avg_cost", "type"):
        assert col in config.PORTFOLIO_CSV_COLUMNS


def test_valid_position_types():
    assert "long" in config.VALID_POSITION_TYPES
    assert "short" in config.VALID_POSITION_TYPES


# ---------------------------------------------------------------------------
# validate_config()
# ---------------------------------------------------------------------------


def test_validate_config_passes_with_defaults():
    errors = config.validate_config()
    assert errors == [], f"Default config should be valid, got errors: {errors}"


def test_validate_config_catches_bad_weights(monkeypatch):
    bad_weights = dict(config.AGENT_WEIGHTS)
    bad_weights["technical"] = 0.99  # will push sum way over 1.0
    monkeypatch.setattr(config, "AGENT_WEIGHTS", bad_weights)
    errors = config.validate_config()
    assert any("AGENT_WEIGHTS" in e for e in errors)


def test_validate_config_catches_bad_score_range(monkeypatch):
    monkeypatch.setattr(config, "SCORE_MIN", 5)
    monkeypatch.setattr(config, "SCORE_MAX", 1)
    errors = config.validate_config()
    assert any("SCORE_MIN" in e for e in errors)


def test_validate_config_catches_bad_temperature(monkeypatch):
    monkeypatch.setattr(config, "LLM_TEMPERATURE", 1.5)
    errors = config.validate_config()
    assert any("LLM_TEMPERATURE" in e for e in errors)


def test_validate_config_catches_zero_peers(monkeypatch):
    monkeypatch.setattr(config, "PEERS_COUNT", 0)
    errors = config.validate_config()
    assert any("PEERS_COUNT" in e for e in errors)
