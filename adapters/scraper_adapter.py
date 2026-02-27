import asyncio
import logging
from datetime import datetime
from urllib.parse import urljoin, urlparse

import trafilatura
from bs4 import BeautifulSoup

from adapters.base import BaseAdapter, RawArticle

logger = logging.getLogger(__name__)

_FETCH_DELAY = 1.0  # seconds between article fetches (politeness)
_DEFAULT_MAX_ARTICLES = 20


def _derive_base_url(url: str) -> str:
    """Derive a base URL (scheme + netloc) from a full URL."""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _parse_date(date_str: str | None, date_format: str | None) -> datetime | None:
    """Parse a date string using the given strptime format, or common fallbacks."""
    if not date_str:
        return None
    date_str = date_str.strip()
    if not date_str:
        return None

    # Try the explicit format first
    if date_format:
        try:
            return datetime.strptime(date_str, date_format)
        except (ValueError, TypeError):
            logger.debug(
                f"Date '{date_str}' did not match format '{date_format}'"
            )

    # Common fallback formats
    fallback_formats = [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d %B %Y",
        "%B %d, %Y",
    ]
    for fmt in fallback_formats:
        try:
            return datetime.strptime(date_str, fmt)
        except (ValueError, TypeError):
            continue

    logger.debug(f"Could not parse date: '{date_str}'")
    return None


class ScraperAdapter(BaseAdapter):
    """Adapter for scraping article links and content from web pages.

    Uses CSS selectors (from ``scraper_config``) to locate article links on an
    index page, then fetches each article page to extract the full text.
    BeautifulSoup handles HTML parsing and selector matching while trafilatura
    provides fallback / primary full-text extraction.
    """

    def __init__(self, source_config: dict):
        super().__init__(source_config)

        scraper_cfg: dict = source_config.get("scraper_config") or {}

        self.index_url: str = source_config["url"]
        self.list_selector: str = scraper_cfg.get("list_selector", "a")
        self.title_selector: str | None = scraper_cfg.get("title_selector")
        self.body_selector: str | None = scraper_cfg.get("body_selector")
        self.date_selector: str | None = scraper_cfg.get("date_selector")
        self.date_format: str | None = scraper_cfg.get("date_format")
        self.base_url: str = scraper_cfg.get(
            "base_url", _derive_base_url(self.index_url)
        )
        self.max_articles: int = int(
            scraper_cfg.get("max_articles", _DEFAULT_MAX_ARTICLES)
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def fetch(self) -> list[RawArticle]:
        """Fetch the index page, discover article links, then scrape each one."""
        logger.info(
            f"Scraping index page: {self.source_name} ({self.index_url})"
        )

        article_links = await self._fetch_article_links()
        if not article_links:
            logger.warning(
                f"No article links found on {self.index_url} "
                f"using selector '{self.list_selector}'"
            )
            return []

        logger.info(
            f"Found {len(article_links)} article link(s) on {self.index_url}, "
            f"fetching up to {self.max_articles}"
        )

        articles: list[RawArticle] = []
        for link_url, link_text in article_links[: self.max_articles]:
            try:
                article = await self._scrape_article(link_url, link_text)
                if article:
                    articles.append(article)
            except Exception as e:
                logger.warning(
                    f"Failed to scrape article {link_url}: {e}"
                )
                continue

            # Politeness delay between fetches
            await asyncio.sleep(_FETCH_DELAY)

        logger.info(
            f"Scraped {len(articles)} article(s) from {self.source_name}"
        )
        return articles

    # ------------------------------------------------------------------
    # Index page: discover links
    # ------------------------------------------------------------------

    async def _fetch_article_links(self) -> list[tuple[str, str]]:
        """Fetch the index page and return a list of (absolute_url, link_text) tuples."""
        try:
            response = await self.client.get(self.index_url)
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to fetch index page {self.index_url}: {e}")
            return []

        soup = BeautifulSoup(response.text, "lxml")
        elements = soup.select(self.list_selector)

        seen_urls: set[str] = set()
        links: list[tuple[str, str]] = []

        for el in elements:
            # The matched element might be an <a> itself or contain one.
            anchor = el if el.name == "a" else el.find("a")
            if anchor is None:
                continue

            href = anchor.get("href")
            if not href:
                continue

            absolute_url = urljoin(self.base_url, href)

            # Deduplicate
            if absolute_url in seen_urls:
                continue
            seen_urls.add(absolute_url)

            link_text = anchor.get_text(strip=True)
            links.append((absolute_url, link_text))

        return links

    # ------------------------------------------------------------------
    # Detail page: scrape a single article
    # ------------------------------------------------------------------

    async def _scrape_article(
        self, url: str, fallback_title: str
    ) -> RawArticle | None:
        """Fetch a single article page and extract its content."""
        try:
            response = await self.client.get(url)
            response.raise_for_status()
        except Exception as e:
            logger.debug(f"Failed to fetch article page {url}: {e}")
            return None

        html = response.text
        soup = BeautifulSoup(html, "lxml")

        # --- title ---
        title = self._extract_title(soup) or fallback_title
        if not title:
            logger.debug(f"No title found for {url}, skipping")
            return None

        # --- body ---
        body_html = self._extract_body_html(soup)
        body_text, body_markdown = self._extract_body_text(html, body_html)

        if not body_text:
            logger.debug(f"No body text extracted for {url}, skipping")
            return None

        # --- date ---
        published_at = self._extract_date(soup)

        return RawArticle(
            source_id=self.source_id,
            source_name=self.source_name,
            url=url,
            title=title.strip(),
            body_text=body_text,
            body_markdown=body_markdown,
            body_html=body_html,
            published_at=published_at,
            language=self.config.get("language", "en"),
            raw_metadata={
                "scraper": True,
                "list_selector": self.list_selector,
            },
        )

    # ------------------------------------------------------------------
    # Extraction helpers
    # ------------------------------------------------------------------

    def _extract_title(self, soup: BeautifulSoup) -> str | None:
        """Extract the article title using the configured CSS selector."""
        if not self.title_selector:
            return None
        el = soup.select_one(self.title_selector)
        if el:
            return el.get_text(strip=True)
        return None

    def _extract_body_html(self, soup: BeautifulSoup) -> str | None:
        """Extract the raw body HTML using the configured CSS selector."""
        if not self.body_selector:
            return None
        el = soup.select_one(self.body_selector)
        if el:
            return str(el)
        return None

    def _extract_body_text(
        self, full_html: str, body_html: str | None
    ) -> tuple[str | None, str | None]:
        """Return (plain_text, markdown) extracted from the article.

        If a ``body_selector`` matched, we use that HTML snippet for
        trafilatura extraction; otherwise we fall back to the full page HTML.
        """
        source_html = body_html if body_html else full_html

        try:
            markdown = trafilatura.extract(
                source_html,
                include_comments=False,
                include_tables=True,
                output_format="markdown",
            )
            plain = trafilatura.extract(
                source_html,
                include_comments=False,
                include_tables=True,
                output_format="txt",
            )
            return plain, markdown
        except Exception as e:
            logger.debug(f"Trafilatura extraction failed: {e}")
            return None, None

    def _extract_date(self, soup: BeautifulSoup) -> datetime | None:
        """Extract and parse the article publication date."""
        if not self.date_selector:
            return None
        el = soup.select_one(self.date_selector)
        if el is None:
            return None

        # Prefer a datetime attribute if present, otherwise use visible text
        date_str = el.get("datetime") or el.get_text(strip=True)
        return _parse_date(date_str, self.date_format)
