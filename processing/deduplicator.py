import logging

from sqlalchemy import select

from storage.database import get_session
from storage.models import Article

logger = logging.getLogger(__name__)


class Deduplicator:
    """Article deduplication using URL exact matching.

    Level 1 (MVP): URL exact match against database.
    Level 2 (Phase 3): Title SimHash for cross-source dedup.
    Level 3 (Future): Content MinHash similarity.
    """

    async def is_duplicate(self, url: str) -> bool:
        """Check if an article with this URL already exists."""
        async with get_session() as session:
            result = await session.execute(
                select(Article.id).where(Article.url == url).limit(1)
            )
            exists = result.scalar_one_or_none() is not None
            if exists:
                logger.debug(f"Duplicate URL found: {url}")
            return exists

    async def filter_new(self, urls: list[str]) -> set[str]:
        """Given a list of URLs, return the set that don't exist in DB yet."""
        if not urls:
            return set()

        async with get_session() as session:
            result = await session.execute(
                select(Article.url).where(Article.url.in_(urls))
            )
            existing = {row[0] for row in result.fetchall()}

        new_urls = set(urls) - existing
        logger.debug(
            f"URL dedup: {len(urls)} checked, {len(existing)} existing, "
            f"{len(new_urls)} new"
        )
        return new_urls
