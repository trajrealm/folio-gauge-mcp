"""
config.py
---------
Central configuration for folio-gauge.
All tuneable constants live here — import from this module everywhere else.
Never hardcode these values in individual files.
"""

# Scoring
from dotenv.variables import Literal


SCORE_MIN: int = 1
SCORE_MAX: int = 5
# Each analyst agent scores buy/sell/hold on this scale.
# 1 = weak signal, 5 = strong signal.

VALID_DECISIONS: tuple[str, ...] = ("BUY", "SELL", "HOLD")
VALID_TIMEFRAMES: tuple[str, ...] = ("short", "mid", "long")

# ---------------------------------------------------------------------------
# Agent weights for orchestrator aggregation
# Must sum to 1.0
# Covers 9 core analysts: technical, fundamentals, sentiment, macro, peers,
# trends, earnings, news, price_volume
# ---------------------------------------------------------------------------

AGENT_WEIGHTS: dict[str, float] = {
    "technical":    0.10,
    "fundamentals": 0.12,
    "sentiment":    0.09,
    "macro":        0.08,
    "peers":        0.06,
    "trends":       0.09,
    "earnings":     0.08,
    "news":         0.08,
    "price_volume": 0.08,
    "discovery":    0.08,
    "portfolio":    0.14,
}

# LLM models

LLM_MODEL_AGENTS: str = "gpt-4o-mini"
LLM_TEMPERATURE_AGENTS: float = 0.3

# Edgar
EDGAR_BASE_URL: str ="https://data.sec.gov"
EDGAR_SEARCH_URL: str ="https://efts.sec.gov/LATEST/search-index"
EDGAR_QDRANT_COLLECTION: str ="edgar_filings"
EDGAR_CHUNK_SIZE: int = 800
EDGAR_CHUNK_OVERLAP: int = 100
EDGAR_TOP_K_RESULTS: int = 5
EDGAR_EMBEDDING_MODEL: str ="text-embedding-3-small"
EDGAR_EMBEDDING_DIMENSION: int = 1536
EDGAR_USER_AGENT: str ="folio-gauge-mcp/1.0 contact: example@example.com"
EDGAR_BATCH_SIZE: int = 100
EDGAR_MAX_CHARS: int = 4000
EDGAR_RECENT_10K_FETCH: bool = True
EDGAR_RECENT_10Q_COUNT: int = 4
EDGAR_RECENT_8K_COUNT: int = 5
EDGAR_NUMBER_8K_IN_SUMMARY: int = 3
EDGAR_NUMBER_10Q_IN_SUMMARY: int = 4

# FRED
FRED_BASE_URL: str ="https://api.stlouisfed.org/fred"
FRED_DEFAULT_SERIES_LIMIT: int = 250
FRED_DEFAULT_MULTISERIES_LIMIT: int = 100
FRED_CPI_LOOKBACK_MONTHS: int = 13
FRED_GDP_LOOKBACK_QUARTERS: int = 2

# Trends
REDDIT_FILTER: str = "all-stocks"

# Technical Analysis
RSI_WINDOW: int = 14
MACD_FAST_EMA_PERIOD: int = 12
MACD_SLOW_EMA_PERIOD: int = 26
MACD_SIGNAL_PERIOD: int = 9

# News Analysis
NEWS_MAX_SUMMARY_CHARS: int = 500
NEWS_PER_NEWS_SOURCE: int = 5
NEWS_PER_REUTERS_SOURCE: int = 3

# Peers Analysis
PEERS_LOOKUP_LIMIT: int = 10

# Polymarket
POLY_DEFAULT_EVENT_LIMIT: int = 10
POLY_CONFIDENCE_CALC_WEIGHT: tuple[float, float, float] = (0.4, 0.3, 0.3)
POLY_NORMALIZATION_DIVISOR: float = 5.0

# Portfolio
PORTFOLIO_CSV_COLUMNS: tuple[str, ...] = ("symbol", "qty", "avg_cost", "type")
VALID_POSITION_TYPES: tuple[str, ...] = ("long", "short")
