# Logistics News Collector

Global logistics and shipping news aggregation system. Collects news from RSS feeds across ocean shipping, air cargo, and supply chain media, stores structured data in PostgreSQL, and exposes a REST API.

## Quick Start

### 1. Start PostgreSQL

```bash
docker-compose up -d
```

This starts PostgreSQL 16 with pgvector extension on port 5432.

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env if you need custom database settings
```

### 4. Run the Application

```bash
python main.py
```

This will:
- Initialize the database (create tables, indexes)
- Seed data sources from `config/sources.yaml`
- Start the scheduler for automatic collection (every 30 minutes)
- Start the API server on http://localhost:8000

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/health` | System health check |
| GET | `/api/v1/sources` | List configured data sources |
| GET | `/api/v1/articles` | List articles (with filters) |
| GET | `/api/v1/articles/{id}` | Get article detail |
| GET | `/api/v1/fetch-logs` | View collection logs |

### Article Filters

`GET /api/v1/articles` supports these query parameters:

- `source_id` — Filter by source
- `transport_mode` — `ocean`, `air`, `rail`, `road`
- `topic` — Primary topic filter
- `language` — `en`, `zh`
- `sentiment` — `positive`, `negative`, `neutral`
- `urgency` — `high`, `medium`, `low`
- `from_date` / `to_date` — Date range
- `search` — Full-text search
- `page` / `page_size` — Pagination

### Interactive API Docs

Once running, visit http://localhost:8000/docs for the auto-generated OpenAPI documentation.

## Data Sources (MVP)

10 English RSS sources covering ocean shipping, air cargo, and supply chain:

1. The Loadstar
2. Splash247
3. FreightWaves
4. gCaptain
5. The Maritime Executive
6. Air Cargo News
7. Supply Chain Dive
8. Journal of Commerce (JOC)
9. SupplyChainBrain
10. Hellenic Shipping News

Sources are configured in `config/sources.yaml`.

## Project Structure

```
├── config/
│   ├── settings.py        # Application settings (pydantic-settings)
│   └── sources.yaml       # Data source configurations
├── adapters/
│   ├── base.py            # BaseAdapter abstract class
│   └── rss_adapter.py     # RSS feed collector
├── processing/
│   ├── cleaner.py         # Text cleaning & normalization
│   └── deduplicator.py    # URL-based deduplication
├── storage/
│   ├── database.py        # Async PostgreSQL connection
│   └── models.py          # SQLAlchemy models
├── api/
│   ├── main.py            # FastAPI app with lifespan
│   └── routes.py          # API endpoints
├── scheduler/
│   └── jobs.py            # APScheduler fetch jobs
├── monitoring/
│   └── health.py          # Source health monitoring
├── scripts/
│   ├── init_db.sql        # Database schema (reference)
│   └── seed_sources.py    # Source seeding from YAML
├── docker-compose.yml     # PostgreSQL + pgvector
├── requirements.txt
└── main.py                # Entry point
```

## Tech Stack

- **Python 3.11+**
- **FastAPI** — REST API
- **SQLAlchemy 2.0** (async) — ORM
- **PostgreSQL 16 + pgvector** — Database with vector support
- **feedparser** — RSS/Atom parsing
- **trafilatura** — Article full-text extraction
- **APScheduler** — Periodic collection jobs
- **httpx** — Async HTTP client
