import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.ratelimit import rate_limiter
from api.routes import router
from api.websocket import ws_manager
from config.settings import settings
from monitoring.logging_config import setup_logging
from discovery.jobs import register_discovery_jobs
from scheduler.jobs import create_scheduler
from scripts.seed_sources import seed_sources
from storage.database import init_db

logger = logging.getLogger(__name__)

# Module-level reference so routes can access the scheduler
_scheduler = None


def get_scheduler():
    """Return the running scheduler instance."""
    return _scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    # Startup
    setup_logging(level=settings.log_level, json_format=settings.json_logging)
    logger.info("Starting Logistics News Collector...")

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    # Seed sources from YAML config
    await seed_sources()
    logger.info("Sources seeded")

    # Start scheduler
    global _scheduler
    scheduler = create_scheduler()
    register_discovery_jobs(scheduler)
    scheduler.start()
    _scheduler = scheduler
    logger.info("Scheduler started (with discovery jobs)")

    yield

    # Shutdown
    _scheduler = None
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


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Skip rate limiting for health check and websocket
    if request.url.path in ("/api/v1/health",) or request.url.path.startswith("/ws"):
        return await call_next(request)
    rate_limiter.check(request)
    return await call_next(request)


app.include_router(router, prefix="/api/v1")

# Serve frontend static files (SPA)
_frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _frontend_dist.is_dir():
    app.mount("/assets", StaticFiles(directory=_frontend_dist / "assets"), name="static")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve the SPA index.html for all non-API routes."""
        file_path = _frontend_dist / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(_frontend_dist / "index.html")


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
