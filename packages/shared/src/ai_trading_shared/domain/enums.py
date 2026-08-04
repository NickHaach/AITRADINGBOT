from __future__ import annotations
"""Domain enums and value objects shared across services."""

from enum import Enum
from typing import Annotated
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class DomainModel(BaseModel):
    """Base for immutable-friendly domain models."""

    model_config = ConfigDict(from_attributes=True, frozen=False, extra="forbid")


class AssetClass(str, Enum):
    STOCK = "stock"
    ETF = "etf"
    OPTION = "option"
    FUTURE = "future"
    FOREX = "forex"
    CRYPTO = "crypto"
    BOND = "bond"
    COMMODITY = "commodity"


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderStatus(str, Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class SignalAction(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    REDUCE = "reduce"
    HEDGE = "hedge"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Urgency(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    BREAKING = "breaking"


class SentimentLabel(str, Enum):
    VERY_BEARISH = "very_bearish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    BULLISH = "bullish"
    VERY_BULLISH = "very_bullish"


class Role(str, Enum):
    VIEWER = "viewer"
    ANALYST = "analyst"
    TRADER = "trader"
    ADMIN = "admin"


class NewsCategory(str, Enum):
    BREAKING = "breaking"
    FINANCIAL = "financial"
    GOVERNMENT = "government"
    CENTRAL_BANK = "central_bank"
    GEOPOLITICAL = "geopolitical"
    ENERGY = "energy"
    TECHNOLOGY = "technology"
    DEFENSE = "defense"
    HEALTHCARE = "healthcare"
    CRYPTO = "crypto"
    OTHER = "other"


Probability = Annotated[float, Field(ge=0.0, le=1.0)]
Pct = Annotated[float, Field(ge=0.0, le=1.0)]


def new_id() -> UUID:
    return uuid4()
