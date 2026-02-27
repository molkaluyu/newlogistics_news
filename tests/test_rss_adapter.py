"""
Tests for adapters/rss_adapter.py -- RSS feed fetching and parsing.

All HTTP requests and external libraries are mocked; no real network calls.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from adapters.base import RawArticle
from adapters.rss_adapter import RSSAdapter, _parse_date


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_source_config(**overrides) -> dict:
    """Create a minimal source config dict for RSSAdapter."""
    base = {
        "source_id": "test_rss",
        "name": "Test Source",
        "type": "rss",
        "url": "https://example.com/feed.xml",
        "language": "en",
    }
    base.update(overrides)
    return base


def _make_rss_entry(**overrides) -> MagicMock:
    """Create a MagicMock that behaves like a feedparser entry."""
    entry = MagicMock()
    entry.link = overrides.get("link", "https://example.com/article-1")
    entry.title = overrides.get("title", "Test Article Title")
    entry.published = overrides.get("published", "Mon, 16 Jun 2025 08:00:00 +0000")
    entry.updated = overrides.get("updated", None)
    entry.summary = overrides.get("summary", "<p>A test summary of decent length that exceeds fifty characters easily.</p>")
    entry.author = overrides.get("author", "Test Author")
    entry.tags = overrides.get("tags", [MagicMock(term="logistics")])

    # Control hasattr behavior
    attrs = {"summary", "author", "tags", "link", "title", "published"}
    attrs.update(overrides.get("_attrs", set()))

    # Remove attributes the caller explicitly wants absent
    for attr_name in overrides.get("_absent", []):
        attrs.discard(attr_name)
        delattr(entry, attr_name)

    return entry


# ---------------------------------------------------------------------------
# _parse_date
# ---------------------------------------------------------------------------


class TestParseDateRfc2822:
    """_parse_date should handle RFC 2822 date strings."""

    def test_standard_rfc2822(self):
        result = _parse_date("Mon, 16 Jun 2025 08:00:00 +0000")
        assert result is not None
        assert result.year == 2025
        assert result.month == 6
        assert result.day == 16
        assert result.hour == 8

    def test_rfc2822_with_timezone_offset(self):
        result = _parse_date("Tue, 17 Jun 2025 10:30:00 +0530")
        assert result is not None
        assert result.year == 2025


class TestParseDateIso8601:
    """_parse_date should handle ISO 8601 strings via feedparser fallback."""

    def test_iso8601_via_feedparser(self):
        """If parsedate_to_datetime fails, feedparser._parse_date is tried."""
        with patch("adapters.rss_adapter.feedparser") as mock_fp:
            mock_fp._parse_date.return_value = (2025, 6, 15, 10, 30, 0, 0, 0, 0)
            # Force parsedate_to_datetime to fail so the feedparser branch runs
            with patch("adapters.rss_adapter.parsedate_to_datetime", side_effect=ValueError):
                result = _parse_date("2025-06-15T10:30:00Z")
            assert result is not None
            assert result.year == 2025
            assert result.month == 6


class TestParseDateEdgeCases:
    """_parse_date should handle None and invalid strings gracefully."""

    def test_none_returns_none(self):
        assert _parse_date(None) is None

    def test_empty_string_returns_none(self):
        assert _parse_date("") is None

    def test_invalid_string_returns_none(self):
        with patch("adapters.rss_adapter.feedparser") as mock_fp:
            mock_fp._parse_date.return_value = None
            result = _parse_date("not-a-date-at-all")
            assert result is None


# ---------------------------------------------------------------------------
# RSSAdapter.fetch
# ---------------------------------------------------------------------------


class TestRSSAdapterFetch:
    """RSSAdapter.fetch should parse feed XML and return RawArticle list."""

    async def test_fetch_success_returns_articles(self):
        """A successful HTTP response with valid feed returns articles."""
        config = _make_source_config()
        adapter = RSSAdapter(config)

        mock_response = MagicMock()
        mock_response.text = "<rss>...</rss>"
        mock_response.raise_for_status = MagicMock()

        adapter.client = AsyncMock()
        adapter.client.get = AsyncMock(return_value=mock_response)

        mock_entry = _make_rss_entry()
        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.entries = [mock_entry]

        with patch("adapters.rss_adapter.feedparser.parse", return_value=mock_feed):
            with patch.object(adapter, "_process_entry", new_callable=AsyncMock) as mock_proc:
                mock_proc.return_value = RawArticle(
                    source_id="test_rss",
                    source_name="Test Source",
                    url="https://example.com/article-1",
                    title="Test Article Title",
                )
                with patch("adapters.rss_adapter.asyncio.sleep", new_callable=AsyncMock):
                    articles = await adapter.fetch()

        assert len(articles) == 1
        assert articles[0].title == "Test Article Title"

    async def test_fetch_http_error_returns_empty(self):
        """If the HTTP request fails, fetch should return an empty list."""
        config = _make_source_config()
        adapter = RSSAdapter(config)

        adapter.client = AsyncMock()
        adapter.client.get = AsyncMock(side_effect=Exception("Connection refused"))

        articles = await adapter.fetch()
        assert articles == []

    async def test_fetch_bozo_no_entries_returns_empty(self):
        """A bozo feed with no entries should return an empty list."""
        config = _make_source_config()
        adapter = RSSAdapter(config)

        mock_response = MagicMock()
        mock_response.text = "<invalid-xml>"
        mock_response.raise_for_status = MagicMock()

        adapter.client = AsyncMock()
        adapter.client.get = AsyncMock(return_value=mock_response)

        mock_feed = MagicMock()
        mock_feed.bozo = True
        mock_feed.entries = []
        mock_feed.bozo_exception = Exception("malformed XML")

        with patch("adapters.rss_adapter.feedparser.parse", return_value=mock_feed):
            articles = await adapter.fetch()

        assert articles == []

    async def test_fetch_skips_failed_entries(self):
        """If _process_entry raises, that entry is skipped."""
        config = _make_source_config()
        adapter = RSSAdapter(config)

        mock_response = MagicMock()
        mock_response.text = "<rss>...</rss>"
        mock_response.raise_for_status = MagicMock()

        adapter.client = AsyncMock()
        adapter.client.get = AsyncMock(return_value=mock_response)

        entry_good = _make_rss_entry(title="Good Article")
        entry_bad = _make_rss_entry(title="Bad Article")

        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.entries = [entry_bad, entry_good]

        good_article = RawArticle(
            source_id="test_rss",
            source_name="Test Source",
            url="https://example.com/good",
            title="Good Article",
        )

        with patch("adapters.rss_adapter.feedparser.parse", return_value=mock_feed):
            with patch.object(
                adapter,
                "_process_entry",
                new_callable=AsyncMock,
                side_effect=[Exception("parse error"), good_article],
            ):
                with patch("adapters.rss_adapter.asyncio.sleep", new_callable=AsyncMock):
                    articles = await adapter.fetch()

        assert len(articles) == 1
        assert articles[0].title == "Good Article"


# ---------------------------------------------------------------------------
# _process_entry
# ---------------------------------------------------------------------------


class TestProcessEntry:
    """_process_entry should convert a feedparser entry to a RawArticle."""

    async def test_returns_raw_article(self):
        """A valid entry with full text produces a RawArticle."""
        config = _make_source_config()
        adapter = RSSAdapter(config)

        entry = _make_rss_entry()

        with patch.object(
            adapter,
            "_extract_full_text",
            new_callable=AsyncMock,
            return_value=("# Markdown body", "Plain body text"),
        ):
            article = await adapter._process_entry(entry)

        assert article is not None
        assert article.source_id == "test_rss"
        assert article.title == "Test Article Title"
        assert article.body_text == "Plain body text"
        assert article.body_markdown == "# Markdown body"
        assert article.raw_metadata.get("rss_author") == "Test Author"
        assert article.raw_metadata.get("rss_tags") == ["logistics"]

    async def test_no_link_returns_none(self):
        """An entry without a link should return None."""
        config = _make_source_config()
        adapter = RSSAdapter(config)

        entry = MagicMock(spec=[])
        entry.link = None
        entry.title = "Has a title"

        # getattr(..., "link", None) returns None when link is None
        with patch("builtins.getattr", side_effect=lambda obj, name, default=None: {
            "link": None,
            "title": "Has a title",
        }.get(name, default)):
            # Simpler: just set the attribute
            pass

        entry = MagicMock()
        entry.link = None
        entry.title = "Title"
        # Override getattr behavior
        original_getattr = getattr

        article = await adapter._process_entry(entry)
        # entry.link is None so the adapter returns None
        # Actually, MagicMock().link returns a MagicMock (truthy), we need spec
        entry2 = MagicMock()
        type(entry2).link = None
        type(entry2).title = "Title"
        # For getattr to return None, use a SimpleNamespace
        from types import SimpleNamespace
        entry_ns = SimpleNamespace(title="Has a title")
        # No link attribute at all
        article = await adapter._process_entry(entry_ns)
        assert article is None

    async def test_fallback_to_rss_summary(self):
        """If full text extraction returns None, falls back to RSS summary."""
        config = _make_source_config()
        adapter = RSSAdapter(config)

        entry = _make_rss_entry(
            summary="<p>This is a long enough summary text that should exceed the fifty character minimum for the summary extraction method.</p>"
        )

        with patch.object(
            adapter,
            "_extract_full_text",
            new_callable=AsyncMock,
            return_value=(None, None),
        ):
            article = await adapter._process_entry(entry)

        assert article is not None
        # The body_text should be the cleaned RSS summary (HTML stripped)
        assert "<p>" not in (article.body_text or "")


# ---------------------------------------------------------------------------
# _extract_full_text
# ---------------------------------------------------------------------------


class TestExtractFullText:
    """_extract_full_text should fetch a page and extract text via trafilatura."""

    async def test_success_returns_markdown_and_plain(self):
        """Successful extraction returns (markdown, plain_text) tuple."""
        config = _make_source_config()
        adapter = RSSAdapter(config)

        mock_response = MagicMock()
        mock_response.text = "<html><body><p>Article content</p></body></html>"
        mock_response.raise_for_status = MagicMock()

        adapter.client = AsyncMock()
        adapter.client.get = AsyncMock(return_value=mock_response)

        with patch("adapters.rss_adapter.trafilatura.extract") as mock_extract:
            mock_extract.side_effect = [
                "# Markdown content",  # first call (markdown format)
                "Plain content",       # second call (txt format)
            ]
            md, plain = await adapter._extract_full_text("https://example.com/page")

        assert md == "# Markdown content"
        assert plain == "Plain content"

    async def test_http_error_returns_none_tuple(self):
        """If the page fetch fails, return (None, None)."""
        config = _make_source_config()
        adapter = RSSAdapter(config)

        adapter.client = AsyncMock()
        adapter.client.get = AsyncMock(side_effect=Exception("404 Not Found"))

        md, plain = await adapter._extract_full_text("https://example.com/missing")
        assert md is None
        assert plain is None

    async def test_trafilatura_error_returns_none_tuple(self):
        """If trafilatura raises, return (None, None)."""
        config = _make_source_config()
        adapter = RSSAdapter(config)

        mock_response = MagicMock()
        mock_response.text = "<html></html>"
        mock_response.raise_for_status = MagicMock()

        adapter.client = AsyncMock()
        adapter.client.get = AsyncMock(return_value=mock_response)

        with patch(
            "adapters.rss_adapter.trafilatura.extract",
            side_effect=Exception("extraction error"),
        ):
            md, plain = await adapter._extract_full_text("https://example.com/page")

        assert md is None
        assert plain is None


# ---------------------------------------------------------------------------
# _get_rss_summary
# ---------------------------------------------------------------------------


class TestGetRssSummary:
    """_get_rss_summary should extract and clean summary text from entries."""

    def test_html_content_stripped(self):
        """HTML tags in the summary should be removed."""
        entry = MagicMock()
        entry.summary = "<p>Rates on major east-west routes have dropped significantly in the latest quarter.</p>"
        result = RSSAdapter._get_rss_summary(entry)
        assert result is not None
        assert "<p>" not in result
        assert "Rates on major east-west routes" in result

    def test_plain_text_returned(self):
        """Plain text summaries exceeding 50 chars should be returned as-is."""
        entry = MagicMock()
        entry.summary = "Air cargo demand continues to rise across all major trade lanes globally."
        result = RSSAdapter._get_rss_summary(entry)
        assert result == "Air cargo demand continues to rise across all major trade lanes globally."

    def test_short_text_returns_none(self):
        """Summaries shorter than 50 characters should return None."""
        entry = MagicMock()
        entry.summary = "Short text"
        result = RSSAdapter._get_rss_summary(entry)
        assert result is None

    def test_none_summary_returns_none(self):
        """An entry with no summary or description should return None."""
        entry = MagicMock(spec=[])
        # No summary or description attribute
        result = RSSAdapter._get_rss_summary(entry)
        assert result is None

    def test_description_fallback(self):
        """If summary is absent, description should be used."""
        entry = MagicMock(spec=["description"])
        entry.description = "A description that is long enough to exceed the fifty character minimum for summary extraction."
        result = RSSAdapter._get_rss_summary(entry)
        assert result is not None
        assert "description" in result.lower()
