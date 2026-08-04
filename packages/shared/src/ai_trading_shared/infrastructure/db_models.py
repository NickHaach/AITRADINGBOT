from __future__ import annotations
"""SQLAlchemy ORM models — system of record schema."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class UserRow(Base):
    __tablename__ = "users"

    id: Mapped[Any] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CompanyRow(Base):
    __tablename__ = "companies"

    id: Mapped[Any] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    ticker: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    exchange: Mapped[str] = mapped_column(String(32))
    sector: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    industry: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class NewsArticleRow(Base):
    __tablename__ = "news_articles"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_news_source_external"),
        Index("ix_news_published_at", "published_at"),
        Index("ix_news_content_hash", "content_hash"),
    )

    id: Mapped[Any] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    external_id: Mapped[str] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(1024))
    body: Mapped[str] = mapped_column(Text)
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    language: Mapped[str] = mapped_column(String(16), default="en")
    content_hash: Mapped[str] = mapped_column(String(64))
    category: Mapped[str] = mapped_column(String(64), default="other")
    countries: Mapped[List[str]] = mapped_column(ARRAY(String), default=list)
    sectors: Mapped[List[str]] = mapped_column(ARRAY(String), default=list)
    companies: Mapped[List[str]] = mapped_column(ARRAY(String), default=list)
    industries: Mapped[List[str]] = mapped_column(ARRAY(String), default=list)
    risk_level: Mapped[str] = mapped_column(String(32), default="low")
    sentiment: Mapped[str] = mapped_column(String(32), default="neutral")
    sentiment_score: Mapped[float] = mapped_column(Numeric(6, 4), default=0)
    confidence: Mapped[float] = mapped_column(Numeric(6, 4), default=0.5)
    urgency: Mapped[str] = mapped_column(String(32), default="medium")
    embedding_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)


class AnnouncementRow(Base):
    __tablename__ = "announcements"

    id: Mapped[Any] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_ticker: Mapped[str] = mapped_column(String(32), index=True)
    filing_type: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(1024))
    body: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(64))
    filed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revenue: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 4), nullable=True)
    eps: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 6), nullable=True)
    margins: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6), nullable=True)
    forward_guidance: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    risks: Mapped[Any] = mapped_column(JSON, default=list)
    opportunities: Mapped[Any] = mapped_column(JSON, default=list)
    impact_score: Mapped[float] = mapped_column(Numeric(6, 4), default=0)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class SignalRow(Base):
    __tablename__ = "signals"

    id: Mapped[Any] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    ticker: Mapped[str] = mapped_column(String(32), index=True)
    asset_class: Mapped[str] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(32))
    expected_return: Mapped[float] = mapped_column(Numeric(12, 6))
    probability_success: Mapped[float] = mapped_column(Numeric(6, 4))
    risk_score: Mapped[float] = mapped_column(Numeric(6, 4))
    confidence: Mapped[float] = mapped_column(Numeric(6, 4))
    time_horizon_days: Mapped[int] = mapped_column()
    rationale: Mapped[Any] = mapped_column(JSON, default=dict)
    model_versions: Mapped[Any] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OrderRow(Base):
    __tablename__ = "orders"

    id: Mapped[Any] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    signal_id: Mapped[Optional[Any]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("signals.id"), nullable=True
    )
    ticker: Mapped[str] = mapped_column(String(32), index=True)
    side: Mapped[str] = mapped_column(String(8))
    order_type: Mapped[str] = mapped_column(String(32))
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    limit_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 6), nullable=True)
    stop_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 6), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    broker: Mapped[str] = mapped_column(String(64), default="paper")
    broker_order_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    filled_quantity: Mapped[Decimal] = mapped_column(Numeric(20, 6), default=0)
    average_fill_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 6), nullable=True)
    reject_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TradeRow(Base):
    __tablename__ = "trades"

    id: Mapped[Any] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    order_id: Mapped[Any] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id"), index=True)
    ticker: Mapped[str] = mapped_column(String(32), index=True)
    side: Mapped[str] = mapped_column(String(8))
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    price: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    fees: Mapped[Decimal] = mapped_column(Numeric(20, 6), default=0)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    pnl: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 6), nullable=True)


class PredictionRow(Base):
    __tablename__ = "predictions"

    id: Mapped[Any] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    ticker: Mapped[str] = mapped_column(String(32), index=True)
    model_name: Mapped[str] = mapped_column(String(128))
    direction_prob_up: Mapped[float] = mapped_column(Numeric(6, 4))
    expected_return: Mapped[float] = mapped_column(Numeric(12, 6))
    volatility_forecast: Mapped[float] = mapped_column(Numeric(12, 6))
    trend_probability: Mapped[float] = mapped_column(Numeric(6, 4))
    mean_reversion_probability: Mapped[float] = mapped_column(Numeric(6, 4))
    breakout_probability: Mapped[float] = mapped_column(Numeric(6, 4))
    risk_score: Mapped[float] = mapped_column(Numeric(6, 4))
    horizon_days: Mapped[int] = mapped_column()
    features: Mapped[Any] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WatchlistRow(Base):
    __tablename__ = "watchlists"

    id: Mapped[Any] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[Any] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    tickers: Mapped[List[str]] = mapped_column(ARRAY(String), default=list)


class StrategyRow(Base):
    __tablename__ = "strategies"

    id: Mapped[Any] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    config: Mapped[Any] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ModelRegistryRow(Base):
    __tablename__ = "models"

    id: Mapped[Any] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(128))
    version: Mapped[str] = mapped_column(String(64))
    model_type: Mapped[str] = mapped_column(String(64))
    metrics: Mapped[Any] = mapped_column(JSON, default=dict)
    artifact_uri: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_production: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("name", "version", name="uq_model_name_version"),)


class BacktestRow(Base):
    __tablename__ = "backtests"

    id: Mapped[Any] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    strategy_id: Mapped[Any] = mapped_column(UUID(as_uuid=True), ForeignKey("strategies.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    metrics: Mapped[Any] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RiskConfigRow(Base):
    __tablename__ = "risk_configs"

    id: Mapped[Any] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    rules: Mapped[Any] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EmbeddingMetaRow(Base):
    __tablename__ = "embeddings"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_type: Mapped[str] = mapped_column(String(64), index=True)
    source_id: Mapped[Any] = mapped_column(UUID(as_uuid=True), index=True)
    vector_dim: Mapped[int] = mapped_column()
    metadata_json: Mapped[Any] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLogRow(Base):
    __tablename__ = "audit_logs"

    id: Mapped[Any] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    actor_id: Mapped[Optional[Any]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(128), index=True)
    resource_type: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    details: Mapped[Any] = mapped_column(JSON, default=dict)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PortfolioSnapshotRow(Base):
    __tablename__ = "portfolio_snapshots"

    id: Mapped[Any] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    cash: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    equity: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    positions: Mapped[Any] = mapped_column(JSON, default=list)
    total_pnl: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    drawdown_pct: Mapped[float] = mapped_column(Numeric(8, 6))
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
