import logging
from datetime import datetime, timedelta

from sqlalchemy import case, func, select
from storage.database import get_session
from storage.models import Article

logger = logging.getLogger(__name__)


class SentimentAnalyzer:
    """Analyzes sentiment trends over time."""

    async def get_sentiment_trend(
        self,
        granularity: str = "day",  # hour, day, week
        transport_mode: str | None = None,
        topic: str | None = None,
        region: str | None = None,
        days: int = 30,
    ) -> dict:
        """Get sentiment distribution over time.

        Returns dict with:
            granularity, data_points (list of {period, positive, negative,
            neutral, mixed, total, sentiment_ratio})
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        async with get_session() as session:
            # Build time bucket expression based on granularity
            if granularity == "hour":
                time_bucket = func.date_trunc("hour", Article.published_at)
            elif granularity == "week":
                time_bucket = func.date_trunc("week", Article.published_at)
            else:
                time_bucket = func.date_trunc("day", Article.published_at)

            query = (
                select(
                    time_bucket.label("period"),
                    func.count(Article.id).label("total"),
                    func.count(
                        case((Article.sentiment == "positive", 1))
                    ).label("positive"),
                    func.count(
                        case((Article.sentiment == "negative", 1))
                    ).label("negative"),
                    func.count(
                        case((Article.sentiment == "neutral", 1))
                    ).label("neutral"),
                    func.count(
                        case((Article.sentiment == "mixed", 1))
                    ).label("mixed"),
                )
                .where(
                    Article.published_at >= cutoff,
                    Article.sentiment.isnot(None),
                )
            )

            if transport_mode:
                query = query.where(
                    Article.transport_modes.contains([transport_mode])
                )
            if topic:
                query = query.where(Article.primary_topic == topic)
            if region:
                query = query.where(Article.regions.contains([region]))

            query = query.group_by(time_bucket).order_by(time_bucket)

            result = await session.execute(query)
            rows = result.all()

        data_points = []
        for row in rows:
            total = row.total or 1
            pos = row.positive or 0
            neg = row.negative or 0
            ratio = (
                round((pos - neg) / total, 4) if total > 0 else 0.0
            )

            data_points.append(
                {
                    "period": row.period.isoformat() if row.period else None,
                    "positive": pos,
                    "negative": neg,
                    "neutral": row.neutral or 0,
                    "mixed": row.mixed or 0,
                    "total": row.total,
                    "sentiment_ratio": ratio,
                }
            )

        return {
            "granularity": granularity,
            "days": days,
            "data_points": data_points,
        }
