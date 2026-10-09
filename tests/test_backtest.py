"""
test_backtest.py
----------------
Unit tests (no network) for the as-of XBRL periods in src/tools/edgar.py and
the evaluation helpers in src/backtest/earnings.py.
Run from project root:
    uv run pytest tests/test_backtest.py
"""

import math

import pandas as pd
import pytest

from src.backtest.earnings import excess_return, parse_tickers, quarterly_ic
from src.tools.edgar import period_key, periods


def test_period_key_matches_sec_frames():
    assert period_key("2024-09-29", "2025-09-27") == "CY2025"  # AAPL fiscal year (Oct-Sep)
    assert period_key("2007-07-01", "2008-06-30") == "CY2008"  # MSFT July-June year: end year
    assert period_key("2024-01-29", "2025-01-26") == "CY2024"  # NVDA year ending late January
    assert period_key("2025-09-28", "2025-12-27") == "CY2025Q4"  # AAPL December quarter
    assert period_key("2009-05-11", "2009-08-30") == "CY2009Q3"  # COST 16-week quarter
    assert period_key("2021-02-15", "2021-05-09") == "CY2021Q1"  # COST 12-week quarter
    assert period_key("2024-09-29", "2025-03-29") is None  # 6-month year to date


def test_periods_keep_latest_filed_value():
    rows = [
        {"start": "2024-01-01", "end": "2024-12-31", "val": 1.0, "filed": "2025-02-01"},
        {"start": "2024-01-01", "end": "2024-12-31", "val": 1.1, "filed": "2026-02-01"},  # restated
        {"start": "2025-01-01", "end": "2025-03-31", "val": 0.3, "filed": "2025-05-01"},
        {"end": "2025-03-31", "val": 9.0, "filed": "2025-05-01"},  # instant value: ignored
    ]
    annual, quarterly = periods(rows)
    assert annual == {"CY2024": 1.1}
    assert quarterly == {"CY2025Q1": 0.3}
    # As of mid-2025 the restatement was not yet filed.
    annual, _ = periods([r for r in rows if r["filed"] <= "2025-06-30"])
    assert annual == {"CY2024": 1.0}


def test_parse_tickers(tmp_path):
    assert parse_tickers("aapl, msft,,JPM") == ["AAPL", "MSFT", "JPM"]
    path = tmp_path / "universe.csv"
    path.write_text("name,symbol\nApple,AAPL\nMicrosoft,msft\n")
    assert parse_tickers(str(path)) == ["AAPL", "MSFT"]


def test_excess_return_starts_after_as_of():
    dates = pd.bdate_range("2025-01-01", periods=6)
    closes = pd.DataFrame({"AAA": [10, 10, 11, 12, 13, 14], "SPY": [100, 100, 100, 101, 102, 103]}, index=dates)
    # as_of 2025-01-02 -> entry close 2025-01-03 (11); 2 days later 2025-01-07 (13).
    assert math.isclose(excess_return(closes, "AAA", "2025-01-02", 2), 13 / 11 - 1 - (102 / 100 - 1))
    assert math.isnan(excess_return(closes, "AAA", "2025-01-02", 10))  # not yet available
    assert math.isnan(excess_return(closes, "BBB", "2025-01-02", 2))  # no prices


def test_quarterly_ic_per_quarter():
    rows = [{"quarter": "2024Q1", "signal": i, "target": i * 2.0} for i in range(10)]
    rows += [{"quarter": "2024Q2", "signal": i, "target": -i * 1.0} for i in range(10)]
    rows += [{"quarter": "2024Q3", "signal": i, "target": i * 1.0} for i in range(5)]  # too few
    ics = quarterly_ic(pd.DataFrame(rows), "signal", "target")
    assert ics.to_dict() == pytest.approx({"2024Q1": 1.0, "2024Q2": -1.0})
