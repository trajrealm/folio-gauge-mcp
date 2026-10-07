"""
src/tools/sector.py
-------------------
Sector trend via yfinance (no API key): returns of the stock, its SPDR
sector ETF (config.SECTOR_ETFS) and the market ETF over 1/3/6 months, and
the excess returns sector vs market and stock vs sector.
"""

from __future__ import annotations

import pandas as pd
import yfinance as yf
from pydantic import BaseModel

from .. import config


class SectorTrend(BaseModel):
    symbol: str
    sector: str | None
    sector_etf: str | None  # None when the sector has no mapped ETF
    stock_returns: dict[str, float | None]  # fractions per config.RETURN_WINDOWS
    sector_returns: dict[str, float | None]
    market_returns: dict[str, float | None]
    sector_vs_market: dict[str, float | None]  # sector - market
    stock_vs_sector: dict[str, float | None]  # stock - sector


def _returns(close: pd.Series) -> dict[str, float | None]:
    close = close.dropna()
    return {
        key: float(close.iloc[-1] / close.iloc[-1 - days] - 1) if len(close) > days else None
        for key, days in config.RETURN_WINDOWS.items()
    }


def _excess(a: dict[str, float | None], b: dict[str, float | None]) -> dict[str, float | None]:
    return {k: a[k] - b[k] if a[k] is not None and b[k] is not None else None for k in a}


def get_sector_trend(symbol: str) -> SectorTrend:
    """Fetch stock, sector ETF and market ETF history in one download."""
    symbol = symbol.upper()
    sector = yf.Ticker(symbol).info.get("sector")
    etf = config.SECTOR_ETFS.get(sector)

    tickers = [symbol, config.MARKET_ETF] + ([etf] if etf else [])
    close = yf.download(tickers, period="1y", progress=False, auto_adjust=True)["Close"]

    stock = _returns(close[symbol])
    market = _returns(close[config.MARKET_ETF])
    sector_returns = _returns(close[etf]) if etf else {k: None for k in config.RETURN_WINDOWS}

    return SectorTrend(
        symbol=symbol,
        sector=sector,
        sector_etf=etf,
        stock_returns=stock,
        sector_returns=sector_returns,
        market_returns=market,
        sector_vs_market=_excess(sector_returns, market),
        stock_vs_sector=_excess(stock, sector_returns),
    )
