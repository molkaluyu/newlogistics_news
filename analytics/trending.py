import logging
from datetime import datetime, timedelta

from sqlalchemy import func, select
from storage.database import get_session
from storage.models import Article

logger = logging.getLogger(__name__)


class TrendingAnalyzer:
    """Analyzes trending topics based on article frequency."""

    async def get_trending(
        self,
        time_window: str = "24h",  # 24h, 7d, 30d
        transport_mode: str | None = None,
        region: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """Get trending topics ranked by frequency.

        Returns list of dicts with:
            topic, count, growth_rate, representative_articles
        """
        # Parse time window
        window_hours = {"24h": 24, "7d": 168, "30d": 720}.get(time_window, 24)
        cutoff = datetime.utcnow() - timedelta(hours=window_hours)
        # For growth rate: compare current period with previous equal period
        prev_cutoff = cutoff - timedelta(hours=window_hours)

        async with get_session() as session:
            # Current period topic counts
            query = (
                select(
                    Article.primary_topic,
                    func.count(Article.id).label("count"),
                )
                .where(Article.primary_topic.isnot(None))
                .where(Article.published_at >= cutoff)
            )
            if transport_mode:
                query = query.where(
                    Article.transport_modes.contains([transport_mode])
                )
            if region:
                query = query.where(Article.regions.contains([region]))

            query = (
                query.group_by(Article.primary_topic)
                .order_by(func.count(Article.id).desc())
                .limit(limit)
            )

            result = await session.execute(query)
            current_counts = result.all()

            if not current_counts:
                return []

            # Previous period for growth rate
            topics = [row.primary_topic for row in current_counts]
            prev_query = (
                select(
                    Article.primary_topic,
                    func.count(Article.id).label("count"),
                )
                .where(Article.primary_topic.in_(topics))
                .where(Article.published_at >= prev_cutoff)
                .where(Article.published_at < cutoff)
            )
            prev_result = await session.execute(
                prev_query.group_by(Article.primary_topic)
            )
            prev_map = {
                row.primary_topic: row.count for row in prev_result.all()
            }

            # Get representative article for each topic
            trending = []
            for row in current_counts:
                topic = row.primary_topic
                count = row.count
                prev_count = prev_map.get(topic, 0)
                growth = (
                    ((count - prev_count) / prev_count * 100)
                    if prev_count > 0
                    else (100.0 if count > 0 else 0.0)
                )

                # Fetch one representative article
                rep_query = (
                    select(
                        Article.id,
                        Article.title,
                        Article.url,
                        Article.source_name,
                    )
                    .where(Article.primary_topic == topic)
                    .where(Article.published_at >= cutoff)
                    .order_by(Article.published_at.desc())
                    .limit(1)
                )
                rep_result = await session.execute(rep_query)
                rep = rep_result.first()

                trending.append(
                    {
                        "topic": topic,
                        "count": count,
                        "growth_rate": round(growth, 1),
                        "representative_article": {
                            "id": rep.id,
                            "title": rep.title,
                            "url": rep.url,
                            "source_name": rep.source_name,
                        }
                        if rep
                        else None,
                    }
                )

            return trending
