"""
Tests for semantic search and related articles API endpoints in api/routes.py.

Uses httpx.AsyncClient with a test FastAPI app.  The database and LLM pipeline
are fully mocked so no real PostgreSQL or OpenAI connection is needed.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


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


def _make_fake_article(**overrides):
    """Create a MagicMock acting as an Article ORM object."""
    defaults = {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "source_id": "loadstar_rss",
        "source_name": "The Loadstar",
        "url": "https://theloadstar.com/article/supply-chain",
        "title": "Supply chain crisis deepens",
        "body_text": "Global supply chains continue to face challenges...",
        "body_markdown": "# Supply chain crisis\n\nGlobal supply chains...",
        "language": "en",
        "published_at": datetime(2025, 6, 15, 10, 30, 0, tzinfo=timezone.utc),
        "fetched_at": datetime(2025, 6, 15, 11, 0, 0, tzinfo=timezone.utc),
        "summary_en": "Supply chains face major challenges globally.",
        "summary_zh": None,
        "transport_modes": ["ocean"],
        "primary_topic": "supply_chain_disruption",
        "secondary_topics": ["port_congestion"],
        "content_type": "news",
        "regions": ["global"],
        "entities": {"companies": ["Maersk"]},
        "sentiment": "negative",
        "market_impact": "high",
        "urgency": "high",
        "key_metrics": [],
        "embedding": [0.1] * 1024,
        "raw_metadata": {},
        "processing_status": "completed",
        "llm_processed": True,
    }
    defaults.update(overrides)
    mock = MagicMock()
    for key, value in defaults.items():
        setattr(mock, key, value)
    return mock


def _build_test_client(mock_session):
    """Create an httpx AsyncClient wired to a test FastAPI app with mocked DB."""
    from api.routes import router
    from fastapi import FastAPI

    test_app = FastAPI()
    test_app.include_router(router, prefix="/api/v1")

    transport = ASGITransport(app=test_app)
    return AsyncClient(transport=transport, base_url="http://test")


# ---------------------------------------------------------------------------
# GET /api/v1/articles/search/semantic
# ---------------------------------------------------------------------------


class TestSemanticSearch:
    async def test_success_with_results(self):
        """Semantic search should return matching articles with similarity scores."""
        mock_session = AsyncMock()

        fake_article = _make_fake_article()
        # Mock the DB result: list of Row-like objects with .Article and .distance
        mock_row = MagicMock()
        mock_row.Article = fake_article
        mock_row.distance = 0.15  # cosine distance, similarity = 1.0 - 0.15 = 0.85

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row]
        mock_session.execute = AsyncMock(return_value=mock_result)

        fake_embedding = [0.1] * 1024

        with patch(
            "api.routes.get_session",
            new=_make_fake_get_session(mock_session),
        ), patch(
            "api.routes.llm_settings"
        ) as mock_llm_settings, patch(
            "processing.llm_pipeline.ArticleProcessor",
        ) as MockProcessor:
            mock_llm_settings.llm_api_key = "test-key"

            mock_proc_instance = AsyncMock()
            mock_proc_instance.generate_embedding = AsyncMock(return_value=fake_embedding)
            mock_proc_instance.close = AsyncMock()
            MockProcessor.return_value = mock_proc_instance

            async with _build_test_client(mock_session) as client:
                resp = await client.get(
                    "/api/v1/articles/search/semantic?q=supply+chain+disruption"
                )

        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "supply chain disruption"
        assert len(data["results"]) == 1
        assert data["results"][0]["id"] == fake_article.id
        assert data["results"][0]["title"] == fake_article.title
        assert data["results"][0]["similarity"] == 0.85

    async def test_no_llm_key_returns_503(self):
        """When LLM_API_KEY is not configured, should return 503."""
        mock_session = AsyncMock()

        with patch(
            "api.routes.get_session",
            new=_make_fake_get_session(mock_session),
        ), patch(
            "api.routes.llm_settings"
        ) as mock_llm_settings:
            mock_llm_settings.llm_api_key = ""

            async with _build_test_client(mock_session) as client:
                resp = await client.get(
                    "/api/v1/articles/search/semantic?q=test+query"
                )

        assert resp.status_code == 503
        assert "LLM_API_KEY not configured" in resp.json()["detail"]

    async def test_embedding_failure_returns_502(self):
        """When embedding generation fails, should return 502."""
        mock_session = AsyncMock()

        with patch(
            "api.routes.get_session",
            new=_make_fake_get_session(mock_session),
        ), patch(
            "api.routes.llm_settings"
        ) as mock_llm_settings, patch(
            "processing.llm_pipeline.ArticleProcessor",
        ) as MockProcessor:
            mock_llm_settings.llm_api_key = "test-key"

            mock_proc_instance = AsyncMock()
            mock_proc_instance.generate_embedding = AsyncMock(
                side_effect=Exception("API timeout")
            )
            mock_proc_instance.close = AsyncMock()
            MockProcessor.return_value = mock_proc_instance

            async with _build_test_client(mock_session) as client:
                resp = await client.get(
                    "/api/v1/articles/search/semantic?q=test+query"
                )

        assert resp.status_code == 502
        assert "Failed to generate query embedding" in resp.json()["detail"]

    async def test_missing_query_param_returns_422(self):
        """Missing the required 'q' parameter should return 422 validation error."""
        mock_session = AsyncMock()

        with patch(
            "api.routes.get_session",
            new=_make_fake_get_session(mock_session),
        ):
            async with _build_test_client(mock_session) as client:
                resp = await client.get("/api/v1/articles/search/semantic")

        assert resp.status_code == 422

    async def test_empty_results(self):
        """When no articles match, should return empty results list."""
        mock_session = AsyncMock()

        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        fake_embedding = [0.1] * 1024

        with patch(
            "api.routes.get_session",
            new=_make_fake_get_session(mock_session),
        ), patch(
            "api.routes.llm_settings"
        ) as mock_llm_settings, patch(
            "processing.llm_pipeline.ArticleProcessor",
        ) as MockProcessor:
            mock_llm_settings.llm_api_key = "test-key"

            mock_proc_instance = AsyncMock()
            mock_proc_instance.generate_embedding = AsyncMock(return_value=fake_embedding)
            mock_proc_instance.close = AsyncMock()
            MockProcessor.return_value = mock_proc_instance

            async with _build_test_client(mock_session) as client:
                resp = await client.get(
                    "/api/v1/articles/search/semantic?q=nonexistent+topic"
                )

        assert resp.status_code == 200
        data = resp.json()
        assert data["results"] == []

    async def test_processor_close_called_on_success(self):
        """The ArticleProcessor should always be closed after use."""
        mock_session = AsyncMock()

        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        fake_embedding = [0.1] * 1024

        with patch(
            "api.routes.get_session",
            new=_make_fake_get_session(mock_session),
        ), patch(
            "api.routes.llm_settings"
        ) as mock_llm_settings, patch(
            "processing.llm_pipeline.ArticleProcessor",
        ) as MockProcessor:
            mock_llm_settings.llm_api_key = "test-key"

            mock_proc_instance = AsyncMock()
            mock_proc_instance.generate_embedding = AsyncMock(return_value=fake_embedding)
            mock_proc_instance.close = AsyncMock()
            MockProcessor.return_value = mock_proc_instance

            async with _build_test_client(mock_session) as client:
                await client.get(
                    "/api/v1/articles/search/semantic?q=test"
                )

            mock_proc_instance.close.assert_called_once()

    async def test_processor_close_called_on_failure(self):
        """The ArticleProcessor should be closed even when embedding fails."""
        mock_session = AsyncMock()

        with patch(
            "api.routes.get_session",
            new=_make_fake_get_session(mock_session),
        ), patch(
            "api.routes.llm_settings"
        ) as mock_llm_settings, patch(
            "processing.llm_pipeline.ArticleProcessor",
        ) as MockProcessor:
            mock_llm_settings.llm_api_key = "test-key"

            mock_proc_instance = AsyncMock()
            mock_proc_instance.generate_embedding = AsyncMock(
                side_effect=Exception("fail")
            )
            mock_proc_instance.close = AsyncMock()
            MockProcessor.return_value = mock_proc_instance

            async with _build_test_client(mock_session) as client:
                await client.get(
                    "/api/v1/articles/search/semantic?q=test"
                )

            mock_proc_instance.close.assert_called_once()


# ---------------------------------------------------------------------------
# GET /api/v1/articles/{id}/related
# ---------------------------------------------------------------------------


class TestRelatedArticles:
    async def test_success_with_related_articles(self):
        """Should return related articles sorted by similarity."""
        mock_session = AsyncMock()

        target_article = _make_fake_article(
            id="target-uuid",
            embedding=[0.1] * 1024,
        )

        # First call: fetch target article
        mock_result_target = MagicMock()
        mock_result_target.scalar_one_or_none.return_value = target_article

        # Second call: fetch related articles
        related_article = _make_fake_article(
            id="related-uuid",
            title="Related supply chain news",
            url="https://example.com/related",
        )
        mock_row = MagicMock()
        mock_row.Article = related_article
        mock_row.distance = 0.2  # similarity = 0.8
        mock_result_related = MagicMock()
        mock_result_related.all.return_value = [mock_row]

        mock_session.execute = AsyncMock(
            side_effect=[mock_result_target, mock_result_related]
        )

        with patch(
            "api.routes.get_session",
            new=_make_fake_get_session(mock_session),
        ):
            async with _build_test_client(mock_session) as client:
                resp = await client.get("/api/v1/articles/target-uuid/related")

        assert resp.status_code == 200
        data = resp.json()
        assert data["article_id"] == "target-uuid"
        assert len(data["related"]) == 1
        assert data["related"][0]["id"] == "related-uuid"
        assert data["related"][0]["similarity"] == 0.8

    async def test_article_not_found_returns_404(self):
        """Requesting related articles for a non-existent article should return 404."""
        mock_session = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "api.routes.get_session",
            new=_make_fake_get_session(mock_session),
        ):
            async with _build_test_client(mock_session) as client:
                resp = await client.get("/api/v1/articles/nonexistent-uuid/related")

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Article not found"

    async def test_no_embedding_returns_422(self):
        """Article without embedding should return 422."""
        mock_session = AsyncMock()

        target_article = _make_fake_article(
            id="no-embed-uuid",
            embedding=None,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = target_article
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "api.routes.get_session",
            new=_make_fake_get_session(mock_session),
        ):
            async with _build_test_client(mock_session) as client:
                resp = await client.get("/api/v1/articles/no-embed-uuid/related")

        assert resp.status_code == 422
        assert "no embedding" in resp.json()["detail"].lower()

    async def test_empty_related_results(self):
        """When no related articles found, should return empty list."""
        mock_session = AsyncMock()

        target_article = _make_fake_article(
            id="lonely-uuid",
            embedding=[0.1] * 1024,
        )

        mock_result_target = MagicMock()
        mock_result_target.scalar_one_or_none.return_value = target_article

        mock_result_related = MagicMock()
        mock_result_related.all.return_value = []

        mock_session.execute = AsyncMock(
            side_effect=[mock_result_target, mock_result_related]
        )

        with patch(
            "api.routes.get_session",
            new=_make_fake_get_session(mock_session),
        ):
            async with _build_test_client(mock_session) as client:
                resp = await client.get("/api/v1/articles/lonely-uuid/related")

        assert resp.status_code == 200
        data = resp.json()
        assert data["article_id"] == "lonely-uuid"
        assert data["related"] == []

    async def test_related_response_shape(self):
        """Verify the shape of each related article in the response."""
        mock_session = AsyncMock()

        target_article = _make_fake_article(
            id="target-uuid",
            embedding=[0.1] * 1024,
        )

        mock_result_target = MagicMock()
        mock_result_target.scalar_one_or_none.return_value = target_article

        related_article = _make_fake_article(
            id="related-uuid",
            title="Related article",
        )
        mock_row = MagicMock()
        mock_row.Article = related_article
        mock_row.distance = 0.25
        mock_result_related = MagicMock()
        mock_result_related.all.return_value = [mock_row]

        mock_session.execute = AsyncMock(
            side_effect=[mock_result_target, mock_result_related]
        )

        with patch(
            "api.routes.get_session",
            new=_make_fake_get_session(mock_session),
        ):
            async with _build_test_client(mock_session) as client:
                resp = await client.get("/api/v1/articles/target-uuid/related")

        assert resp.status_code == 200
        related = resp.json()["related"][0]
        expected_keys = {
            "id", "source_id", "source_name", "url", "title",
            "summary_en", "summary_zh", "language", "published_at",
            "transport_modes", "primary_topic", "sentiment", "similarity",
        }
        assert set(related.keys()) == expected_keys
