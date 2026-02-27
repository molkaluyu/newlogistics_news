import logging

import yaml
from sqlalchemy import select

from config.settings import settings
from storage.database import get_session
from storage.models import Source

logger = logging.getLogger(__name__)


async def seed_sources():
    """Load sources from YAML config and insert into database. Idempotent."""
    with open(settings.sources_yaml_path, "r") as f:
        data = yaml.safe_load(f)

    sources = data.get("sources", [])
    if not sources:
        logger.warning("No sources found in sources.yaml")
        return

    async with get_session() as session:
        for src in sources:
            # Check if source already exists
            result = await session.execute(
                select(Source).where(Source.source_id == src["source_id"])
            )
            existing = result.scalar_one_or_none()

            if existing:
                logger.debug(f"Source already exists: {src['source_id']}")
                continue

            source = Source(
                source_id=src["source_id"],
                name=src["name"],
                type=src["type"],
                url=src["url"],
                language=src.get("language"),
                categories=src.get("categories", []),
                fetch_interval_minutes=src.get("fetch_interval_minutes", 30),
                enabled=src.get("enabled", True),
                priority=src.get("priority", 5),
                notes=src.get("notes"),
            )
            session.add(source)
            logger.info(f"Added source: {src['source_id']} ({src['name']})")

    logger.info(f"Source seeding complete. {len(sources)} sources in config.")
