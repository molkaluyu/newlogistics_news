"""
Logistics News Collector — Entry Point

Starts the FastAPI application with scheduler for automated news collection.

Usage:
    docker-compose up -d      # Start PostgreSQL with pgvector
    pip install -r requirements.txt
    python main.py             # Start the application
"""

import uvicorn

from config.settings import settings

if __name__ == "__main__":
    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        log_level=settings.log_level.lower(),
    )
