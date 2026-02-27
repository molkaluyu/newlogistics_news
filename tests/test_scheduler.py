"""
Tests for scheduler/jobs.py -- source fetching, scheduling, and article conversion.

All file I/O, adapters, database access, and external services are mocked.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest

from adapters.base import RawArticle
from scheduler.jobs import _raw_to_article, create_scheduler, fetch_source, load_sources_config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


SAMPLE_SOURCES_YAML = """\
sources:
  - source_id: loadstar_rss
    name: The Loadstar
    type: rss
    url: https://theloadstar.com/feed/
    language: en
    enabled: true
    fetch_interval_minutes: 30
  - source_id: freightwaves_rss
    name: FreightWaves
    type: rss
    url: https://www.freightwaves.com/feed/
    language: en
    enabled: true
    fetch_interval_minutes: 45
  - source_id: disabled_source
    name: Disabled Source
    type: rss
    url: https://disabled.example.com/feed/
    language: en
    enabled: false
    fetch_interval_minutes: 60
"""


def _make_fake_get_session(mock_session):
    """Create a patched get_session that yields mock_session."""

    @asynccontextmanager
    async def _fake():
        yield mock_session

    return _fake


def _sample_raw_article(**overrides) -> RawArticle:
    """Create a sample RawArticle for testing."""
    defaults = {
        "source_id": "loadstar_rss",
        "source_name": "The Loadstar",
        "url": "https://theloadstar.com/article/test",
        "title": "Test Article - The Loadstar",
        "body_text": "This is the body text of a test article for logistics testing.",
        "body_markdown": "# Test Article\n\nThis is the body text.",
        "published_at": datetime(2025, 6, 15, 10, 30, 0, tzinfo=timezone.utc),
        "language": "en",
        "raw_metadata": {"rss_author": "Test Author"},
    }
    defaults.update(overrides)
    return RawArticle(**defaults)


# ---------------------------------------------------------------------------
# load_sources_config
# ---------------------------------------------------------------------------


class TestLoadSourcesConfig:
    """load_sources_config should read YAML and return source dicts."""

    def test_loads_yaml_correctly(self):
        """Should parse YAML file and return list of source configs."""
        with patch("builtins.open", mock_open(read_data=SAMPLE_SOURCES_YAML)):
            sources = load_sources_config()

        assert len(sources) == 3
        assert sources[0]["source_id"] == "loadstar_rss"
        assert sources[0]["name"] == "The Loadstar"
        assert sources[0]["enabled"] is True

    def test_returns_empty_when_no_sources_key(self):
        """If YAML has no 'sources' key, return an empty list."""
        yaml_data = "other_key:\n  - item1\n"
        with patch("builtins.open", mock_open(read_data=yaml_data)):
            sources = load_sources_config()

        assert sources == []

    def test_returns_source_fields(self):
        """Each source dict should contain expected fields."""
        with patch("builtins.open", mock_open(read_data=SAMPLE_SOURCES_YAML)):
            sources = load_sources_config()

        first = sources[0]
        assert "source_id" in first
        assert "name" in first
        assert "type" in first
        assert "url" in first
        assert "fetch_interval_minutes" in first


# ---------------------------------------------------------------------------
# _raw_to_article
# ---------------------------------------------------------------------------


class TestRawToArticle:
    """_raw_to_article should convert a RawArticle to an Article model."""

    def test_converts_basic_fields(self):
        """Basic fields should be transferred from RawArticle to Article."""
        raw = _sample_raw_article()

        with patch("scheduler.jobs.clean_text", return_value="Cleaned body text"):
            with patch("scheduler.jobs.clean_title", return_value="Test Article"):
                with patch("scheduler.jobs.detect_language", return_value="en"):
                    article = _raw_to_article(raw)

        assert article.source_id == "loadstar_rss"
        assert article.source_name == "The Loadstar"
        assert article.url == "https://theloadstar.com/article/test"
        assert article.title == "Test Article"
        assert article.body_text == "Cleaned body text"
        assert article.processing_status == "pending"

    def test_detects_language_from_body(self):
        """Language should be detected from the cleaned body text."""
        raw = _sample_raw_article()

        with patch("scheduler.jobs.clean_text", return_value="Chinese text content"):
            with patch("scheduler.jobs.clean_title", return_value="Title"):
                with patch("scheduler.jobs.detect_language", return_value="zh-cn") as mock_detect:
                    article = _raw_to_article(raw)
                    mock_detect.assert_called_once_with("Chinese text content")

        assert article.language == "zh-cn"

    def test_fallback_language_when_no_body(self):
        """When cleaned body is None/empty, should use raw.language or 'en'."""
        raw = _sample_raw_article(language="ja")

        with patch("scheduler.jobs.clean_text", return_value=None):
            with patch("scheduler.jobs.clean_title", return_value="Title"):
                article = _raw_to_article(raw)

        assert article.language == "ja"

    def test_preserves_raw_metadata(self):
        """raw_metadata should be passed through to the Article."""
        raw = _sample_raw_article(raw_metadata={"rss_author": "John Doe", "rss_tags": ["ocean"]})

        with patch("scheduler.jobs.clean_text", return_value="Body"):
            with patch("scheduler.jobs.clean_title", return_value="Title"):
                with patch("scheduler.jobs.detect_language", return_value="en"):
                    article = _raw_to_article(raw)

        assert article.raw_metadata == {"rss_author": "John Doe", "rss_tags": ["ocean"]}


# ---------------------------------------------------------------------------
# fetch_source
# ---------------------------------------------------------------------------


class TestFetchSourceHappyPath:
    """fetch_source should fetch, deduplicate, and store articles."""

    async def test_fetches_and_stores_new_articles(self):
        """Happy path: fetch articles, check dedup, store new ones."""
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        fake_get_session = _make_fake_get_session(mock_session)

        raw_articles = [_sample_raw_article(url=f"https://example.com/article-{i}") for i in range(3)]

        mock_adapter_instance = AsyncMock()
        mock_adapter_instance.fetch = AsyncMock(return_value=raw_articles)
        mock_adapter_instance.__aenter__ = AsyncMock(return_value=mock_adapter_instance)
        mock_adapter_instance.__aexit__ = AsyncMock(return_value=False)

        mock_adapter_cls = MagicMock(return_value=mock_adapter_instance)

        with patch("scheduler.jobs.load_sources_config", return_value=[
            {"source_id": "test_rss", "name": "Test", "type": "rss", "url": "https://example.com/feed", "enabled": True},
        ]):
            with patch.dict("scheduler.jobs.ADAPTER_MAP", {"rss": mock_adapter_cls}):
                with patch("scheduler.jobs.get_session", new=fake_get_session):
                    with patch("scheduler.jobs.deduplicator") as mock_dedup:
                        mock_dedup.is_duplicate = AsyncMock(return_value=False)
                        with patch("scheduler.jobs._raw_to_article") as mock_convert:
                            mock_convert.return_value = MagicMock()
                            with patch("scheduler.jobs._log_fetch", new_callable=AsyncMock):
                                with patch("scheduler.jobs._update_source_last_fetched", new_callable=AsyncMock):
                                    await fetch_source("test_rss")

        # All 3 articles should be processed (not duplicates)
        assert mock_dedup.is_duplicate.call_count == 3
        assert mock_convert.call_count == 3


class TestFetchSourceDisabled:
    """fetch_source should skip disabled sources."""

    async def test_disabled_source_skipped(self):
        """A disabled source should not fetch any articles."""
        with patch("scheduler.jobs.load_sources_config", return_value=[
            {"source_id": "disabled_src", "name": "Disabled", "type": "rss", "enabled": False},
        ]):
            with patch("scheduler.jobs._log_fetch", new_callable=AsyncMock) as mock_log:
                with patch("scheduler.jobs._update_source_last_fetched", new_callable=AsyncMock):
                    await fetch_source("disabled_src")

        # _log_fetch should still be called to record the skipped fetch
        # Actually, the code returns early before _log_fetch for disabled sources
        # Let's verify no adapter was created
        # The function returns early, so _log_fetch is NOT called
        mock_log.assert_not_called()


class TestFetchSourceUnknownId:
    """fetch_source should handle unknown source_id gracefully."""

    async def test_unknown_source_id_returns_early(self):
        """An unknown source_id should log an error and return."""
        with patch("scheduler.jobs.load_sources_config", return_value=[
            {"source_id": "known_src", "name": "Known", "type": "rss", "enabled": True},
        ]):
            with patch("scheduler.jobs._log_fetch", new_callable=AsyncMock) as mock_log:
                with patch("scheduler.jobs._update_source_last_fetched", new_callable=AsyncMock):
                    await fetch_source("nonexistent_source")

        # Function returns before _log_fetch for unknown sources
        mock_log.assert_not_called()


# ---------------------------------------------------------------------------
# create_scheduler
# ---------------------------------------------------------------------------


class TestCreateScheduler:
    """create_scheduler should set up jobs for enabled sources."""

    def test_creates_jobs_for_enabled_sources(self):
        """Only enabled sources should get scheduled jobs."""
        with patch.dict("os.environ", {"TZ": "UTC"}):
            with patch("builtins.open", mock_open(read_data=SAMPLE_SOURCES_YAML)):
                with patch("scheduler.jobs.llm_settings") as mock_llm:
                    mock_llm.llm_api_key = "test-key"
                    scheduler = create_scheduler()

        jobs = scheduler.get_jobs()
        job_ids = [job.id for job in jobs]

        # 2 enabled sources + health_check + llm_processing
        assert "fetch_loadstar_rss" in job_ids
        assert "fetch_freightwaves_rss" in job_ids
        assert "fetch_disabled_source" not in job_ids
        assert "health_check" in job_ids
        assert "llm_processing" in job_ids

    def test_no_llm_job_without_api_key(self):
        """If no LLM API key is configured, skip the LLM processing job."""
        with patch.dict("os.environ", {"TZ": "UTC"}):
            with patch("builtins.open", mock_open(read_data=SAMPLE_SOURCES_YAML)):
                with patch("scheduler.jobs.llm_settings") as mock_llm:
                    mock_llm.llm_api_key = ""
                    scheduler = create_scheduler()

        job_ids = [job.id for job in scheduler.get_jobs()]
        assert "llm_processing" not in job_ids

    def test_health_check_always_scheduled(self):
        """The health check job should always be created."""
        with patch.dict("os.environ", {"TZ": "UTC"}):
            with patch("builtins.open", mock_open(read_data=SAMPLE_SOURCES_YAML)):
                with patch("scheduler.jobs.llm_settings") as mock_llm:
                    mock_llm.llm_api_key = ""
                    scheduler = create_scheduler()

        job_ids = [job.id for job in scheduler.get_jobs()]
        assert "health_check" in job_ids
