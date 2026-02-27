import io
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select, text
from starlette.responses import StreamingResponse

from analytics.entity_graph import EntityAnalyzer
from analytics.export import export_articles_csv, export_articles_json
from analytics.sentiment import SentimentAnalyzer
from analytics.trending import TrendingAnalyzer
from config.llm_settings import llm_settings
from monitoring.health import SourceHealthMonitor
from storage.database import get_session
from storage.models import Article, FetchLog, Source, SourceCandidate, Subscription

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check():
    """System health check."""
    try:
        async with get_session() as session:
            result = await session.execute(select(func.count(Article.id)))
            article_count = result.scalar_one()

            result = await session.execute(select(func.count(Source.source_id)))
            source_count = result.scalar_one()

            result = await session.execute(
                select(func.max(Article.fetched_at))
            )
            last_fetch = result.scalar_one()

        return {
            "status": "healthy",
            "article_count": article_count,
            "source_count": source_count,
            "last_fetch_at": last_fetch.isoformat() if last_fetch else None,
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}


@router.get("/health/sources")
async def source_health():
    """Check health of all configured data sources."""
    monitor = SourceHealthMonitor()
    reports = await monitor.check_all()

    return [
        {
            "source_id": r.source_id,
            "name": r.name,
            "enabled": r.enabled,
            "health_status": r.health_status,
            "last_fetched_at": r.last_fetched_at.isoformat()
            if r.last_fetched_at
            else None,
            "fetch_count_24h": r.fetch_count_24h,
            "success_rate_24h": r.success_rate_24h,
            "total_articles_24h": r.total_articles_24h,
            "avg_duration_ms": r.avg_duration_ms,
            "alerts": r.alerts,
        }
        for r in reports
    ]


@router.get("/sources")
async def list_sources():
    """List all configured data sources."""
    async with get_session() as session:
        result = await session.execute(
            select(Source).order_by(Source.priority, Source.name)
        )
        sources = result.scalars().all()

    return [
        {
            "source_id": s.source_id,
            "name": s.name,
            "type": s.type,
            "url": s.url,
            "language": s.language,
            "categories": s.categories,
            "enabled": s.enabled,
            "priority": s.priority,
            "last_fetched_at": s.last_fetched_at.isoformat()
            if s.last_fetched_at
            else None,
            "health_status": s.health_status,
        }
        for s in sources
    ]


@router.get("/articles")
async def list_articles(
    source_id: str | None = Query(None, description="Filter by source ID"),
    transport_mode: str | None = Query(
        None, description="Filter by transport mode (ocean, air, rail, road)"
    ),
    topic: str | None = Query(None, description="Filter by primary topic"),
    language: str | None = Query(None, description="Filter by language (en, zh)"),
    sentiment: str | None = Query(
        None, description="Filter by sentiment (positive, negative, neutral)"
    ),
    urgency: str | None = Query(
        None, description="Filter by urgency (high, medium, low)"
    ),
    from_date: datetime | None = Query(None, description="Articles published after"),
    to_date: datetime | None = Query(None, description="Articles published before"),
    search: str | None = Query(None, description="Full-text search query"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Articles per page"),
):
    """List articles with optional filters and pagination."""
    async with get_session() as session:
        query = select(Article).order_by(Article.published_at.desc().nullslast())

        # Apply filters
        if source_id:
            query = query.where(Article.source_id == source_id)
        if transport_mode:
            query = query.where(Article.transport_modes.contains([transport_mode]))
        if topic:
            query = query.where(Article.primary_topic == topic)
        if language:
            query = query.where(Article.language == language)
        if sentiment:
            query = query.where(Article.sentiment == sentiment)
        if urgency:
            query = query.where(Article.urgency == urgency)
        if from_date:
            query = query.where(Article.published_at >= from_date)
        if to_date:
            query = query.where(Article.published_at <= to_date)
        if search:
            query = query.where(
                func.to_tsvector("english", Article.title + " " + Article.body_text)
                .match(search)
            )

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = (await session.execute(count_query)).scalar_one()

        # Paginate
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        result = await session.execute(query)
        articles = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size if total > 0 else 0,
        "articles": [
            {
                "id": a.id,
                "source_id": a.source_id,
                "source_name": a.source_name,
                "url": a.url,
                "title": a.title,
                "summary_en": a.summary_en,
                "summary_zh": a.summary_zh,
                "language": a.language,
                "published_at": a.published_at.isoformat()
                if a.published_at
                else None,
                "transport_modes": a.transport_modes,
                "primary_topic": a.primary_topic,
                "content_type": a.content_type,
                "regions": a.regions,
                "sentiment": a.sentiment,
                "urgency": a.urgency,
                "processing_status": a.processing_status,
            }
            for a in articles
        ],
    }


@router.get("/articles/{article_id}")
async def get_article(article_id: str):
    """Get a single article by ID with full details."""
    async with get_session() as session:
        result = await session.execute(
            select(Article).where(Article.id == article_id)
        )
        article = result.scalar_one_or_none()

    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    return {
        "id": article.id,
        "source_id": article.source_id,
        "source_name": article.source_name,
        "url": article.url,
        "title": article.title,
        "body_text": article.body_text,
        "body_markdown": article.body_markdown,
        "language": article.language,
        "published_at": article.published_at.isoformat()
        if article.published_at
        else None,
        "fetched_at": article.fetched_at.isoformat() if article.fetched_at else None,
        "summary_en": article.summary_en,
        "summary_zh": article.summary_zh,
        "transport_modes": article.transport_modes,
        "primary_topic": article.primary_topic,
        "secondary_topics": article.secondary_topics,
        "content_type": article.content_type,
        "regions": article.regions,
        "entities": article.entities,
        "sentiment": article.sentiment,
        "market_impact": article.market_impact,
        "urgency": article.urgency,
        "key_metrics": article.key_metrics,
        "processing_status": article.processing_status,
        "llm_processed": article.llm_processed,
        "raw_metadata": article.raw_metadata,
    }


@router.get("/articles/search/semantic")
async def semantic_search(
    q: str = Query(..., description="Natural language search query"),
    transport_mode: str | None = Query(None, description="Filter by transport mode"),
    topic: str | None = Query(None, description="Filter by primary topic"),
    language: str | None = Query(None, description="Filter by language"),
    limit: int = Query(10, ge=1, le=50, description="Max results"),
):
    """Semantic search using vector similarity.

    Converts the query to an embedding and finds the most similar articles
    using pgvector cosine distance (via HNSW index).
    """
    if not llm_settings.llm_api_key:
        raise HTTPException(status_code=503, detail="LLM_API_KEY not configured")

    from processing.llm_pipeline import ArticleProcessor

    processor = ArticleProcessor()
    try:
        query_embedding = await processor.generate_embedding(q)
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
        raise HTTPException(status_code=502, detail="Failed to generate query embedding")
    finally:
        await processor.close()

    async with get_session() as session:
        # Build base query with cosine distance
        cosine_dist = Article.embedding.cosine_distance(query_embedding)
        query = (
            select(
                Article,
                cosine_dist.label("distance"),
            )
            .where(Article.embedding.isnot(None))
            .order_by(cosine_dist)
        )

        # Apply optional filters
        if transport_mode:
            query = query.where(Article.transport_modes.contains([transport_mode]))
        if topic:
            query = query.where(Article.primary_topic == topic)
        if language:
            query = query.where(Article.language == language)

        query = query.limit(limit)
        result = await session.execute(query)
        rows = result.all()

    return {
        "query": q,
        "results": [
            {
                "id": row.Article.id,
                "source_id": row.Article.source_id,
                "source_name": row.Article.source_name,
                "url": row.Article.url,
                "title": row.Article.title,
                "summary_en": row.Article.summary_en,
                "summary_zh": row.Article.summary_zh,
                "language": row.Article.language,
                "published_at": row.Article.published_at.isoformat()
                if row.Article.published_at
                else None,
                "transport_modes": row.Article.transport_modes,
                "primary_topic": row.Article.primary_topic,
                "sentiment": row.Article.sentiment,
                "similarity": round(1.0 - row.distance, 4),
            }
            for row in rows
        ],
    }


@router.get("/articles/{article_id}/related")
async def related_articles(
    article_id: str,
    limit: int = Query(5, ge=1, le=20, description="Max related articles"),
    exclude_same_source: bool = Query(
        False, description="Exclude articles from the same source"
    ),
):
    """Find articles related to the given article using vector similarity."""
    async with get_session() as session:
        # Fetch the target article's embedding
        result = await session.execute(
            select(Article).where(Article.id == article_id)
        )
        article = result.scalar_one_or_none()

    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    if article.embedding is None:
        raise HTTPException(
            status_code=422,
            detail="Article has no embedding (not yet processed by LLM)",
        )

    target_embedding = list(article.embedding)

    async with get_session() as session:
        cosine_dist = Article.embedding.cosine_distance(target_embedding)
        query = (
            select(
                Article,
                cosine_dist.label("distance"),
            )
            .where(Article.embedding.isnot(None))
            .where(Article.id != article_id)
            .order_by(cosine_dist)
        )

        if exclude_same_source:
            query = query.where(Article.source_id != article.source_id)

        query = query.limit(limit)
        result = await session.execute(query)
        rows = result.all()

    return {
        "article_id": article_id,
        "related": [
            {
                "id": row.Article.id,
                "source_id": row.Article.source_id,
                "source_name": row.Article.source_name,
                "url": row.Article.url,
                "title": row.Article.title,
                "summary_en": row.Article.summary_en,
                "summary_zh": row.Article.summary_zh,
                "language": row.Article.language,
                "published_at": row.Article.published_at.isoformat()
                if row.Article.published_at
                else None,
                "transport_modes": row.Article.transport_modes,
                "primary_topic": row.Article.primary_topic,
                "sentiment": row.Article.sentiment,
                "similarity": round(1.0 - row.distance, 4),
            }
            for row in rows
        ],
    }


# ---------------------------------------------------------------------------
# Subscriptions CRUD
# ---------------------------------------------------------------------------


@router.post("/subscriptions", status_code=201)
async def create_subscription(payload: dict):
    """Create a new notification subscription."""
    name = payload.get("name")
    channel = payload.get("channel")
    if not name or not channel:
        raise HTTPException(
            status_code=422, detail="'name' and 'channel' are required"
        )
    if channel not in ("websocket", "webhook", "email"):
        raise HTTPException(
            status_code=422,
            detail="'channel' must be one of: websocket, webhook, email",
        )

    frequency = payload.get("frequency", "realtime")
    if frequency not in ("realtime", "daily", "weekly"):
        raise HTTPException(
            status_code=422,
            detail="'frequency' must be one of: realtime, daily, weekly",
        )

    sub = Subscription(
        name=name,
        source_ids=payload.get("source_ids"),
        transport_modes=payload.get("transport_modes"),
        topics=payload.get("topics"),
        regions=payload.get("regions"),
        urgency_min=payload.get("urgency_min"),
        languages=payload.get("languages"),
        channel=channel,
        channel_config=payload.get("channel_config"),
        frequency=frequency,
        enabled=payload.get("enabled", True),
    )

    async with get_session() as session:
        session.add(sub)
        await session.flush()
        sub_id = sub.id

    return {
        "id": sub_id,
        "name": name,
        "channel": channel,
        "frequency": frequency,
        "enabled": sub.enabled,
    }


@router.get("/subscriptions")
async def list_subscriptions():
    """List all notification subscriptions."""
    async with get_session() as session:
        result = await session.execute(
            select(Subscription).order_by(Subscription.created_at.desc())
        )
        subs = result.scalars().all()

    return [
        {
            "id": s.id,
            "name": s.name,
            "source_ids": s.source_ids,
            "transport_modes": s.transport_modes,
            "topics": s.topics,
            "regions": s.regions,
            "urgency_min": s.urgency_min,
            "languages": s.languages,
            "channel": s.channel,
            "channel_config": s.channel_config,
            "frequency": s.frequency,
            "enabled": s.enabled,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        }
        for s in subs
    ]


@router.get("/subscriptions/{sub_id}")
async def get_subscription(sub_id: str):
    """Get a single subscription by ID."""
    async with get_session() as session:
        result = await session.execute(
            select(Subscription).where(Subscription.id == sub_id)
        )
        sub = result.scalar_one_or_none()

    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    return {
        "id": sub.id,
        "name": sub.name,
        "source_ids": sub.source_ids,
        "transport_modes": sub.transport_modes,
        "topics": sub.topics,
        "regions": sub.regions,
        "urgency_min": sub.urgency_min,
        "languages": sub.languages,
        "channel": sub.channel,
        "channel_config": sub.channel_config,
        "frequency": sub.frequency,
        "enabled": sub.enabled,
        "created_at": sub.created_at.isoformat() if sub.created_at else None,
        "updated_at": sub.updated_at.isoformat() if sub.updated_at else None,
    }


@router.put("/subscriptions/{sub_id}")
async def update_subscription(sub_id: str, payload: dict):
    """Update an existing subscription."""
    async with get_session() as session:
        result = await session.execute(
            select(Subscription).where(Subscription.id == sub_id)
        )
        sub = result.scalar_one_or_none()

        if not sub:
            raise HTTPException(status_code=404, detail="Subscription not found")

        # Validate channel if provided
        if "channel" in payload:
            if payload["channel"] not in ("websocket", "webhook", "email"):
                raise HTTPException(
                    status_code=422,
                    detail="'channel' must be one of: websocket, webhook, email",
                )

        # Validate frequency if provided
        if "frequency" in payload:
            if payload["frequency"] not in ("realtime", "daily", "weekly"):
                raise HTTPException(
                    status_code=422,
                    detail="'frequency' must be one of: realtime, daily, weekly",
                )

        updatable_fields = [
            "name",
            "source_ids",
            "transport_modes",
            "topics",
            "regions",
            "urgency_min",
            "languages",
            "channel",
            "channel_config",
            "frequency",
            "enabled",
        ]
        for field in updatable_fields:
            if field in payload:
                setattr(sub, field, payload[field])

        await session.flush()

        return {
            "id": sub.id,
            "name": sub.name,
            "source_ids": sub.source_ids,
            "transport_modes": sub.transport_modes,
            "topics": sub.topics,
            "regions": sub.regions,
            "urgency_min": sub.urgency_min,
            "languages": sub.languages,
            "channel": sub.channel,
            "channel_config": sub.channel_config,
            "frequency": sub.frequency,
            "enabled": sub.enabled,
            "created_at": sub.created_at.isoformat() if sub.created_at else None,
            "updated_at": sub.updated_at.isoformat() if sub.updated_at else None,
        }


@router.delete("/subscriptions/{sub_id}", status_code=204)
async def delete_subscription(sub_id: str):
    """Delete a subscription."""
    async with get_session() as session:
        result = await session.execute(
            select(Subscription).where(Subscription.id == sub_id)
        )
        sub = result.scalar_one_or_none()

        if not sub:
            raise HTTPException(status_code=404, detail="Subscription not found")

        await session.delete(sub)

    return None


# ---------------------------------------------------------------------------
# Analytics & Intelligence
# ---------------------------------------------------------------------------


@router.get("/analytics/trending")
async def trending_topics(
    time_window: str = Query("24h", description="Time window (24h, 7d, 30d)"),
    transport_mode: str | None = Query(
        None, description="Filter by transport mode"
    ),
    region: str | None = Query(None, description="Filter by region"),
    limit: int = Query(10, ge=1, le=50, description="Max topics to return"),
):
    """Get trending topics ranked by article frequency."""
    analyzer = TrendingAnalyzer()
    return await analyzer.get_trending(
        time_window=time_window,
        transport_mode=transport_mode,
        region=region,
        limit=limit,
    )


@router.get("/analytics/sentiment-trend")
async def sentiment_trend(
    granularity: str = Query(
        "day", description="Time granularity (hour, day, week)"
    ),
    transport_mode: str | None = Query(
        None, description="Filter by transport mode"
    ),
    topic: str | None = Query(None, description="Filter by primary topic"),
    region: str | None = Query(None, description="Filter by region"),
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
):
    """Get sentiment distribution over time."""
    analyzer = SentimentAnalyzer()
    return await analyzer.get_sentiment_trend(
        granularity=granularity,
        transport_mode=transport_mode,
        topic=topic,
        region=region,
        days=days,
    )


@router.get("/analytics/entities")
async def top_entities(
    entity_type: str | None = Query(
        None,
        description="Entity type (companies, ports, people, organizations)",
    ),
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    limit: int = Query(20, ge=1, le=100, description="Max entities to return"),
):
    """Get most frequently mentioned entities."""
    analyzer = EntityAnalyzer()
    return await analyzer.get_top_entities(
        entity_type=entity_type,
        days=days,
        limit=limit,
    )


@router.get("/analytics/entities/graph")
async def entity_graph(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    min_cooccurrence: int = Query(
        2, ge=1, description="Minimum co-occurrence count"
    ),
    limit: int = Query(50, ge=1, le=200, description="Max edges to return"),
):
    """Get entity co-occurrence graph."""
    analyzer = EntityAnalyzer()
    return await analyzer.get_entity_cooccurrence(
        days=days,
        min_cooccurrence=min_cooccurrence,
        limit=limit,
    )


@router.get("/export/articles")
async def export_articles(
    format: str = Query("json", description="Export format (csv, json)"),
    source_id: str | None = Query(None, description="Filter by source ID"),
    transport_mode: str | None = Query(
        None, description="Filter by transport mode"
    ),
    topic: str | None = Query(None, description="Filter by primary topic"),
    language: str | None = Query(None, description="Filter by language"),
    from_date: datetime | None = Query(
        None, description="Articles published after"
    ),
    to_date: datetime | None = Query(
        None, description="Articles published before"
    ),
):
    """Export articles as CSV or JSON."""
    if format == "csv":
        csv_content = await export_articles_csv(
            source_id=source_id,
            transport_mode=transport_mode,
            topic=topic,
            language=language,
            from_date=from_date,
            to_date=to_date,
        )
        return StreamingResponse(
            io.StringIO(csv_content),
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=articles_export.csv"
            },
        )
    else:
        data = await export_articles_json(
            source_id=source_id,
            transport_mode=transport_mode,
            topic=topic,
            language=language,
            from_date=from_date,
            to_date=to_date,
        )
        return data


@router.get("/fetch-logs")
async def list_fetch_logs(
    source_id: str | None = Query(None, description="Filter by source ID"),
    limit: int = Query(50, ge=1, le=200, description="Number of logs to return"),
):
    """List recent fetch logs for monitoring."""
    async with get_session() as session:
        query = select(FetchLog).order_by(FetchLog.started_at.desc().nullslast())

        if source_id:
            query = query.where(FetchLog.source_id == source_id)

        query = query.limit(limit)
        result = await session.execute(query)
        logs = result.scalars().all()

    return [
        {
            "id": log.id,
            "source_id": log.source_id,
            "started_at": log.started_at.isoformat() if log.started_at else None,
            "completed_at": log.completed_at.isoformat()
            if log.completed_at
            else None,
            "status": log.status,
            "articles_found": log.articles_found,
            "articles_new": log.articles_new,
            "articles_dedup": log.articles_dedup,
            "error_message": log.error_message,
            "duration_ms": log.duration_ms,
        }
        for log in logs
    ]


# ---------------------------------------------------------------------------
# API Key Management (Admin)
# ---------------------------------------------------------------------------


@router.post("/admin/api-keys")
async def create_api_key(
    name: str = Query(..., description="Name for this API key"),
    role: str = Query("reader", description="Role: admin or reader"),
):
    """Create a new API key. Returns the key only once."""
    from api.auth import generate_api_key, hash_api_key
    from storage.models import APIKey

    raw_key = generate_api_key()
    key_hash = hash_api_key(raw_key)

    api_key = APIKey(name=name, key_hash=key_hash, role=role)
    async with get_session() as session:
        session.add(api_key)

    return {
        "id": api_key.id,
        "name": name,
        "role": role,
        "api_key": raw_key,  # Only shown once!
        "message": "Save this key - it cannot be retrieved again",
    }


@router.get("/admin/api-keys")
async def list_api_keys():
    """List all API keys (without revealing the actual keys)."""
    from storage.models import APIKey

    async with get_session() as session:
        result = await session.execute(
            select(APIKey).order_by(APIKey.created_at.desc())
        )
        keys = result.scalars().all()

    return [
        {
            "id": k.id,
            "name": k.name,
            "role": k.role,
            "enabled": k.enabled,
            "created_at": k.created_at.isoformat() if k.created_at else None,
            "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
        }
        for k in keys
    ]


@router.delete("/admin/api-keys/{key_id}", status_code=204)
async def delete_api_key(key_id: str):
    """Delete an API key."""
    from storage.models import APIKey

    async with get_session() as session:
        result = await session.execute(
            select(APIKey).where(APIKey.id == key_id)
        )
        key = result.scalar_one_or_none()
        if not key:
            raise HTTPException(status_code=404, detail="API key not found")
        await session.delete(key)


# ---------------------------------------------------------------------------
# Source Discovery
# ---------------------------------------------------------------------------


@router.post("/discovery/start")
async def start_discovery():
    """Start the automatic source discovery process."""
    from api.main import get_scheduler
    from discovery.jobs import start_discovery as _start, get_discovery_status

    scheduler = get_scheduler()
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not available")

    _start(scheduler)
    return get_discovery_status()


@router.post("/discovery/stop")
async def stop_discovery():
    """Stop the automatic source discovery process."""
    from api.main import get_scheduler
    from discovery.jobs import stop_discovery as _stop, get_discovery_status

    scheduler = get_scheduler()
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not available")

    _stop(scheduler)
    return get_discovery_status()


@router.get("/discovery/status")
async def discovery_status():
    """Get current discovery system status."""
    from discovery.jobs import get_discovery_status

    status = get_discovery_status()

    # Add candidate counts
    async with get_session() as session:
        for s in ("discovered", "validating", "validated", "approved", "rejected"):
            result = await session.execute(
                select(func.count(SourceCandidate.id)).where(
                    SourceCandidate.status == s
                )
            )
            status[f"count_{s}"] = result.scalar_one()

    return status


@router.post("/discovery/scan")
async def trigger_discovery_scan():
    """Manually trigger a discovery scan (one-shot)."""
    from discovery.engine import DiscoveryEngine

    async with DiscoveryEngine() as engine:
        result = await engine.run()

    return {
        "candidates_found": len(result),
        "candidates": result,
    }


@router.post("/discovery/validate")
async def trigger_discovery_validate(
    limit: int = Query(10, ge=1, le=50, description="Max candidates to validate"),
):
    """Manually trigger validation of pending candidates."""
    from discovery.validator import SourceValidator

    async with SourceValidator() as validator:
        result = await validator.validate_batch(limit=limit)

    return result


@router.get("/discovery/candidates")
async def list_candidates(
    status: str | None = Query(None, description="Filter by status"),
    language: str | None = Query(None, description="Filter by language"),
    min_quality: int | None = Query(None, ge=0, le=100, description="Min quality score"),
    sort: str = Query("created_at", description="Sort by: created_at, quality_score, relevance_score"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List source candidates with filtering and pagination."""
    async with get_session() as session:
        query = select(SourceCandidate)

        if status:
            query = query.where(SourceCandidate.status == status)
        if language:
            query = query.where(SourceCandidate.language == language)
        if min_quality is not None:
            query = query.where(SourceCandidate.quality_score >= min_quality)

        # Sort
        if sort == "quality_score":
            query = query.order_by(SourceCandidate.quality_score.desc().nullslast())
        elif sort == "relevance_score":
            query = query.order_by(SourceCandidate.relevance_score.desc().nullslast())
        else:
            query = query.order_by(SourceCandidate.created_at.desc())

        # Count
        count_q = select(func.count()).select_from(query.subquery())
        total = (await session.execute(count_q)).scalar_one()

        # Paginate
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        result = await session.execute(query)
        candidates = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size if total > 0 else 0,
        "candidates": [
            {
                "id": c.id,
                "url": c.url,
                "name": c.name,
                "feed_url": c.feed_url,
                "source_type": c.source_type,
                "language": c.language,
                "categories": c.categories,
                "discovered_via": c.discovered_via,
                "discovery_query": c.discovery_query,
                "status": c.status,
                "quality_score": c.quality_score,
                "relevance_score": c.relevance_score,
                "articles_fetched": c.articles_fetched,
                "fetch_success": c.fetch_success,
                "error_message": c.error_message,
                "auto_approved": c.auto_approved,
                "sample_articles": c.sample_articles,
                "validation_details": c.validation_details,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "validated_at": c.validated_at.isoformat() if c.validated_at else None,
            }
            for c in candidates
        ],
    }


@router.post("/discovery/candidates/{candidate_id}/approve")
async def approve_candidate(candidate_id: str):
    """Approve a validated candidate and promote it to an active source."""
    from discovery.validator import SourceValidator

    async with get_session() as session:
        result = await session.execute(
            select(SourceCandidate).where(SourceCandidate.id == candidate_id)
        )
        candidate = result.scalar_one_or_none()

    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    if candidate.status == "approved":
        raise HTTPException(status_code=409, detail="Candidate already approved")

    async with SourceValidator() as validator:
        await validator._promote_to_source(
            candidate,
            candidate.name,
            candidate.feed_url,
            candidate.source_type or "universal",
        )

    # Update candidate status
    async with get_session() as session:
        from sqlalchemy import update
        from datetime import datetime

        await session.execute(
            update(SourceCandidate)
            .where(SourceCandidate.id == candidate_id)
            .values(status="approved", reviewed_at=datetime.utcnow())
        )

    return {"id": candidate_id, "status": "approved", "message": "Source created successfully"}


@router.post("/discovery/candidates/{candidate_id}/reject")
async def reject_candidate(candidate_id: str):
    """Reject a candidate source."""
    async with get_session() as session:
        result = await session.execute(
            select(SourceCandidate).where(SourceCandidate.id == candidate_id)
        )
        candidate = result.scalar_one_or_none()

    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    async with get_session() as session:
        from sqlalchemy import update
        from datetime import datetime

        await session.execute(
            update(SourceCandidate)
            .where(SourceCandidate.id == candidate_id)
            .values(status="rejected", reviewed_at=datetime.utcnow())
        )

    return {"id": candidate_id, "status": "rejected"}


@router.post("/discovery/probe")
async def probe_url(payload: dict):
    """Manually probe a single URL to check if it's a valid news source.

    Accepts: {"url": "https://example.com"}
    """
    url = payload.get("url")
    if not url:
        raise HTTPException(status_code=422, detail="'url' is required")

    from discovery.validator import SourceValidator

    async with SourceValidator() as validator:
        # Create a temporary candidate-like object for validation
        reachable, html, final_url = await validator._check_connectivity(url)
        if not reachable:
            return {
                "url": url,
                "reachable": False,
                "error": "Site unreachable",
            }

        site_name = validator._extract_site_name(html, url)
        feed_url = await validator._probe_feed(url, html)
        articles, fetch_error = await validator._trial_fetch(url, site_name, None)

        quality = validator._score_quality(articles) if articles else 0
        relevance = validator._score_relevance(articles, "en") if articles else 0

        return {
            "url": url,
            "final_url": final_url,
            "reachable": True,
            "name": site_name,
            "feed_url": feed_url,
            "source_type": "rss" if feed_url else "universal",
            "articles_fetched": len(articles),
            "quality_score": quality,
            "relevance_score": relevance,
            "combined_score": int(quality * 0.4 + relevance * 0.6),
            "sample_articles": [
                {
                    "title": a.get("title", "")[:200],
                    "url": a.get("url", ""),
                    "body_preview": (a.get("body_text") or "")[:300],
                }
                for a in articles[:3]
            ],
            "fetch_error": fetch_error,
        }


@router.post("/process")
async def trigger_llm_processing(
    batch_size: int = Query(10, ge=1, le=50, description="Number of articles to process"),
):
    """Manually trigger LLM processing for pending articles."""
    if not llm_settings.llm_api_key:
        raise HTTPException(status_code=503, detail="LLM_API_KEY not configured")

    from processing.llm_pipeline import ArticleProcessor

    processor = ArticleProcessor()
    try:
        summary = await processor.process_pending_batch(batch_size=batch_size)
        return summary
    finally:
        await processor.close()
