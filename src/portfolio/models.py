"""
src/portfolio/models.py
-----------------------
A holding: one long or short position.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Holding(BaseModel):
    symbol: str
    qty: float = Field(gt=0)
    avg_cost: float = Field(gt=0)
    position_type: Literal["long", "short"]
