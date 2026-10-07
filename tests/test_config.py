"""
test_config.py
--------------
Checks config invariants. No network or API keys.
Run from project root:
    uv run pytest tests/test_config.py
"""

from src import config
from src.agent.graph import ANALYSTS


def test_weights_sum_to_one():
    assert round(sum(config.AGENT_WEIGHTS.values()), 10) == 1.0


def test_weights_cover_exactly_the_analysts():
    assert set(config.AGENT_WEIGHTS) == set(ANALYSTS)


def test_horizons_partition_the_analysts():
    agents = [a for group in config.HORIZONS.values() for a in group]
    assert sorted(agents) == sorted(ANALYSTS)


def test_weights_positive():
    assert all(w > 0 for w in config.AGENT_WEIGHTS.values())


def test_band_pairs_ordered():
    softening, recession = config.MACRO_SAHM_BANDS
    calm, stressed = config.MACRO_VIX_BANDS
    assert softening < recession
    assert calm < stressed
    assert config.NEWS_NET_BAND < config.NEWS_STRONG_BAND
