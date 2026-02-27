import asyncio
import logging
from datetime import datetime
from email.utils import parsedate_to_datetime

import feedparser
import trafilatura

from adapters.base import BaseAdapter, RawArticle

logger = logging.getLogger(__name__)


def _parse_date(date_str: str | None) -> datetime | None:
    """Parse various date formats from RSS feeds."""
    if not date_str:
        return None
    try:
        return parsedate_to_datetime(date_str)
    except (ValueError, TypeError):
        pass
    # feedparser's own date parsing
    try:
        parsed = feedparser._parse_date(date_str)
        if parsed:
            return datetime(*parsed[:6])
    except Exception:
        pass
    return None


class RSSAdapter(BaseAdapter):
    """Adapter for RSS/Atom feed sources."""

    async def fetch(self) -> list[RawArticle]:
        """Fetch and parse an RSS feed, extracting full article text."""
        url = self.config["url"]
        logger.info(f"Fetching RSS feed: {self.source_name} ({url})")

        try:
            response = await self.client.get(url)
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to fetch RSS feed {url}: {e}")
            return []

        feed = feedparser.parse(response.text)

        if feed.bozo and not feed.entries:
            logger.warning(
                f"RSS feed {url} has parsing issues: {feed.bozo_exception}"
            )
            return []

        articles = []
        for entry in feed.entries:
            try:
                article = await self._process_entry(entry)
                if article:
                    articles.append(article)
            except Exception as e:
                logger.warning(
                    f"Failed to process entry '{getattr(entry, 'title', '?')}': {e}"
                )
                continue

            # Small delay between full-page fetches to be polite
            await asyncio.sleep(0.5)

        logger.info(
            f"Fetched {len(articles)} articles from {self.source_name}"
        )
        return articles

    async def _process_entry(self, entry) -> RawArticle | None:
        """Process a single RSS feed entry into a RawArticle."""
        url = getattr(entry, "link", None)
        title = getattr(entry, "title", None)

        if not url or not title:
            return None

        # Extract full article text
        body_markdown, body_text = await self._extract_full_text(url)

        # Fallback to RSS summary if full text extraction fails
        if not body_text:
            body_text = self._get_rss_summary(entry)
            body_markdown = body_text

        # Parse published date
        published_at = _parse_date(
            getattr(entry, "published", None)
            or getattr(entry, "updated", None)
        )

        # Collect RSS metadata
        raw_metadata = {}
        if hasattr(entry, "summary"):
            raw_metadata["rss_summary"] = entry.summary
        if hasattr(entry, "tags"):
            raw_metadata["rss_tags"] = [t.term for t in entry.tags]
        if hasattr(entry, "author"):
            raw_metadata["rss_author"] = entry.author

        return RawArticle(
            source_id=self.source_id,
            source_name=self.source_name,
            url=url,
            title=title.strip(),
            body_text=body_text,
            body_markdown=body_markdown,
            published_at=published_at,
            language=self.config.get("language", "en"),
            raw_metadata=raw_metadata,
        )

    async def _extract_full_text(self, url: str) -> tuple[str | None, str | None]:
        """Fetch the full article page and extract text with trafilatura.

        Returns (markdown, plain_text) tuple.
        """
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            html = response.text
        except Exception as e:
            logger.debug(f"Failed to fetch full page {url}: {e}")
            return None, None

        try:
            # Extract as markdown (for storage and LLM processing)
            markdown = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=True,
                output_format="markdown",
            )
            # Extract as plain text (for search indexing)
            plain = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=True,
                output_format="txt",
            )
            return markdown, plain
        except Exception as e:
            logger.debug(f"Trafilatura extraction failed for {url}: {e}")
            return None, None

    @staticmethod
    def _get_rss_summary(entry) -> str | None:
        """Extract summary/description from RSS entry as fallback."""
        summary = getattr(entry, "summary", None) or getattr(
            entry, "description", None
        )
        if not summary:
            return None
        # Strip HTML tags from summary (basic cleanup)
        import re

        clean = re.sub(r"<[^>]+>", "", summary)
        clean = clean.strip()
        return clean if len(clean) > 50 else None
