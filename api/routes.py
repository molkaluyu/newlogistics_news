import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select, text

from config.llm_settings import llm_settings
from monitoring.health import SourceHealthMonitor
from storage.database import get_session
from storage.models import Article, FetchLog, Source

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
