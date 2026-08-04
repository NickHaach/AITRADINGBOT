"""Backtesting Engine package."""

from backtesting.application.engine import BacktestEngine, MomentumNewsStrategy, bars_from_closes
from backtesting.domain.models import BacktestResult

__all__ = ["BacktestEngine", "MomentumNewsStrategy", "BacktestResult", "bars_from_closes"]
__version__ = "0.1.0"
