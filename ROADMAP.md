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

## Phase 4: Real-time Push & Subscriptions (实时推送 + 订阅)

目标：从 "被动查询" 进化为 "主动推送"，支持用户个性化订阅

### 4.1 WebSocket 实时推送
- [ ] `api/websocket.py` — WebSocket 端点
  - `/ws/articles` 新文章实时推送
  - 支持按 transport_mode / topic / region 过滤订阅
  - 连接管理器 (心跳, 重连, 并发连接上限)
- [ ] 采集管线完成后触发广播

### 4.2 Webhook 通知
- [ ] `notifications/webhook.py` — Webhook 推送服务
  - 用户注册 Webhook URL + 触发条件
  - HMAC 签名验证
  - 重试机制 (指数退避, 最多 3 次)
  - 投递日志记录
- [ ] Webhook 管理 API (CRUD)
- [ ] 数据模型: `WebhookSubscription` 表

### 4.3 邮件摘要
- [ ] `notifications/email.py` — 邮件推送服务
  - 每日/每周摘要邮件 (按用户偏好)
  - HTML 邮件模板 (Jinja2)
  - SMTP / SendGrid 集成
- [ ] 调度器新增邮件摘要定时任务

### 4.4 订阅管理
- [ ] 数据模型: `Subscription` 表
  - 订阅条件 (source_ids, topics, regions, transport_modes, urgency)
  - 通知渠道 (websocket / webhook / email)
  - 频率设置 (realtime / daily / weekly)
- [ ] 订阅 CRUD API 端点

---

## Phase 5: Analytics & Intelligence (分析与情报)

目标：从 "数据收集" 升级为 "情报平台"，提供趋势分析与市场洞察

### 5.1 趋势分析
- [ ] `analytics/trending.py` — 热点话题检测
  - 基于时间窗口的话题频率统计
  - 话题突发度计算 (当前频率 / 历史基线)
  - 话题关联实体聚合
- [ ] `GET /api/v1/analytics/trending` 端点
  - 参数: time_window (24h/7d/30d), transport_mode, region
  - 返回: 话题排名, 频率, 增长率, 代表性文章

### 5.2 情感时序分析
- [ ] `GET /api/v1/analytics/sentiment-trend` 端点
  - 按时间粒度 (hour/day/week) 聚合情感分布
  - 支持按运输方式、区域、话题切片
  - 返回时序数据 (适配前端图表)
- [ ] 市场情绪指标 — 正面/负面比率 + 移动平均

### 5.3 实体知识图谱
- [ ] `analytics/entity_graph.py` — 实体关系分析
  - 从 entities JSONB 提取公司、港口、人物共现关系
  - 实体出现频率排名
  - 实体关联网络
- [ ] `GET /api/v1/analytics/entities` 端点
  - Top-N 实体排名
  - 实体时序活跃度
  - 实体关联图 (JSON Graph 格式)

### 5.4 文章聚类
- [ ] `analytics/clustering.py` — 向量聚类
  - 基于 embedding 的 K-Means / DBSCAN 聚类
  - 自动生成聚类标签 (LLM summarize cluster)
  - 事件检测 (多源报道同一事件)
- [ ] `GET /api/v1/analytics/clusters` 端点

### 5.5 数据导出
- [ ] `GET /api/v1/export/articles` — CSV / JSON 批量导出
  - 支持全部筛选条件
  - 流式响应 (StreamingResponse) 处理大数据量
  - 导出字段可选
- [ ] `POST /api/v1/reports/schedule` — 定时报告
  - 配置报告模板 (话题摘要 / 市场情绪 / 实体动态)
  - 生成频率 (daily / weekly)
  - 输出格式 (JSON / CSV / PDF)

---

## Phase 6: Production Hardening (生产加固)

目标：满足企业级生产环境要求，安全、可观测、可扩展

### 6.1 认证与权限
- [ ] `api/auth.py` — 认证中间件
  - API Key 认证 (适合服务间调用)
  - JWT Token 认证 (适合用户登录)
  - 角色权限: admin (全功能) / reader (只读) / subscriber (读+订阅)
- [ ] 数据模型: `User`, `APIKey` 表
- [ ] 用户管理 API 端点

### 6.2 API 限流与缓存
- [ ] Redis 集成 (`storage/redis.py`)
- [ ] API 速率限制 (slowapi / 自定义中间件)
  - 按 API Key 分级限流
  - 全局 / 端点级别配置
- [ ] 响应缓存
  - 文章列表: 短 TTL (30s)
  - 热点话题/趋势: 中 TTL (5min)
  - 健康检查: 不缓存

### 6.3 可观测性
- [ ] `monitoring/metrics.py` — Prometheus 指标
  - 采集指标: fetch_duration, articles_per_fetch, error_rate
  - API 指标: request_count, latency_histogram, error_rate
  - LLM 指标: tokens_used, processing_time, success_rate
  - 系统指标: DB 连接池, 队列深度
- [ ] `/metrics` Prometheus 端点 (prometheus-fastapi-instrumentator)
- [ ] Grafana Dashboard JSON 模板
- [ ] 结构化 JSON 日志 (python-json-logger)
  - 请求 ID 追踪
  - 采集任务关联 ID

### 6.4 CI/CD
- [ ] `.github/workflows/ci.yml`
  - Lint (ruff)
  - Type check (mypy)
  - Unit tests (pytest)
  - Docker build 验证
- [ ] `.github/workflows/cd.yml`
  - 自动部署到 staging/production
  - Database migration 自动执行
  - 健康检查等待

### 6.5 性能与扩展
- [ ] Gunicorn + Uvicorn workers 生产配置
- [ ] 数据库连接池调优
- [ ] 文章数据归档策略 (90 天以上数据迁移至冷存储)
- [ ] 水平扩展方案 (无状态 API + 共享 DB + Redis)
- [ ] 负载测试脚本 (locust)

### 6.6 Docker 生产优化
- [ ] Multi-stage Dockerfile (减小镜像体积)
- [ ] docker-compose.prod.yml (Redis + 应用多实例)
- [ ] Health check 优化
- [ ] 安全: 非 root 用户运行, 最小权限

---

## Milestone Summary

| Phase | 名称 | 核心交付 | 预置依赖 |
|-------|------|----------|----------|
| **0+1** ✅ | MVP Foundation | RSS 采集 + LLM 分析 + REST API | — |
| **2** ✅ | Multi-Source | API/Scraper 适配器 + 中文源 + Alembic | Phase 1 |
| **3** ✅ | Smart Dedup & Search | SimHash/MinHash + 语义搜索 + 相关推荐 | Phase 2 |
| **4** | Real-time & Subscribe | WebSocket + Webhook + 邮件 + 订阅管理 | Phase 1 |
| **5** | Analytics & Intelligence | 趋势/情感/实体/聚类 + 数据导出 | Phase 3 |
| **6** | Production Hardening | 认证/限流/缓存/监控/CI/CD | Phase 4+5 |

> **Note:** Phase 4 可与 Phase 3 并行开发，两者无强依赖。Phase 5 依赖 Phase 3 的语义搜索能力。Phase 6 应贯穿始终，但集中加固放在最后。
