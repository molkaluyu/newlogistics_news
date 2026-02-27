import csv
import io
import json
import logging
from datetime import datetime

from sqlalchemy import select
from storage.database import get_session
from storage.models import Article

logger = logging.getLogger(__name__)

# Fields available for export
EXPORT_FIELDS = [
    "id",
    "source_id",
    "source_name",
    "url",
    "title",
    "body_text",
    "language",
    "published_at",
    "summary_en",
    "summary_zh",
    "transport_modes",
    "primary_topic",
    "secondary_topics",
    "content_type",
    "regions",
    "entities",
    "sentiment",
    "market_impact",
    "urgency",
    "key_metrics",
]


async def export_articles_csv(
    source_id: str | None = None,
    transport_mode: str | None = None,
    topic: str | None = None,
    language: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    fields: list[str] | None = None,
) -> str:
    """Export articles as CSV string.
    Returns the full CSV content as a string (for StreamingResponse).
    """
    fields = fields or EXPORT_FIELDS
    # Validate fields
    fields = [f for f in fields if f in EXPORT_FIELDS]

    articles = await _query_articles(
        source_id, transport_mode, topic, language, from_date, to_date
    )

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()

    for article in articles:
        row = {}
        for f in fields:
            val = getattr(article, f, None)
            if isinstance(val, (list, dict)):
                row[f] = json.dumps(val, ensure_ascii=False, default=str)
            elif isinstance(val, datetime):
                row[f] = val.isoformat()
            else:
                row[f] = val
        writer.writerow(row)

    return output.getvalue()


async def export_articles_json(
    source_id: str | None = None,
    transport_mode: str | None = None,
    topic: str | None = None,
    language: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    fields: list[str] | None = None,
) -> list[dict]:
    """Export articles as list of dicts."""
    fields = fields or EXPORT_FIELDS
    fields = [f for f in fields if f in EXPORT_FIELDS]

    articles = await _query_articles(
        source_id, transport_mode, topic, language, from_date, to_date
    )

    result = []
    for article in articles:
        row = {}
        for f in fields:
            val = getattr(article, f, None)
            if isinstance(val, datetime):
                val = val.isoformat()
            row[f] = val
        result.append(row)

    return result


async def _query_articles(
    source_id=None,
    transport_mode=None,
    topic=None,
    language=None,
    from_date=None,
    to_date=None,
    max_rows: int = 10000,
):
    """Query articles with filters, up to max_rows."""
    async with get_session() as session:
        query = select(Article).order_by(
            Article.published_at.desc().nullslast()
        )

        if source_id:
            query = query.where(Article.source_id == source_id)
        if transport_mode:
            query = query.where(
                Article.transport_modes.contains([transport_mode])
            )
        if topic:
            query = query.where(Article.primary_topic == topic)
        if language:
            query = query.where(Article.language == language)
        if from_date:
            query = query.where(Article.published_at >= from_date)
        if to_date:
            query = query.where(Article.published_at <= to_date)

        query = query.limit(max_rows)
        result = await session.execute(query)
        return result.scalars().all()
