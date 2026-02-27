"""
Tests for the immediate LLM pipeline trigger in scheduler/jobs.py.

Validates that _process_new_articles correctly processes articles through
the LLM pipeline and dispatches notifications after fetch.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scheduler.jobs import _process_new_articles, fetch_source


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_get_session(mock_session):
    @asynccontextmanager
    async def _fake():
        yield mock_session

    return _fake


# ---------------------------------------------------------------------------
# _process_new_articles
# ---------------------------------------------------------------------------


class TestProcessNewArticles:
    """_process_new_articles should process articles via LLM and dispatch notifications."""

    async def test_returns_early_for_empty_list(self):
        """Empty article_ids list should return immediately without creating a processor."""
        with patch("processing.llm_pipeline.ArticleProcessor") as MockProcessor:
            await _process_new_articles([])
            MockProcessor.assert_not_called()

    async def test_processes_each_article(self):
        """Should call process_article for each article ID."""
        mock_processor = AsyncMock()
        mock_processor.process_article = AsyncMock(return_value=False)
        mock_processor.close = AsyncMock()

        with patch(
            "processing.llm_pipeline.ArticleProcessor",
            return_value=mock_processor,
        ):
            await _process_new_articles(["id-1", "id-2", "id-3"])

        assert mock_processor.process_article.call_count == 3
        mock_processor.process_article.assert_any_call("id-1")
        mock_processor.process_article.assert_any_call("id-2")
        mock_processor.process_article.assert_any_call("id-3")

    async def test_closes_processor_in_finally(self):
        """Processor.close() should always be called, even if an error occurs."""
        mock_processor = AsyncMock()
        mock_processor.process_article = AsyncMock(side_effect=RuntimeError("boom"))
        mock_processor.close = AsyncMock()

        with patch(
            "processing.llm_pipeline.ArticleProcessor",
            return_value=mock_processor,
        ):
            with pytest.raises(RuntimeError, match="boom"):
                await _process_new_articles(["id-1"])

        mock_processor.close.assert_awaited_once()

    async def test_counts_successes(self):
        """Should count successful processings correctly."""
        mock_processor = AsyncMock()
        # First succeeds, second fails, third succeeds
        mock_processor.process_article = AsyncMock(
            side_effect=[True, False, True]
        )
        mock_processor.close = AsyncMock()

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # No article found
        mock_session.execute = AsyncMock(return_value=mock_result)
        fake_get_session = _make_fake_get_session(mock_session)

        with patch(
            "processing.llm_pipeline.ArticleProcessor",
            return_value=mock_processor,
        ):
            with patch("scheduler.jobs.get_session", new=fake_get_session):
                with patch(
                    "notifications.dispatcher.NotificationDispatcher"
                ) as MockDispatcher:
                    MockDispatcher.return_value.dispatch = AsyncMock()
                    await _process_new_articles(["id-1", "id-2", "id-3"])

        assert mock_processor.process_article.call_count == 3

    async def test_dispatches_notifications_on_success(self):
        """After successful LLM processing, should dispatch notifications."""
        mock_processor = AsyncMock()
        mock_processor.process_article = AsyncMock(return_value=True)
        mock_processor.close = AsyncMock()

        # Mock the article fetched from DB
        mock_article = MagicMock()
        mock_article.id = "art-1"
        mock_article.source_id = "test_rss"
        mock_article.source_name = "Test Source"
        mock_article.url = "https://example.com/article"
        mock_article.title = "Test Article"
        mock_article.summary_en = "Summary"
        mock_article.summary_zh = "摘要"
        mock_article.transport_modes = ["ocean"]
        mock_article.primary_topic = "shipping"
        mock_article.regions = ["asia"]
        mock_article.sentiment = "positive"
        mock_article.market_impact = "medium"
        mock_article.urgency = "low"
        mock_article.language = "en"
        mock_article.published_at = datetime(2025, 6, 15, tzinfo=timezone.utc)

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_article
        mock_session.execute = AsyncMock(return_value=mock_result)
        fake_get_session = _make_fake_get_session(mock_session)

        mock_dispatcher = AsyncMock()
        mock_dispatcher.dispatch = AsyncMock()

        with patch(
            "processing.llm_pipeline.ArticleProcessor",
            return_value=mock_processor,
        ):
            with patch("scheduler.jobs.get_session", new=fake_get_session):
                with patch(
                    "notifications.dispatcher.NotificationDispatcher",
                    return_value=mock_dispatcher,
                ):
                    await _process_new_articles(["art-1"])

        mock_dispatcher.dispatch.assert_awaited_once()
        dispatch_arg = mock_dispatcher.dispatch.call_args[0][0]
        assert dispatch_arg["id"] == "art-1"
        assert dispatch_arg["title"] == "Test Article"
        assert dispatch_arg["transport_modes"] == ["ocean"]

    async def test_handles_notification_dispatch_failure(self):
        """Notification dispatch failure should not prevent processing other articles."""
        mock_processor = AsyncMock()
        mock_processor.process_article = AsyncMock(return_value=True)
        mock_processor.close = AsyncMock()

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock(
            id="art-1",
            source_id="test",
            source_name="Test",
            url="https://example.com",
            title="Title",
            summary_en="Sum",
            summary_zh=None,
            transport_modes=[],
            primary_topic="topic",
            regions=[],
            sentiment="neutral",
            market_impact="low",
            urgency="low",
            language="en",
            published_at=None,
        )
        mock_session.execute = AsyncMock(return_value=mock_result)
        fake_get_session = _make_fake_get_session(mock_session)

        mock_dispatcher = AsyncMock()
        mock_dispatcher.dispatch = AsyncMock(
            side_effect=RuntimeError("webhook failed")
        )

        with patch(
            "processing.llm_pipeline.ArticleProcessor",
            return_value=mock_processor,
        ):
            with patch("scheduler.jobs.get_session", new=fake_get_session):
                with patch(
                    "notifications.dispatcher.NotificationDispatcher",
                    return_value=mock_dispatcher,
                ):
                    # Should NOT raise — notification failure is caught
                    await _process_new_articles(["art-1", "art-2"])

        # Both articles should still be processed
        assert mock_processor.process_article.call_count == 2


# ---------------------------------------------------------------------------
# fetch_source: pipeline trigger integration
# ---------------------------------------------------------------------------


class TestFetchSourcePipelineTrigger:
    """fetch_source should trigger immediate LLM processing for new articles."""

    async def test_triggers_llm_when_new_articles(self):
        """When articles_new > 0 and LLM key is set, should call _process_new_articles."""
        from adapters.base import RawArticle

        raw = RawArticle(
            source_id="test_rss",
            source_name="Test",
            url="https://example.com/article-1",
            title="Test Article",
            body_text="Article body text for testing purposes.",
            language="en",
        )

        mock_adapter = AsyncMock()
        mock_adapter.fetch = AsyncMock(return_value=[raw])
        mock_adapter.__aenter__ = AsyncMock(return_value=mock_adapter)
        mock_adapter.__aexit__ = AsyncMock(return_value=False)
        mock_adapter_cls = MagicMock(return_value=mock_adapter)

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        fake_get_session = _make_fake_get_session(mock_session)

        with patch(
            "scheduler.jobs.load_sources_config",
            return_value=[
                {
                    "source_id": "test_rss",
                    "name": "Test",
                    "type": "rss",
                    "url": "https://example.com/feed",
                    "enabled": True,
                }
            ],
        ):
            with patch.dict(
                "scheduler.jobs.ADAPTER_MAP", {"rss": mock_adapter_cls}
            ):
                with patch("scheduler.jobs.get_session", new=fake_get_session):
                    with patch("scheduler.jobs.deduplicator") as mock_dedup:
                        mock_dedup.is_duplicate = AsyncMock(return_value=False)
                        with patch(
                            "scheduler.jobs._raw_to_article"
                        ) as mock_convert:
                            mock_article = MagicMock()
                            mock_article.id = "art-uuid-1"
                            mock_convert.return_value = mock_article
                            with patch(
                                "scheduler.jobs._log_fetch",
                                new_callable=AsyncMock,
                            ):
                                with patch(
                                    "scheduler.jobs._update_source_last_fetched",
                                    new_callable=AsyncMock,
                                ):
                                    with patch(
                                        "scheduler.jobs.llm_settings"
                                    ) as mock_llm:
                                        mock_llm.llm_api_key = "test-key"
                                        with patch(
                                            "scheduler.jobs._process_new_articles",
                                            new_callable=AsyncMock,
                                        ) as mock_process:
                                            await fetch_source("test_rss")

        mock_process.assert_awaited_once_with(["art-uuid-1"])

    async def test_no_trigger_when_zero_new_articles(self):
        """When all articles are duplicates, should NOT trigger LLM processing."""
        from adapters.base import RawArticle

        raw = RawArticle(
            source_id="test_rss",
            source_name="Test",
            url="https://example.com/old-article",
            title="Old Article",
            body_text="Already seen.",
            language="en",
        )

        mock_adapter = AsyncMock()
        mock_adapter.fetch = AsyncMock(return_value=[raw])
        mock_adapter.__aenter__ = AsyncMock(return_value=mock_adapter)
        mock_adapter.__aexit__ = AsyncMock(return_value=False)
        mock_adapter_cls = MagicMock(return_value=mock_adapter)

        mock_session = AsyncMock()
        fake_get_session = _make_fake_get_session(mock_session)

        with patch(
            "scheduler.jobs.load_sources_config",
            return_value=[
                {
                    "source_id": "test_rss",
                    "name": "Test",
                    "type": "rss",
                    "url": "https://example.com/feed",
                    "enabled": True,
                }
            ],
        ):
            with patch.dict(
                "scheduler.jobs.ADAPTER_MAP", {"rss": mock_adapter_cls}
            ):
                with patch("scheduler.jobs.get_session", new=fake_get_session):
                    with patch("scheduler.jobs.deduplicator") as mock_dedup:
                        mock_dedup.is_duplicate = AsyncMock(return_value=True)
                        with patch(
                            "scheduler.jobs._log_fetch",
                            new_callable=AsyncMock,
                        ):
                            with patch(
                                "scheduler.jobs._update_source_last_fetched",
                                new_callable=AsyncMock,
                            ):
                                with patch(
                                    "scheduler.jobs.llm_settings"
                                ) as mock_llm:
                                    mock_llm.llm_api_key = "test-key"
                                    with patch(
                                        "scheduler.jobs._process_new_articles",
                                        new_callable=AsyncMock,
                                    ) as mock_process:
                                        await fetch_source("test_rss")

        mock_process.assert_not_awaited()

    async def test_no_trigger_when_no_llm_key(self):
        """When LLM API key is empty, should NOT trigger LLM processing."""
        from adapters.base import RawArticle

        raw = RawArticle(
            source_id="test_rss",
            source_name="Test",
            url="https://example.com/article-new",
            title="New Article",
            body_text="Brand new content.",
            language="en",
        )

        mock_adapter = AsyncMock()
        mock_adapter.fetch = AsyncMock(return_value=[raw])
        mock_adapter.__aenter__ = AsyncMock(return_value=mock_adapter)
        mock_adapter.__aexit__ = AsyncMock(return_value=False)
        mock_adapter_cls = MagicMock(return_value=mock_adapter)

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        fake_get_session = _make_fake_get_session(mock_session)

        with patch(
            "scheduler.jobs.load_sources_config",
            return_value=[
                {
                    "source_id": "test_rss",
                    "name": "Test",
                    "type": "rss",
                    "url": "https://example.com/feed",
                    "enabled": True,
                }
            ],
        ):
            with patch.dict(
                "scheduler.jobs.ADAPTER_MAP", {"rss": mock_adapter_cls}
            ):
                with patch("scheduler.jobs.get_session", new=fake_get_session):
                    with patch("scheduler.jobs.deduplicator") as mock_dedup:
                        mock_dedup.is_duplicate = AsyncMock(return_value=False)
                        with patch(
                            "scheduler.jobs._raw_to_article"
                        ) as mock_convert:
                            mock_convert.return_value = MagicMock(id="art-1")
                            with patch(
                                "scheduler.jobs._log_fetch",
                                new_callable=AsyncMock,
                            ):
                                with patch(
                                    "scheduler.jobs._update_source_last_fetched",
                                    new_callable=AsyncMock,
                                ):
                                    with patch(
                                        "scheduler.jobs.llm_settings"
                                    ) as mock_llm:
                                        mock_llm.llm_api_key = ""  # No key
                                        with patch(
                                            "scheduler.jobs._process_new_articles",
                                            new_callable=AsyncMock,
                                        ) as mock_process:
                                            await fetch_source("test_rss")

        mock_process.assert_not_awaited()
