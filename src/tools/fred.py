"""
tools/fred.py
-------------
Macro snapshot from FRED (Federal Reserve Economic Data).
Requires FRED_API_KEY. One request per series (config.FRED_SERIES), cached
for the day: the values are the same for every ticker and change daily at most.

Computed (percent / percentage points):
  - fed funds rate now and 6 months ago
  - CPI year-over-year inflation now and 6 months ago
  - unemployment rate and the Sahm indicator (3-month average unemployment
    minus its low over the prior 12 months; >= 0.5 has signalled recessions)
  - real GDP growth, latest quarter, annualized
  - 10Y-2Y yield curve and VIX, latest
"""

from __future__ import annotations

import os
from datetime import date, timedelta
from functools import lru_cache

from pydantic import BaseModel

from .. import config
from ..utils.http import get_json


class MacroSnapshot(BaseModel):
    fed_funds: float
    fed_funds_6m_ago: float
    cpi_yoy: float
    cpi_yoy_6m_ago: float
    cpi_as_of: str  # CPI is published with a ~1 month lag
    unemployment: float
    sahm: float
    gdp_growth: float
    gdp_as_of: str  # quarter start date; published with a ~1 quarter lag
    yield_curve: float
    vix: float


def _series(series_id: str) -> list[tuple[str, float]]:
    """(date, value) pairs, oldest first; missing values ('.') dropped."""
    start = date.today() - timedelta(days=config.FRED_HISTORY_DAYS)
    data = get_json(
        f"{config.FRED_BASE_URL}/series/observations",
        params={
            "series_id": series_id,
            "api_key": os.environ["FRED_API_KEY"],
            "file_type": "json",
            "observation_start": start.isoformat(),
        },
    )
    return [(o["date"], float(o["value"])) for o in data["observations"] if o["value"] != "."]


def _on_or_before(series: list[tuple[str, float]], day: date) -> float:
    return [v for d, v in series if d <= day.isoformat()][-1]


def _months_before(day: str, months: int) -> date:
    d = date.fromisoformat(day)
    y, m = divmod(d.year * 12 + d.month - 1 - months, 12)
    return date(y, m + 1, 1)


@lru_cache(maxsize=1)
def _snapshot(day: str) -> MacroSnapshot:
    s = {name: _series(series_id) for name, series_id in config.FRED_SERIES.items()}
    fed, cpi, unemp, gdp = s["fed_funds"], s["cpi"], s["unemployment"], s["gdp"]

    # Look up by calendar month, not row offset: months can be missing
    # (October 2025 was not collected during the government shutdown).
    def yoy(months_back: int) -> float:
        end = _months_before(cpi[-1][0], months_back)
        return (_on_or_before(cpi, end) / _on_or_before(cpi, _months_before(end.isoformat(), 12)) - 1) * 100

    ma3 = [sum(v for _, v in unemp[i - 3 : i]) / 3 for i in range(3, len(unemp) + 1)]

    return MacroSnapshot(
        fed_funds=fed[-1][1],
        fed_funds_6m_ago=_on_or_before(fed, date.fromisoformat(day) - timedelta(days=182)),
        cpi_yoy=yoy(0),
        cpi_yoy_6m_ago=yoy(6),
        cpi_as_of=cpi[-1][0],
        unemployment=unemp[-1][1],
        sahm=ma3[-1] - min(ma3[-13:-1]),
        gdp_growth=((gdp[-1][1] / gdp[-2][1]) ** 4 - 1) * 100,
        gdp_as_of=gdp[-1][0],
        yield_curve=s["yield_curve"][-1][1],
        vix=s["vix"][-1][1],
    )


def get_macro_snapshot() -> MacroSnapshot:
    """Today's macro snapshot (cached for the day)."""
    return _snapshot(date.today().isoformat())
