"""
Tests for monitoring/health.py -- source health monitoring.

All database access is mocked; no real PostgreSQL connection is needed.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from monitoring.health import SourceHealthMonitor, SourceHealthReport


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_get_session(mock_session):
    """Create a patched get_session that yields mock_session."""

    @asynccontextmanager
    async def _fake():
        yield mock_session

    return _fake


def _make_source(source_id="test_rss", name="Test Source", enabled=True,
                 last_fetched_at=None, health_status="healthy"):
    """Create a MagicMock that behaves like a Source model instance."""
    source = MagicMock()
    source.source_id = source_id
    source.name = name
    source.enabled = enabled
    source.last_fetched_at = last_fetched_at or datetime.utcnow()
    source.health_status = health_status
    return source


def _make_fetch_log(status="success", articles_new=5, duration_ms=3000,
                    started_at=None):
    """Create a MagicMock that behaves like a FetchLog model instance."""
    log = MagicMock()
    log.status = status
    log.articles_new = articles_new
    log.duration_ms = duration_ms
    log.started_at = started_at or datetime.utcnow()
    return log


# ---------------------------------------------------------------------------
# check_all
# ---------------------------------------------------------------------------


class TestCheckAll:
    """SourceHealthMonitor.check_all should return reports for all sources."""

    async def test_returns_reports_for_all_sources(self):
        """check_all should return one SourceHealthReport per source."""
        monitor = SourceHealthMonitor()

        sources = [
            _make_source(source_id="src_1", name="Source One"),
            _make_source(source_id="src_2", name="Source Two"),
            _make_source(source_id="src_3", name="Source Three"),
        ]

        # First session call: select all sources
        mock_session_sources = AsyncMock()
        mock_result_sources = MagicMock()
        mock_result_sources.scalars.return_value.all.return_value = sources
        mock_session_sources.execute = AsyncMock(return_value=mock_result_sources)

        # Session calls for _check_source: each source needs fetch logs
        mock_session_logs = AsyncMock()
        healthy_logs = [
            _make_fetch_log(status="success", articles_new=5),
            _make_fetch_log(status="success", articles_new=3),
        ]
        mock_result_logs = MagicMock()
        mock_result_logs.scalars.return_value.all.return_value = healthy_logs
        mock_session_logs.execute = AsyncMock(return_value=mock_result_logs)

        call_count = 0

        @asynccontextmanager
        async def _multi_session():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                yield mock_session_sources
            else:
                yield mock_session_logs

        with patch("monitoring.health.get_session", new=_multi_session):
            reports = await monitor.check_all()

        assert len(reports) == 3
        assert all(isinstance(r, SourceHealthReport) for r in reports)
        source_ids = [r.source_id for r in reports]
        assert "src_1" in source_ids
        assert "src_2" in source_ids
        assert "src_3" in source_ids


# ---------------------------------------------------------------------------
# _check_source - healthy
# ---------------------------------------------------------------------------


class TestCheckSourceHealthy:
    """_check_source should report 'healthy' when stats are good."""

    async def test_healthy_source(self):
        """Source with good success rate and articles should be healthy."""
        monitor = SourceHealthMonitor()
        source = _make_source()

        healthy_logs = [
            _make_fetch_log(status="success", articles_new=5, duration_ms=2000),
            _make_fetch_log(status="success", articles_new=3, duration_ms=3000),
            _make_fetch_log(status="success", articles_new=7, duration_ms=2500),
        ]

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = healthy_logs
        mock_session.execute = AsyncMock(return_value=mock_result)

        fake_get_session = _make_fake_get_session(mock_session)

        with patch("monitoring.health.get_session", new=fake_get_session):
            report = await monitor._check_source(source)

        assert report.health_status == "healthy"
        assert report.alerts == []
        assert report.fetch_count_24h == 3
        assert report.success_rate_24h == 1.0
        assert report.total_articles_24h == 15


# ---------------------------------------------------------------------------
# _check_source - degraded (no fetches)
# ---------------------------------------------------------------------------


class TestCheckSourceNoFetches:
    """_check_source should report 'degraded' when no fetches in 24h."""

    async def test_no_fetches_in_24h(self):
        """Source with zero fetch logs in the last 24 hours should be degraded."""
        monitor = SourceHealthMonitor()
        source = _make_source()

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        fake_get_session = _make_fake_get_session(mock_session)

        with patch("monitoring.health.get_session", new=fake_get_session):
            report = await monitor._check_source(source)

        assert report.health_status == "degraded"
        assert "No fetches in last 24 hours" in report.alerts


# ---------------------------------------------------------------------------
# _check_source - degraded (low success rate)
# ---------------------------------------------------------------------------


class TestCheckSourceLowSuccessRate:
    """_check_source should report 'degraded' when success rate is below 80%."""

    async def test_low_success_rate(self):
        """Source with < 80% success rate should be degraded."""
        monitor = SourceHealthMonitor()
        source = _make_source()

        logs = [
            _make_fetch_log(status="success", articles_new=2),
            _make_fetch_log(status="failed", articles_new=0),
            _make_fetch_log(status="failed", articles_new=0),
            _make_fetch_log(status="failed", articles_new=0),
            _make_fetch_log(status="failed", articles_new=0),
        ]

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = logs
        mock_session.execute = AsyncMock(return_value=mock_result)

        fake_get_session = _make_fake_get_session(mock_session)

        with patch("monitoring.health.get_session", new=fake_get_session):
            report = await monitor._check_source(source)

        assert report.health_status in ("degraded", "down")
        assert any("Low success rate" in alert for alert in report.alerts)


# ---------------------------------------------------------------------------
# _check_source - down (3 consecutive failures)
# ---------------------------------------------------------------------------


class TestCheckSourceConsecutiveFailures:
    """_check_source should report 'down' with 3 consecutive failures."""

    async def test_three_consecutive_failures(self):
        """Source with 3 most-recent failures should be marked down."""
        monitor = SourceHealthMonitor()
        source = _make_source()

        now = datetime.utcnow()
        logs = [
            _make_fetch_log(status="failed", articles_new=0, started_at=now - timedelta(minutes=10)),
            _make_fetch_log(status="failed", articles_new=0, started_at=now - timedelta(minutes=20)),
            _make_fetch_log(status="failed", articles_new=0, started_at=now - timedelta(minutes=30)),
        ]

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = logs
        mock_session.execute = AsyncMock(return_value=mock_result)

        fake_get_session = _make_fake_get_session(mock_session)

        with patch("monitoring.health.get_session", new=fake_get_session):
            report = await monitor._check_source(source)

        assert report.health_status == "down"
        assert any("3 consecutive failures" in alert for alert in report.alerts)


# ---------------------------------------------------------------------------
# _check_source - degraded (no new articles)
# ---------------------------------------------------------------------------


class TestCheckSourceNoArticles:
    """_check_source should report 'degraded' when no articles in 24h."""

    async def test_no_articles_in_24h(self):
        """Successful fetches but zero new articles should be degraded."""
        monitor = SourceHealthMonitor()
        source = _make_source()

        logs = [
            _make_fetch_log(status="success", articles_new=0),
            _make_fetch_log(status="success", articles_new=0),
            _make_fetch_log(status="success", articles_new=0),
        ]

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = logs
        mock_session.execute = AsyncMock(return_value=mock_result)

        fake_get_session = _make_fake_get_session(mock_session)

        with patch("monitoring.health.get_session", new=fake_get_session):
            report = await monitor._check_source(source)

        assert report.health_status == "degraded"
        assert any("No new articles" in alert for alert in report.alerts)


# ---------------------------------------------------------------------------
# _check_source - disabled source
# ---------------------------------------------------------------------------


class TestCheckSourceDisabled:
    """_check_source should return early for disabled sources."""

    async def test_disabled_source_returns_early(self):
        """A disabled source should return a report without alerts or DB queries."""
        monitor = SourceHealthMonitor()
        source = _make_source(enabled=False, health_status="healthy")

        # No get_session mock needed -- the method returns before DB access
        report = await monitor._check_source(source)

        assert report.enabled is False
        assert report.alerts == []
        assert report.fetch_count_24h == 0


# ---------------------------------------------------------------------------
# SourceHealthReport defaults
# ---------------------------------------------------------------------------


class TestSourceHealthReportDefaults:
    """SourceHealthReport dataclass should have sensible defaults."""

    def test_default_values(self):
        report = SourceHealthReport(
            source_id="test",
            name="Test",
            enabled=True,
            last_fetched_at=None,
            health_status="healthy",
        )
        assert report.fetch_count_24h == 0
        assert report.success_rate_24h == 0.0
        assert report.total_articles_24h == 0
        assert report.avg_duration_ms == 0.0
        assert report.alerts == []

    def test_alerts_mutable_default(self):
        """Each report instance should have its own alerts list."""
        report1 = SourceHealthReport(
            source_id="a", name="A", enabled=True,
            last_fetched_at=None, health_status="healthy",
        )
        report2 = SourceHealthReport(
            source_id="b", name="B", enabled=True,
            last_fetched_at=None, health_status="healthy",
        )
        report1.alerts.append("test alert")
        assert report2.alerts == []
