import json
import logging

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections with optional filter subscriptions."""

    def __init__(self, max_connections: int = 100):
        self.max_connections = max_connections
        # Maps WebSocket -> filter criteria dict
        self._connections: dict[WebSocket, dict] = {}

    async def connect(self, ws: WebSocket, filters: dict | None = None):
        if len(self._connections) >= self.max_connections:
            await ws.close(code=1013, reason="Max connections reached")
            return False
        await ws.accept()
        self._connections[ws] = filters or {}
        logger.info(f"WebSocket connected (total: {len(self._connections)})")
        return True

    def disconnect(self, ws: WebSocket):
        self._connections.pop(ws, None)
        logger.info(f"WebSocket disconnected (total: {len(self._connections)})")

    def _matches_filters(self, article: dict, filters: dict) -> bool:
        """Check if article matches the subscription filters."""
        if not filters:
            return True

        if "transport_mode" in filters and filters["transport_mode"]:
            modes = article.get("transport_modes") or []
            if filters["transport_mode"] not in modes:
                return False

        if "topic" in filters and filters["topic"]:
            if article.get("primary_topic") != filters["topic"]:
                return False

        if "region" in filters and filters["region"]:
            regions = article.get("regions") or []
            if filters["region"] not in regions:
                return False

        if "language" in filters and filters["language"]:
            if article.get("language") != filters["language"]:
                return False

        return True

    async def broadcast_article(self, article: dict):
        """Send article to all matching connected clients."""
        dead = []
        for ws, filters in self._connections.items():
            if self._matches_filters(article, filters):
                try:
                    await ws.send_json({"type": "new_article", "data": article})
                except Exception:
                    dead.append(ws)
        for ws in dead:
            self._connections.pop(ws, None)

    @property
    def connection_count(self) -> int:
        return len(self._connections)


# Singleton manager
ws_manager = ConnectionManager()
