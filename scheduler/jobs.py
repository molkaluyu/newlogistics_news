import logging
import time
from datetime import datetime

import yaml
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from adapters.base import RawArticle
from adapters.rss_adapter import RSSAdapter
from config.llm_settings import llm_settings
from config.settings import settings
from monitoring.health import SourceHealthMonitor
from processing.cleaner import clean_text, clean_title
from processing.deduplicator import Deduplicator
from processing.language import detect_language
from storage.database import get_session
from storage.models import Article, FetchLog, Source

logger = logging.getLogger(__name__)

# Adapter registry by source type
ADAPTER_MAP = {
    "rss": RSSAdapter,
}

deduplicator = Deduplicator()


def load_sources_config() -> list[dict]:
    """Load source configurations from YAML file."""
    with open(settings.sources_yaml_path, "r") as f:
        data = yaml.safe_load(f)
    return data.get("sources", [])


async def fetch_source(source_id: str):
    """Fetch articles from a single source. Called by scheduler."""
    sources = load_sources_config()
    source_config = next((s for s in sources if s["source_id"] == source_id), None)

    if not source_config:
        logger.error(f"Source config not found: {source_id}")
        return

    if not source_config.get("enabled", True):
        logger.info(f"Source {source_id} is disabled, skipping")
        return

    source_type = source_config.get("type", "rss")
    adapter_cls = ADAPTER_MAP.get(source_type)

    if not adapter_cls:
        logger.error(f"No adapter for source type: {source_type}")
        return

    started_at = datetime.utcnow()
    start_time = time.time()
    articles_found = 0
    articles_new = 0
    articles_dedup = 0
    status = "success"
    error_message = None

    try:
        async with adapter_cls(source_config) as adapter:
            raw_articles: list[RawArticle] = await adapter.fetch()
            articles_found = len(raw_articles)

            for raw in raw_articles:
                # Check dedup
                if await deduplicator.is_duplicate(raw.url):
                    articles_dedup += 1
                    continue

                # Clean and store
                article = _raw_to_article(raw)
                async with get_session() as session:
                    session.add(article)
                articles_new += 1

    except Exception as e:
        status = "failed"
        error_message = str(e)[:1000]
        logger.error(f"Error fetching {source_id}: {e}", exc_info=True)

    # Log the fetch
    duration_ms = int((time.time() - start_time) * 1000)
    await _log_fetch(
        source_id=source_id,
        started_at=started_at,
        status=status,
        articles_found=articles_found,
        articles_new=articles_new,
        articles_dedup=articles_dedup,
        error_message=error_message,
        duration_ms=duration_ms,
    )

    # Update source last_fetched_at
    await _update_source_last_fetched(source_id)

    logger.info(
        f"Fetch complete: {source_id} | "
        f"found={articles_found}, new={articles_new}, dedup={articles_dedup}, "
        f"status={status}, duration={duration_ms}ms"
    )


def _raw_to_article(raw: RawArticle) -> Article:
    """Convert a RawArticle to an Article database model."""
    cleaned_body = clean_text(raw.body_text)

    # Detect actual language from article body instead of relying on source config
    language = detect_language(cleaned_body) if cleaned_body else (raw.language or "en")

    return Article(
        source_id=raw.source_id,
        source_name=raw.source_name,
        url=raw.url,
        title=clean_title(raw.title) or raw.title,
        body_text=cleaned_body,
        body_markdown=raw.body_markdown,
        language=language,
        published_at=raw.published_at,
        fetched_at=raw.fetched_at,
        raw_metadata=raw.raw_metadata,
        processing_status="pending",
    )


async def _log_fetch(
    source_id: str,
    started_at: datetime,
    status: str,
    articles_found: int,
    articles_new: int,
    articles_dedup: int,
    error_message: str | None,
    duration_ms: int,
):
    """Write a fetch log entry to the database."""
    log = FetchLog(
        source_id=source_id,
        started_at=started_at,
        completed_at=datetime.utcnow(),
        status=status,
        articles_found=articles_found,
        articles_new=articles_new,
        articles_dedup=articles_dedup,
        error_message=error_message,
        duration_ms=duration_ms,
    )
    try:
        async with get_session() as session:
            session.add(log)
    except Exception as e:
        logger.error(f"Failed to write fetch log: {e}")


async def _update_source_last_fetched(source_id: str):
    """Update the last_fetched_at timestamp for a source."""
    try:
        async with get_session() as session:
            from sqlalchemy import update

            await session.execute(
                update(Source)
                .where(Source.source_id == source_id)
                .values(last_fetched_at=datetime.utcnow())
            )
    except Exception as e:
        logger.error(f"Failed to update source last_fetched_at: {e}")


async def run_health_check():
    """Run health checks on all sources. Called by scheduler."""
    monitor = SourceHealthMonitor()
    reports = await monitor.check_all()

    for report in reports:
        if report.alerts:
            logger.warning(
                f"Source {report.source_id} ({report.name}): "
                f"status={report.health_status}, alerts={report.alerts}"
            )

    logger.info(f"Health check complete: {len(reports)} sources checked")


async def run_llm_processing():
    """Process pending articles through the LLM pipeline. Called by scheduler."""
    if not llm_settings.llm_api_key:
        return  # LLM not configured, skip silently

    from processing.llm_pipeline import ArticleProcessor

    processor = ArticleProcessor()
    try:
        summary = await processor.process_pending_batch()
        if summary["total"] > 0:
            logger.info(
                f"LLM processing complete: {summary['success']}/{summary['total']} succeeded"
            )
    except Exception as e:
        logger.error(f"LLM processing batch failed: {e}", exc_info=True)
    finally:
        await processor.close()


def create_scheduler() -> AsyncIOScheduler:
    """Create and configure the APScheduler with jobs for all enabled sources."""
    scheduler = AsyncIOScheduler()
    sources = load_sources_config()

    for source in sources:
        if not source.get("enabled", True):
            continue

        interval_minutes = source.get(
            "fetch_interval_minutes", settings.rss_fetch_interval_minutes
        )

        scheduler.add_job(
            fetch_source,
            trigger="interval",
            args=[source["source_id"]],
            minutes=interval_minutes,
            id=f"fetch_{source['source_id']}",
            max_instances=1,
            misfire_grace_time=300,  # 5 minute grace period
            jitter=120,  # Random delay 0-120s to spread requests
            replace_existing=True,
        )
        logger.info(
            f"Scheduled job: {source['source_id']} every {interval_minutes}min"
        )

    # Health check job: monitor all sources every 30 minutes
    scheduler.add_job(
        run_health_check,
        trigger="interval",
        minutes=30,
        id="health_check",
        max_instances=1,
        misfire_grace_time=300,
        replace_existing=True,
    )
    logger.info("Scheduled job: health_check every 30min")

    # LLM processing job: process pending articles every 10 minutes
    if llm_settings.llm_api_key:
        scheduler.add_job(
            run_llm_processing,
            trigger="interval",
            minutes=10,
            id="llm_processing",
            max_instances=1,
            misfire_grace_time=300,
            replace_existing=True,
        )
        logger.info("Scheduled job: llm_processing every 10min")

    return scheduler
