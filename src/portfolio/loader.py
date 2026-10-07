"""
src/portfolio/loader.py
-----------------------
CSV reader for portfolio files. Extra columns are ignored.

  symbol,qty,avg_cost,type
  AAPL,50,178.00,long
  MSFT,20,310.00,long
  TSLA,10,220.00,short

Invalid rows raise (pydantic ValidationError names the row's problem).
"""

from __future__ import annotations

import csv
from pathlib import Path

from src.portfolio.models import Holding


def load_portfolio_csv(filepath: str | Path) -> list[Holding]:
    with open(filepath, encoding="utf-8", newline="") as f:
        return [
            Holding(
                symbol=row["symbol"].strip().upper(),
                qty=row["qty"],
                avg_cost=row["avg_cost"],
                position_type=row["type"].strip().lower(),
            )
            for row in csv.DictReader(f)
        ]
