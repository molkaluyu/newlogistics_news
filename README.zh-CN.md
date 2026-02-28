# 物流新闻采集平台

[English](README.md) | [中文](README.zh-CN.md)

全球物流与航运新闻情报平台。自动从 16+ 个信息源（RSS、API、网页爬虫）采集海运、空运、供应链领域新闻，提供 LLM 智能分析、语义搜索、实时推送、趋势分析和信息源自动发现。

## 功能特性

- **多源采集** — RSS、REST API、网页爬虫、零配置通用适配器
- **16 个预置信息源** — 10 个英文 + 6 个中文物流/航运新闻站点
- **LLM 分析管线** — 30 字段结构化提取、中英双语摘要、情感分析、实体识别、紧急度评估
- **智能去重** — 三级级联：URL 精确匹配 → 标题 SimHash → 内容 MinHash
- **语义搜索** — pgvector HNSW 索引、自然语言查询、相关文章推荐
- **实时推送** — WebSocket 实时流 + Webhook 通知（HMAC-SHA256 签名）
- **趋势分析** — 热点话题追踪、情感时序分析、实体共现图谱
- **信息源自动发现** — DuckDuckGo/Google 搜索 + 种子扩展、质量/相关性评分、高分自动入库
- **Web 可视化面板** — React SPA 9 页面、暗色模式、响应式布局
- **生产就绪** — API Key 认证、限流、结构化日志、Docker、CI/CD

## 快速开始

### 1. 启动 PostgreSQL

```bash
docker-compose up -d
```

启动 PostgreSQL 16 + pgvector 扩展，端口 5432。

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
cp .env.example .env
# 按需修改数据库连接等配置
```

可选配置：
- `LLM_API_KEY` — 启用 LLM 分析管线（OpenAI 兼容接口）
- `DISCOVERY_SEARCH_API` + `DISCOVERY_SEARCH_ENGINE_ID` — Google CSE（可选，默认使用免费的 DuckDuckGo）

### 4. 运行应用

```bash
python main.py
```

启动后将自动完成：
- 初始化数据库（建表、建索引）
- 从 `config/sources.yaml` 导入 16 个预置信息源
- 启动调度器（采集每 30 分钟、健康检查每 30 分钟、信息源发现每 24 小时）
- 启动 API 服务 http://localhost:8000
- 在 http://localhost:8000/ 提供 Web 面板

### 5. 构建前端（可选）

```bash
cd frontend && npm install && npm run build
```

构建后的 SPA 由 FastAPI 自动托管。

## API 接口

### 健康检查
| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/v1/health` | 系统健康检查 |
| GET | `/api/v1/health/sources` | 所有源的健康状态 |

### 文章
| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/v1/articles` | 文章列表（筛选、分页、全文搜索） |
| GET | `/api/v1/articles/{id}` | 文章详情（含 LLM 分析结果） |
| GET | `/api/v1/articles/search/semantic` | 向量语义搜索 |
| GET | `/api/v1/articles/{id}/related` | 相关文章推荐 |

### 信息源
| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/v1/sources` | 已配置的信息源列表 |
| GET | `/api/v1/fetch-logs` | 采集历史日志 |

### 信息源发现
| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/v1/discovery/start` | 启动自动发现 |
| POST | `/api/v1/discovery/stop` | 停止自动发现 |
| GET | `/api/v1/discovery/status` | 发现系统运行状态 |
| POST | `/api/v1/discovery/scan` | 手动触发发现扫描 |
| POST | `/api/v1/discovery/validate` | 手动触发候选源验证 |
| GET | `/api/v1/discovery/candidates` | 候选源列表（分页、筛选） |
| POST | `/api/v1/discovery/candidates/{id}/approve` | 批准候选源 → 创建信息源 |
| POST | `/api/v1/discovery/candidates/{id}/reject` | 拒绝候选源 |
| POST | `/api/v1/discovery/probe` | 即时探测任意 URL 是否为有效信息源 |

### 订阅管理
| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/v1/subscriptions` | 创建订阅 |
| GET | `/api/v1/subscriptions` | 订阅列表 |
| GET | `/api/v1/subscriptions/{id}` | 订阅详情 |
| PUT | `/api/v1/subscriptions/{id}` | 更新订阅 |
| DELETE | `/api/v1/subscriptions/{id}` | 删除订阅 |

### 分析
| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/v1/analytics/trending` | 热点话题排行 |
| GET | `/api/v1/analytics/sentiment-trend` | 情感趋势时序 |
| GET | `/api/v1/analytics/entities` | 实体频率排行 |
| GET | `/api/v1/analytics/entities/graph` | 实体共现关系图 |

### 导出与管理
| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/v1/export/articles` | CSV/JSON 导出（支持筛选） |
| POST | `/api/v1/admin/api-keys` | 创建 API Key |
| GET | `/api/v1/admin/api-keys` | API Key 列表 |
| DELETE | `/api/v1/admin/api-keys/{id}` | 删除 API Key |
| POST | `/api/v1/process` | 手动触发 LLM 处理 |

### WebSocket
| 端点 | 说明 |
|------|------|
| `/ws/articles` | 实时文章推送（支持条件过滤） |

### 文章筛选参数

`GET /api/v1/articles` 支持以下查询参数：

- `source_id` — 按信息源筛选
- `transport_mode` — 运输方式：`ocean`、`air`、`rail`、`road`
- `topic` — 主题筛选
- `language` — 语言：`en`、`zh`
- `sentiment` — 情感：`positive`、`negative`、`neutral`
- `urgency` — 紧急度：`high`、`medium`、`low`
- `from_date` / `to_date` — 日期范围
- `search` — 全文搜索
- `page` / `page_size` — 分页

### 交互式 API 文档

启动后访问 http://localhost:8000/docs 查看自动生成的 OpenAPI 文档。

## 信息源

### 预置信息源（16 个）

**英文源（RSS，30 分钟采集间隔）：**
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

**中文源（爬虫，60 分钟采集间隔）：**
11. 中国航务周刊
12. 搜航网
13. 国际船舶网
14. 中国物流与采购网
15. 运联智库
16. 航运界

### 自动发现

系统可通过以下方式自动发现新信息源：
- **DuckDuckGo 搜索**（免费、默认、无需 API Key）
- **Google 自定义搜索**（可选，需要 API Key）
- **种子 URL 扩展**（从 12 个已知行业站点爬取外链）

发现的候选源将经过验证（连通性、文章质量、物流相关性）并获得 0-100 评分。综合评分 ≥ 75 的源自动批准并加入采集管线。

信息源配置位于 `config/sources.yaml` 和 `config/discovery_seeds.yaml`。

## 项目结构

```
├── config/
│   ├── settings.py              # 应用配置 (pydantic-settings)
│   ├── sources.yaml             # 16 个预置信息源配置
│   └── discovery_seeds.yaml     # 发现搜索关键词 + 种子 URL + 相关性词库
├── adapters/
│   ├── base.py                  # BaseAdapter 抽象基类
│   ├── rss_adapter.py           # RSS/Atom 采集器
│   ├── api_adapter.py           # REST API 数据源适配器
│   ├── scraper_adapter.py       # CSS 选择器网页爬虫
│   └── universal_adapter.py     # 零配置通用适配器（三级策略级联）
├── discovery/
│   ├── engine.py                # 信息源发现引擎（DuckDuckGo/Google + 种子扩展）
│   ├── validator.py             # 候选源验证 + 质量/相关性评分
│   └── jobs.py                  # 发现调度任务（支持启停控制）
├── processing/
│   ├── cleaner.py               # 文本清洗与标准化
│   ├── deduplicator.py          # 三级去重（URL + SimHash + MinHash）
│   ├── simhash.py               # 标题 SimHash 指纹
│   ├── minhash.py               # 内容 MinHash + LSH 索引
│   └── llm_pipeline.py          # LLM 分析管线（30 字段提取）
├── storage/
│   ├── database.py              # 异步 PostgreSQL 连接
│   └── models.py                # SQLAlchemy 模型（8 张表）
├── api/
│   ├── main.py                  # FastAPI 应用与生命周期
│   ├── routes.py                # 35+ 个 API 端点
│   ├── auth.py                  # API Key 认证
│   ├── ratelimit.py             # 滑动窗口限流器
│   └── websocket.py             # WebSocket 连接管理
├── analytics/
│   ├── trending.py              # 热点话题分析
│   ├── sentiment.py             # 情感时序分析
│   ├── entity_graph.py          # 实体共现图谱
│   └── export.py                # CSV/JSON 数据导出
├── notifications/
│   ├── dispatcher.py            # 通知分发器
│   └── webhook.py               # Webhook 投递（HMAC-SHA256）
├── scheduler/
│   └── jobs.py                  # APScheduler 采集/健康/LLM 任务
├── monitoring/
│   ├── health.py                # 信息源健康监控
│   └── logging_config.py        # JSON 结构化日志
├── frontend/
│   └── src/
│       ├── api/                 # 7 个 API 客户端模块
│       ├── pages/               # 9 个页面组件
│       ├── components/          # 可复用 UI 组件
│       └── hooks/               # WebSocket Hook
├── scripts/
│   └── seed_sources.py          # 从 YAML 导入信息源
├── alembic/                     # 数据库迁移
├── tests/                       # 343+ 单元测试
├── docker-compose.yml           # PostgreSQL + pgvector（开发环境）
├── docker-compose.prod.yml      # 生产配置（资源限制）
├── Dockerfile                   # 多阶段生产构建
├── .github/workflows/ci.yml     # CI 流水线（测试 + 代码检查 + Docker）
├── requirements.txt
└── main.py                      # 入口文件
```

## 技术栈

- **Python 3.11+** — 核心运行时
- **FastAPI** — REST API + WebSocket
- **SQLAlchemy 2.0**（异步） — PostgreSQL ORM
- **PostgreSQL 16 + pgvector** — 数据库 + 向量相似度搜索
- **React 18 + TypeScript + Vite** — Web 前端 SPA
- **Tailwind CSS** — 样式框架（支持暗色模式）
- **TanStack Query** — 前端数据获取与缓存
- **feedparser** — RSS/Atom 解析
- **trafilatura** — 文章全文提取
- **duckduckgo-search** — 免费 Web 搜索（信息源发现）
- **APScheduler** — 定时任务调度
- **httpx** — 异步 HTTP 客户端
- **Alembic** — 数据库迁移

## 开发路线图

详见 [ROADMAP.md](ROADMAP.md)，共 8 个阶段已全部完成。

| 阶段 | 状态 | 说明 |
|------|------|------|
| 0+1 | 已完成 | MVP：RSS 采集 + LLM 分析 + REST API |
| 2 | 已完成 | 多源扩展：API/Scraper 适配器 + 中文源 + Alembic |
| 3 | 已完成 | 智能去重（SimHash/MinHash）+ 语义搜索 |
| 4 | 已完成 | 实时推送：WebSocket + Webhook + 订阅管理 |
| 5 | 已完成 | 分析：趋势 + 情感 + 实体图谱 + 导出 |
| 6 | 已完成 | 生产加固：通用爬虫 + 认证 + 限流 + 日志 + CI/CD + Docker |
| 7 | 已完成 | Web 面板：React SPA 9 页面 |
| 8 | 已完成 | 信息源发现：DuckDuckGo 搜索 + 自动验证 + 自动入库 |
