"""
tools/market.py
---------------
Market data via yfinance - profile, price, fundamentals, analyst ratings.
No API key required.

Units: ratios and rates are fractions (0.25 = 25%), debt_to_equity is a
multiple (0.78 = 0.78x). yfinance reports debtToEquity and dividendYield as
percents, so those two are divided by 100 here.
"""

from __future__ import annotations

import yfinance as yf
from pydantic import BaseModel


class CompanyProfile(BaseModel):
    symbol: str
    name: str
    sector: str | None
    industry: str | None
    sector_key: str | None  # yfinance key for yf.Sector
    industry_key: str | None  # yfinance key for yf.Industry
    market_cap: float | None
    employees: int | None
    description: str | None
    website: str | None


class Fundamentals(BaseModel):
    symbol: str
    pe_ratio: float | None
    forward_pe: float | None
    peg_ratio: float | None
    price_to_book: float | None
    ev_to_ebitda: float | None
    free_cash_flow_yield: float | None  # fraction
    debt_to_equity: float | None  # multiple
    current_ratio: float | None
    quick_ratio: float | None
    return_on_equity: float | None  # fraction
    return_on_assets: float | None  # fraction
    operating_margin: float | None  # fraction
    profit_margin: float | None  # fraction
    revenue_growth: float | None  # fraction, latest quarter YoY
    earnings_growth: float | None  # fraction, latest quarter YoY


class PriceSummary(BaseModel):
    symbol: str
    current_price: float | None
    previous_close: float | None
    day_high: float | None
    day_low: float | None
    week_52_high: float | None
    week_52_low: float | None
    average_volume: int | None
    dividend_yield: float | None  # fraction


class AnalystSummary(BaseModel):
    symbol: str
    recommendation: str | None  # e.g. "buy", "hold", "sell"
    target_mean_price: float | None
    target_high_price: float | None
    target_low_price: float | None
    number_of_analysts: int | None


class TickerSnapshot(BaseModel):
    profile: CompanyProfile
    price: PriceSummary
    fundamentals: Fundamentals
    analysts: AnalystSummary


def _percent_to_fraction(value: float | None) -> float | None:
    return value / 100 if value is not None else None


def _free_cash_flow_yield(info: dict) -> float | None:
    fcf, market_cap = info.get("freeCashflow"), info.get("marketCap")
    return fcf / market_cap if fcf is not None and market_cap else None


def get_ticker_snapshot(symbol: str) -> TickerSnapshot:
    """Fetch profile, price, fundamentals and analyst data in one yfinance call."""
    symbol = symbol.upper()
    info = yf.Ticker(symbol).info

    return TickerSnapshot(
        profile=CompanyProfile(
            symbol=symbol,
            name=info.get("longName") or info.get("shortName") or symbol,
            sector=info.get("sector"),
            industry=info.get("industry"),
            sector_key=info.get("sectorKey"),
            industry_key=info.get("industryKey"),
            market_cap=info.get("marketCap"),
            employees=info.get("fullTimeEmployees"),
            description=info.get("longBusinessSummary"),
            website=info.get("website"),
        ),
        price=PriceSummary(
            symbol=symbol,
            current_price=info.get("currentPrice"),
            previous_close=info.get("previousClose"),
            day_high=info.get("dayHigh"),
            day_low=info.get("dayLow"),
            week_52_high=info.get("fiftyTwoWeekHigh"),
            week_52_low=info.get("fiftyTwoWeekLow"),
            average_volume=info.get("averageVolume"),
            dividend_yield=_percent_to_fraction(info.get("dividendYield")),
        ),
        fundamentals=Fundamentals(
            symbol=symbol,
            pe_ratio=info.get("trailingPE"),
            forward_pe=info.get("forwardPE"),
            peg_ratio=info.get("trailingPegRatio"),
            price_to_book=info.get("priceToBook"),
            ev_to_ebitda=info.get("enterpriseToEbitda"),
            free_cash_flow_yield=_free_cash_flow_yield(info),
            debt_to_equity=_percent_to_fraction(info.get("debtToEquity")),
            current_ratio=info.get("currentRatio"),
            quick_ratio=info.get("quickRatio"),
            return_on_equity=info.get("returnOnEquity"),
            return_on_assets=info.get("returnOnAssets"),
            operating_margin=info.get("operatingMargins"),
            profit_margin=info.get("profitMargins"),
            revenue_growth=info.get("revenueGrowth"),
            earnings_growth=info.get("earningsGrowth"),
        ),
        analysts=AnalystSummary(
            symbol=symbol,
            recommendation=info.get("recommendationKey"),
            target_mean_price=info.get("targetMeanPrice"),
            target_high_price=info.get("targetHighPrice"),
            target_low_price=info.get("targetLowPrice"),
            number_of_analysts=info.get("numberOfAnalystOpinions"),
        ),
    )


def get_portfolio_snapshots(symbols: list[str]) -> list[TickerSnapshot]:
    """Fetch snapshots for multiple tickers."""
    return [get_ticker_snapshot(s) for s in symbols]
