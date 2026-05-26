"""
tools/fred.py
-------------
Federal Reserve Economic Data (FRED) API client.

Base URL: https://api.stlouisfed.org/fred
Requires: FRED_API_KEY environment variable
Free tier: No rate limits per se, but be respectful (~5 req/sec safe)

Key series IDs:
  - DFF: Effective Federal Funds Rate (daily)
  - T10Y2Y: 10-Year minus 2-Year Treasury Spread (daily)
  - CPIAUCSL: Consumer Price Index (monthly)
  - UNRATE: Unemployment Rate (monthly)
  - GDPC1: Real Gross Domestic Product (quarterly)
  - VIX: CBOE Volatility Index (daily)
"""

from __future__ import annotations

import os
import time
from typing import Optional, Literal

import httpx
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential
from .. import config
from ..utils.logger import get_logger

logger = get_logger(__name__)


class FredObservation(BaseModel):
    """A single data point from FRED."""

    date: str  # YYYY-MM-DD
    value: float | None


class FredSeries(BaseModel):
    """FRED economic series data."""

    series_id: str  # e.g. "DFF"
    title: str  # Human-readable name
    units: str | None  # e.g. "Percent", "Index"
    frequency: str | None  # e.g. "Daily", "Monthly", "Quarterly"
    observations: list[FredObservation]  # Time series data


class EconomicIndicators(BaseModel):
    """Snapshot of key macro indicators."""

    fed_funds_rate: float | None  # Latest DFF (%)
    unemployment_rate: float | None  # Latest UNRATE (%)
    cpi_yoy_change: float | None  # YoY CPI change (%)
    yield_spread_10y2y: float | None  # 10Y - 2Y Treasury (%)
    gdp_growth_rate: float | None  # Latest GDPC1 growth (% annualized)
    vix_index: float | None  # CBOE VIX (index)
    fetched_at: str  # ISO 8601 timestamp when fetched


class FredClient:
    """FRED API client."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize FRED client.
        """
        self.api_key = api_key or os.getenv("FRED_API_KEY")
        if not self.api_key:
            raise ValueError(
                "FRED_API_KEY not provided and FRED_API_KEY environment variable not set."
            )

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def _get(self, endpoint: str, params: dict) -> dict:
        """
        GET request with retry logic.
        """
        time.sleep(0.2)  # Rate limiting

        url = f"{config.FRED_BASE_URL}/{endpoint}"
        params["api_key"] = self.api_key
        params["file_type"] = "json"

        response = httpx.get(url, params=params, timeout=15)
        response.raise_for_status()

        return response.json()

    def get_series(
        self,
        series_id: str,
        limit: int = config.FRED_DEFAULT_SERIES_LIMIT,
        sort_order: Literal["asc", "desc"] = "desc",
    ) -> FredSeries:
        """
        Fetch a FRED series.
        """
        series_info = self._get("series", {"series_id": series_id})
        series_meta = series_info.get("seriess", [{}])[0]

        obs_response = self._get(
            "series/observations",
            {
                "series_id": series_id,
                "limit": min(limit, 100000),
                "sort_order": sort_order,
            },
        )

        observations = [
            FredObservation(
                date=o["date"], value=float(o["value"]) if o["value"] != "." else None
            )
            for o in obs_response.get("observations", [])
        ]

        return FredSeries(
            series_id=series_id,
            title=series_meta.get("title", ""),
            units=series_meta.get("units", ""),
            frequency=series_meta.get("frequency", ""),
            observations=observations,
        )

    def get_latest_value(self, series_id: str) -> float | None:
        """
        Get the latest value for a series.
        """
        series = self.get_series(series_id, limit=1)
        if series.observations and series.observations[0].value is not None:
            return series.observations[0].value
        return None

    def get_multiple_series(
        self, series_ids: list[str], limit: int = config.FRED_DEFAULT_MULTISERIES_LIMIT
    ) -> dict[str, FredSeries]:
        """
        Fetch multiple series in parallel (sequential for simplicity).

        """
        result = {}
        for series_id in series_ids:
            try:
                result[series_id] = self.get_series(series_id, limit=limit)
            except Exception as e:
                logger.error(f"Failed to fetch {series_id}: {e}")
        return result

def get_economic_indicators(api_key: Optional[str] = None) -> EconomicIndicators:
    from datetime import datetime, timezone

    client = FredClient(api_key)

    fed_funds = client.get_latest_value("DFF")
    unemployment = client.get_latest_value("UNRATE")
    yield_spread = client.get_latest_value("T10Y2Y")
    vix = client.get_latest_value("VIXCLS")

    # CPI: fetch last 13 months to compute YoY % change
    cpi_series = client.get_series("CPIAUCSL", limit=config.FRED_CPI_LOOKBACK_MONTHS, sort_order="desc")
    cpi_yoy = None
    if len(cpi_series.observations) >= config.FRED_CPI_LOOKBACK_MONTHS:
        latest_cpi = cpi_series.observations[0].value
        year_ago_cpi = cpi_series.observations[12].value
        if latest_cpi and year_ago_cpi and year_ago_cpi != 0:
            cpi_yoy = round(((latest_cpi - year_ago_cpi) / year_ago_cpi) * 100, 2)

    # GDP: fetch last 2 quarters to compute QoQ annualized growth
    gdp_series = client.get_series("GDPC1", limit=config.FRED_GDP_LOOKBACK_QUARTERS, sort_order="desc")
    gdp_growth = None
    if len(gdp_series.observations) >= config.FRED_GDP_LOOKBACK_QUARTERS:
        latest_gdp = gdp_series.observations[0].value
        prior_gdp = gdp_series.observations[1].value
        if latest_gdp and prior_gdp and prior_gdp != 0:
            # Annualize the quarterly growth rate
            gdp_growth = round(((latest_gdp / prior_gdp) ** 4 - 1) * 100, 2)

    return EconomicIndicators(
        fed_funds_rate=fed_funds,
        unemployment_rate=unemployment,
        cpi_yoy_change=cpi_yoy,
        yield_spread_10y2y=yield_spread,
        gdp_growth_rate=gdp_growth,
        vix_index=vix,
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )


def get_interest_rate_environment(api_key: Optional[str] = None) -> dict:
    """
    Fetch interest rate data for macro analysis.

    Returns dict with:
      - fed_funds_rate (current)
      - 10y2y_spread (rate curve)
      - cpi (inflation proxy)
    """
    client = FredClient(api_key)

    return {
        "fed_funds_rate": client.get_latest_value("DFF"),
        "10y2y_spread": client.get_latest_value("T10Y2Y"),
        "cpi": client.get_latest_value("CPIAUCSL"),
    }


def get_unemployment_data(
    api_key: Optional[str] = None, months: int = 12
) -> list[FredObservation]:
    """
    Fetch unemployment rate history.
    """
    client = FredClient(api_key)
    series = client.get_series("UNRATE", limit=months + 5)
    return series.observations


def get_gdp_data(
    api_key: Optional[str] = None, quarters: int = 20
) -> list[FredObservation]:
    """
    Fetch GDP (real, quarterly) history.
    """
    client = FredClient(api_key)
    series = client.get_series("GDPC1", limit=quarters + 5)
    return series.observations


def get_vix_data(
    api_key: Optional[str] = None, days: int = 60
) -> list[FredObservation]:
    """
    Fetch VIX (volatility index) history.
    """
    client = FredClient(api_key)
    series = client.get_series("VIXCLS", limit=days + 10)
    return series.observations
