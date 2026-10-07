"""
config.py
---------
Central configuration for folio-gauge.
All tuneable constants live here — import from this module everywhere else.
Never hardcode these values in individual files.
"""

import os


SCORE_MIN: int = 1
SCORE_MAX: int = 5
# Each analyst agent scores buy/sell/hold on this scale.
# 1 = weak signal, 5 = strong signal.

VALID_DECISIONS: tuple[str, ...] = ("BUY", "SELL", "HOLD")
VALID_TIMEFRAMES: tuple[str, ...] = ("short", "mid", "long")

# ---------------------------------------------------------------------------
# Agent weights for orchestrator aggregation
# Must sum to 1.0
# Covers 8 core analysts: technical, fundamentals, sentiment, macro, peers,
# sector, earnings, news
# ---------------------------------------------------------------------------

AGENT_WEIGHTS: dict[str, float] = {
    "technical":    0.10,
    "fundamentals": 0.12,
    "sentiment":    0.09,
    "macro":        0.08,
    "peers":        0.06,
    "sector":       0.09,
    "earnings":     0.08,
    "news":         0.08,
    "discovery":    0.08,
    "portfolio":    0.14,
}

# LLM models

LLM_MODEL_AGENTS: str = "gpt-4o-mini"
LLM_TEMPERATURE_AGENTS: float = 0.3

# Edgar
EDGAR_BASE_URL: str = "https://data.sec.gov"
EDGAR_ARCHIVES_URL: str = "https://www.sec.gov/Archives/edgar/data"
EDGAR_USER_AGENT: str = os.getenv("EDGAR_USER_AGENT", "")
EDGAR_RECENT_10Q_COUNT: int = 4
EDGAR_RECENT_8K_COUNT: int = 5
EDGAR_NUMBER_8K_IN_SUMMARY: int = 3
EDGAR_MAX_CHARS: int = 4000
# XBRL concepts per metric; the first concept with the most recent data wins.
EDGAR_FACT_CONCEPTS: dict[str, tuple[str, ...]] = {
    "eps_diluted": ("EarningsPerShareDiluted",),
    "revenue": (
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ),
    "net_income": ("NetIncomeLoss",),
    "operating_cash_flow": ("NetCashProvidedByUsedInOperatingActivities",),
}

# Vector DB (Qdrant local mode, no server needed)
QDRANT_PATH: str = os.getenv("QDRANT_PATH", "data/qdrant")
EDGAR_QDRANT_COLLECTION: str = "edgar_filings"
EDGAR_CHUNK_SIZE: int = 800
EDGAR_CHUNK_OVERLAP: int = 100
EDGAR_TOP_K_RESULTS: int = 5
EDGAR_EMBEDDING_MODEL: str = "text-embedding-3-small"
EDGAR_EMBEDDING_DIMENSION: int = 1536
EDGAR_BATCH_SIZE: int = 100

# FRED
FRED_BASE_URL: str ="https://api.stlouisfed.org/fred"
FRED_DEFAULT_SERIES_LIMIT: int = 250
FRED_DEFAULT_MULTISERIES_LIMIT: int = 100
FRED_CPI_LOOKBACK_MONTHS: int = 13
FRED_GDP_LOOKBACK_QUARTERS: int = 2

# Attention: Reddit mentions via ApeWisdom (no key), StockTwits trending
REDDIT_FILTER: str = "all-stocks"

# Return lookbacks in trading days (technical and sector)
RETURN_WINDOWS: dict[str, int] = {"return_1m": 21, "return_3m": 63, "return_6m": 126}

# Sector: yfinance sector -> SPDR sector ETF, benchmarked against the market ETF
SECTOR_ETFS: dict[str, str] = {
    "Technology": "XLK",
    "Financial Services": "XLF",
    "Healthcare": "XLV",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Communication Services": "XLC",
    "Industrials": "XLI",
    "Energy": "XLE",
    "Basic Materials": "XLB",
    "Real Estate": "XLRE",
    "Utilities": "XLU",
}
MARKET_ETF: str = "SPY"
# Excess return beyond +/-band per window votes +1/-1 (sector vs market, stock vs sector).
# 1m is shown as context only: equal-weighted, a 1m bounce cancelled a 6m trend.
SECTOR_RELATIVE_BANDS: dict[str, float] = {"return_3m": 0.04, "return_6m": 0.06}

# Technical Analysis (price and volume)
TECHNICAL_HISTORY_PERIOD: str = "2y"
RSI_WINDOW: int = 14
MACD_FAST_EMA_PERIOD: int = 12
MACD_SLOW_EMA_PERIOD: int = 26
MACD_SIGNAL_PERIOD: int = 9
TECHNICAL_VOLUME_WINDOW: int = 20  # volume balance and recent average volume
TECHNICAL_VOLUME_BASELINE: int = 63  # baseline average volume (3 months)
# Labels
TECHNICAL_RETURN_BANDS: dict[str, float] = {"return_1m": 0.02, "return_3m": 0.05, "return_6m": 0.10}
TECHNICAL_VOLUME_BALANCE_BAND: float = 0.10  # (up - down volume) / total beyond +/-10%
TECHNICAL_RSI_BANDS: tuple[float, float] = (70, 30)  # overbought / oversold

# News Analysis
NEWS_MAX_AGE_DAYS: int = 14
NEWS_MAX_ARTICLES: int = 25  # newest articles sent to the LLM
NEWS_SUMMARY_CHARS: int = 300
NEWS_HIGH_MATERIALITY_WEIGHT: int = 2
NEWS_NET_BAND: float = 0.15  # net sentiment beyond +/-0.15 -> positive/negative
NEWS_STRONG_BAND: float = 0.5  # beyond +/-0.5 -> score 5 / 1
NEWS_FULL_COVERAGE: int = 10  # relevant articles for full coverage

# Peers Analysis
PEERS_COUNT: int = 5
PEERS_MIN_INDUSTRY: int = 3  # fewer industry peers than this -> fill from sector
PEERS_MIN_WEIGHT_RATIO: float = 0.1  # peer market weight >= 10% of the target's
PEERS_PREMIUM_BAND: float = 0.15  # median premium beyond +/-15% -> premium/discount
PEERS_QUALITY_NET: int = 2  # (metrics above median - below) >= 2 -> stronger, <= -2 -> weaker

# Fundamentals labels: metric -> (bullish, bearish) threshold.
# bullish < bearish means lower is better. Each metric votes +1/0/-1;
# the mean vote beyond +/-LABEL_VOTE_BAND sets the label.
FUNDAMENTALS_RULES: dict[str, dict[str, tuple[float, float]]] = {
    "valuation": {
        "forward_pe": (15, 25),
        "peg_ratio": (1.0, 2.0),
        "ev_to_ebitda": (10, 20),
        "free_cash_flow_yield": (0.05, 0.02),
    },
    "profitability": {
        "return_on_equity": (0.15, 0.08),
        "operating_margin": (0.20, 0.10),
    },
    "financial_health": {
        "debt_to_equity": (1.0, 2.0),
        "current_ratio": (1.5, 1.0),
    },
}
LABEL_VOTE_BAND: float = 0.33

# Earnings labels
EARNINGS_EPS_BANDS: tuple[float, float, float] = (0.15, 0.05, -0.05)  # strong / solid / flat / declining
EARNINGS_CASH_CONVERSION: tuple[float, float] = (0.9, 0.7)  # OCF/NI >= 0.9 high, < 0.7 low
EARNINGS_MOMENTUM_BAND: float = 0.10  # latest quarter EPS YoY vs annual YoY beyond +/-10pp

# Polymarket: markets matching this are dropped - price bets (any question with
# a dollar price level, or "Up or Down": they mirror the current price, not
# sentiment) and unnamed placeholder outcomes ("Candidate A", "Other").
POLY_DEFAULT_EVENT_LIMIT: int = 10
POLY_SKIP_PATTERN: str = r"\$\s?\d|up or down|candidate [a-z]\b|will other\b"

# Sentiment labels
SENTIMENT_MIN_TAGGED: int = 5  # fewer bullish/bearish-tagged StockTwits posts -> not assessable
SENTIMENT_NET_BAND: float = 0.2  # (bullish - bearish) / tagged beyond +/-0.2
SENTIMENT_MESSAGES_FOR_LLM: int = 10
ATTENTION_MIN_MENTIONS: int = 10  # fewer Reddit mentions -> "low" attention
ATTENTION_CHANGE_BAND: float = 0.25  # 24h mention change beyond +/-25% -> rising/falling

# Portfolio
PORTFOLIO_CSV_COLUMNS: tuple[str, ...] = ("symbol", "qty", "avg_cost", "type")
VALID_POSITION_TYPES: tuple[str, ...] = ("long", "short")
