# Logistics News Collector

[English](README.md) | [中文](README.zh-CN.md)

Global logistics and shipping news intelligence platform. Automatically collects, analyzes, and structures news from 16+ sources (RSS, API, web scraper) across ocean shipping, air cargo, and supply chain media. Features LLM-powered analysis, semantic search, real-time push, trend analytics, and automatic source discovery.

## Features

- **Multi-source collection** — RSS, REST API, web scraper, and zero-config universal adapter
- **16 pre-configured sources** — 10 English + 6 Chinese logistics/shipping news sites
- **LLM analysis pipeline** — 30-field structured extraction, bilingual summaries (EN/ZH), sentiment, entities, urgency
- **Smart deduplication** — 3-level cascade: URL exact match → Title SimHash → Content MinHash
- **Semantic search** — pgvector HNSW index, natural language query, related article recommendations
- **Real-time push** — WebSocket live feed + Webhook notifications (HMAC-SHA256 signed)
- **Trend analytics** — Topic trending, sentiment timeline, entity co-occurrence graph
- **Automatic source discovery** — DuckDuckGo/Google search + seed expansion, quality/relevance scoring, auto-approve
- **Web dashboard** — React SPA with 9 pages, dark mode, responsive layout
- **Production-ready** — API key auth, rate limiting, structured logging, Docker, CI/CD

## Quick Start

### 1. Start PostgreSQL

```bash
docker-compose up -d
```

Starts PostgreSQL 16 with pgvector extension on port 5432.

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env if you need custom database settings
```

Optional settings:
- `LLM_API_KEY` — Enable LLM analysis pipeline (OpenAI-compatible)
- `DISCOVERY_SEARCH_API` + `DISCOVERY_SEARCH_ENGINE_ID` — Google CSE (optional, DuckDuckGo is used by default for free)

### 4. Run the Application

```bash
python main.py
```

This will:
- Initialize the database (create tables, indexes)
- Seed 16 data sources from `config/sources.yaml`
- Start the scheduler (collection every 30 min, health check every 30 min, discovery every 24h)
- Start the API server on http://localhost:8000
- Serve the web dashboard at http://localhost:8000/

### 5. Build Frontend (optional)

```bash
cd frontend && npm install && npm run build
```

The built SPA is served automatically by FastAPI.

## API Endpoints

### Health & Status
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/health` | System health check |
| GET | `/api/v1/health/sources` | All sources' health status |

### Articles
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/articles` | List with filters, pagination, full-text search |
| GET | `/api/v1/articles/{id}` | Article detail with LLM analysis |
| GET | `/api/v1/articles/search/semantic` | Vector similarity search |
| GET | `/api/v1/articles/{id}/related` | Find similar articles |

### Sources
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/sources` | List configured sources |
| GET | `/api/v1/fetch-logs` | Fetch history logs |

### Source Discovery
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/discovery/start` | Start automatic discovery |
| POST | `/api/v1/discovery/stop` | Stop automatic discovery |
| GET | `/api/v1/discovery/status` | Discovery system status |
| POST | `/api/v1/discovery/scan` | Trigger discovery scan manually |
| POST | `/api/v1/discovery/validate` | Trigger validation of pending candidates |
| GET | `/api/v1/discovery/candidates` | List candidates (paginated, filterable) |
| POST | `/api/v1/discovery/candidates/{id}/approve` | Approve candidate → create source |
| POST | `/api/v1/discovery/candidates/{id}/reject` | Reject candidate |
| POST | `/api/v1/discovery/probe` | Probe any URL to check if it's a valid source |

### Subscriptions
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/subscriptions` | Create subscription |
| GET | `/api/v1/subscriptions` | List subscriptions |
| GET | `/api/v1/subscriptions/{id}` | Get subscription |
| PUT | `/api/v1/subscriptions/{id}` | Update subscription |
| DELETE | `/api/v1/subscriptions/{id}` | Delete subscription |

### Analytics
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/analytics/trending` | Top topics by frequency |
| GET | `/api/v1/analytics/sentiment-trend` | Sentiment over time |
| GET | `/api/v1/analytics/entities` | Top entities by type |
| GET | `/api/v1/analytics/entities/graph` | Entity co-occurrence graph |

### Export & Admin
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/export/articles` | CSV/JSON export with filters |
| POST | `/api/v1/admin/api-keys` | Create API key |
| GET | `/api/v1/admin/api-keys` | List API keys |
| DELETE | `/api/v1/admin/api-keys/{id}` | Delete API key |
| POST | `/api/v1/process` | Trigger LLM processing |

### WebSocket
| Endpoint | Description |
|----------|-------------|
| `/ws/articles` | Real-time article push with optional filters |

### Article Filters

`GET /api/v1/articles` supports:

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

Visit http://localhost:8000/docs for auto-generated OpenAPI documentation.

## Data Sources

### Pre-configured (16 sources)

**English (RSS, 30-min intervals):**
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

**Chinese (Scraper, 60-min intervals):**
11. 中国航务周刊 (China Shipping Gazette)
12. 搜航网 (Sofreight)
13. 国际船舶网 (International Marine)
14. 中国物流与采购网 (CFLP)
15. 运联智库 (YunLink)
16. 航运界 (Shipping Circle)

### Automatic Discovery

The system can automatically discover new sources via:
- **DuckDuckGo search** (free, default, no API key needed)
- **Google Custom Search** (optional, requires API key)
- **Seed URL expansion** (crawl outbound links from 12 known industry sites)

Discovered sources are validated (connectivity, article quality, logistics relevance) and scored 0-100. Sources scoring ≥ 75 are auto-approved and added to the collection pipeline.

Sources are configured in `config/sources.yaml` and `config/discovery_seeds.yaml`.

## Project Structure

```
├── config/
│   ├── settings.py              # Application settings (pydantic-settings)
│   ├── sources.yaml             # 16 pre-configured data sources
│   └── discovery_seeds.yaml     # Discovery search queries + seed URLs + relevance keywords
├── adapters/
│   ├── base.py                  # BaseAdapter abstract class
│   ├── rss_adapter.py           # RSS/Atom feed collector
│   ├── api_adapter.py           # REST API data source adapter
│   ├── scraper_adapter.py       # CSS selector-based web scraper
│   └── universal_adapter.py     # Zero-config universal adapter (3-strategy cascade)
├── discovery/
│   ├── engine.py                # Source discovery engine (DuckDuckGo/Google + seed expansion)
│   ├── validator.py             # Candidate validation + quality/relevance scoring
│   └── jobs.py                  # Discovery scheduler jobs with start/stop control
├── processing/
│   ├── cleaner.py               # Text cleaning & normalization
│   ├── deduplicator.py          # 3-level dedup (URL + SimHash + MinHash)
│   ├── simhash.py               # Title SimHash fingerprint
│   ├── minhash.py               # Content MinHash + LSH index
│   └── llm_pipeline.py          # LLM analysis pipeline (30-field extraction)
├── storage/
│   ├── database.py              # Async PostgreSQL connection
│   └── models.py                # SQLAlchemy models (8 tables)
├── api/
│   ├── main.py                  # FastAPI app with lifespan
│   ├── routes.py                # 35+ API endpoints
│   ├── auth.py                  # API key authentication
│   ├── ratelimit.py             # Sliding window rate limiter
│   └── websocket.py             # WebSocket connection manager
├── analytics/
│   ├── trending.py              # Topic trending analysis
│   ├── sentiment.py             # Sentiment timeline analysis
│   ├── entity_graph.py          # Entity co-occurrence graph
│   └── export.py                # CSV/JSON data export
├── notifications/
│   ├── dispatcher.py            # Notification dispatcher
│   └── webhook.py               # Webhook delivery (HMAC-SHA256)
├── scheduler/
│   └── jobs.py                  # APScheduler fetch/health/LLM jobs
├── monitoring/
│   ├── health.py                # Source health monitoring
│   └── logging_config.py        # JSON structured logging
├── frontend/
│   └── src/
│       ├── api/                 # 7 API client modules
│       ├── pages/               # 9 page components
│       ├── components/          # Reusable UI components
│       └── hooks/               # WebSocket hook
├── scripts/
│   └── seed_sources.py          # Source seeding from YAML
├── alembic/                     # Database migrations
├── tests/                       # 343+ unit tests
├── docker-compose.yml           # PostgreSQL + pgvector (dev)
├── docker-compose.prod.yml      # Production config with resource limits
├── Dockerfile                   # Multi-stage production build
├── .github/workflows/ci.yml     # CI pipeline (test + lint + docker)
├── requirements.txt
└── main.py                      # Entry point
```

## Tech Stack

- **Python 3.11+** — Core runtime
- **FastAPI** — REST API + WebSocket
- **SQLAlchemy 2.0** (async) — ORM with PostgreSQL
- **PostgreSQL 16 + pgvector** — Database with vector similarity search
- **React 18 + TypeScript + Vite** — Web dashboard SPA
- **Tailwind CSS** — Styling with dark mode
- **TanStack Query** — Frontend data fetching & caching
- **feedparser** — RSS/Atom parsing
- **trafilatura** — Article full-text extraction
- **duckduckgo-search** — Free web search for source discovery
- **APScheduler** — Periodic job scheduling
- **httpx** — Async HTTP client
- **Alembic** — Database migrations

## Development Roadmap

See [ROADMAP.md](ROADMAP.md) for detailed development history across 8 completed phases.

| Phase | Status | Description |
|-------|--------|-------------|
| 0+1 | Done | MVP: RSS collection + LLM analysis + REST API |
| 2 | Done | Multi-source: API/Scraper adapters + Chinese sources + Alembic |
| 3 | Done | Smart dedup (SimHash/MinHash) + semantic search |
| 4 | Done | Real-time push: WebSocket + Webhook + subscriptions |
| 5 | Done | Analytics: trending + sentiment + entity graph + export |
| 6 | Done | Production: universal adapter + auth + rate limit + logging + CI/CD + Docker |
| 7 | Done | Web dashboard: React SPA 9 pages |
| 8 | Done | Source discovery: DuckDuckGo search + auto-validate + auto-approve |
