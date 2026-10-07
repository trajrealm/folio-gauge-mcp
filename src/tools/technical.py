"""
src/tools/technical.py
----------------------
Price and volume indicators from yfinance daily history (one request).
No API key required.

Indicators (None when history is too short):
  - SMA 50, 200
  - RSI 14 (Wilder smoothing)
  - MACD 12/26/9 (value, signal, histogram)
  - Returns over 1, 3 and 6 months
  - 52-week intraday high/low and position in that range
  - Volume balance: (up-day volume - down-day volume) / total volume over
    the last TECHNICAL_VOLUME_WINDOW days (the normalized OBV change)
  - Relative volume: recent average volume / 3-month average volume
"""

from __future__ import annotations

import pandas as pd
import yfinance as yf
from pydantic import BaseModel

from .. import config


class TechnicalSnapshot(BaseModel):
    symbol: str
    trading_days: int
    price: float
    sma_50: float | None
    sma_200: float | None
    rsi_14: float | None
    macd_value: float | None
    macd_signal: float | None
    macd_histogram: float | None
    return_1m: float | None  # fraction
    return_3m: float | None
    return_6m: float | None
    week_52_high: float
    week_52_low: float
    range_position: float  # 0 = at 52-week low, 1 = at 52-week high
    volume_balance: float | None  # -1 (all selling) to +1 (all buying)
    relative_volume: float | None  # recent / baseline average volume


def _sma(close: pd.Series, window: int) -> float | None:
    return float(close.iloc[-window:].mean()) if len(close) >= window else None


def _rsi(close: pd.Series, window: int = config.RSI_WINDOW) -> float | None:
    """Wilder's RSI (EMA with alpha=1/window), as used by TradingView."""
    if len(close) < window + 1:
        return None
    delta = close.diff()
    avg_gain = delta.clip(lower=0).ewm(alpha=1 / window, adjust=False).mean().iloc[-1]
    avg_loss = (-delta).clip(lower=0).ewm(alpha=1 / window, adjust=False).mean().iloc[-1]
    return 100.0 if avg_loss == 0 else float(100 - 100 / (1 + avg_gain / avg_loss))


def _macd(close: pd.Series) -> tuple[float | None, float | None, float | None]:
    """(MACD line, signal line, histogram)."""
    if len(close) < config.MACD_SLOW_EMA_PERIOD + config.MACD_SIGNAL_PERIOD:
        return None, None, None
    fast = close.ewm(span=config.MACD_FAST_EMA_PERIOD, adjust=False).mean()
    slow = close.ewm(span=config.MACD_SLOW_EMA_PERIOD, adjust=False).mean()
    line = fast - slow
    signal = line.ewm(span=config.MACD_SIGNAL_PERIOD, adjust=False).mean()
    return float(line.iloc[-1]), float(signal.iloc[-1]), float(line.iloc[-1] - signal.iloc[-1])


def _return(close: pd.Series, days: int) -> float | None:
    return float(close.iloc[-1] / close.iloc[-1 - days] - 1) if len(close) > days else None


def _volume_balance(close: pd.Series, volume: pd.Series) -> float | None:
    window = config.TECHNICAL_VOLUME_WINDOW
    if len(close) <= window:
        return None
    direction = close.diff().iloc[-window:].apply(lambda d: 1 if d > 0 else -1 if d < 0 else 0)
    recent = volume.iloc[-window:]
    return float((direction * recent).sum() / recent.sum()) if recent.sum() else None


def _relative_volume(volume: pd.Series) -> float | None:
    if len(volume) < config.TECHNICAL_VOLUME_BASELINE:
        return None
    baseline = volume.iloc[-config.TECHNICAL_VOLUME_BASELINE :].mean()
    return float(volume.iloc[-config.TECHNICAL_VOLUME_WINDOW :].mean() / baseline) if baseline else None


def get_technical_snapshot(symbol: str) -> TechnicalSnapshot | None:
    """Compute all indicators from one history request. None if there is no history."""
    symbol = symbol.upper()
    hist = yf.Ticker(symbol).history(period=config.TECHNICAL_HISTORY_PERIOD)
    if hist.empty:
        return None

    close, volume = hist["Close"], hist["Volume"]
    high, low = float(hist["High"].iloc[-252:].max()), float(hist["Low"].iloc[-252:].min())
    macd_value, macd_signal, macd_histogram = _macd(close)
    returns = {k: _return(close, d) for k, d in config.TECHNICAL_RETURN_WINDOWS.items()}

    return TechnicalSnapshot(
        symbol=symbol,
        trading_days=len(close),
        price=float(close.iloc[-1]),
        sma_50=_sma(close, 50),
        sma_200=_sma(close, 200),
        rsi_14=_rsi(close),
        macd_value=macd_value,
        macd_signal=macd_signal,
        macd_histogram=macd_histogram,
        **returns,
        week_52_high=high,
        week_52_low=low,
        range_position=(float(close.iloc[-1]) - low) / (high - low) if high > low else 0.5,
        volume_balance=_volume_balance(close, volume),
        relative_volume=_relative_volume(volume),
    )
