import asyncio
import logging
import os
from datetime import datetime

import trafilatura

from adapters.base import BaseAdapter, RawArticle

logger = logging.getLogger(__name__)

# Try to import dateutil for robust date parsing; fall back to basic parsing.
try:
    from dateutil import parser as dateutil_parser

    _HAS_DATEUTIL = True
except ImportError:  # pragma: no cover
    _HAS_DATEUTIL = False


def _parse_date(date_str: str | None) -> datetime | None:
    """Parse a date string into a datetime object.

    Uses dateutil.parser when available for broad format support.
    Falls back to a handful of common ISO-like formats otherwise.
    """
    if not date_str:
        return None

    if _HAS_DATEUTIL:
        try:
            return dateutil_parser.parse(date_str)
        except (ValueError, OverflowError):
            return None

    # Fallback: try common ISO formats manually.
    for fmt in (
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def _resolve_secret(value: str) -> str:
    """If *value* starts with ``$``, read the corresponding environment variable.

    Otherwise return *value* as-is.
    """
    if value.startswith("$"):
        env_name = value[1:]
        resolved = os.environ.get(env_name)
        if resolved is None:
            raise ValueError(
                f"Environment variable '{env_name}' (referenced as '{value}') is not set"
            )
        return resolved
    return value


def _extract_by_dot_path(data: dict | list, path: str):
    """Walk *data* using a dot-separated *path* (e.g. ``"data.articles"``).

    Each segment is used as a dictionary key.  Returns ``None`` when the path
    cannot be resolved.
    """
    current = data
    for segment in path.split("."):
        if isinstance(current, dict):
            current = current.get(segment)
        else:
            return None
        if current is None:
            return None
    return current


class APIAdapter(BaseAdapter):
    """Adapter for REST/JSON API data sources.

    Configuration is driven by ``parser_config`` inside the source definition.
    Supported keys:

    * **Authentication** --
      ``auth_type`` (``"api_key_header"`` | ``"api_key_query"`` |
      ``"bearer_token"`` | ``null``), ``auth_key``, ``auth_value``.
    * **Pagination** --
      ``pagination_type`` (``"page_number"`` | ``"offset"`` | ``"cursor"`` |
      ``null``), ``pagination_param``, ``page_size_param``, ``page_size``,
      ``max_pages`` (default 10).
    * **Response mapping** --
      ``items_path`` (dot-notation path to the items array),
      ``mapping`` (dict mapping ``RawArticle`` field names to response keys).
    * **Full-text extraction** --
      ``fetch_full_text`` (bool, default ``false``) -- when ``true`` and the
      API response does not include a body, fetch each article URL and use
      *trafilatura* to extract the full text.
    """

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def __init__(self, source_config: dict):
        super().__init__(source_config)
        self.parser_config: dict = source_config.get("parser_config") or {}
        self.url: str = source_config["url"]

        # Authentication --------------------------------------------------
        self.auth_type: str | None = self.parser_config.get("auth_type")
        self.auth_key: str | None = self.parser_config.get("auth_key")
        self._auth_value: str | None = self.parser_config.get("auth_value")

        # Pagination ------------------------------------------------------
        self.pagination_type: str | None = self.parser_config.get("pagination_type")
        self.pagination_param: str | None = self.parser_config.get("pagination_param")
        self.page_size_param: str | None = self.parser_config.get("page_size_param")
        self.page_size: int | None = self.parser_config.get("page_size")
        self.max_pages: int = self.parser_config.get("max_pages", 10)

        # Response mapping ------------------------------------------------
        self.items_path: str | None = self.parser_config.get("items_path")
        self.mapping: dict = self.parser_config.get("mapping") or {}

        # Full-text -------------------------------------------------------
        self.fetch_full_text: bool = self.parser_config.get("fetch_full_text", False)

    # ------------------------------------------------------------------
    # Authentication helpers
    # ------------------------------------------------------------------

    def _get_auth_value(self) -> str:
        """Return the resolved authentication secret."""
        if self._auth_value is None:
            raise ValueError("auth_value is required when auth_type is set")
        return _resolve_secret(self._auth_value)

    def _apply_auth_headers(self, headers: dict) -> None:
        """Mutate *headers* in-place to add header-based authentication."""
        if self.auth_type == "api_key_header":
            headers[self.auth_key] = self._get_auth_value()
        elif self.auth_type == "bearer_token":
            headers["Authorization"] = f"Bearer {self._get_auth_value()}"

    def _apply_auth_params(self, params: dict) -> None:
        """Mutate *params* in-place to add query-param authentication."""
        if self.auth_type == "api_key_query":
            params[self.auth_key] = self._get_auth_value()

    # ------------------------------------------------------------------
    # Pagination helpers
    # ------------------------------------------------------------------

    def _apply_pagination_params(
        self, params: dict, page: int, offset: int, cursor: str | None
    ) -> None:
        """Mutate *params* to include the pagination query parameters."""
        if self.pagination_type is None:
            return

        if self.page_size_param and self.page_size is not None:
            params[self.page_size_param] = self.page_size

        if self.pagination_type == "page_number":
            params[self.pagination_param] = page
        elif self.pagination_type == "offset":
            params[self.pagination_param] = offset
        elif self.pagination_type == "cursor":
            if cursor is not None:
                params[self.pagination_param] = cursor

    @staticmethod
    def _extract_next_cursor(data: dict | list) -> str | None:
        """Try to find a ``next_cursor`` / ``next`` / ``cursor`` value in *data*.

        Returns ``None`` when no cursor can be found (signals the last page).
        """
        if not isinstance(data, dict):
            return None

        # Check common locations for cursor values.
        for key in ("next_cursor", "cursor", "next", "next_page"):
            value = data.get(key)
            if value:
                return str(value)

        # Check inside a nested "pagination" / "meta" / "paging" object.
        for wrapper_key in ("pagination", "meta", "paging"):
            wrapper = data.get(wrapper_key)
            if isinstance(wrapper, dict):
                for key in ("next_cursor", "cursor", "next", "next_page"):
                    value = wrapper.get(key)
                    if value:
                        return str(value)

        return None

    # ------------------------------------------------------------------
    # Core fetch logic
    # ------------------------------------------------------------------

    async def fetch(self) -> list[RawArticle]:
        """Fetch articles from the configured REST API endpoint."""
        logger.info(f"Fetching API source: {self.source_name} ({self.url})")

        all_items: list[dict] = []
        page = 1
        offset = 0
        cursor: str | None = None

        for page_num in range(1, self.max_pages + 1):
            items, next_cursor, raw_response = await self._fetch_page(
                page=page, offset=offset, cursor=cursor
            )

            if items is None:
                # Request failed -- stop pagination.
                break

            all_items.extend(items)
            logger.debug(
                f"Page {page_num}: received {len(items)} items "
                f"(total so far: {len(all_items)})"
            )

            # Determine whether we should continue paginating.
            if not items:
                break

            if self.pagination_type is None:
                break

            if self.pagination_type == "cursor":
                cursor = next_cursor or self._extract_next_cursor(raw_response)
                if not cursor:
                    break
            elif self.pagination_type == "page_number":
                page += 1
            elif self.pagination_type == "offset":
                offset += len(items)

            # If the page returned fewer items than page_size, assume last page.
            if self.page_size is not None and len(items) < self.page_size:
                break

        # Convert raw dicts into RawArticle instances.
        articles: list[RawArticle] = []
        for item in all_items:
            try:
                article = self._map_item(item)
                if article:
                    articles.append(article)
            except Exception as exc:
                logger.warning(f"Failed to map API item: {exc}")
                continue

        # Optional full-text extraction for articles missing a body.
        if self.fetch_full_text:
            articles = await self._enrich_full_text(articles)

        logger.info(
            f"Fetched {len(articles)} articles from {self.source_name}"
        )
        return articles

    async def _fetch_page(
        self,
        page: int,
        offset: int,
        cursor: str | None,
    ) -> tuple[list[dict] | None, str | None, dict | list | None]:
        """Fetch a single page of results from the API.

        Returns ``(items, next_cursor, raw_response)``.  On failure the first
        element is ``None``.
        """
        headers: dict = {}
        params: dict = {}

        self._apply_auth_headers(headers)
        self._apply_auth_params(params)
        self._apply_pagination_params(params, page=page, offset=offset, cursor=cursor)

        try:
            response = await self.client.get(
                self.url, headers=headers, params=params
            )
            response.raise_for_status()
        except Exception as exc:
            logger.error(
                f"API request failed for {self.source_name} ({self.url}): {exc}"
            )
            return None, None, None

        try:
            data = response.json()
        except Exception as exc:
            logger.error(
                f"Failed to decode JSON from {self.source_name}: {exc}"
            )
            return None, None, None

        # Extract the items array using the configured path.
        if self.items_path:
            items = _extract_by_dot_path(data, self.items_path)
        else:
            # Assume the top-level response is the items list.
            items = data

        if not isinstance(items, list):
            logger.warning(
                f"Expected a list at items_path='{self.items_path}' "
                f"but got {type(items).__name__} for {self.source_name}"
            )
            return None, None, data

        # Attempt to find a cursor for cursor-based pagination.
        next_cursor: str | None = None
        if self.pagination_type == "cursor" and isinstance(data, dict):
            next_cursor = self._extract_next_cursor(data)

        return items, next_cursor, data

    # ------------------------------------------------------------------
    # Mapping
    # ------------------------------------------------------------------

    def _map_item(self, item: dict) -> RawArticle | None:
        """Convert a single response dict into a :class:`RawArticle`.

        Uses the ``mapping`` from ``parser_config`` to translate keys.
        """

        def _get(field_name: str, default=None):
            """Look up a RawArticle field in *item* using the mapping."""
            source_key = self.mapping.get(field_name, field_name)
            return _extract_by_dot_path(item, source_key) if source_key else default

        url = _get("url")
        title = _get("title")

        if not url or not title:
            logger.debug(f"Skipping item without url or title: {item!r:.200}")
            return None

        published_at = _parse_date(_get("published_at"))

        return RawArticle(
            source_id=self.source_id,
            source_name=self.source_name,
            url=str(url),
            title=str(title).strip(),
            body_text=_get("body_text"),
            body_markdown=_get("body_markdown"),
            body_html=_get("body_html"),
            published_at=published_at,
            language=_get("language") or self.config.get("language", "en"),
            raw_metadata={"api_item": item},
        )

    # ------------------------------------------------------------------
    # Full-text enrichment
    # ------------------------------------------------------------------

    async def _enrich_full_text(
        self, articles: list[RawArticle]
    ) -> list[RawArticle]:
        """For articles missing body text, fetch the URL and extract with trafilatura."""
        enriched: list[RawArticle] = []
        for article in articles:
            if article.body_text:
                enriched.append(article)
                continue

            markdown, plain = await self._extract_full_text(article.url)
            if plain:
                article.body_text = plain
            if markdown:
                article.body_markdown = markdown

            enriched.append(article)

            # Be polite between full-page fetches.
            await asyncio.sleep(0.5)

        return enriched

    async def _extract_full_text(
        self, url: str
    ) -> tuple[str | None, str | None]:
        """Fetch *url* and extract full text via trafilatura.

        Returns ``(markdown, plain_text)``.
        """
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            html = response.text
        except Exception as exc:
            logger.debug(f"Failed to fetch full page {url}: {exc}")
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
        except Exception as exc:
            logger.debug(f"Trafilatura extraction failed for {url}: {exc}")
            return None, None
