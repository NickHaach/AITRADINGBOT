from __future__ import annotations
"""Core domain entities shared across services."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from ai_trading_shared.domain.enums import (
    AssetClass,
    DomainModel,
    NewsCategory,
    OrderStatus,
    OrderType,
    Pct,
    Probability,
    RiskLevel,
    Role,
    SentimentLabel,
    Side,
    SignalAction,
    Urgency,
    new_id,
)


class Company(DomainModel):
    id: UUID = Field(default_factory=new_id)
    ticker: str
    name: str
    exchange: str
    sector: str | None = None
    industry: str | None = None
    country: str | None = None
    currency: str = "USD"
    is_active: bool = True


class User(DomainModel):
    id: UUID = Field(default_factory=new_id)
    email: str
    hashed_password: str
    full_name: str
    role: Role = Role.VIEWER
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


class NewsArticle(DomainModel):
    id: UUID = Field(default_factory=new_id)
    external_id: str
    source: str
    title: str
    body: str
    url: str | None = None
    published_at: datetime
    ingested_at: datetime = Field(default_factory=datetime.utcnow)
    language: str = "en"
    content_hash: str
    category: NewsCategory = NewsCategory.OTHER
    countries: list[str] = Field(default_factory=list)
    sectors: list[str] = Field(default_factory=list)
    companies: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.LOW
    sentiment: SentimentLabel = SentimentLabel.NEUTRAL
    sentiment_score: float = Field(default=0.0, ge=-1.0, le=1.0)
    confidence: Probability = 0.5
    urgency: Urgency = Urgency.MEDIUM
    embedding_id: str | None = None


class Announcement(DomainModel):
    id: UUID = Field(default_factory=new_id)
    company_ticker: str
    filing_type: str
    title: str
    body: str
    source: str
    filed_at: datetime
    revenue: Decimal | None = None
    eps: Decimal | None = None
    margins: Decimal | None = None
    forward_guidance: str | None = None
    risks: list[str] = Field(default_factory=list)
    opportunities: list[str] = Field(default_factory=list)
    impact_score: float = Field(default=0.0, ge=-1.0, le=1.0)
    summary: str | None = None


class Signal(DomainModel):
    id: UUID = Field(default_factory=new_id)
    ticker: str
    asset_class: AssetClass
    action: SignalAction
    expected_return: float
    probability_success: Probability
    risk_score: Probability
    confidence: Probability
    time_horizon_days: int = Field(ge=1)
    rationale: dict
    model_versions: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Order(DomainModel):
    id: UUID = Field(default_factory=new_id)
    signal_id: UUID | None = None
    ticker: str
    side: Side
    order_type: OrderType
    quantity: Decimal
    limit_price: Decimal | None = None
    stop_price: Decimal | None = None
    status: OrderStatus = OrderStatus.PENDING
    broker: str = "paper"
    broker_order_id: str | None = None
    filled_quantity: Decimal = Decimal("0")
    average_fill_price: Decimal | None = None
    reject_reason: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Trade(DomainModel):
    id: UUID = Field(default_factory=new_id)
    order_id: UUID
    ticker: str
    side: Side
    quantity: Decimal
    price: Decimal
    fees: Decimal = Decimal("0")
    executed_at: datetime = Field(default_factory=datetime.utcnow)
    pnl: Decimal | None = None


class Position(DomainModel):
    ticker: str
    quantity: Decimal
    avg_cost: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal
    sector: str | None = None
    country: str | None = None


class PortfolioSnapshot(DomainModel):
    id: UUID = Field(default_factory=new_id)
    cash: Decimal
    equity: Decimal
    positions: list[Position]
    total_pnl: Decimal
    drawdown_pct: Pct
    as_of: datetime = Field(default_factory=datetime.utcnow)


class Prediction(DomainModel):
    id: UUID = Field(default_factory=new_id)
    ticker: str
    model_name: str
    direction_prob_up: Probability
    expected_return: float
    volatility_forecast: float
    trend_probability: Probability
    mean_reversion_probability: Probability
    breakout_probability: Probability
    risk_score: Probability
    horizon_days: int
    features: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RiskDecision(DomainModel):
    approved: bool
    reasons: list[str] = Field(default_factory=list)
    sized_quantity: Decimal | None = None
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    checks: dict = Field(default_factory=dict)


class LLMReasoningResult(DomainModel):
    what_happened: str
    why_important: str
    beneficiaries: list[str]
    losers: list[str]
    expected_reaction: str
    time_horizon: str
    confidence: Probability
    catalysts: list[str]
    risks: list[str]
    raw: dict = Field(default_factory=dict)


class Watchlist(DomainModel):
    id: UUID = Field(default_factory=new_id)
    user_id: UUID
    name: str
    tickers: list[str] = Field(default_factory=list)


class AuditLog(DomainModel):
    id: UUID = Field(default_factory=new_id)
    actor_id: UUID | None = None
    action: str
    resource_type: str
    resource_id: str | None = None
    details: dict = Field(default_factory=dict)
    ip_address: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class EmbeddingRecord(DomainModel):
    id: str
    source_type: str
    source_id: UUID
    vector_dim: int
    metadata: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
