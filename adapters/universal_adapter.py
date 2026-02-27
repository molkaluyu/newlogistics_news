"""Zero-config universal adapter.

Auto-discovers RSS/Atom feeds or extracts articles directly from any news
website URL using trafilatura -- no CSS selector configuration required.

Discovery strategy cascade:
1. RSS auto-discovery via ``<link rel="alternate">`` tags and common feed paths.
2. Trafilatura feed discovery via ``trafilatura.feeds.find_feed_urls()``.
3. Direct link extraction from the page with trafilatura article extraction.
"""

import asyncio
import logging
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlparse

import feedparser
import trafilatura
from bs4 import BeautifulSoup
from trafilatura.feeds import find_feed_urls

from adapters.base import BaseAdapter, RawArticle

logger = logging.getLogger(__name__)

_MAX_ARTICLES = 20
_FETCH_DELAY = 0.5  # seconds between article fetches (politeness)

# Common feed path suffixes to probe when auto-discovery fails.
_COMMON_FEED_PATHS = [
    "/feed",
    "/rss",
    "/atom.xml",
    "/feed.xml",
    "/rss.xml",
    "/feeds/posts/default",
    "/index.xml",
]

# URL path segments that usually indicate non-article pages.
_NON_ARTICLE_SEGMENTS = re.compile(
    r"^/(#|$)"
    r"|/(tag|category|categories|author|page|search|login|signup|register|contact"
    r"|about|privacy|terms|faq|help|archive|archives|wp-content|wp-admin"
    r"|cdn-cgi|static|assets|images|img|css|js|fonts)(/|$)",
    re.IGNORECASE,
)

# File extensions that are definitely not articles.
_NON_ARTICLE_EXT = re.compile(
    r"\.(png|jpg|jpeg|gif|svg|webp|ico|css|js|woff2?|ttf|eot|pdf|zip|gz|mp[34]|mov)(\?|$)",
    re.IGNORECASE,
)


def _parse_rss_date(date_str: str | None) -> datetime | None:
    """Parse various date formats from RSS feeds."""
    if not date_str:
        return None
    try:
        return parsedate_to_datetime(date_str)
    except (ValueError, TypeError):
        pass
    try:
        parsed = feedparser._parse_date(date_str)
        if parsed:
            return datetime(*parsed[:6])
    except Exception:
        pass
    return None


class UniversalAdapter(BaseAdapter):
    """Zero-config adapter: auto-discovers feeds or extracts articles via trafilatura."""

    def __init__(self, source_config: dict):
        super().__init__(source_config)
        self.max_articles: int = int(
            source_config.get("max_articles", _MAX_ARTICLES)
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def fetch(self) -> list[RawArticle]:
        """Fetch articles using a cascading discovery strategy."""
        url = self.config["url"]
        logger.info(
            f"UniversalAdapter: fetching {self.source_name} ({url})"
        )

        # Strategy 1: RSS auto-discovery from HTML <link> tags + common paths
        articles = await self._try_rss_discovery(url)
        if articles:
            logger.info(
                f"UniversalAdapter: strategy=rss_discovery yielded "
                f"{len(articles)} articles for {self.source_name}"
            )
            return articles[: self.max_articles]

        # Strategy 2: Trafilatura feed discovery
        articles = await self._try_trafilatura_feed_discovery(url)
        if articles:
            logger.info(
                f"UniversalAdapter: strategy=trafilatura_feed_discovery yielded "
                f"{len(articles)} articles for {self.source_name}"
            )
            return articles[: self.max_articles]

        # Strategy 3: Extract article links from the page itself
        articles = await self._extract_from_page(url)
        logger.info(
            f"UniversalAdapter: strategy=page_extraction yielded "
            f"{len(articles)} articles for {self.source_name}"
        )
        return articles[: self.max_articles]

    # ------------------------------------------------------------------
    # Strategy 1: RSS auto-discovery
    # ------------------------------------------------------------------

    async def _try_rss_discovery(self, url: str) -> list[RawArticle]:
        """Fetch page, look for RSS/Atom ``<link>`` tags, try common feed paths."""
        # Step 1a: Fetch the page and look for <link rel="alternate"> tags
        feed_url = await self._discover_feed_from_html(url)
        if feed_url:
            articles = await self._parse_feed(feed_url)
            if articles:
                return articles

        # Step 1b: Try common feed paths
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"

        for path in _COMMON_FEED_PATHS:
            candidate = base + path
            articles = await self._parse_feed(candidate)
            if articles:
                logger.debug(
                    f"UniversalAdapter: found feed at common path {candidate}"
                )
                return articles

        return []

    async def _discover_feed_from_html(self, url: str) -> str | None:
        """Parse the HTML at *url* for ``<link rel="alternate" type="application/rss+xml">``.

        Returns the first discovered feed URL, or None.
        """
        try:
            response = await self.client.get(url)
            response.raise_for_status()
        except Exception as e:
            logger.debug(f"UniversalAdapter: failed to fetch {url}: {e}")
            return None

        soup = BeautifulSoup(response.text, "lxml")
        for link_type in (
            "application/rss+xml",
            "application/atom+xml",
            "application/rdf+xml",
        ):
            link = soup.find("link", attrs={"rel": "alternate", "type": link_type})
            if link and link.get("href"):
                href = link["href"]
                return urljoin(url, href)

        return None

    async def _parse_feed(self, feed_url: str) -> list[RawArticle]:
        """Fetch and parse a feed URL, returning articles or an empty list."""
        try:
            response = await self.client.get(feed_url)
            response.raise_for_status()
        except Exception:
            return []

        content_type = response.headers.get("content-type", "")
        text = response.text

        # Quick sanity check: does this look like XML/feed content?
        if not text.strip():
            return []
        # Reject obvious HTML-only responses that are not feeds
        if "<rss" not in text[:500] and "<feed" not in text[:500] and "<rdf" not in text[:1000]:
            if "text/html" in content_type and "xml" not in content_type:
                return []

        feed = feedparser.parse(text)
        if feed.bozo and not feed.entries:
            return []

        articles: list[RawArticle] = []
        for entry in feed.entries[: self.max_articles]:
            article = await self._entry_to_article(entry)
            if article:
                articles.append(article)
            await asyncio.sleep(_FETCH_DELAY)

        return articles

    async def _entry_to_article(self, entry) -> RawArticle | None:
        """Convert a feedparser entry into a RawArticle with full-text extraction."""
        url = getattr(entry, "link", None)
        title = getattr(entry, "title", None)
        if not url or not title:
            return None

        # Extract full article text via trafilatura
        body_markdown, body_text = await self._extract_full_text(url)

        # Fallback: use RSS summary
        if not body_text:
            summary = getattr(entry, "summary", None) or getattr(entry, "description", None)
            if summary:
                clean = re.sub(r"<[^>]+>", "", summary).strip()
                if len(clean) > 50:
                    body_text = clean
                    body_markdown = clean

        published_at = _parse_rss_date(
            getattr(entry, "published", None) or getattr(entry, "updated", None)
        )

        raw_metadata: dict = {"universal_strategy": "rss_discovery"}
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

    # ------------------------------------------------------------------
    # Strategy 2: Trafilatura feed discovery
    # ------------------------------------------------------------------

    async def _try_trafilatura_feed_discovery(self, url: str) -> list[RawArticle]:
        """Use trafilatura.feeds.find_feed_urls() to discover feeds."""
        try:
            feed_urls = await asyncio.to_thread(
                find_feed_urls, url, target_lang=self.config.get("language")
            )
        except Exception as e:
            logger.debug(
                f"UniversalAdapter: trafilatura feed discovery failed for {url}: {e}"
            )
            return []

        if not feed_urls:
            return []

        logger.debug(
            f"UniversalAdapter: trafilatura discovered {len(feed_urls)} feed(s) for {url}"
        )

        # Try the first few discovered feeds
        for feed_url in feed_urls[:3]:
            articles = await self._parse_feed(feed_url)
            if articles:
                # Tag the strategy
                for a in articles:
                    a.raw_metadata["universal_strategy"] = "trafilatura_feed_discovery"
                return articles

        return []

    # ------------------------------------------------------------------
    # Strategy 3: Page link extraction + trafilatura
    # ------------------------------------------------------------------

    async def _extract_from_page(self, url: str) -> list[RawArticle]:
        """Fall back to extracting article links from the page itself."""
        try:
            response = await self.client.get(url)
            response.raise_for_status()
        except Exception as e:
            logger.error(
                f"UniversalAdapter: failed to fetch page {url}: {e}"
            )
            return []

        html = response.text
        parsed_base = urlparse(url)
        base_domain = parsed_base.netloc
        base_url = f"{parsed_base.scheme}://{parsed_base.netloc}"

        soup = BeautifulSoup(html, "lxml")
        seen_urls: set[str] = set()
        candidate_links: list[tuple[str, str]] = []

        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            absolute_url = urljoin(base_url, href)

            # Remove fragment
            absolute_url = absolute_url.split("#")[0]

            if absolute_url in seen_urls:
                continue
            seen_urls.add(absolute_url)

            link_text = anchor.get_text(strip=True)
            if self._looks_like_article_url(absolute_url, base_domain) and link_text:
                candidate_links.append((absolute_url, link_text))

        if not candidate_links:
            logger.debug(
                f"UniversalAdapter: no article-like links found on {url}"
            )
            return []

        logger.debug(
            f"UniversalAdapter: found {len(candidate_links)} candidate article links on {url}"
        )

        articles: list[RawArticle] = []
        for link_url, link_text in candidate_links[: self.max_articles]:
            try:
                article = await self._extract_article(link_url, link_text)
                if article:
                    articles.append(article)
            except Exception as e:
                logger.debug(
                    f"UniversalAdapter: failed to extract article from {link_url}: {e}"
                )
                continue
            await asyncio.sleep(_FETCH_DELAY)

        return articles

    async def _extract_article(
        self, url: str, fallback_title: str
    ) -> RawArticle | None:
        """Fetch a single article URL and extract content with trafilatura."""
        body_markdown, body_text = await self._extract_full_text(url)
        if not body_text:
            return None

        # Try to extract a better title from the page via trafilatura metadata
        title = fallback_title
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            html = response.text
            metadata = trafilatura.extract_metadata(html)
            if metadata and metadata.title:
                title = metadata.title
            # Try to get published date from metadata
            published_at = None
            if metadata and metadata.date:
                try:
                    published_at = datetime.fromisoformat(metadata.date)
                except (ValueError, TypeError):
                    published_at = None
        except Exception:
            published_at = None

        return RawArticle(
            source_id=self.source_id,
            source_name=self.source_name,
            url=url,
            title=title.strip(),
            body_text=body_text,
            body_markdown=body_markdown,
            published_at=published_at,
            language=self.config.get("language", "en"),
            raw_metadata={"universal_strategy": "page_extraction"},
        )

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    async def _extract_full_text(self, url: str) -> tuple[str | None, str | None]:
        """Fetch *url* and extract (markdown, plain_text) via trafilatura."""
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            html = response.text
        except Exception as e:
            logger.debug(f"UniversalAdapter: failed to fetch {url}: {e}")
            return None, None

        try:
            markdown = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=True,
                output_format="markdown",
            )
            plain = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=True,
                output_format="txt",
            )
            return markdown, plain
        except Exception as e:
            logger.debug(
                f"UniversalAdapter: trafilatura extraction failed for {url}: {e}"
            )
            return None, None

    @staticmethod
    def _looks_like_article_url(url: str, base_domain: str) -> bool:
        """Heuristic to filter article URLs from navigation links."""
        parsed = urlparse(url)

        # Must be same domain (or subdomain)
        if not parsed.netloc.endswith(base_domain) and base_domain not in parsed.netloc:
            return False

        path = parsed.path

        # Must have a non-trivial path
        if not path or path == "/":
            return False

        # Exclude non-article extensions
        if _NON_ARTICLE_EXT.search(path):
            return False

        # Exclude common non-article path segments
        if _NON_ARTICLE_SEGMENTS.search(path):
            return False

        # Heuristic: article URLs typically have path depth >= 2
        # (e.g., /news/some-article or /2024/01/article-slug)
        segments = [s for s in path.split("/") if s]
        if len(segments) < 2:
            return False

        # Positive signals: paths with dates, slugs with hyphens, numeric IDs
        has_date = bool(re.search(r"/\d{4}/", path))
        has_slug = bool(re.search(r"/[a-z0-9]+-[a-z0-9]+-", path, re.IGNORECASE))
        has_numeric_id = bool(re.search(r"/\d{3,}", path))
        has_html_ext = path.endswith((".html", ".htm", ".shtml"))

        if has_date or has_slug or has_numeric_id or has_html_ext:
            return True

        # Still allow if path depth >= 2 (conservative catch-all)
        return len(segments) >= 2
