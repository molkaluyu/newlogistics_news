"""
Tests for processing/deduplicator.py -- URL-based article deduplication.

All database access is mocked; no real PostgreSQL connection is needed.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from processing.deduplicator import Deduplicator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_get_session(mock_session):
    """Create a patched get_session that yields mock_session."""
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _fake():
        yield mock_session

    return _fake


# ---------------------------------------------------------------------------
# is_duplicate
# ---------------------------------------------------------------------------


class TestIsDuplicateNewUrl:
    async def test_new_url_returns_false(self):
        """A URL not in the database should not be considered a duplicate."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "processing.deduplicator.get_session",
            new=_make_fake_get_session(mock_session),
        ):
            dedup = Deduplicator()
            result = await dedup.is_duplicate("https://example.com/new-article")

        assert result is False

    async def test_new_url_queries_database(self):
        """is_duplicate should execute a SELECT query against the Article table."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "processing.deduplicator.get_session",
            new=_make_fake_get_session(mock_session),
        ):
            dedup = Deduplicator()
            await dedup.is_duplicate("https://example.com/test")

        mock_session.execute.assert_called_once()


class TestIsDuplicateExistingUrl:
    async def test_existing_url_returns_true(self):
        """A URL that exists in the database should be considered a duplicate."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        # scalar_one_or_none returns a non-None value (the article ID)
        mock_result.scalar_one_or_none.return_value = "some-uuid-value"
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "processing.deduplicator.get_session",
            new=_make_fake_get_session(mock_session),
        ):
            dedup = Deduplicator()
            result = await dedup.is_duplicate("https://example.com/existing-article")

        assert result is True

    async def test_existing_url_integer_id(self):
        """Even if the ID is an integer, a truthy value means duplicate."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = 42
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "processing.deduplicator.get_session",
            new=_make_fake_get_session(mock_session),
        ):
            dedup = Deduplicator()
            result = await dedup.is_duplicate("https://example.com/existing")

        assert result is True


# ---------------------------------------------------------------------------
# filter_new
# ---------------------------------------------------------------------------


class TestFilterNewUrls:
    async def test_all_new_urls(self):
        """When no URLs exist in the DB, all should be returned as new."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []  # no existing URLs
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "processing.deduplicator.get_session",
            new=_make_fake_get_session(mock_session),
        ):
            dedup = Deduplicator()
            urls = [
                "https://example.com/article-1",
                "https://example.com/article-2",
                "https://example.com/article-3",
            ]
            result = await dedup.filter_new(urls)

        assert result == set(urls)

    async def test_some_existing_urls(self):
        """Only URLs not already in the DB should be returned."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        # Simulate that article-1 already exists in the DB
        mock_result.fetchall.return_value = [
            ("https://example.com/article-1",),
        ]
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "processing.deduplicator.get_session",
            new=_make_fake_get_session(mock_session),
        ):
            dedup = Deduplicator()
            urls = [
                "https://example.com/article-1",
                "https://example.com/article-2",
                "https://example.com/article-3",
            ]
            result = await dedup.filter_new(urls)

        assert "https://example.com/article-1" not in result
        assert "https://example.com/article-2" in result
        assert "https://example.com/article-3" in result
        assert len(result) == 2

    async def test_all_existing_urls(self):
        """When all URLs exist in the DB, the result should be empty."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            ("https://example.com/article-1",),
            ("https://example.com/article-2",),
        ]
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "processing.deduplicator.get_session",
            new=_make_fake_get_session(mock_session),
        ):
            dedup = Deduplicator()
            urls = [
                "https://example.com/article-1",
                "https://example.com/article-2",
            ]
            result = await dedup.filter_new(urls)

        assert result == set()

    async def test_empty_url_list(self):
        """An empty input list should return an empty set without querying the DB."""
        # No need to mock the session at all -- the code returns early for empty lists
        dedup = Deduplicator()
        result = await dedup.filter_new([])
        assert result == set()

    async def test_returns_set_type(self):
        """filter_new should always return a set."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "processing.deduplicator.get_session",
            new=_make_fake_get_session(mock_session),
        ):
            dedup = Deduplicator()
            result = await dedup.filter_new(["https://example.com/test"])

        assert isinstance(result, set)

    async def test_duplicate_input_urls_deduplicated(self):
        """Duplicate URLs in the input list should be collapsed since the result is a set."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "processing.deduplicator.get_session",
            new=_make_fake_get_session(mock_session),
        ):
            dedup = Deduplicator()
            urls = [
                "https://example.com/article-1",
                "https://example.com/article-1",
                "https://example.com/article-2",
            ]
            result = await dedup.filter_new(urls)

        # set(urls) has 2 elements; none are in DB so both should be returned
        assert len(result) == 2
