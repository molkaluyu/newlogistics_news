import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router
from api.websocket import ws_manager
from config.settings import settings
from scheduler.jobs import create_scheduler
from scripts.seed_sources import seed_sources
from storage.database import init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    # Startup
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("Starting Logistics News Collector...")

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    # Seed sources from YAML config
    await seed_sources()
    logger.info("Sources seeded")

    # Start scheduler
    scheduler = create_scheduler()
    scheduler.start()
    logger.info("Scheduler started")

    yield

    # Shutdown
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")


app = FastAPI(
    title="Logistics News Collector API",
    description="Global logistics and shipping news aggregation system",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


@app.websocket("/ws/articles")
async def websocket_articles(
    ws: WebSocket,
    transport_mode: str | None = Query(None),
    topic: str | None = Query(None),
    region: str | None = Query(None),
    language: str | None = Query(None),
):
    """WebSocket endpoint for real-time article push with optional filters."""
    filters: dict = {}
    if transport_mode:
        filters["transport_mode"] = transport_mode
    if topic:
        filters["topic"] = topic
    if region:
        filters["region"] = region
    if language:
        filters["language"] = language

    connected = await ws_manager.connect(ws, filters)
    if not connected:
        return

    try:
        while True:
            # Keep connection alive; listen for client messages (ping/pong)
            try:
                data = await asyncio.wait_for(ws.receive_text(), timeout=30.0)
                # Respond to explicit ping messages from clients
                if data == "ping":
                    await ws.send_text("pong")
            except asyncio.TimeoutError:
                # Send a heartbeat to detect dead connections
                try:
                    await ws.send_json({"type": "heartbeat"})
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        ws_manager.disconnect(ws)
