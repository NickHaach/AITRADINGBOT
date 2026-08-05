-- Incremental tables for market persistence, outcomes, and knowledge graph
CREATE TABLE IF NOT EXISTS market_bars (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker VARCHAR(32) NOT NULL,
    asset_class VARCHAR(32) NOT NULL DEFAULT 'stock',
    timestamp TIMESTAMPTZ NOT NULL,
    open NUMERIC(20,6) NOT NULL,
    high NUMERIC(20,6) NOT NULL,
    low NUMERIC(20,6) NOT NULL,
    close NUMERIC(20,6) NOT NULL,
    volume NUMERIC(20,4) NOT NULL DEFAULT 0,
    vwap NUMERIC(20,6),
    UNIQUE (ticker, timestamp)
);
CREATE INDEX IF NOT EXISTS ix_market_bars_ticker_ts ON market_bars (ticker, timestamp);

CREATE TABLE IF NOT EXISTS market_features (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker VARCHAR(32) UNIQUE NOT NULL,
    as_of TIMESTAMPTZ NOT NULL,
    last_price NUMERIC(20,6) NOT NULL,
    returns_1d NUMERIC(12,6) NOT NULL,
    returns_5d NUMERIC(12,6) NOT NULL,
    returns_20d NUMERIC(12,6) NOT NULL,
    volatility_10d NUMERIC(12,6) NOT NULL,
    volatility_20d NUMERIC(12,6) NOT NULL,
    volume_zscore_20d NUMERIC(12,6) NOT NULL,
    liquidity_score NUMERIC(8,6) NOT NULL,
    trend_strength NUMERIC(8,6) NOT NULL,
    high_20d NUMERIC(20,6) NOT NULL,
    low_20d NUMERIC(20,6) NOT NULL,
    distance_from_high_20d NUMERIC(12,6) NOT NULL,
    bars_used INT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS trade_outcomes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id UUID NOT NULL,
    trade_id UUID,
    ticker VARCHAR(32) NOT NULL,
    action VARCHAR(32) NOT NULL,
    predicted_direction VARCHAR(8) NOT NULL,
    predicted_return NUMERIC(12,6) NOT NULL,
    probability_success NUMERIC(6,4) NOT NULL,
    confidence NUMERIC(6,4) NOT NULL,
    model_versions JSONB NOT NULL DEFAULT '[]',
    actual_return NUMERIC(12,6) NOT NULL,
    holding_days INT NOT NULL,
    correct_direction BOOLEAN NOT NULL DEFAULT FALSE,
    pnl NUMERIC(20,6) NOT NULL,
    closed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS graph_nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_type VARCHAR(64) NOT NULL,
    external_key VARCHAR(255) NOT NULL,
    label VARCHAR(512) NOT NULL,
    properties JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (node_type, external_key)
);

CREATE TABLE IF NOT EXISTS graph_edges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_node_id UUID NOT NULL REFERENCES graph_nodes(id),
    to_node_id UUID NOT NULL REFERENCES graph_nodes(id),
    relationship VARCHAR(64) NOT NULL,
    weight NUMERIC(8,4) NOT NULL DEFAULT 1.0,
    properties JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_graph_edges_rel ON graph_edges (relationship);
