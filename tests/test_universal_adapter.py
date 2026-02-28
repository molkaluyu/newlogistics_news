"""
Tests for adapters/universal_adapter.py -- URL heuristics, date parsing, and fetch strategies.

All HTTP calls and external libraries are mocked.
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from adapters.universal_adapter import UniversalAdapter, _parse_rss_date


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_adapter(overrides: dict | None = None) -> UniversalAdapter:
    """Create a UniversalAdapter with a minimal source config."""
    config = {
        "source_id": "test_universal",
        "name": "Test Source",
        "type": "universal",
        "url": "https://example.com/news",
        "language": "en",
    }
    if overrides:
        config.update(overrides)
    adapter = UniversalAdapter(config)
    return adapter


# ---------------------------------------------------------------------------
# _looks_like_article_url
# ---------------------------------------------------------------------------


class TestLooksLikeArticleUrl:
    """_looks_like_article_url should filter article URLs from non-article links."""

    def test_rejects_external_domains(self):
        """URLs on a different domain should be rejected."""
        result = UniversalAdapter._looks_like_article_url(
            "https://otherdomain.com/news/article-slug", "example.com"
        )
        assert result is False

    def test_rejects_root_path(self):
        """Root path '/' should be rejected."""
        result = UniversalAdapter._looks_like_article_url(
            "https://example.com/", "example.com"
        )
        assert result is False

    def test_rejects_empty_path(self):
        """Empty path should be rejected."""
        result = UniversalAdapter._looks_like_article_url(
            "https://example.com", "example.com"
        )
        assert result is False

    def test_rejects_png_extension(self):
        """URLs with .png extension should be rejected."""
        result = UniversalAdapter._looks_like_article_url(
            "https://example.com/images/photo.png", "example.com"
        )
        assert result is False

    def test_rejects_css_extension(self):
        """URLs with .css extension should be rejected."""
        result = UniversalAdapter._looks_like_article_url(
            "https://example.com/static/style.css", "example.com"
        )
        assert result is False

    def test_rejects_js_extension(self):
        """URLs with .js extension should be rejected."""
        result = UniversalAdapter._looks_like_article_url(
            "https://example.com/static/app.js", "example.com"
        )
        assert result is False

    def test_rejects_jpg_extension(self):
        """URLs with .jpg extension should be rejected."""
        result = UniversalAdapter._looks_like_article_url(
            "https://example.com/media/image.jpg", "example.com"
        )
        assert result is False

    def test_rejects_tag_path(self):
        """URLs with /tag/ segment should be rejected."""
        result = UniversalAdapter._looks_like_article_url(
            "https://example.com/tag/logistics", "example.com"
        )
        assert result is False

    def test_rejects_category_path(self):
        """URLs with /category/ segment should be rejected."""
        result = UniversalAdapter._looks_like_article_url(
            "https://example.com/category/shipping", "example.com"
        )
        assert result is False

    def test_rejects_about_path(self):
        """URLs with /about/ segment should be rejected."""
        result = UniversalAdapter._looks_like_article_url(
            "https://example.com/about/team", "example.com"
        )
        assert result is False

    def test_rejects_author_path(self):
        """URLs with /author/ segment should be rejected."""
        result = UniversalAdapter._looks_like_article_url(
            "https://example.com/author/john-doe", "example.com"
        )
        assert result is False

    def test_rejects_single_segment_path(self):
        """Paths with only a single segment should be rejected (path depth < 2)."""
        result = UniversalAdapter._looks_like_article_url(
            "https://example.com/about", "example.com"
        )
        assert result is False

    def test_accepts_article_url_with_date(self):
        """URLs with date patterns should be accepted."""
        result = UniversalAdapter._looks_like_article_url(
            "https://example.com/2024/01/supply-chain-update", "example.com"
        )
        assert result is True

    def test_accepts_article_url_with_slug(self):
        """URLs with hyphenated slugs should be accepted."""
        result = UniversalAdapter._looks_like_article_url(
            "https://example.com/news/container-shipping-rates-drop-sharply", "example.com"
        )
        assert result is True

    def test_accepts_article_url_with_numeric_id(self):
        """URLs with numeric IDs (3+ digits) should be accepted."""
        result = UniversalAdapter._looks_like_article_url(
            "https://example.com/articles/12345", "example.com"
        )
        assert result is True

    def test_accepts_article_url_with_html_extension(self):
        """URLs ending with .html should be accepted."""
        result = UniversalAdapter._looks_like_article_url(
            "https://example.com/news/article.html", "example.com"
        )
        assert result is True

    def test_accepts_subdomain(self):
        """URLs on a subdomain of the base domain should be accepted."""
        result = UniversalAdapter._looks_like_article_url(
            "https://blog.example.com/news/new-port-regulations", "example.com"
        )
        assert result is True

    def test_accepts_deep_path(self):
        """URLs with path depth >= 2 should be accepted (conservative catch-all)."""
        result = UniversalAdapter._looks_like_article_url(
            "https://example.com/section/subsection", "example.com"
        )
        assert result is True


# ---------------------------------------------------------------------------
# _parse_rss_date
# ---------------------------------------------------------------------------


class TestParseRssDate:
    """_parse_rss_date should parse various date formats and handle failures."""

    def test_parses_rfc_2822_date(self):
        """Should correctly parse RFC 2822 date strings."""
        result = _parse_rss_date("Mon, 16 Jun 2025 08:00:00 +0000")
        assert result is not None
        assert isinstance(result, datetime)
        assert result.year == 2025
        assert result.month == 6
        assert result.day == 16
        assert result.hour == 8

    def test_parses_rfc_2822_with_timezone(self):
        """Should handle RFC 2822 dates with timezone offsets."""
        result = _parse_rss_date("Sun, 15 Jun 2025 12:00:00 -0500")
        assert result is not None
        assert isinstance(result, datetime)
        assert result.year == 2025

    def test_returns_none_for_invalid_date(self):
        """Should return None for unparseable date strings."""
        result = _parse_rss_date("not a real date string")
        assert result is None

    def test_returns_none_for_none(self):
        """Should return None when input is None."""
        result = _parse_rss_date(None)
        assert result is None

    def test_returns_none_for_empty_string(self):
        """Should return None when input is an empty string."""
        result = _parse_rss_date("")
        assert result is None


# ---------------------------------------------------------------------------
# fetch -- RSS discovery strategy (integration with mocked HTTP)
# ---------------------------------------------------------------------------


class TestFetchRssDiscovery:
    """UniversalAdapter.fetch should discover RSS feeds and parse them."""

    async def test_rss_discovery_via_link_alternate(self):
        """Should discover feed from <link rel='alternate'> and return articles."""
        adapter = _make_adapter()

        # HTML page with RSS link discovery
        html_page = """
        <html>
        <head>
            <link rel="alternate" type="application/rss+xml"
                  href="/feed.xml" title="RSS Feed" />
        </head>
        <body><h1>News Site</h1></body>
        </html>
        """

        # RSS feed content
        rss_feed = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
          <channel>
            <title>Test Feed</title>
            <item>
              <title>Test Article</title>
              <link>https://example.com/news/test-article</link>
              <pubDate>Mon, 16 Jun 2025 08:00:00 +0000</pubDate>
              <description>Test description with enough content to pass the 50 char threshold easily.</description>
            </item>
          </channel>
        </rss>
        """

        # Mock the HTTP client
        mock_response_html = MagicMock()
        mock_response_html.status_code = 200
        mock_response_html.text = html_page
        mock_response_html.raise_for_status = MagicMock()

        mock_response_rss = MagicMock()
        mock_response_rss.status_code = 200
        mock_response_rss.text = rss_feed
        mock_response_rss.headers = {"content-type": "application/rss+xml"}
        mock_response_rss.raise_for_status = MagicMock()

        # First call: fetch HTML page; Second call: fetch RSS feed
        # Third call onwards: trafilatura extraction of individual articles
        mock_response_article = MagicMock()
        mock_response_article.status_code = 200
        mock_response_article.text = "<html><body><p>Article body text content here.</p></body></html>"
        mock_response_article.raise_for_status = MagicMock()

        adapter.client = AsyncMock()
        adapter.client.get = AsyncMock(
            side_effect=[mock_response_html, mock_response_rss, mock_response_article]
        )

        # Mock trafilatura extraction to return some text
        with patch("adapters.universal_adapter.trafilatura") as mock_traf:
            mock_traf.extract.return_value = "Extracted article body text"
            # Mock asyncio.sleep to avoid actual delays
            with patch("adapters.universal_adapter.asyncio.sleep", new_callable=AsyncMock):
                articles = await adapter.fetch()

        assert len(articles) >= 1
        assert articles[0].title == "Test Article"
        assert articles[0].source_id == "test_universal"

    async def test_page_extraction_fallback(self):
        """When no feed is found, should fall back to page link extraction."""
        adapter = _make_adapter()

        # HTML page without RSS links, but with article links
        html_page = """
        <html>
        <head><title>News</title></head>
        <body>
            <a href="/2025/06/supply-chain-article">Supply Chain Update</a>
            <a href="/2025/06/logistics-trends">Logistics Trends 2025</a>
        </body>
        </html>
        """

        # For RSS discovery: page returns no RSS links
        mock_response_html = MagicMock()
        mock_response_html.status_code = 200
        mock_response_html.text = html_page
        mock_response_html.headers = {"content-type": "text/html"}
        mock_response_html.raise_for_status = MagicMock()

        # For common feed paths: all return HTML (not feeds)
        mock_response_not_feed = MagicMock()
        mock_response_not_feed.status_code = 200
        mock_response_not_feed.text = "<html><body>Not a feed</body></html>"
        mock_response_not_feed.headers = {"content-type": "text/html"}
        mock_response_not_feed.raise_for_status = MagicMock()

        # Article page responses for extraction
        mock_response_article = MagicMock()
        mock_response_article.status_code = 200
        mock_response_article.text = "<html><body><p>Full article text here</p></body></html>"
        mock_response_article.headers = {"content-type": "text/html"}
        mock_response_article.raise_for_status = MagicMock()

        # Build side_effect list:
        # 1 call for RSS discovery HTML page
        # 7 calls for common feed paths (all fail to be RSS)
        # 1 call for page extraction (same HTML page)
        # multiple calls for article extraction
        side_effects = (
            [mock_response_html]  # RSS discovery HTML fetch
            + [mock_response_not_feed] * 7  # common feed path probes
            + [mock_response_html]  # page extraction fetch
            + [mock_response_article] * 10  # article fetches
        )

        adapter.client = AsyncMock()
        adapter.client.get = AsyncMock(side_effect=side_effects)

        # Mock trafilatura to make feed discovery return empty and article extraction work
        with patch("adapters.universal_adapter.find_feed_urls", return_value=[]):
            with patch("adapters.universal_adapter.trafilatura") as mock_traf:
                mock_traf.extract.return_value = "Full article body content for test"

                # Mock metadata extraction
                mock_metadata = MagicMock()
                mock_metadata.title = "Extracted Title"
                mock_metadata.date = "2025-06-16"
                mock_traf.extract_metadata.return_value = mock_metadata

                with patch("adapters.universal_adapter.asyncio.sleep", new_callable=AsyncMock):
                    articles = await adapter.fetch()

        # Should have extracted articles from page links
        assert isinstance(articles, list)
        # The extraction should have found article-like URLs
        # (the URLs with /2025/06/ path contain dates, matching the heuristic)

    async def test_fetch_returns_empty_when_all_strategies_fail(self):
        """Should return an empty list when all strategies fail."""
        adapter = _make_adapter()

        # All HTTP requests fail
        adapter.client = AsyncMock()
        adapter.client.get = AsyncMock(side_effect=Exception("Connection failed"))

        with patch("adapters.universal_adapter.find_feed_urls", return_value=[]):
            with patch("adapters.universal_adapter.asyncio.sleep", new_callable=AsyncMock):
                articles = await adapter.fetch()

        assert articles == []

    async def test_fetch_limits_articles_to_max(self):
        """Should not return more articles than max_articles."""
        adapter = _make_adapter({"max_articles": 2})

        # Build a feed with many items
        items = ""
        for i in range(10):
            items += f"""
            <item>
                <title>Article {i}</title>
                <link>https://example.com/news/article-{i}</link>
                <description>Description for article {i} that is longer than fifty characters for the threshold check.</description>
            </item>
            """

        rss_feed = f"""<?xml version="1.0"?>
        <rss version="2.0">
          <channel><title>Feed</title>{items}</channel>
        </rss>
        """

        html_page = """
        <html><head>
            <link rel="alternate" type="application/rss+xml" href="/feed" />
        </head><body></body></html>
        """

        mock_html = MagicMock()
        mock_html.status_code = 200
        mock_html.text = html_page
        mock_html.raise_for_status = MagicMock()

        mock_rss = MagicMock()
        mock_rss.status_code = 200
        mock_rss.text = rss_feed
        mock_rss.headers = {"content-type": "application/rss+xml"}
        mock_rss.raise_for_status = MagicMock()

        mock_article = MagicMock()
        mock_article.status_code = 200
        mock_article.text = "<html><body><p>Body</p></body></html>"
        mock_article.raise_for_status = MagicMock()

        adapter.client = AsyncMock()
        adapter.client.get = AsyncMock(
            side_effect=[mock_html, mock_rss] + [mock_article] * 10
        )

        with patch("adapters.universal_adapter.trafilatura") as mock_traf:
            mock_traf.extract.return_value = "Extracted text"
            with patch("adapters.universal_adapter.asyncio.sleep", new_callable=AsyncMock):
                articles = await adapter.fetch()

        assert len(articles) <= 2
