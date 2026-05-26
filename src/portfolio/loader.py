"""
src/portfolio/loader.py
-----------------------
CSV reader for portfolio files.

Expected CSV format:
  symbol,qty,avg_cost,type
  AAPL,50,178.00,long
  MSFT,20,310.00,long
  TSLA,10,220.00,short

Additional columns are ignored.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional
import config
from src.portfolio.models import Portfolio, Holding
from src.utils.logger import get_logger

logger = get_logger(__name__)

class PortfolioLoadError(Exception):
    """Raised when portfolio CSV cannot be loaded."""
    pass


def load_portfolio_csv(filepath: str | Path, portfolio_name: Optional[str] = None) -> Portfolio:
    """
    Load a portfolio from a CSV file.
    
    Expected columns: symbol, qty, avg_cost, type
    Additional columns are ignored.
    """
    filepath = Path(filepath)
    
    if not filepath.exists():
        raise PortfolioLoadError(f"Portfolio file not found: {filepath}")
    
    if not filepath.is_file():
        raise PortfolioLoadError(f"Not a file: {filepath}")
    
    portfolio = Portfolio(name=portfolio_name or filepath.stem)
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            
            if not reader.fieldnames:
                raise PortfolioLoadError("CSV file is empty or has no header row.")
            
            # Check for required columns
            required_cols = {"symbol", "qty", "avg_cost", "type"}
            header_set = set(reader.fieldnames)
            missing_cols = required_cols - header_set
            
            if missing_cols:
                raise PortfolioLoadError(
                    f"CSV missing required columns: {missing_cols}. "
                    f"Found: {header_set}"
                )
            
            for row_num, row in enumerate(reader, start=2):  # start=2 because row 1 is header
                try:
                    holding = _parse_holding_row(row, row_num)
                    portfolio.add_holding(holding)
                except ValueError as e:
                    logger.error(f"Row {row_num}: {e}")
                    raise PortfolioLoadError(f"Row {row_num}: {e}")
    
    except csv.Error as e:
        logger.error(f"CSV parsing error: {e}")
        raise PortfolioLoadError(f"CSV parsing error: {e}")
    
    if not portfolio.holdings:
        logger.error("Portfolio has no holdings (file may be empty or malformed).")
        raise PortfolioLoadError("Portfolio has no holdings (file may be empty or malformed).")
    
    # Validate all holdings
    validation_errors = portfolio.validate()
    if validation_errors:
        logger.error(f"Portfolio validation failed:\n" + "\n".join(validation_errors))
        raise PortfolioLoadError(
            f"Portfolio validation failed:\n" + "\n".join(validation_errors)
        )
    
    return portfolio


def _parse_holding_row(row: dict[str, str], row_num: int) -> Holding:
    """
    Parse a single CSV row into a Holding object.
    """
    symbol = row.get("symbol", "").strip().upper()
    qty_str = row.get("qty", "").strip()
    avg_cost_str = row.get("avg_cost", "").strip()
    position_type = row.get("type", "").strip().lower()
    
    # Validate symbol
    if not symbol:
        raise ValueError("symbol is empty")
    
    # Parse qty
    try:
        qty = float(qty_str)
    except ValueError:
        raise ValueError(f"qty '{qty_str}' is not a valid number")
    
    # Parse avg_cost
    try:
        avg_cost = float(avg_cost_str)
    except ValueError:
        raise ValueError(f"avg_cost '{avg_cost_str}' is not a valid number")
    
    # Normalize position type
    if position_type not in config.VALID_POSITION_TYPES:
        raise ValueError(
            f"type '{position_type}' not valid. Must be one of {config.VALID_POSITION_TYPES}"
        )
    
    return Holding(
        symbol=symbol,
        qty=qty,
        avg_cost=avg_cost,
        position_type=position_type,
    )


def save_portfolio_csv(portfolio: Portfolio, filepath: str | Path) -> None:
    """
    Save a portfolio to a CSV file.
    """
    filepath = Path(filepath)
    
    try:
        with open(filepath, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=config.PORTFOLIO_CSV_COLUMNS,
            )
            writer.writeheader()
            
            for holding in portfolio.holdings:
                writer.writerow({
                    "symbol": holding.symbol,
                    "qty": holding.qty,
                    "avg_cost": holding.avg_cost,
                    "type": holding.position_type,
                })
    
    except IOError as e:
        raise PortfolioLoadError(f"Failed to write portfolio CSV: {e}")


def load_portfolio_from_list(
    holdings_data: list[dict[str, any]],
    portfolio_name: Optional[str] = None,
) -> Portfolio:
    """
    Load a portfolio from a list of dicts (useful for programmatic creation).
    
    Each dict should have: symbol, qty, avg_cost, type
    """
    portfolio = Portfolio(name=portfolio_name)
    
    for i, data in enumerate(holdings_data):
        try:
            holding = Holding(
                symbol=data.get("symbol", "").strip().upper(),
                qty=float(data.get("qty", 0)),
                avg_cost=float(data.get("avg_cost", 0)),
                position_type=data.get("type", "").strip().lower(),
            )
            errors = holding.validate()
            if errors:
                raise ValueError(f"Invalid holding {i}: {errors[0]}")
            portfolio.add_holding(holding)
        except (KeyError, TypeError, ValueError) as e:
            raise ValueError(f"Holding {i}: {e}")
    
    return portfolio
