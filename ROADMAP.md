# Logistics News Collector — Development Roadmap

## Phase 0 + Phase 1: MVP Foundation ✅ (已完成)

基础设施 + 核心采集 + API 服务

### Phase 0: Infrastructure
- [x] Docker Compose — PostgreSQL 16 + pgvector
- [x] SQLAlchemy 2.0 async ORM (Source, Article, FetchLog)
- [x] Database init script (pgvector extension + 3 tables + 12 索引)
- [x] Pydantic-settings 配置管理 (.env / YAML)
- [x] Project scaffolding (adapters / processing / storage / api / scheduler / monitoring)

### Phase 1: Core Collection & API
- [x] BaseAdapter 抽象基类 (支持 rss / api / scraper 类型扩展)
- [x] RSSAdapter — feedparser 解析 + trafilatura 全文提取
- [x] 10 个英文 RSS 源 (海运 / 空运 / 供应链)
- [x] Text cleaner — HTML 清洗, Unicode NFKC 标准化, 标题去源名
- [x] URL 精确去重 (Level 1)
- [x] 语言检测 (langdetect)
- [x] LLM 分析管线 — 30 字段结构化提取 + 中英双语摘要
- [x] 向量嵌入生成 (text-embedding-3-large, 1024 维)
- [x] APScheduler 定时调度 (采集 / 健康检查 / LLM 处理)
- [x] FastAPI REST API — 7 个端点, 全文搜索, 分页, 多维过滤
- [x] 源健康监控 + 告警 (24h 窗口分析)
- [x] Dockerfile + docker-compose 一键部署
- [x] 86 个单元测试 (cleaner / models / api / deduplicator)

---

## Phase 2: Multi-Source Expansion (多源扩展) ✅ (已完成)

目标：突破 RSS 单一采集方式，接入中文源，建立数据库版本管理

### 2.1 新增适配器
- [x] `adapters/api_adapter.py` — REST API 数据源适配器
  - 支持 JSON/XML 响应解析
  - 可配置认证方式 (API Key / Bearer Token)
  - 分页遍历逻辑 (page_number / offset / cursor)
  - 响应字段映射 (通过 `parser_config` JSONB 配置)
- [x] `adapters/scraper_adapter.py` — 网页爬虫适配器
  - 基于 CSS selector 的文章列表+详情页提取
  - 利用 `scraper_config` JSONB 配置选择器规则
  - trafilatura 全文提取 fallback
- [x] 更新 `scheduler/jobs.py` ADAPTER_MAP 注册新适配器

### 2.2 中文新闻源
- [x] 接入 7 个中文物流/航运源到 `config/sources.yaml`
  - 中国航务周刊, 搜航网, 国际船舶网, 中国物流与采购网, 运联智库, 航运界, 中国港口网
- [x] 中文全文提取优化 (trafilatura 中文编码兼容性)
- [x] 中文文本清洗规则 (全角标点标准化)

### 2.3 数据库迁移管理
- [x] 集成 Alembic async migration (alembic/env.py)
- [x] 初始迁移 baseline ready
- [x] 迁移脚本模板 + 配置

### 2.4 补全测试 (81 新测试, 总计 167)
- [x] `tests/test_rss_adapter.py` — RSS 适配器测试 (21)
- [x] `tests/test_language.py` — 语言检测测试 (9)
- [x] `tests/test_llm_pipeline.py` — LLM 管线测试 (29)
- [x] `tests/test_scheduler.py` — 调度器测试 (13)
- [x] `tests/test_health.py` — 健康监控测试 (10)

---

## Phase 3: Advanced Dedup & Semantic Search (智能去重 + 语义搜索) ✅ (已完成)

目标：解决跨源重复文章问题，释放 pgvector 向量搜索能力

### 3.1 Title SimHash 去重 (Level 2)
- [x] `processing/simhash.py` — SimHash 指纹生成
  - 中英文分词 (CJK 单字 + 英文单词)
  - 64-bit SimHash 指纹 (MD5-based)
  - 汉明距离阈值匹配 (≤3 视为相似)
- [x] Article 模型新增 `title_simhash: BigInteger` 列 + 索引
- [x] Deduplicator 扩展：URL match → SimHash fallback → MinHash
- [x] LLM 管线自动计算 SimHash 指纹

### 3.2 Content MinHash 去重 (Level 3)
- [x] `processing/minhash.py` — MinHash 内容指纹
  - Character-level Shingling (5-gram) + 128 个哈希函数
  - Jaccard 相似度估算
  - LSH (Locality-Sensitive Hashing) 内存索引 (16 bands × 8 rows)
- [x] Article 模型新增 `content_minhash: ARRAY(BigInteger)` 列
- [x] Deduplicator.check_all_levels() 三级联合去重

### 3.3 语义搜索 API
- [x] `GET /api/v1/articles/search/semantic` 端点
  - 输入自然语言查询 → 生成查询向量
  - pgvector cosine distance 搜索 (HNSW 索引)
  - 支持混合搜索 (语义 + transport_mode / topic / language 过滤)
  - 返回相似度分数
- [x] `GET /api/v1/articles/{id}/related` 端点
  - 基于向量相似度推荐相关文章
  - exclude_same_source 排除同源选项
  - limit 参数控制 Top-K

### 3.4 向量索引优化
- [x] HNSW 索引 (m=16, ef_construction=64, vector_cosine_ops)
- [x] Alembic 迁移 002: 新增 dedup 列 + HNSW 索引

---

## Phase 4: Real-time Push & Subscriptions (实时推送 + 订阅) ✅ (已完成)

目标：从 "被动查询" 进化为 "主动推送"，支持用户个性化订阅

### 4.1 WebSocket 实时推送
- [x] `api/websocket.py` — ConnectionManager + WebSocket 端点
  - `/ws/articles` 新文章实时推送 (带心跳, ping/pong)
  - 支持按 transport_mode / topic / region / language 过滤订阅
  - 连接管理器 (最大 100 连接, 自动清理死连接)
- [x] `notifications/dispatcher.py` 采集管线触发广播

### 4.2 Webhook 通知
- [x] `notifications/webhook.py` — Webhook 推送服务
  - HMAC-SHA256 签名 (X-Webhook-Signature header)
  - 重试机制 (指数退避 2/4/8s, 最多 3 次)
  - 投递日志记录 (WebhookDeliveryLog 表)
- [x] 订阅 CRUD API (POST/GET/PUT/DELETE /api/v1/subscriptions)
- [x] 数据模型: Subscription + WebhookDeliveryLog 表
- [x] Alembic 迁移 003: subscriptions + webhook_delivery_logs

### 4.3 订阅管理
- [x] Subscription 模型 — 多维过滤条件 (source_ids, transport_modes, topics, regions, languages, urgency)
- [x] 通知渠道: websocket / webhook (email 留待 Phase 6)
- [x] 频率设置: realtime / daily / weekly
- [x] 订阅 CRUD 5 个端点

---

## Phase 5: Analytics & Intelligence (分析与情报) ✅ (已完成)

目标：从 "数据收集" 升级为 "情报平台"，提供趋势分析与市场洞察

### 5.1 趋势分析
- [x] `analytics/trending.py` — TrendingAnalyzer
  - 基于时间窗口的话题频率统计 (24h/7d/30d)
  - 增长率计算 (当前频率 vs 上一同等周期)
  - 代表性文章关联
- [x] `GET /api/v1/analytics/trending` 端点

### 5.2 情感时序分析
- [x] `analytics/sentiment.py` — SentimentAnalyzer
- [x] `GET /api/v1/analytics/sentiment-trend` 端点
  - 按时间粒度 (hour/day/week) 聚合情感分布
  - 支持按运输方式、区域、话题切片
  - 情感比率 (positive - negative) / total

### 5.3 实体知识图谱
- [x] `analytics/entity_graph.py` — EntityAnalyzer
  - get_top_entities(): 实体频率排名 (按类型筛选)
  - get_entity_cooccurrence(): 共现关系图 (JSON Graph 格式)
- [x] `GET /api/v1/analytics/entities` + `/entities/graph` 端点

### 5.5 数据导出
- [x] `analytics/export.py` — CSV / JSON 批量导出
  - 支持全部筛选条件 (source_id, transport_mode, topic, language, date range)
  - CSV: StreamingResponse (text/csv)
  - JSON: 标准 JSON 响应
  - 20 个可选导出字段, 最多 10000 行
- [x] `GET /api/v1/export/articles` 端点 (format=csv/json)

---

## Phase 6: Production Hardening (生产加固) ✅ (已完成)

目标：满足企业级生产环境要求，安全、可观测、可扩展

### 6.1 通用爬虫增强
- [x] `adapters/universal_adapter.py` — 零配置通用适配器
  - 三级策略级联: RSS 自动发现 → trafilatura Feed 发现 → 页面链接提取
  - RSS 自动发现: `<link rel="alternate">` 标签 + 常见 Feed 路径探测
  - trafilatura Feed 发现: `find_feed_urls()` 自动扫描
  - 页面提取: 文章 URL 启发式过滤 + trafilatura 全文提取
  - 已注册到 `scheduler/jobs.py` ADAPTER_MAP

### 6.2 即时管线触发
- [x] `scheduler/jobs.py` — 采集完成后立即触发 LLM 处理
  - `fetch_source()` 跟踪 `new_article_ids`
  - `_process_new_articles()` 逐篇 LLM 处理 + 通知分发
  - 消除 10 分钟轮询延迟, 保留 `run_llm_processing()` 作为定时兜底

### 6.3 认证与权限
- [x] `api/auth.py` — API Key 认证中间件
  - SHA-256 哈希存储, `lnc_` 前缀随机密钥生成
  - 开放默认模式 (无 Key 时免认证, 有 Key 后强制认证)
  - 角色支持: admin / reader / subscriber
- [x] 数据模型: `APIKey` 表 (name, key_hash, role, enabled)
- [x] Admin API 端点: POST/GET/DELETE `/api/v1/admin/api-keys`
- [x] Alembic 迁移 004: api_keys 表

### 6.4 API 限流
- [x] `api/ratelimit.py` — 内存滑动窗口限流器
  - 按 API Key / IP 地址识别客户端
  - 默认 120 RPM, 可配置
  - FastAPI 中间件集成 (跳过 /health 和 /ws 路径)

### 6.5 结构化日志
- [x] `monitoring/logging_config.py` — JSON 结构化日志
  - `JSONFormatter`: timestamp, level, logger, message, exception
  - 支持 source_id / article_id 上下文字段
  - `setup_logging()`: 可切换 JSON / 传统格式
  - 静默 httpx / httpcore / asyncio 噪音日志

### 6.6 CI/CD
- [x] `.github/workflows/ci.yml` — GitHub Actions 工作流
  - test: PostgreSQL 16 service + pytest
  - lint: ruff 代码检查
  - docker: Docker build 验证

### 6.7 Docker 生产优化
- [x] `Dockerfile` — Multi-stage 构建
  - Builder 阶段: gcc + libxml2-dev 编译依赖
  - Runtime 阶段: 精简镜像 + 非 root appuser
- [x] `docker-compose.prod.yml` — 生产配置
  - 资源限制 (memory / cpus)
  - 健康检查
  - 必须配置 POSTGRES_PASSWORD

---

## Phase 7: Web Dashboard (可视化界面) ✅ (已完成)

目标：为非技术用户提供直观的 Web 界面，覆盖新闻浏览、搜索、分析全流程

### 7.1 技术选型与项目搭建
- [x] React 18 + Vite + TypeScript
- [x] Tailwind CSS (自定义 @theme 主题变量, 暗色模式)
- [x] Recharts (趋势柱状图, 情感面积图)
- [x] TanStack Query (React Query v5) 数据缓存与同步
- [x] FastAPI `StaticFiles` 托管 SPA

### 7.2 核心页面 (8 页)
- [x] **Dashboard 首页** — 4 指标卡 + 热点排行 + 最新文章
- [x] **新闻 Feed 流** — 10 维筛选 (transport/sentiment/urgency/language/date/search), URL 同步, 分页
- [x] **语义搜索页** — 自然语言输入 → 语义搜索结果 + 相似度百分比条
- [x] **文章详情页** — Markdown 正文 + LLM 分析 (实体/情感/指标) + 相关推荐
- [x] **数据源看板** — 健康状态表格 + 成功率 + 采集日志 (可折叠)
- [x] **趋势分析页** — 热点话题柱状图 + 情感时序堆叠图 + 实体排行
- [x] **订阅管理页** — CRUD 表单 (websocket/webhook), 筛选条件, 启用/禁用
- [x] **设置页** — API Key 管理 (创建/列表/删除) + LLM 配置占位

### 7.3 实时功能
- [x] WebSocket 集成 — `useWebSocket` hook, 自动重连, Header Badge 通知
- [x] 暗色模式切换 (Sun/Moon 图标, localStorage 持久化)
- [x] 响应式布局 (侧边栏折叠/汉堡菜单, Tailwind 断点)

### 7.4 数据导出交互
- [x] 一键导出当前筛选结果 (CSV / JSON) via ExportButton
- [ ] 定时报告配置界面 (Future)

### 7.5 项目结构
```
frontend/
├── src/
│   ├── api/          — 7 个 API 模块 (articles, analytics, sources, subscriptions, discovery, admin, client)
│   ├── hooks/        — useWebSocket
│   ├── components/   — layout(3) + articles(3) + search(1) + common(3)
│   ├── pages/        — 9 个页面
│   └── lib/          — utils (cn, formatDate, badges)
└── vite.config.ts    — proxy /api + /ws to backend
```

---

## Phase 8: Source Discovery (信息源自动发现) ✅ (已完成)

目标：自动搜索、发现、验证新的物流新闻源，高评分自动入库，支持手动启停

### 8.1 发现引擎
- [x] `discovery/engine.py` — DiscoveryEngine
  - DuckDuckGo 免费搜索 (默认, 零配置, 无限调用)
  - Google Custom Search API (可选, 需 API Key)
  - 种子 URL 出站链接爬取 (12 个预置种子站点)
  - 域名去重 + 屏蔽列表 (社交媒体 / 搜索引擎 / 电商)
- [x] `config/discovery_seeds.yaml` — 种子配置
  - 25 条搜索关键词 (15 英文 + 10 中文)
  - 12 个种子 URL (物流/航运行业站点)
  - 相关性关键词库 (high/medium/low 三级权重)

### 8.2 验证器
- [x] `discovery/validator.py` — SourceValidator
  - 连通性检测 (HTTP reachability)
  - RSS/Atom Feed 探测 (`<link>` 标签 + 常见路径)
  - 试抓文章 (复用 UniversalAdapter, 最多 5 篇)
  - 质量评分 (0-100): 标题完整性 / 正文长度 / 发布日期 / URL 规范性
  - 相关性评分 (0-100): 物流关键词匹配 (中英文独立词库)
  - 综合评分 = 质量 × 0.4 + 相关性 × 0.6
  - 站点名称自动提取 (`<title>` 标签解析)

### 8.3 自动审批 + 入库
- [x] 综合评分 ≥ 75 自动批准 → 写入 Source 表 → 立即参与采集调度
- [x] `SourceCandidate` 数据模型
  - 状态流: discovered → validating → validated → approved / rejected
  - 存储质量/相关性评分、示例文章、验证详情
- [x] `_promote_to_source()` 自动生成 source_id 并写入源表

### 8.4 调度与控制
- [x] `discovery/jobs.py` — APScheduler 集成
  - 发现扫描任务 (默认每 24 小时)
  - 验证任务 (默认每 2 小时)
  - 手动启停 API (pause/resume job)
  - 运行状态追踪 (last_scan_at, total_scans, in_progress)
- [x] 防重入锁 (scan_in_progress / validate_in_progress)

### 8.5 API 端点 (10 个)
- [x] `POST /api/v1/discovery/start` — 启动自动发现
- [x] `POST /api/v1/discovery/stop` — 停止自动发现
- [x] `GET /api/v1/discovery/status` — 运行状态 + 各阶段计数
- [x] `POST /api/v1/discovery/scan` — 手动触发发现扫描
- [x] `POST /api/v1/discovery/validate` — 手动触发验证
- [x] `GET /api/v1/discovery/candidates` — 候选源列表 (分页/筛选/排序)
- [x] `POST /api/v1/discovery/candidates/{id}/approve` — 批准 → 写入 Source
- [x] `POST /api/v1/discovery/candidates/{id}/reject` — 拒绝
- [x] `POST /api/v1/discovery/probe` — 即时探测任意 URL

### 8.6 前端 Discovery 页面
- [x] 启停控制 (Start/Stop 按钮 + 运行状态)
- [x] 5 指标统计卡 (Status / Discovered / Validating / Approved / Rejected)
- [x] 手动操作 (Run Scan Now / Validate Pending)
- [x] URL 探测面板 (输入 URL → 即时验证 + 评分 + 示例文章预览)
- [x] 候选源表格 (状态筛选 / 展开详情 / 一键批准或拒绝)
- [x] 侧边栏导航 + Header 标题注册

---

## Milestone Summary

| Phase | 名称 | 核心交付 | 预置依赖 |
|-------|------|----------|----------|
| **0+1** ✅ | MVP Foundation | RSS 采集 + LLM 分析 + REST API | — |
| **2** ✅ | Multi-Source | API/Scraper 适配器 + 中文源 + Alembic | Phase 1 |
| **3** ✅ | Smart Dedup & Search | SimHash/MinHash + 语义搜索 + 相关推荐 | Phase 2 |
| **4** ✅ | Real-time & Subscribe | WebSocket + Webhook + 订阅管理 | Phase 1 |
| **5** ✅ | Analytics & Intelligence | 趋势/情感/实体 + 数据导出 | Phase 3 |
| **6** ✅ | Production Hardening | 通用爬虫/即时管线/认证/限流/日志/CI/CD/Docker | Phase 4+5 |
| **7** ✅ | Web Dashboard | React SPA 9 页 + 筛选/导出/暗色模式/实时推送 | Phase 4+5+6 |
| **8** ✅ | Source Discovery | DuckDuckGo 搜索 + 自动验证评分 + 高分自动入库 + 手动启停 | Phase 6+7 |

> **Note:** Phase 4 和 Phase 5 可并行开发，两者无强依赖。Phase 6 应贯穿始终，但集中加固放在最后。Phase 7 依赖后端 API 就绪，建议 Phase 6 之后启动。Phase 8 依赖 UniversalAdapter (Phase 6) 和前端框架 (Phase 7)。
