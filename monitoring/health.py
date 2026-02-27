import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import func, select

from storage.database import get_session
from storage.models import FetchLog, Source

logger = logging.getLogger(__name__)


@dataclass
class SourceHealthReport:
    source_id: str
    name: str
    enabled: bool
    last_fetched_at: datetime | None
    health_status: str
    fetch_count_24h: int = 0
    success_rate_24h: float = 0.0
    total_articles_24h: int = 0
    avg_duration_ms: float = 0.0
    alerts: list[str] = field(default_factory=list)


class SourceHealthMonitor:
    """Monitor the health of each data source."""

    async def check_all(self) -> list[SourceHealthReport]:
        """Check health of all sources."""
        async with get_session() as session:
            result = await session.execute(select(Source))
            sources = result.scalars().all()

        reports = []
        for source in sources:
            report = await self._check_source(source)
            reports.append(report)

        return reports

    async def _check_source(self, source: Source) -> SourceHealthReport:
        """Check health of a single source."""
        report = SourceHealthReport(
            source_id=source.source_id,
            name=source.name,
            enabled=source.enabled,
            last_fetched_at=source.last_fetched_at,
            health_status=source.health_status,
        )

        if not source.enabled:
            return report

        cutoff = datetime.utcnow() - timedelta(hours=24)

        async with get_session() as session:
            # Get recent fetch logs
            result = await session.execute(
                select(FetchLog).where(
                    FetchLog.source_id == source.source_id,
                    FetchLog.started_at >= cutoff,
                )
            )
            logs = result.scalars().all()

        if not logs:
            report.alerts.append("No fetches in last 24 hours")
            report.health_status = "degraded"
            return report

        report.fetch_count_24h = len(logs)
        successful = [l for l in logs if l.status == "success"]
        report.success_rate_24h = len(successful) / len(logs) if logs else 0
        report.total_articles_24h = sum(l.articles_new for l in logs)
        durations = [l.duration_ms for l in logs if l.duration_ms]
        report.avg_duration_ms = sum(durations) / len(durations) if durations else 0

        # Generate alerts
        if report.success_rate_24h < 0.8:
            report.alerts.append(
                f"Low success rate: {report.success_rate_24h:.0%}"
            )
            report.health_status = "degraded"

        if report.total_articles_24h == 0:
            report.alerts.append("No new articles in 24 hours")
            report.health_status = "degraded"

        # Check for consecutive failures
        recent_statuses = [l.status for l in sorted(logs, key=lambda x: x.started_at or datetime.min, reverse=True)][:3]
        if all(s == "failed" for s in recent_statuses):
            report.alerts.append("3 consecutive failures")
            report.health_status = "down"

        if not report.alerts:
            report.health_status = "healthy"

        return report
