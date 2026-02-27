"""Article deduplication with three progressive levels.

Level 1: URL exact match (fast, catches same-URL reposts).
Level 2: Title SimHash (catches cross-source duplicates with similar titles).
Level 3: Content MinHash (catches rewritten / near-duplicate articles).
"""

import logging

from sqlalchemy import select

from storage.database import get_session
from storage.models import Article

logger = logging.getLogger(__name__)


class Deduplicator:
    """Multi-level article deduplication."""

    def __init__(
        self,
        simhash_threshold: int = 3,
        minhash_threshold: float = 0.5,
    ):
        self.simhash_threshold = simhash_threshold
        self.minhash_threshold = minhash_threshold

    # ── Level 1: URL exact match ──

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

    # ── Level 2: Title SimHash ──

    async def find_simhash_duplicates(
        self,
        title_simhash: int,
        exclude_id: str | None = None,
    ) -> list[dict]:
        """Find articles with similar title SimHash.

        Searches articles whose title_simhash is within Hamming distance
        of `simhash_threshold`.

        Returns:
            List of dicts with id, title, url, hamming_distance.
        """
        from processing.simhash import hamming_distance

        async with get_session() as session:
            # Fetch all non-null simhashes (indexed column, efficient scan)
            query = select(
                Article.id, Article.title, Article.url, Article.title_simhash
            ).where(Article.title_simhash.isnot(None))

            if exclude_id:
                query = query.where(Article.id != exclude_id)

            result = await session.execute(query)
            rows = result.fetchall()

        matches = []
        for row in rows:
            dist = hamming_distance(title_simhash, row.title_simhash)
            if dist <= self.simhash_threshold:
                matches.append(
                    {
                        "id": row.id,
                        "title": row.title,
                        "url": row.url,
                        "hamming_distance": dist,
                    }
                )

        if matches:
            logger.info(
                f"SimHash dedup: found {len(matches)} similar title(s) "
                f"(threshold={self.simhash_threshold})"
            )

        return matches

    # ── Level 3: Content MinHash ──

    async def find_minhash_duplicates(
        self,
        content_minhash: list[int],
        exclude_id: str | None = None,
    ) -> list[dict]:
        """Find articles with similar content using MinHash signatures.

        Returns:
            List of dicts with id, title, url, jaccard_similarity.
        """
        from processing.minhash import jaccard_from_minhash

        async with get_session() as session:
            query = select(
                Article.id,
                Article.title,
                Article.url,
                Article.content_minhash,
            ).where(Article.content_minhash.isnot(None))

            if exclude_id:
                query = query.where(Article.id != exclude_id)

            result = await session.execute(query)
            rows = result.fetchall()

        matches = []
        for row in rows:
            try:
                jaccard = jaccard_from_minhash(content_minhash, list(row.content_minhash))
            except ValueError:
                continue
            if jaccard >= self.minhash_threshold:
                matches.append(
                    {
                        "id": row.id,
                        "title": row.title,
                        "url": row.url,
                        "jaccard_similarity": round(jaccard, 4),
                    }
                )

        if matches:
            logger.info(
                f"MinHash dedup: found {len(matches)} similar article(s) "
                f"(threshold={self.minhash_threshold})"
            )

        return matches

    # ── Combined check ──

    async def check_all_levels(
        self,
        url: str,
        title_simhash: int | None = None,
        content_minhash: list[int] | None = None,
        exclude_id: str | None = None,
    ) -> dict:
        """Run all dedup levels and return combined results.

        Returns:
            Dict with keys:
                is_url_duplicate: bool
                simhash_matches: list[dict]
                minhash_matches: list[dict]
                is_duplicate: bool (True if any level found a match)
        """
        url_dup = await self.is_duplicate(url)

        simhash_matches = []
        if title_simhash is not None:
            simhash_matches = await self.find_simhash_duplicates(
                title_simhash, exclude_id
            )

        minhash_matches = []
        if content_minhash is not None:
            minhash_matches = await self.find_minhash_duplicates(
                content_minhash, exclude_id
            )

        return {
            "is_url_duplicate": url_dup,
            "simhash_matches": simhash_matches,
            "minhash_matches": minhash_matches,
            "is_duplicate": url_dup or bool(simhash_matches) or bool(minhash_matches),
        }
