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

## Phase 7: Web Dashboard (可视化界面)

目标：为非技术用户提供直观的 Web 界面，覆盖新闻浏览、搜索、分析全流程

### 7.1 技术选型与项目搭建
- [ ] 前端框架: React / Next.js + TypeScript
- [ ] UI 组件库: Ant Design / shadcn/ui
- [ ] 图表库: Recharts / ECharts (趋势、情感、实体图表)
- [ ] 状态管理: React Query (API 缓存与同步)
- [ ] 部署: FastAPI StaticFiles 托管 / Nginx 反向代理

### 7.2 核心页面
- [ ] **新闻 Feed 流** — 按时间线展示文章, 支持 transport_mode / topic / region / urgency 多维筛选
- [ ] **语义搜索页** — 自然语言输入 → 语义搜索结果 + 相似度可视化
- [ ] **文章详情页** — 完整正文 + LLM 分析结果 (实体、情感、指标) + 相关文章推荐
- [ ] **数据源看板** — 各源健康状态、采集频率、成功率实时监控
- [ ] **趋势分析页** — 热点话题排行、情感时序图、实体关联图 (依赖 Phase 5 API)
- [ ] **订阅管理页** — 创建/编辑/删除订阅, 通知渠道配置 (依赖 Phase 4 API)

### 7.3 实时功能
- [ ] WebSocket 集成 — 新文章实时弹窗/Badge 通知 (依赖 Phase 4 WebSocket)
- [ ] 暗色模式切换
- [ ] 响应式布局 (桌面 + 平板 + 手机)

### 7.4 数据导出交互
- [ ] 一键导出当前筛选结果 (CSV / JSON)
- [ ] 定时报告配置界面

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
| **7** | Web Dashboard | React 前端 + 新闻浏览/搜索/分析/订阅界面 | Phase 4+5+6 |

> **Note:** Phase 4 和 Phase 5 可并行开发，两者无强依赖。Phase 6 应贯穿始终，但集中加固放在最后。Phase 7 依赖后端 API 就绪，建议 Phase 6 之后启动。
