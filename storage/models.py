import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Source(Base):
    __tablename__ = "sources"

    source_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # rss/api/scraper
    url: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str | None] = mapped_column(String(10))
    categories: Mapped[list | None] = mapped_column(ARRAY(String(100)), default=list)
    fetch_interval_minutes: Mapped[int] = mapped_column(Integer, default=30)
    parser_config: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    scraper_config: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=5)
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    health_status: Mapped[str] = mapped_column(String(20), default="healthy")
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    source_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_name: Mapped[str | None] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(Text, unique=True, nullable=False)

    # Content
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body_text: Mapped[str | None] = mapped_column(Text)
    body_markdown: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(10))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Summaries
    summary_en: Mapped[str | None] = mapped_column(Text)
    summary_zh: Mapped[str | None] = mapped_column(Text)

    # Classification (arrays for flexible multi-label)
    transport_modes: Mapped[list | None] = mapped_column(
        ARRAY(String(50)), default=list
    )
    primary_topic: Mapped[str | None] = mapped_column(String(100))
    secondary_topics: Mapped[list | None] = mapped_column(
        ARRAY(String(100)), default=list
    )
    content_type: Mapped[str | None] = mapped_column(String(50))
    regions: Mapped[list | None] = mapped_column(ARRAY(String(50)), default=list)

    # Entities (complex nested structure → JSONB)
    entities: Mapped[dict | None] = mapped_column(JSONB, default=dict)

    # Analysis
    sentiment: Mapped[str | None] = mapped_column(String(20))
    market_impact: Mapped[str | None] = mapped_column(String(20))
    urgency: Mapped[str | None] = mapped_column(String(20))
    key_metrics: Mapped[list | None] = mapped_column(JSONB, default=list)

    # Deduplication fingerprints
    title_simhash: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    content_minhash: Mapped[list | None] = mapped_column(
        ARRAY(BigInteger), nullable=True
    )

    # Embedding (1024-dim for bge-m3)
    embedding = mapped_column(Vector(1024), nullable=True)

    # Metadata
    raw_metadata: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    processing_status: Mapped[str] = mapped_column(String(20), default="pending")
    llm_processed: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("idx_articles_published_at", "published_at", postgresql_using="btree"),
        Index(
            "idx_articles_transport",
            "transport_modes",
            postgresql_using="gin",
        ),
        Index("idx_articles_topic", "primary_topic"),
        Index("idx_articles_regions", "regions", postgresql_using="gin"),
        Index("idx_articles_sentiment", "sentiment"),
        Index("idx_articles_urgency", "urgency"),
        Index("idx_articles_status", "processing_status"),
        Index("idx_articles_title_simhash", "title_simhash"),
        Index(
            "idx_articles_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class FetchLog(Base):
    __tablename__ = "fetch_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str | None] = mapped_column(String(20))  # success/partial/failed
    articles_found: Mapped[int] = mapped_column(Integer, default=0)
    articles_new: Mapped[int] = mapped_column(Integer, default=0)
    articles_dedup: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[int | None] = mapped_column(Integer)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    # Filter criteria (all optional, acts as AND when multiple set)
    source_ids: Mapped[list | None] = mapped_column(ARRAY(String(100)))
    transport_modes: Mapped[list | None] = mapped_column(ARRAY(String(50)))
    topics: Mapped[list | None] = mapped_column(ARRAY(String(100)))
    regions: Mapped[list | None] = mapped_column(ARRAY(String(50)))
    urgency_min: Mapped[str | None] = mapped_column(String(20))  # minimum urgency level
    languages: Mapped[list | None] = mapped_column(ARRAY(String(10)))

    # Notification channel
    channel: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # websocket / webhook / email
    channel_config: Mapped[dict | None] = mapped_column(
        JSONB, default=dict
    )  # channel-specific config

    # Frequency
    frequency: Mapped[str] = mapped_column(
        String(20), default="realtime"
    )  # realtime / daily / weekly

    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WebhookDeliveryLog(Base):
    __tablename__ = "webhook_delivery_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subscription_id: Mapped[str] = mapped_column(
        String(36), nullable=False, index=True
    )
    article_id: Mapped[str] = mapped_column(String(36), nullable=False)

    url: Mapped[str] = mapped_column(Text, nullable=False)
    status_code: Mapped[int | None] = mapped_column(Integer)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    error_message: Mapped[str | None] = mapped_column(Text)

    delivered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class APIKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="reader")  # admin / reader
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
