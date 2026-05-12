"""
tools/market.py
---------------
Market data via yfinance — price, fundamentals, earnings, analyst ratings.
No API key required.
"""

from __future__ import annotations

import yfinance as yf
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Output models
# ---------------------------------------------------------------------------

class CompanyProfile(BaseModel):
    symbol: str
    name: str
    sector: str | None
    industry: str | None
    market_cap: float | None
    employees: int | None
    description: str | None
    website: str | None


class Fundamentals(BaseModel):
    symbol: str
    pe_ratio: float | None
    forward_pe: float | None
    price_to_book: float | None
    debt_to_equity: float | None
    return_on_equity: float | None
    profit_margin: float | None
    revenue_growth: float | None
    earnings_growth: float | None
    current_ratio: float | None
    quick_ratio: float | None


class PriceSummary(BaseModel):
    symbol: str
    current_price: float | None
    previous_close: float | None
    day_high: float | None
    day_low: float | None
    week_52_high: float | None
    week_52_low: float | None
    average_volume: int | None
    dividend_yield: float | None


class AnalystSummary(BaseModel):
    symbol: str
    recommendation: str | None        # e.g. "buy", "hold", "sell"
    target_mean_price: float | None
    target_high_price: float | None
    target_low_price: float | None
    number_of_analysts: int | None


class TickerSnapshot(BaseModel):
    profile: CompanyProfile
    price: PriceSummary
    fundamentals: Fundamentals
    analysts: AnalystSummary


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe(info: dict, key: str, cast=None):
    """Safely extract a value from yfinance info dict."""
    val = info.get(key)
    if val is None:
        return None
    if cast:
        try:
            return cast(val)
        except (TypeError, ValueError):
            return None
    return val


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def get_profile(symbol: str) -> CompanyProfile:
    """Return basic company profile for a ticker."""
    info = yf.Ticker(symbol).info
    return CompanyProfile(
        symbol=symbol.upper(),
        name=_safe(info, "longName") or _safe(info, "shortName") or symbol,
        sector=_safe(info, "sector"),
        industry=_safe(info, "industry"),
        market_cap=_safe(info, "marketCap", float),
        employees=_safe(info, "fullTimeEmployees", int),
        description=_safe(info, "longBusinessSummary"),
        website=_safe(info, "website"),
    )


def get_price_summary(symbol: str) -> PriceSummary:
    """Return current price snapshot for a ticker."""
    info = yf.Ticker(symbol).info
    return PriceSummary(
        symbol=symbol.upper(),
        current_price=_safe(info, "currentPrice", float),
        previous_close=_safe(info, "previousClose", float),
        day_high=_safe(info, "dayHigh", float),
        day_low=_safe(info, "dayLow", float),
        week_52_high=_safe(info, "fiftyTwoWeekHigh", float),
        week_52_low=_safe(info, "fiftyTwoWeekLow", float),
        average_volume=_safe(info, "averageVolume", int),
        dividend_yield=_safe(info, "dividendYield", float),
    )


def get_fundamentals(symbol: str) -> Fundamentals:
    """Return key fundamental ratios for a ticker."""
    info = yf.Ticker(symbol).info
    return Fundamentals(
        symbol=symbol.upper(),
        pe_ratio=_safe(info, "trailingPE", float),
        forward_pe=_safe(info, "forwardPE", float),
        price_to_book=_safe(info, "priceToBook", float),
        debt_to_equity=_safe(info, "debtToEquity", float),
        return_on_equity=_safe(info, "returnOnEquity", float),
        profit_margin=_safe(info, "profitMargins", float),
        revenue_growth=_safe(info, "revenueGrowth", float),
        earnings_growth=_safe(info, "earningsGrowth", float),
        current_ratio=_safe(info, "currentRatio", float),
        quick_ratio=_safe(info, "quickRatio", float),
    )


def get_analyst_summary(symbol: str) -> AnalystSummary:
    """Return analyst consensus and price targets."""
    info = yf.Ticker(symbol).info
    return AnalystSummary(
        symbol=symbol.upper(),
        recommendation=_safe(info, "recommendationKey"),
        target_mean_price=_safe(info, "targetMeanPrice", float),
        target_high_price=_safe(info, "targetHighPrice", float),
        target_low_price=_safe(info, "targetLowPrice", float),
        number_of_analysts=_safe(info, "numberOfAnalystOpinions", int),
    )


def get_ticker_snapshot(symbol: str) -> TickerSnapshot:
    """
    Single-call convenience: fetch all market data for a ticker.
    Makes only ONE yfinance request by reusing the Ticker object.
    """
    ticker = yf.Ticker(symbol)
    info = ticker.info

    profile = CompanyProfile(
        symbol=symbol.upper(),
        name=_safe(info, "longName") or _safe(info, "shortName") or symbol,
        sector=_safe(info, "sector"),
        industry=_safe(info, "industry"),
        market_cap=_safe(info, "marketCap", float),
        employees=_safe(info, "fullTimeEmployees", int),
        description=_safe(info, "longBusinessSummary"),
        website=_safe(info, "website"),
    )

    price = PriceSummary(
        symbol=symbol.upper(),
        current_price=_safe(info, "currentPrice", float),
        previous_close=_safe(info, "previousClose", float),
        day_high=_safe(info, "dayHigh", float),
        day_low=_safe(info, "dayLow", float),
        week_52_high=_safe(info, "fiftyTwoWeekHigh", float),
        week_52_low=_safe(info, "fiftyTwoWeekLow", float),
        average_volume=_safe(info, "averageVolume", int),
        dividend_yield=_safe(info, "dividendYield", float),
    )

    fundamentals = Fundamentals(
        symbol=symbol.upper(),
        pe_ratio=_safe(info, "trailingPE", float),
        forward_pe=_safe(info, "forwardPE", float),
        price_to_book=_safe(info, "priceToBook", float),
        debt_to_equity=_safe(info, "debtToEquity", float),
        return_on_equity=_safe(info, "returnOnEquity", float),
        profit_margin=_safe(info, "profitMargins", float),
        revenue_growth=_safe(info, "revenueGrowth", float),
        earnings_growth=_safe(info, "earningsGrowth", float),
        current_ratio=_safe(info, "currentRatio", float),
        quick_ratio=_safe(info, "quickRatio", float),
    )

    analysts = AnalystSummary(
        symbol=symbol.upper(),
        recommendation=_safe(info, "recommendationKey"),
        target_mean_price=_safe(info, "targetMeanPrice", float),
        target_high_price=_safe(info, "targetHighPrice", float),
        target_low_price=_safe(info, "targetLowPrice", float),
        number_of_analysts=_safe(info, "numberOfAnalystOpinions", int),
    )

    return TickerSnapshot(
        profile=profile,
        price=price,
        fundamentals=fundamentals,
        analysts=analysts,
    )


def get_portfolio_snapshots(symbols: list[str]) -> list[TickerSnapshot]:
    """Fetch snapshots for multiple tickers."""
    return [get_ticker_snapshot(s) for s in symbols]