"""
Tests for processing/llm_pipeline.py -- LLM-based article analysis pipeline.

All database access, HTTP calls, and LLM APIs are mocked.
"""

import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from processing.llm_pipeline import ArticleProcessor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_get_session(mock_session):
    """Create a patched get_session that yields mock_session."""

    @asynccontextmanager
    async def _fake():
        yield mock_session

    return _fake


VALID_LLM_RESPONSE = {
    "summary_en": "Global supply chains face major disruption.",
    "summary_zh": "\u5168\u7403\u4f9b\u5e94\u94fe\u9762\u4e34\u91cd\u5927\u4e2d\u65ad\u3002",
    "transport_modes": ["ocean"],
    "primary_topic": "supply_chain_disruption",
    "secondary_topics": ["port_operations"],
    "content_type": "news",
    "regions": ["Asia", "Europe"],
    "entities": {
        "companies": ["Maersk"],
        "ports": ["Shanghai"],
        "people": [],
        "organizations": ["IMO"],
    },
    "sentiment": "negative",
    "market_impact": "high",
    "urgency": "high",
    "key_metrics": [
        {
            "metric": "freight_rate",
            "value": "2350",
            "unit": "USD/FEU",
            "context": "Shanghai-LA spot rate",
        }
    ],
}


# ---------------------------------------------------------------------------
# _parse_llm_json
# ---------------------------------------------------------------------------


class TestParseLlmJsonClean:
    """_parse_llm_json should handle clean JSON strings."""

    def test_clean_json(self):
        raw = json.dumps({"key": "value"})
        result = ArticleProcessor._parse_llm_json(raw)
        assert result == {"key": "value"}

    def test_json_with_whitespace(self):
        raw = "  \n  " + json.dumps({"a": 1}) + "  \n  "
        result = ArticleProcessor._parse_llm_json(raw)
        assert result == {"a": 1}


class TestParseLlmJsonMarkdownFenced:
    """_parse_llm_json should strip markdown code fences."""

    def test_json_fenced(self):
        raw = "```json\n" + json.dumps({"key": "value"}) + "\n```"
        result = ArticleProcessor._parse_llm_json(raw)
        assert result == {"key": "value"}

    def test_plain_fenced(self):
        raw = "```\n" + json.dumps({"key": "value"}) + "\n```"
        result = ArticleProcessor._parse_llm_json(raw)
        assert result == {"key": "value"}

    def test_fenced_with_extra_whitespace(self):
        raw = "```json\n  " + json.dumps({"x": 42}) + "  \n```"
        result = ArticleProcessor._parse_llm_json(raw)
        assert result == {"x": 42}


class TestParseLlmJsonInvalid:
    """_parse_llm_json should raise on invalid JSON."""

    def test_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            ArticleProcessor._parse_llm_json("not valid json at all")

    def test_empty_string_raises(self):
        with pytest.raises(json.JSONDecodeError):
            ArticleProcessor._parse_llm_json("")

    def test_truncated_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            ArticleProcessor._parse_llm_json('{"key": "val')


# ---------------------------------------------------------------------------
# _validate_extracted
# ---------------------------------------------------------------------------


class TestValidateExtractedValid:
    """_validate_extracted should accept well-formed data."""

    def test_valid_full_data(self):
        result = ArticleProcessor._validate_extracted(VALID_LLM_RESPONSE)
        assert result["summary_en"] == "Global supply chains face major disruption."
        assert result["sentiment"] == "negative"
        assert result["market_impact"] == "high"
        assert result["urgency"] == "high"
        assert result["content_type"] == "news"
        assert result["primary_topic"] == "supply_chain_disruption"
        assert result["transport_modes"] == ["ocean"]
        assert result["regions"] == ["Asia", "Europe"]
        assert "companies" in result["entities"]
        assert len(result["key_metrics"]) == 1

    def test_enum_values_lowercased(self):
        data = {**VALID_LLM_RESPONSE, "sentiment": "Negative", "urgency": "HIGH"}
        result = ArticleProcessor._validate_extracted(data)
        assert result["sentiment"] == "negative"
        assert result["urgency"] == "high"


class TestValidateExtractedMissingFields:
    """_validate_extracted should gracefully handle missing fields."""

    def test_empty_dict(self):
        result = ArticleProcessor._validate_extracted({})
        assert result == {}

    def test_missing_optional_fields(self):
        data = {"summary_en": "A summary.", "sentiment": "neutral"}
        result = ArticleProcessor._validate_extracted(data)
        assert result["summary_en"] == "A summary."
        assert result["sentiment"] == "neutral"
        assert "transport_modes" not in result
        assert "entities" not in result


class TestValidateExtractedWrongTypes:
    """_validate_extracted should skip fields with wrong types."""

    def test_sentiment_not_string(self):
        data = {"sentiment": 123}
        result = ArticleProcessor._validate_extracted(data)
        assert "sentiment" not in result

    def test_transport_modes_not_list(self):
        data = {"transport_modes": "ocean"}
        result = ArticleProcessor._validate_extracted(data)
        assert "transport_modes" not in result

    def test_entities_not_dict(self):
        data = {"entities": ["Maersk"]}
        result = ArticleProcessor._validate_extracted(data)
        assert "entities" not in result

    def test_summary_en_not_string(self):
        data = {"summary_en": 42}
        result = ArticleProcessor._validate_extracted(data)
        assert "summary_en" not in result


class TestValidateExtractedEnumValidation:
    """_validate_extracted should reject invalid enum values."""

    def test_invalid_sentiment_rejected(self):
        data = {"sentiment": "angry"}
        result = ArticleProcessor._validate_extracted(data)
        assert "sentiment" not in result

    def test_invalid_content_type_rejected(self):
        data = {"content_type": "blog_post"}
        result = ArticleProcessor._validate_extracted(data)
        assert "content_type" not in result

    def test_invalid_market_impact_rejected(self):
        data = {"market_impact": "extreme"}
        result = ArticleProcessor._validate_extracted(data)
        assert "market_impact" not in result

    def test_invalid_urgency_rejected(self):
        data = {"urgency": "critical"}
        result = ArticleProcessor._validate_extracted(data)
        assert "urgency" not in result


# ---------------------------------------------------------------------------
# process_article - success path
# ---------------------------------------------------------------------------


class TestProcessArticleSuccess:
    """process_article should extract structured data and persist it."""

    async def test_success_returns_true(self):
        """Full success path: load article, call LLM, generate embedding, persist."""
        processor = ArticleProcessor()

        # Mock the article from DB
        mock_article = MagicMock()
        mock_article.title = "Supply chain crisis"
        mock_article.body_text = "Global supply chains face challenges..." * 10

        mock_session = AsyncMock()

        # First call: select article -> returns article
        mock_result_article = MagicMock()
        mock_result_article.scalar_one_or_none.return_value = mock_article

        # Third call (after _set_status): select for _mark_failed won't be called on success
        # The session.execute calls:
        # 1. select Article (load) -> returns article
        # 2. update Article (set_status) -> done
        # 3. update Article (persist results) -> done
        mock_session.execute = AsyncMock(return_value=mock_result_article)

        fake_get_session = _make_fake_get_session(mock_session)

        llm_json = json.dumps(VALID_LLM_RESPONSE)
        embedding = [0.1] * 1024

        with patch("processing.llm_pipeline.get_session", new=fake_get_session):
            with patch.object(
                processor, "_call_chat", new_callable=AsyncMock, return_value=llm_json
            ):
                with patch.object(
                    processor,
                    "generate_embedding",
                    new_callable=AsyncMock,
                    return_value=embedding,
                ):
                    result = await processor.process_article("test-uuid-123")

        assert result is True


# ---------------------------------------------------------------------------
# process_article - failure paths
# ---------------------------------------------------------------------------


class TestProcessArticleNotFound:
    """process_article should return False when article is not in DB."""

    async def test_article_not_found_returns_false(self):
        processor = ArticleProcessor()

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        fake_get_session = _make_fake_get_session(mock_session)

        with patch("processing.llm_pipeline.get_session", new=fake_get_session):
            result = await processor.process_article("nonexistent-uuid")

        assert result is False


class TestProcessArticleNoBodyText:
    """process_article should return False when article has no body_text."""

    async def test_no_body_text_returns_false(self):
        processor = ArticleProcessor()

        mock_article = MagicMock()
        mock_article.title = "Title Only Article"
        mock_article.body_text = ""

        mock_session = AsyncMock()
        mock_result_article = MagicMock()
        mock_result_article.scalar_one_or_none.return_value = mock_article
        mock_session.execute = AsyncMock(return_value=mock_result_article)

        fake_get_session = _make_fake_get_session(mock_session)

        with patch("processing.llm_pipeline.get_session", new=fake_get_session):
            result = await processor.process_article("uuid-no-body")

        assert result is False

    async def test_none_body_text_returns_false(self):
        processor = ArticleProcessor()

        mock_article = MagicMock()
        mock_article.title = "Title Only"
        mock_article.body_text = None

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_article
        mock_session.execute = AsyncMock(return_value=mock_result)

        fake_get_session = _make_fake_get_session(mock_session)

        with patch("processing.llm_pipeline.get_session", new=fake_get_session):
            result = await processor.process_article("uuid-none-body")

        assert result is False


class TestProcessArticleLlmApiError:
    """process_article should return False on LLM HTTP errors."""

    async def test_http_error_returns_false(self):
        processor = ArticleProcessor()

        mock_article = MagicMock()
        mock_article.title = "Test Article"
        mock_article.body_text = "Sufficient body text for processing." * 5

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_article
        mock_session.execute = AsyncMock(return_value=mock_result)

        fake_get_session = _make_fake_get_session(mock_session)

        # Simulate an HTTP 429 error from the LLM API
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "Rate limit exceeded"

        with patch("processing.llm_pipeline.get_session", new=fake_get_session):
            with patch.object(
                processor,
                "_call_chat",
                new_callable=AsyncMock,
                side_effect=httpx.HTTPStatusError(
                    "429 Too Many Requests",
                    request=MagicMock(),
                    response=mock_response,
                ),
            ):
                result = await processor.process_article("uuid-api-error")

        assert result is False


class TestProcessArticleJsonParseError:
    """process_article should return False when LLM returns unparseable JSON."""

    async def test_json_error_returns_false(self):
        processor = ArticleProcessor()

        mock_article = MagicMock()
        mock_article.title = "Test Article"
        mock_article.body_text = "Sufficient body text for processing." * 5

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_article
        mock_session.execute = AsyncMock(return_value=mock_result)

        fake_get_session = _make_fake_get_session(mock_session)

        with patch("processing.llm_pipeline.get_session", new=fake_get_session):
            with patch.object(
                processor,
                "_call_chat",
                new_callable=AsyncMock,
                return_value="This is not JSON at all, sorry!",
            ):
                result = await processor.process_article("uuid-bad-json")

        assert result is False


# ---------------------------------------------------------------------------
# process_pending_batch
# ---------------------------------------------------------------------------


class TestProcessPendingBatch:
    """process_pending_batch should process a batch of pending articles."""

    async def test_no_pending_articles(self):
        """When no articles are pending, return zeroed summary."""
        processor = ArticleProcessor()

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        fake_get_session = _make_fake_get_session(mock_session)

        with patch("processing.llm_pipeline.get_session", new=fake_get_session):
            summary = await processor.process_pending_batch(batch_size=5)

        assert summary == {"total": 0, "success": 0, "failed": 0}

    async def test_batch_processes_articles(self):
        """Pending articles should be processed and counted."""
        processor = ArticleProcessor()

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            ("uuid-1",),
            ("uuid-2",),
            ("uuid-3",),
        ]
        mock_session.execute = AsyncMock(return_value=mock_result)

        fake_get_session = _make_fake_get_session(mock_session)

        with patch("processing.llm_pipeline.get_session", new=fake_get_session):
            with patch.object(
                processor,
                "process_article",
                new_callable=AsyncMock,
                side_effect=[True, True, False],
            ):
                summary = await processor.process_pending_batch(batch_size=10)

        assert summary["total"] == 3
        assert summary["success"] == 2
        assert summary["failed"] == 1

    async def test_batch_all_success(self):
        """When all articles succeed, failed count is zero."""
        processor = ArticleProcessor()

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("uuid-1",), ("uuid-2",)]
        mock_session.execute = AsyncMock(return_value=mock_result)

        fake_get_session = _make_fake_get_session(mock_session)

        with patch("processing.llm_pipeline.get_session", new=fake_get_session):
            with patch.object(
                processor,
                "process_article",
                new_callable=AsyncMock,
                return_value=True,
            ):
                summary = await processor.process_pending_batch(batch_size=10)

        assert summary == {"total": 2, "success": 2, "failed": 0}
