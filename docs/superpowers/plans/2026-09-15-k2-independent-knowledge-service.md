# K2 独立知识服务 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to execute this plan task-by-task. This plan does not authorize K3 indexing, K4 TikTok Shop synchronization, CRM cutover, or production release.

**Goal:** 在不依赖 CRM 用户、店铺和 FAQ 表的前提下，交付一个可独立启动、可被公司内部多系统安全调用的知识证据服务底座。

**Architecture:** 新服务使用独立 FastAPI 入口、`company_knowledge` 数据库、独立 SQLAlchemy metadata/Alembic 历史和 `company-knowledge` 对象桶。应用身份与店铺委托身份使用非对称 JWT，权限最终以服务端应用/空间/店铺授权为准。`POST /internal/v1/evidence:search` 只返回证据契约四态，K2 默认在索引未建立时失败关闭；检索算法、内容入库和消费系统切流后续分别在 K3/K4 实施。

**Tech Stack:** Python 3.11, FastAPI, Pydantic Settings, SQLAlchemy asyncio, PostgreSQL/pgvector, Alembic, PyJWT + cryptography, MinIO, Docker Compose, pytest.

**Specs:** `架构师/ADR-001-KB-独立知识服务与空间授权边界-v1.0.md`、`API-001-KB`、`SEC-001-KB`、`DEP-001-KB`、`DATA-001-KB`及 `验收-001-KB-KBG0联合架构评审结论-v1.0.md`。

**Execution Status (2026-09-15):** Tasks 1～6 的 K2 工程实现和开发侧验证已完成，当前 Alembic head 为 `003_kb_audit_trace`。正式独立 QA 不由本次开发实施替代，因此未生成测试工程师权威报告；K3～K5 和生产放行仍未开始。

## Global Constraints

- 所有正式产品代码只放入 `CRM智能聊天系统/`；项目 PRD、代码、测试和实施记录不是 RAG 语料。
- 不复用 CRM `stores`、`users`、`knowledge_documents`、`knowledge_chunks` 外键或 CRM HS256 JWT；不用伪店铺表示 `company_shared`。
- K2 不导入或发布 K1 内容，不生成向量，不调用 TK，不启用自动发送，不下线旧 FAQ 链路。
- 认证或授权权威不可用时返回 HTTP 503；无效身份返回 401；已认证但超范围返回 403；不得通过请求正文中的 `shop_ref` 提权。
- 日志和审计只保存低敏标识与 JTI 哈希，不记录 Token、查询正文、知识正文、客户资料或真实店铺 ID。
- 生产/预发配置必须拒绝示例密码、MinIO root 账号、错误数据库名、空 audience 和空验签密钥集。
- 每个行为先写会失败的测试，再写最小实现；提交前运行定向测试、全量相关测试、Ruff、Mypy、Alembic 离线 SQL 和 Compose 解析。

---

### Task 1: 冻结独立运行时与健康契约

**Files:**
- Create: `CRM智能聊天系统/backend/app/knowledge_service/__init__.py`
- Create: `CRM智能聊天系统/backend/app/knowledge_service/config.py`
- Create: `CRM智能聊天系统/backend/app/knowledge_service/main.py`
- Create: `CRM智能聊天系统/backend/tests/test_knowledge_service_config.py`
- Create: `CRM智能聊天系统/backend/tests/test_knowledge_service_health.py`

- [x] 先写配置隔离、生产密钥/数据库/对象存储拒绝和健康端点测试，确认因模块不存在而失败。
- [x] 实现独立 `KnowledgeServiceSettings`，不读 CRM `.env`，并提供 `/internal/health/live` 与 `/internal/health/ready`。
- [x] 运行 `pytest tests/test_knowledge_service_config.py tests/test_knowledge_service_health.py -q`，再运行 `ruff check app/knowledge_service tests/test_knowledge_service_*.py`。

### Task 2: 建立独立数据模型与 Alembic 历史

**Files:**
- Create: `CRM智能聊天系统/backend/app/knowledge_service/database.py`
- Create: `CRM智能聊天系统/backend/app/knowledge_service/models.py`
- Create: `CRM智能聊天系统/backend/knowledge_alembic.ini`
- Create: `CRM智能聊天系统/backend/knowledge_migrations/env.py`
- Create: `CRM智能聊天系统/backend/knowledge_migrations/script.py.mako`
- Create: `CRM智能聊天系统/backend/knowledge_migrations/versions/001_create_knowledge_service_baseline.py`
- Create: `CRM智能聊天系统/backend/tests/test_knowledge_service_models.py`
- Create: `CRM智能聊天系统/backend/tests/test_knowledge_service_migrations.py`

- [x] 先写元数据不得引用 CRM 表、核心表/唯一约束/审计字段与独立 Alembic 版本链的失败测试。
- [x] 实现应用、应用空间授权、店铺空间授权、撤销凭证、覆盖单元、来源、内容版本、版本审批、索引代次和低敏审计表；不建 K3 向量切片表。
- [x] 生成并检查 `alembic -c knowledge_alembic.ini upgrade head --sql`，并在本地独立数据库完成升级/降级/再升级及 003 实际升级验证。

### Task 3: 实现服务身份和空间授权

**Files:**
- Modify: `CRM智能聊天系统/backend/pyproject.toml`
- Modify: `CRM智能聊天系统/backend/uv.lock`
- Create: `CRM智能聊天系统/backend/app/knowledge_service/auth.py`
- Create: `CRM智能聊天系统/backend/app/knowledge_service/authorization.py`
- Create: `CRM智能聊天系统/backend/app/knowledge_service/repository.py`
- Create: `CRM智能聊天系统/backend/tests/test_knowledge_service_auth.py`
- Create: `CRM智能聊天系统/backend/tests/test_knowledge_service_authorization.py`

- [x] 先写 ES256/EdDSA `typ`、`kid`、issuer、audience、token_type、必填 claims、最长 TTL、30 秒时钟偏差、撤销 JTI、应用停用、空间交集、店铺委托与服务端 grant 交集测试。
- [x] 新增显式 `cryptography` 依赖，使用 PyJWT 完成标准非对称签名验证；不实现自定义密码算法。
- [x] 实现可替换的授权仓储接口及 SQLAlchemy 实现，严格区分 401、403 和权威不可用 503。

### Task 4: 实现内部证据 API 四态契约与审计

**Files:**
- Create: `CRM智能聊天系统/backend/app/knowledge_service/schemas.py`
- Create: `CRM智能聊天系统/backend/app/knowledge_service/errors.py`
- Create: `CRM智能聊天系统/backend/app/knowledge_service/service.py`
- Create: `CRM智能聊天系统/backend/app/knowledge_service/api.py`
- Create: `CRM智能聊天系统/backend/tests/test_knowledge_service_api.py`
- Create: `CRM智能聊天系统/backend/tests/test_knowledge_service_openapi.py`

- [x] 先写请求/response DTO、`ok/no_evidence/conflict/unavailable` 四态、固定 reason code、401/403/503 包络和低敏审计的失败测试。
- [x] 实现 `POST /internal/v1/evidence:search`；`company_shared` 禁止带 `shop_ref`，`shop_private` 必须同时通过应用 Token、店铺委托 Token、服务端 grant 和内容策略交集。
- [x] K2 默认 searcher 在无 K3 活跃索引代次时返回 `unavailable/INDEX_GENERATION_UNAVAILABLE`，不伪造检索结果；测试通过注入 fake searcher 锁定四态序列化。
- [x] 检查 OpenAPI 与 `API-001-KB` 一致，并确认审计中无 query、Token 或店铺真实标识；响应与审计使用同一 `trace_id`。

### Task 5: 交付 Compose、独立库和 MinIO 最小权限配置

**Files:**
- Create: `CRM智能聊天系统/docker-compose.knowledge.yml`
- Create: `CRM智能聊天系统/deploy/postgres/bootstrap-company-knowledge.sql`
- Create: `CRM智能聊天系统/deploy/minio/company-knowledge-policy.json`
- Modify: `CRM智能聊天系统/.env.example`
- Modify: `CRM智能聊天系统/deploy/postgres/README.md`
- Modify: `CRM智能聊天系统/deploy/minio/README.md`
- Create: `CRM智能聊天系统/backend/tests/test_knowledge_service_deployment.py`

- [x] 先写 Compose 服务、独立库/角色、专用 bucket/服务账号、只读挂载、健康检查和无默认真密钥的静态失败测试。
- [x] 实现同 PostgreSQL 集群下的 `company_knowledge` 独立库、migration/runtime 角色，以及 `company-knowledge` 桶和对象前缀限制策略。
- [x] 运行 `docker compose -f docker-compose.yml -f docker-compose.knowledge.yml config`，并完成实际启动、迁移、健康、MinIO 初始化和 runtime DDL 拒绝验证。

### Task 6: 契约同步、验证与实施交接

**Files:**
- Modify: `架构师/API-001-KB-内部证据检索与兼容契约-v1.0.md`
- Modify: `共享记忆文档/智能客服平台 — 管理端接口文档.md`
- Modify: `共享记忆文档/开发任务拆解（按人天分配）.md`
- Deferred to independent QA: `测试工程师/` 中的 K2 正式测试报告及 `共享记忆文档/测试报告索引.md`
- Create: `共享记忆文档/实施记录/PhaseX-PX-00-全栈开发工程师Agent-K2独立知识服务-004.md`
- Modify: `共享记忆文档/实施记录索引.md`

- [x] 同步实际路径、委托 Token header、配置、K2 实现状态与 K3/K4 未实施边界，不把单元测试写成生产验收。
- [x] 运行知识服务全量测试、CRM 健康/安全回归、Ruff、Mypy、`git diff --check`、Alembic 离线 SQL、Compose config 和实际容器/数据库验证。
- [x] 按实施记录规范记录修改、验证、遗留风险和回滚；正式测试结论明确延期到测试工程师独立执行，本次不创建竞争性报告或索引条目。

## K2 Completion Gate

K2 只有在独立进程、数据库/迁移、对象存储配置、身份与授权、内部证据 API、审计与负向测试都完成时才能标记完成。完成 K2 不代表已有可检索内容；在 K3 发布活跃索引代次前，默认返回 `unavailable/INDEX_GENERATION_UNAVAILABLE`。未经 K4/K5 真实消费系统验收，不声称 TK 已自动同步、CRM 已切流或多系统共用已验证。
