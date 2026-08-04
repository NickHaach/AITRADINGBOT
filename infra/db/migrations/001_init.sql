-- AI Trading Platform initial schema
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Tables are also managed by SQLAlchemy metadata; this SQL provides
-- a bootstrap-compatible schema for docker-entrypoint init.

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(320) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    role VARCHAR(32) NOT NULL DEFAULT 'viewer',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker VARCHAR(32) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    exchange VARCHAR(32) NOT NULL,
    sector VARCHAR(128),
    industry VARCHAR(128),
    country VARCHAR(8),
    currency VARCHAR(8) NOT NULL DEFAULT 'USD',
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS news_articles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id VARCHAR(255) NOT NULL,
    source VARCHAR(64) NOT NULL,
    title VARCHAR(1024) NOT NULL,
    body TEXT NOT NULL,
    url TEXT,
    published_at TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    language VARCHAR(16) NOT NULL DEFAULT 'en',
    content_hash VARCHAR(64) NOT NULL,
    category VARCHAR(64) NOT NULL DEFAULT 'other',
    countries TEXT[] NOT NULL DEFAULT '{}',
    sectors TEXT[] NOT NULL DEFAULT '{}',
    companies TEXT[] NOT NULL DEFAULT '{}',
    industries TEXT[] NOT NULL DEFAULT '{}',
    risk_level VARCHAR(32) NOT NULL DEFAULT 'low',
    sentiment VARCHAR(32) NOT NULL DEFAULT 'neutral',
    sentiment_score NUMERIC(6,4) NOT NULL DEFAULT 0,
    confidence NUMERIC(6,4) NOT NULL DEFAULT 0.5,
    urgency VARCHAR(32) NOT NULL DEFAULT 'medium',
    embedding_id VARCHAR(128),
    UNIQUE (source, external_id)
);

CREATE INDEX IF NOT EXISTS ix_news_published_at ON news_articles (published_at DESC);
CREATE INDEX IF NOT EXISTS ix_news_content_hash ON news_articles (content_hash);

CREATE TABLE IF NOT EXISTS announcements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_ticker VARCHAR(32) NOT NULL,
    filing_type VARCHAR(64) NOT NULL,
    title VARCHAR(1024) NOT NULL,
    body TEXT NOT NULL,
    source VARCHAR(64) NOT NULL,
    filed_at TIMESTAMPTZ NOT NULL,
    revenue NUMERIC(20,4),
    eps NUMERIC(20,6),
    margins NUMERIC(10,6),
    forward_guidance TEXT,
    risks JSONB NOT NULL DEFAULT '[]',
    opportunities JSONB NOT NULL DEFAULT '[]',
    impact_score NUMERIC(6,4) NOT NULL DEFAULT 0,
    summary TEXT
);

CREATE TABLE IF NOT EXISTS signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker VARCHAR(32) NOT NULL,
    asset_class VARCHAR(32) NOT NULL,
    action VARCHAR(32) NOT NULL,
    expected_return NUMERIC(12,6) NOT NULL,
    probability_success NUMERIC(6,4) NOT NULL,
    risk_score NUMERIC(6,4) NOT NULL,
    confidence NUMERIC(6,4) NOT NULL,
    time_horizon_days INT NOT NULL,
    rationale JSONB NOT NULL DEFAULT '{}',
    model_versions JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id UUID REFERENCES signals(id),
    ticker VARCHAR(32) NOT NULL,
    side VARCHAR(8) NOT NULL,
    order_type VARCHAR(32) NOT NULL,
    quantity NUMERIC(20,6) NOT NULL,
    limit_price NUMERIC(20,6),
    stop_price NUMERIC(20,6),
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    broker VARCHAR(64) NOT NULL DEFAULT 'paper',
    broker_order_id VARCHAR(128),
    filled_quantity NUMERIC(20,6) NOT NULL DEFAULT 0,
    average_fill_price NUMERIC(20,6),
    reject_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES orders(id),
    ticker VARCHAR(32) NOT NULL,
    side VARCHAR(8) NOT NULL,
    quantity NUMERIC(20,6) NOT NULL,
    price NUMERIC(20,6) NOT NULL,
    fees NUMERIC(20,6) NOT NULL DEFAULT 0,
    executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    pnl NUMERIC(20,6)
);

CREATE TABLE IF NOT EXISTS predictions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker VARCHAR(32) NOT NULL,
    model_name VARCHAR(128) NOT NULL,
    direction_prob_up NUMERIC(6,4) NOT NULL,
    expected_return NUMERIC(12,6) NOT NULL,
    volatility_forecast NUMERIC(12,6) NOT NULL,
    trend_probability NUMERIC(6,4) NOT NULL,
    mean_reversion_probability NUMERIC(6,4) NOT NULL,
    breakout_probability NUMERIC(6,4) NOT NULL,
    risk_score NUMERIC(6,4) NOT NULL,
    horizon_days INT NOT NULL,
    features JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS watchlists (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    name VARCHAR(128) NOT NULL,
    tickers TEXT[] NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS strategies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(128) UNIQUE NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    config JSONB NOT NULL DEFAULT '{}',
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS models (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(128) NOT NULL,
    version VARCHAR(64) NOT NULL,
    model_type VARCHAR(64) NOT NULL,
    metrics JSONB NOT NULL DEFAULT '{}',
    artifact_uri TEXT,
    is_production BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (name, version)
);

CREATE TABLE IF NOT EXISTS backtests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id UUID NOT NULL REFERENCES strategies(id),
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ NOT NULL,
    metrics JSONB NOT NULL DEFAULT '{}',
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS risk_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(128) UNIQUE NOT NULL,
    rules JSONB NOT NULL DEFAULT '{}',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS embeddings (
    id VARCHAR(128) PRIMARY KEY,
    source_type VARCHAR(64) NOT NULL,
    source_id UUID NOT NULL,
    vector_dim INT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_id UUID,
    action VARCHAR(128) NOT NULL,
    resource_type VARCHAR(64) NOT NULL,
    resource_id VARCHAR(128),
    details JSONB NOT NULL DEFAULT '{}',
    ip_address VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cash NUMERIC(20,6) NOT NULL,
    equity NUMERIC(20,6) NOT NULL,
    positions JSONB NOT NULL DEFAULT '[]',
    total_pnl NUMERIC(20,6) NOT NULL,
    drawdown_pct NUMERIC(8,6) NOT NULL,
    as_of TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
