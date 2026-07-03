"""
src/tools/technical.py
----------------------
Technical indicators using yfinance (price history) + pure pandas (computation).
No API key required. No rate limits. No extra dependencies beyond yfinance.

Replaces polygon.py — produces the same TechnicalSnapshot output model.

Indicators computed from daily close prices:
  - SMA 20, 50, 200  (Simple Moving Average)
  - RSI 14           (Relative Strength Index — Wilder smoothing)
  - MACD 12/26/9     (value, signal line, histogram)
"""

from __future__ import annotations

import traceback
from datetime import datetime, timezone

import pandas as pd
import yfinance as yf
from pydantic import BaseModel
from .. import config
from ..utils.logger import get_logger

logger = get_logger(__name__)


class Candle(BaseModel):
    """Single OHLCV candle."""

    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float | None


class TechnicalSnapshot(BaseModel):
    """
    Complete technical analysis snapshot for a ticker.
    Drop-in compatible with the retired polygon.py TechnicalSnapshot.
    """

    symbol: str
    price: float | None  # Latest close price
    sma_20: float | None  # 20-day Simple Moving Average
    sma_50: float | None  # 50-day Simple Moving Average
    sma_200: float | None  # 200-day Simple Moving Average
    rsi_14: float | None  # 14-day RSI (0-100, Wilder smoothing)
    macd_value: float | None  # MACD line (EMA12 - EMA26)
    macd_signal: float | None  # Signal line (EMA9 of MACD)
    macd_histogram: float | None  # Histogram (MACD - signal)
    fetched_at: str  # ISO 8601 UTC


def _sma(close: pd.Series, window: int) -> float | None:
    """Simple Moving Average — arithmetic mean of last `window` closes.
    Falls back to whatever history is available if fewer than `window` points exist."""
    if len(close) == 0:
        return None
    effective_window = min(window, len(close))
    val = close.rolling(effective_window, min_periods=1).mean().iloc[-1]
    return None if pd.isna(val) else round(float(val), 4)

def _sma_points_used(close: pd.Series, window: int) -> int:
    """How many data points actually went into the SMA (for transparency)."""
    return min(window, len(close))

def _rsi(close: pd.Series, window: int = config.RSI_WINDOW) -> float | None:
    """
    Relative Strength Index using Wilder's smoothing (EMA with alpha=1/window).
    Matches the standard RSI definition used by TradingView, Polygon, etc.
    """
    if len(close) < window + 1:
        return None

    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)

    # Wilder smoothing = EMA with alpha = 1/window, adjust=False
    avg_gain = gain.ewm(alpha=1 / window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / window, adjust=False).mean()

    last_loss = avg_loss.iloc[-1]
    if last_loss == 0:
        return 100.0

    rs = avg_gain.iloc[-1] / last_loss
    val = 100 - (100 / (1 + rs))
    return None if pd.isna(val) else round(float(val), 4)


def _macd(
    close: pd.Series,
    fast: int = config.MACD_FAST_EMA_PERIOD,
    slow: int = config.MACD_SLOW_EMA_PERIOD,
    signal: int = config.MACD_SIGNAL_PERIOD,
) -> tuple[float | None, float | None, float | None]:
    """
    MACD indicator.

    Returns:
        (macd_value, macd_signal, macd_histogram)
    """
    if len(close) < slow + signal:
        return None, None, None

    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line

    def _last(s: pd.Series) -> float | None:
        val = s.iloc[-1]
        return None if pd.isna(val) else round(float(val), 4)

    return _last(macd_line), _last(signal_line), _last(histogram)


def get_ohlcv_history(symbol: str, period: str = "1y") -> list[Candle]:
    """
    Fetch historical daily OHLCV candles for a ticker.
    """
    try:
        hist = yf.Ticker(symbol.upper()).history(period=period)
        if hist.empty:
            return []

        return [
            Candle(
                timestamp=str(ts)[:10],
                open=round(float(row["Open"]), 4),
                high=round(float(row["High"]), 4),
                low=round(float(row["Low"]), 4),
                close=round(float(row["Close"]), 4),
                volume=float(row["Volume"]) if row["Volume"] else None,
            )
            for ts, row in hist.iterrows()
        ]

    except Exception as e:
        logger.error(f"Error fetching OHLCV history for {symbol}: {e}")
        return []


def get_technical_snapshot(symbol: str) -> TechnicalSnapshot:
    """
    Fetch OHLCV history and compute all technical indicators in one call.
    Single yfinance request — no rate limits, no API key required.

    Fetches 1 year of daily data (~252 trading days), which is enough for
    all indicators including SMA-200 (~200 trading days needed).
    """
    symbol = symbol.upper()

    def _empty() -> TechnicalSnapshot:
        return TechnicalSnapshot(
            symbol=symbol,
            price=None,
            sma_20=None,
            sma_50=None,
            sma_200=None,
            rsi_14=None,
            macd_value=None,
            macd_signal=None,
            macd_histogram=None,
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )

    try:
        hist = yf.Ticker(symbol).history(period="1y")
        if hist.empty:
            return _empty()

        close = hist["Close"]

        macd_val, macd_sig, macd_hist = _macd(close)

        return TechnicalSnapshot(
            symbol=symbol,
            price=round(float(close.iloc[-1]), 4),
            sma_20=_sma(close, 20),
            sma_50=_sma(close, 50),
            sma_200=_sma(close, 200),
            rsi_14=_rsi(close, 14),
            macd_value=macd_val,
            macd_signal=macd_sig,
            macd_histogram=macd_hist,
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )

    except Exception as e:
        logger.error(f"Error computing technical snapshot for {symbol}: {e}")
        return _empty()
