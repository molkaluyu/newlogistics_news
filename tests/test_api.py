"""
Tests for api/routes.py -- FastAPI endpoints.

Uses httpx.AsyncClient with a test FastAPI app.  The database is fully
mocked so no real PostgreSQL connection is needed.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers to build mock SQLAlchemy results
# ---------------------------------------------------------------------------


def _scalar_one_result(value):
    """Create a mock Result whose .scalar_one() returns *value*."""
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = value
    return mock_result


def _scalar_one_or_none_result(value):
    """Create a mock Result whose .scalar_one_or_none() returns *value*."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = value
    return mock_result


def _scalars_all_result(items: list):
    """Create a mock Result whose .scalars().all() returns *items*."""
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = items
    mock_result.scalars.return_value = mock_scalars
    return mock_result


# ---------------------------------------------------------------------------
# /api/v1/health
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    async def test_health_endpoint_healthy(self, async_client, mock_app_get_session):
        """GET /api/v1/health should return status, article_count, source_count, last_fetch_at."""
        session = mock_app_get_session
        last_fetch = datetime(2025, 6, 15, 10, 0, 0, tzinfo=timezone.utc)

        # Three sequential execute() calls: article count, source count, last fetch
        session.execute = AsyncMock(
            side_effect=[
                _scalar_one_result(42),       # article count
                _scalar_one_result(10),       # source count
                _scalar_one_result(last_fetch),  # last fetch
            ]
        )

        resp = await async_client.get("/api/v1/health")
        assert resp.status_code == 200

        data = resp.json()
        assert data["status"] == "healthy"
        assert data["article_count"] == 42
        assert data["source_count"] == 10
        assert data["last_fetch_at"] == last_fetch.isoformat()

    async def test_health_endpoint_no_articles(self, async_client, mock_app_get_session):
        """Health should still report healthy with zero articles and no last_fetch."""
        session = mock_app_get_session
        session.execute = AsyncMock(
            side_effect=[
                _scalar_one_result(0),
                _scalar_one_result(0),
                _scalar_one_result(None),
            ]
        )

        resp = await async_client.get("/api/v1/health")
        assert resp.status_code == 200

        data = resp.json()
        assert data["status"] == "healthy"
        assert data["article_count"] == 0
        assert data["last_fetch_at"] is None

    async def test_health_endpoint_db_error(self, async_client, mock_app_get_session):
        """If the DB query raises, health should return unhealthy."""
        session = mock_app_get_session
        session.execute = AsyncMock(side_effect=Exception("connection refused"))

        resp = await async_client.get("/api/v1/health")
        assert resp.status_code == 200

        data = resp.json()
        assert data["status"] == "unhealthy"
        assert "connection refused" in data["error"]


# ---------------------------------------------------------------------------
# /api/v1/sources
# ---------------------------------------------------------------------------


class TestListSources:
    async def test_list_sources(self, async_client, mock_app_get_session, sample_source):
        """GET /api/v1/sources should return a list of source dicts."""
        session = mock_app_get_session
        session.execute = AsyncMock(
            return_value=_scalars_all_result([sample_source])
        )

        resp = await async_client.get("/api/v1/sources")
        assert resp.status_code == 200

        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["source_id"] == "loadstar_rss"
        assert data[0]["name"] == "The Loadstar"
        assert data[0]["enabled"] is True
        assert data[0]["health_status"] == "healthy"

    async def test_list_sources_empty(self, async_client, mock_app_get_session):
        """Empty source list should return an empty array."""
        session = mock_app_get_session
        session.execute = AsyncMock(
            return_value=_scalars_all_result([])
        )

        resp = await async_client.get("/api/v1/sources")
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# /api/v1/articles
# ---------------------------------------------------------------------------


class TestListArticlesEmpty:
    async def test_list_articles_empty(self, async_client, mock_app_get_session):
        """No articles should return a paginated response with empty list."""
        session = mock_app_get_session
        session.execute = AsyncMock(
            side_effect=[
                _scalar_one_result(0),            # count query
                _scalars_all_result([]),           # articles query
            ]
        )

        resp = await async_client.get("/api/v1/articles")
        assert resp.status_code == 200

        data = resp.json()
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["articles"] == []
        assert data["pages"] == 0


class TestListArticlesWithFilters:
    async def test_filter_by_source_id(self, async_client, mock_app_get_session, sample_article):
        """Filtering by source_id should pass through to the query."""
        session = mock_app_get_session
        session.execute = AsyncMock(
            side_effect=[
                _scalar_one_result(1),
                _scalars_all_result([sample_article]),
            ]
        )

        resp = await async_client.get("/api/v1/articles?source_id=loadstar_rss")
        assert resp.status_code == 200

        data = resp.json()
        assert data["total"] == 1
        assert len(data["articles"]) == 1
        assert data["articles"][0]["source_id"] == "loadstar_rss"

    async def test_filter_by_sentiment(self, async_client, mock_app_get_session, sample_article):
        """Filtering by sentiment should work."""
        session = mock_app_get_session
        session.execute = AsyncMock(
            side_effect=[
                _scalar_one_result(1),
                _scalars_all_result([sample_article]),
            ]
        )

        resp = await async_client.get("/api/v1/articles?sentiment=negative")
        assert resp.status_code == 200

        data = resp.json()
        assert data["total"] == 1
        assert data["articles"][0]["sentiment"] == "negative"

    async def test_pagination_params(self, async_client, mock_app_get_session, sample_article):
        """page and page_size should be reflected in the response."""
        session = mock_app_get_session
        session.execute = AsyncMock(
            side_effect=[
                _scalar_one_result(50),
                _scalars_all_result([sample_article]),
            ]
        )

        resp = await async_client.get("/api/v1/articles?page=2&page_size=10")
        assert resp.status_code == 200

        data = resp.json()
        assert data["page"] == 2
        assert data["page_size"] == 10
        assert data["total"] == 50
        assert data["pages"] == 5  # ceil(50/10)

    async def test_article_response_shape(self, async_client, mock_app_get_session, sample_article):
        """Verify the shape of an article object in the list response."""
        session = mock_app_get_session
        session.execute = AsyncMock(
            side_effect=[
                _scalar_one_result(1),
                _scalars_all_result([sample_article]),
            ]
        )

        resp = await async_client.get("/api/v1/articles")
        assert resp.status_code == 200

        article = resp.json()["articles"][0]
        expected_keys = {
            "id", "source_id", "source_name", "url", "title",
            "summary_en", "summary_zh", "language", "published_at",
            "transport_modes", "primary_topic", "content_type",
            "regions", "sentiment", "urgency", "processing_status",
        }
        assert expected_keys == set(article.keys())


# ---------------------------------------------------------------------------
# /api/v1/articles/{article_id}
# ---------------------------------------------------------------------------


class TestGetArticleNotFound:
    async def test_get_article_not_found(self, async_client, mock_app_get_session):
        """Requesting a non-existent article should return 404."""
        session = mock_app_get_session
        session.execute = AsyncMock(
            return_value=_scalar_one_or_none_result(None)
        )

        resp = await async_client.get("/api/v1/articles/nonexistent-uuid")
        assert resp.status_code == 404

        data = resp.json()
        assert data["detail"] == "Article not found"

    async def test_get_article_found(self, async_client, mock_app_get_session, sample_article):
        """Requesting an existing article should return full details."""
        session = mock_app_get_session
        session.execute = AsyncMock(
            return_value=_scalar_one_or_none_result(sample_article)
        )

        resp = await async_client.get(f"/api/v1/articles/{sample_article.id}")
        assert resp.status_code == 200

        data = resp.json()
        assert data["id"] == sample_article.id
        assert data["title"] == sample_article.title
        assert data["body_text"] == sample_article.body_text
        assert data["body_markdown"] == sample_article.body_markdown
        assert data["entities"] == sample_article.entities
        assert data["llm_processed"] is True


# ---------------------------------------------------------------------------
# /api/v1/fetch-logs
# ---------------------------------------------------------------------------


class TestFetchLogs:
    async def test_list_fetch_logs(self, async_client, mock_app_get_session, sample_fetch_log):
        """GET /api/v1/fetch-logs should return a list of log dicts."""
        session = mock_app_get_session
        session.execute = AsyncMock(
            return_value=_scalars_all_result([sample_fetch_log])
        )

        resp = await async_client.get("/api/v1/fetch-logs")
        assert resp.status_code == 200

        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1

        log = data[0]
        assert log["source_id"] == "loadstar_rss"
        assert log["status"] == "success"
        assert log["articles_found"] == 10
        assert log["articles_new"] == 7
        assert log["articles_dedup"] == 3
        assert log["duration_ms"] == 5000
        assert log["error_message"] is None

    async def test_list_fetch_logs_empty(self, async_client, mock_app_get_session):
        """No logs should return an empty list."""
        session = mock_app_get_session
        session.execute = AsyncMock(
            return_value=_scalars_all_result([])
        )

        resp = await async_client.get("/api/v1/fetch-logs")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_fetch_logs_filter_by_source(self, async_client, mock_app_get_session, sample_fetch_log):
        """Filtering fetch logs by source_id should be accepted."""
        session = mock_app_get_session
        session.execute = AsyncMock(
            return_value=_scalars_all_result([sample_fetch_log])
        )

        resp = await async_client.get("/api/v1/fetch-logs?source_id=loadstar_rss")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
