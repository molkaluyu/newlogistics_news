import logging
from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy import select
from storage.database import get_session
from storage.models import Article

logger = logging.getLogger(__name__)


class EntityAnalyzer:
    """Analyzes entity relationships from article entities JSONB."""

    async def get_top_entities(
        self,
        entity_type: str | None = None,  # companies, ports, people, organizations (or None for all)
        days: int = 30,
        limit: int = 20,
    ) -> list[dict]:
        """Get most frequently mentioned entities.

        The Article.entities field is JSONB with structure:
        {"companies": [...], "ports": [...], "people": [...], "organizations": [...]}
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        async with get_session() as session:
            query = select(Article.entities).where(
                Article.entities.isnot(None),
                Article.published_at >= cutoff,
            )
            result = await session.execute(query)
            rows = result.all()

        counter: Counter = Counter()
        entity_types = (
            [entity_type]
            if entity_type
            else ["companies", "ports", "people", "organizations"]
        )

        for row in rows:
            entities = row[0]
            if not isinstance(entities, dict):
                continue
            for etype in entity_types:
                for name in entities.get(etype, []):
                    if isinstance(name, str) and name.strip():
                        counter[(name.strip(), etype)] += 1

        return [
            {"name": name, "type": etype, "count": count}
            for (name, etype), count in counter.most_common(limit)
        ]

    async def get_entity_cooccurrence(
        self,
        days: int = 30,
        min_cooccurrence: int = 2,
        limit: int = 50,
    ) -> dict:
        """Get entity co-occurrence graph (entities appearing in same articles).

        Returns a JSON-graph-format dict:
        { "nodes": [{"id", "type", "count"}], "edges": [{"source", "target", "weight"}] }
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        async with get_session() as session:
            query = select(Article.entities).where(
                Article.entities.isnot(None),
                Article.published_at >= cutoff,
            )
            result = await session.execute(query)
            rows = result.all()

        # Count individual entities and co-occurrences
        entity_counter: Counter = Counter()
        edge_counter: Counter = Counter()
        entity_type_map: dict[str, str] = {}

        for row in rows:
            entities = row[0]
            if not isinstance(entities, dict):
                continue

            # Flatten all entities from this article
            article_entities = []
            for etype in ["companies", "ports", "people", "organizations"]:
                for name in entities.get(etype, []):
                    if isinstance(name, str) and name.strip():
                        clean = name.strip()
                        article_entities.append(clean)
                        entity_counter[clean] += 1
                        entity_type_map[clean] = etype

            # Count pairwise co-occurrences
            unique = sorted(set(article_entities))
            for i in range(len(unique)):
                for j in range(i + 1, len(unique)):
                    edge_counter[(unique[i], unique[j])] += 1

        # Filter edges by min_cooccurrence
        filtered_edges = [
            (src, tgt, w)
            for (src, tgt), w in edge_counter.most_common()
            if w >= min_cooccurrence
        ][:limit]

        # Collect nodes that appear in edges
        node_set: set[str] = set()
        for src, tgt, _ in filtered_edges:
            node_set.add(src)
            node_set.add(tgt)

        nodes = [
            {
                "id": name,
                "type": entity_type_map.get(name, "unknown"),
                "count": entity_counter[name],
            }
            for name in node_set
        ]
        nodes.sort(key=lambda n: n["count"], reverse=True)

        edges = [
            {"source": src, "target": tgt, "weight": w}
            for src, tgt, w in filtered_edges
        ]

        return {"nodes": nodes, "edges": edges}
