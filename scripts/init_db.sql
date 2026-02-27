-- Initialize pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Sources configuration table
CREATE TABLE IF NOT EXISTS sources (
    source_id       VARCHAR(100) PRIMARY KEY,
    name            VARCHAR(200) NOT NULL,
    type            VARCHAR(20) NOT NULL,
    url             TEXT NOT NULL,
    language        VARCHAR(10),
    categories      VARCHAR(100)[] DEFAULT '{}',
    fetch_interval_minutes INTEGER DEFAULT 30,
    parser_config   JSONB DEFAULT '{}',
    scraper_config  JSONB DEFAULT '{}',
    enabled         BOOLEAN DEFAULT TRUE,
    priority        INTEGER DEFAULT 5,
    last_fetched_at TIMESTAMPTZ,
    health_status   VARCHAR(20) DEFAULT 'healthy',
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Main articles table
CREATE TABLE IF NOT EXISTS articles (
    id              VARCHAR(36) PRIMARY KEY,
    source_id       VARCHAR(100) NOT NULL,
    source_name     VARCHAR(200),
    url             TEXT UNIQUE NOT NULL,

    title           TEXT NOT NULL,
    body_text       TEXT,
    body_markdown   TEXT,
    language        VARCHAR(10),
    published_at    TIMESTAMPTZ,
    fetched_at      TIMESTAMPTZ DEFAULT NOW(),

    summary_en      TEXT,
    summary_zh      TEXT,

    transport_modes VARCHAR(50)[] DEFAULT '{}',
    primary_topic   VARCHAR(100),
    secondary_topics VARCHAR(100)[] DEFAULT '{}',
    content_type    VARCHAR(50),
    regions         VARCHAR(50)[] DEFAULT '{}',

    entities        JSONB DEFAULT '{}',

    sentiment       VARCHAR(20),
    market_impact   VARCHAR(20),
    urgency         VARCHAR(20),
    key_metrics     JSONB DEFAULT '[]',

    embedding       vector(1024),

    raw_metadata    JSONB DEFAULT '{}',
    processing_status VARCHAR(20) DEFAULT 'pending',
    llm_processed   BOOLEAN DEFAULT FALSE,

    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for articles
CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source_id);
CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_transport ON articles USING GIN(transport_modes);
CREATE INDEX IF NOT EXISTS idx_articles_topic ON articles(primary_topic);
CREATE INDEX IF NOT EXISTS idx_articles_regions ON articles USING GIN(regions);
CREATE INDEX IF NOT EXISTS idx_articles_sentiment ON articles(sentiment);
CREATE INDEX IF NOT EXISTS idx_articles_urgency ON articles(urgency);
CREATE INDEX IF NOT EXISTS idx_articles_status ON articles(processing_status);

-- Full-text search index
CREATE INDEX IF NOT EXISTS idx_articles_fts ON articles USING GIN(
    to_tsvector('english', coalesce(title, '') || ' ' || coalesce(body_text, ''))
);

-- Fetch logs table
CREATE TABLE IF NOT EXISTS fetch_logs (
    id              BIGSERIAL PRIMARY KEY,
    source_id       VARCHAR(100) REFERENCES sources(source_id),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    status          VARCHAR(20),
    articles_found  INTEGER DEFAULT 0,
    articles_new    INTEGER DEFAULT 0,
    articles_dedup  INTEGER DEFAULT 0,
    error_message   TEXT,
    duration_ms     INTEGER
);

CREATE INDEX IF NOT EXISTS idx_fetch_logs_source ON fetch_logs(source_id);
CREATE INDEX IF NOT EXISTS idx_fetch_logs_started ON fetch_logs(started_at DESC);
