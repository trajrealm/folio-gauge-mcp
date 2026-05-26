"""
src/portfolio/models.py
-----------------------
Dataclasses for portfolio and holding management.

Portfolio: A collection of holdings (long and short positions).
Holding: A single position with symbol, quantity, average cost, and type.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import config


@dataclass
class Holding:
    """
    Represents a single position in a portfolio.
    
    Attributes:
        symbol: Ticker symbol (e.g., "AAPL")
        qty: Quantity of shares (positive for long, negative for short)
        avg_cost: Average cost per share at which position was entered
        position_type: "long" or "short" — determines how P&L is calculated
    """
    symbol: str
    qty: float
    avg_cost: float
    position_type: str
    
    def validate(self) -> list[str]:
        """
        Validate this holding's fields.
        Returns list of error strings; empty means valid.
        """
        errors: list[str] = []
        
        if not self.symbol.strip():
            errors.append("Symbol must not be empty.")
        
        if self.qty <= 0:
            errors.append(f"Quantity must be positive, got {self.qty}.")
        
        if self.avg_cost <= 0:
            errors.append(f"Average cost must be positive, got {self.avg_cost}.")
        
        if self.position_type not in config.VALID_POSITION_TYPES:
            errors.append(
                f"Position type '{self.position_type}' not valid. "
                f"Must be one of {config.VALID_POSITION_TYPES}."
            )
        
        return errors
    
    def current_value(self, current_price: float) -> float:
        """
        Calculate current market value of this holding.
        For long positions: qty * current_price
        For short positions: qty * (2 * avg_cost - current_price)
        """
        if self.position_type == "long":
            return self.qty * current_price
        else:  # short
            # Short P&L: profit if price drops below avg_cost
            return self.qty * (2 * self.avg_cost - current_price)
    
    def unrealized_pnl(self, current_price: float) -> float:
        """
        Calculate unrealized P&L.

        """
        if self.position_type == "long":
            return self.qty * (current_price - self.avg_cost)
        else:  # short
            return self.qty * (self.avg_cost - current_price)
    
    def cost_basis(self) -> float:
        """Return total cost basis (qty * avg_cost)."""
        return self.qty * self.avg_cost


@dataclass
class Portfolio:
    """
    Represents a complete portfolio of positions.
    
    Attributes:
        holdings: List of Holding objects
        name: Optional name for the portfolio (e.g., "My IRA")
    """
    holdings: list[Holding] = field(default_factory=list)
    name: Optional[str] = None
    
    def validate(self) -> list[str]:
        """
        Validate all holdings in the portfolio.
        Returns list of error strings; empty means all valid.
        """
        errors: list[str] = []
        
        for i, holding in enumerate(self.holdings):
            holding_errors = holding.validate()
            if holding_errors:
                errors.extend([f"Holding {i} ({holding.symbol}): {e}" for e in holding_errors])
        
        return errors
    
    def add_holding(self, holding: Holding) -> None:
        """Add a holding to the portfolio."""
        self.holdings.append(holding)
    
    def get_holding(self, symbol: str) -> Optional[Holding]:
        """Get a holding by symbol. Returns None if not found."""
        symbol = symbol.upper()
        for h in self.holdings:
            if h.symbol.upper() == symbol:
                return h
        return None
    
    def symbols(self) -> list[str]:
        """Return list of all symbols in the portfolio."""
        return [h.symbol.upper() for h in self.holdings]
    
    def total_cost_basis(self) -> float:
        """Return total cost basis across all holdings."""
        return sum(h.cost_basis() for h in self.holdings)
    
    def total_current_value(self, prices: dict[str, float]) -> float:
        """
        Calculate total current portfolio value.
        
        Args:
            prices: Dict mapping symbol → current price
        
        Returns:
            Total portfolio value
        """
        total = 0.0
        for holding in self.holdings:
            price = prices.get(holding.symbol.upper())
            if price is not None:
                total += holding.current_value(price)
        return total
    
    def total_unrealized_pnl(self, prices: dict[str, float]) -> float:
        """
        Calculate total unrealized P&L.
        
        Args:
            prices: Dict mapping symbol → current price
        
        Returns:
            Total unrealized profit/loss
        """
        total_pnl = 0.0
        for holding in self.holdings:
            price = prices.get(holding.symbol.upper())
            if price is not None:
                total_pnl += holding.unrealized_pnl(price)
        return total_pnl
    
    def return_pct(self, prices: dict[str, float]) -> float:
        """
        Calculate total return as a percentage.
        
        Args:
            prices: Dict mapping symbol → current price
        
        Returns:
            Return percentage (e.g., 0.05 = 5%)
        """
        cost_basis = self.total_cost_basis()
        if cost_basis == 0:
            return 0.0
        pnl = self.total_unrealized_pnl(prices)
        return pnl / cost_basis
    
    def long_positions(self) -> list[Holding]:
        """Return all long positions."""
        return [h for h in self.holdings if h.position_type == "long"]
    
    def short_positions(self) -> list[Holding]:
        """Return all short positions."""
        return [h for h in self.holdings if h.position_type == "short"]
    
    def position_count(self) -> int:
        """Return total number of positions."""
        return len(self.holdings)
    
    def long_count(self) -> int:
        """Return number of long positions."""
        return len(self.long_positions())
    
    def short_count(self) -> int:
        """Return number of short positions."""
        return len(self.short_positions())
