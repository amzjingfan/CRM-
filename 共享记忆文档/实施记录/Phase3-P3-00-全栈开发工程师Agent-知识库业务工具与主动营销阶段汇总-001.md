# 知识库、业务工具与主动营销阶段汇总实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase3（项目实际实施序列） |
| 任务编号 | P3-00（阶段汇总） |
| 模块编号 | M03（知识库、业务工具与主动营销） |
| 主责 Agent | 全栈开发工程师Agent |
| 协作 Agent | 架构师Agent、AIAgent开发工程师Agent、测试工程师Agent |
| 实施状态 | 已完成 |
| 开始日期 | 2026-08-20 |
| 完成日期 | 2026-08-21 |
| 最近集成复核日期 | 2026-08-21 |
| 代码位置 | `CRM智能聊天系统/` |

## 2. 需求与依据

- 产品需求：`共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md` 中知识库、快捷操作和主动营销章节。
- 接口依据：`共享记忆文档/智能客服平台 — 管理端接口文档.md`，以及本次新增的“Phase 3 已实现接口增量”。
- 架构依据：初始实施依据为 `架构师/ARCH-001-SYS-系统总体架构设计-v1.1.md`、`架构师/ARCH-003-DATA-数据库与向量库初版设计-v1.0.md`；当前生效增量为 `架构师/ARCH-001-SYS-系统总体架构设计-v1.3.md`、`架构师/ARCH-003-DATA-数据库与向量库初版设计-v1.1.md`。
- 任务依据：`全栈开发工程师/PLAN-001-全栈工程实施计划-v1.0.md` 的 Phase 3，以及用户确认的“Phase 3：知识库、业务工具与主动营销实施计划（基于当前代码重制）”。
- 验收依据：`共享记忆文档/MVP范围与验收标准.md` 中 FAQ、订单工具、营销、安全、可运行性和回归要求。
- 代码规范：`共享记忆文档/代码编写手册.md`。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 建立可管理、可批量导入并可安全交给 AI 向量化的 FAQ 知识库。
- 建立统一、受权限和店铺边界约束、可幂等追踪的业务工具执行层。
- 建立弃单挽回和中差评跟进的主动营销任务与管理页面。
- 保留 AI Agent 模块所有权边界，并向 AI 工程师提供稳定交接契约。

### 3.2 实施范围

- 010～013 数据库迁移及 Phase 3 权限。
- FAQ 分类、条目、版本、切片、CSV/XLSX 导入和 MinIO 文件存储。
- 订单/物流/客户查询、Mock 地址修改、Mock 发券、转人工和平台消息工具。
- `tool_calls` 幂等、状态、脱敏摘要和审计链路。
- 评价事件、弃单/中差评活动、频控、重试、等待 AI 和转化状态。
- 知识库、营销、工作台快捷工具和只读 Agent 状态页面。
- Jobs Worker、测试、README、接口增量和本实施记录。

### 3.3 非目标

- 修改 `app/agent`、`agent_runs`、Prompt、模型适配和意图分类。
- Embedding、RAG、AI 自动回复、AI 营销文案和 Agent 工具选择。
- TikTok Shop、Shopee、Amazon 真实平台写操作联调。
- `/agents` CRUD、模型切换、启停 API、SSE 和 Java 服务。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单。
- [x] 已读取最新 PRD、接口文档、任务拆解、团队职责和 MVP 验收标准。
- [x] 已读取代码编写手册、项目及目录 `AGENTS.md` 和适用 UI/UX Skill。
- [x] 已确认数据库基线为 `009_agent_runs`，并保留全部 AI Agent 既有测试。
- [x] 已明确依赖、非目标、Mock 边界、验收方式和潜在风险。

## 5. 实施方案

### 5.1 方案说明

知识库使用 `knowledge_documents` 保存 FAQ 当前内容和版本，发布或正文修改后统一将向量状态重置为 `pending`。AI 工程师通过内部向量化端口读取待处理文档、原子替换指定版本的切片并回写状态；正式检索只能读取当前版本的 `published + ready` 切片。

所有业务动作通过 `ToolDefinition`、`ToolExecutionContext` 和 `ToolResult` 统一描述。写工具强制幂等键，先创建 `tool_calls`，再执行受控动作并记录终态；同键不同请求、执行中冲突和外部结果未知都有独立状态，不把失败伪装为成功。营销 Worker 只调用工具层，不直接调用平台适配器。

营销使用数据库行锁和 `SKIP LOCKED` 认领任务，按弃单或评价来源生成事件，执行 24 小时冷却、30 天最多 3 次、三档重试和转化判断。AI 内容模式进入 `waiting_ai`，当前阶段绝不发送。

### 5.2 依赖关系

- 前置依赖：Phase 1 认证/RBAC/基础设施；Phase 2 店铺、客户、订单、会话、平台适配和审计；AI Phase 1 的只读 `agent_runs` 外键目标。
- 后续依赖：Embedding/RAG、Agent 工具选择及正式数据库、接口、端到端和浏览器回归已经由协作 Agent 完成并形成独立记录；AI 营销文案、公开 AI 回复和真实平台能力仍属于后续任务。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 跨店铺越权 | 泄露订单、客户或知识数据 | Repository 层强制店铺集合过滤，直接 ID 查询不可见统一 404 |
| 写工具重复执行 | 重复发券、消息或状态变更 | 请求哈希、店铺级幂等唯一约束、执行中冲突和未知终态禁止自动重试 |
| FAQ 版本与向量错配 | 检索旧答案 | 内容变更递增版本并失效向量，只读取当前版本 `published + ready` 切片 |
| 导入单行错误 | 整批数据丢失 | 异步逐行处理，允许部分成功，仅保存脱敏错误摘要 |
| AI 内容缺失 | 误发空白或未经审核内容 | `content_mode=ai` 固定进入 `waiting_ai`，不调用发送工具 |
| Mock 被误认为真实执行 | 业务错误判断 | API、数据库和页面统一暴露 `mocked=true`/“模拟执行” |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `CRM智能聊天系统/backend/migrations/versions/010_*.py`～`013_*.py` | 新增 | Phase 3 权限、知识库、工具/发券、评价/营销可逆迁移 | 全栈开发工程师Agent |
| `CRM智能聊天系统/backend/app/knowledge_base/` | 新增 | FAQ、导入、MinIO、向量化交接端口 | 全栈开发工程师Agent |
| `CRM智能聊天系统/backend/app/tools/` | 新增 | 工具契约、幂等执行、追踪和 Mock 发券 | 全栈开发工程师Agent |
| `CRM智能聊天系统/backend/app/marketing/` | 新增 | 活动、事件、触发、频控、重试和 Worker 逻辑 | 全栈开发工程师Agent |
| `CRM智能聊天系统/backend/app/jobs/worker.py` | 新增 | 知识导入和营销独立任务循环 | 全栈开发工程师Agent |
| `CRM智能聊天系统/backend/app/workspace/` | 修改 | 物流、改地址、发券、消息和转人工接入工具追踪 | 全栈开发工程师Agent |
| `CRM智能聊天系统/backend/app/integrations/` | 修改 | 增加评价标准事件和处理链路 | 全栈开发工程师Agent |
| `CRM智能聊天系统/frontend/app/knowledge/` | 新增 | FAQ 管理、发布、归档和导入进度页面 | 全栈开发工程师Agent |
| `CRM智能聊天系统/frontend/app/marketing/` | 新增 | 活动管理、启停和事件状态页面 | 全栈开发工程师Agent |
| `CRM智能聊天系统/frontend/app/agents/` | 新增 | AI 能力只读交接状态页 | 全栈开发工程师Agent |
| `CRM智能聊天系统/frontend/app/workspace/`、`components/AppShell.tsx`、`lib/api.ts` | 修改 | 快捷工具、幂等头、导航、主题、中英文和 Mock 提示 | 全栈开发工程师Agent |
| `CRM智能聊天系统/docker-compose.yml`、`.env.example` | 修改 | Jobs 服务、MinIO 凭据传递和 Phase 3 配置 | 全栈开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_phase3_domain.py`、`frontend/tests/phase3.test.mjs` | 新增 | Phase 3 后端领域和前端安全/交互回归 | 全栈开发工程师Agent |
| `CRM智能聊天系统/backend/scripts/verify_phase3_runtime.py` | 新增 | 真实基础设施主链路验收及夹具清理 | 全栈开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：新增知识库分类/条目/发布/归档/导入，物流/改地址/发券工具，营销活动/启停/事件接口；消息和转人工写操作纳入统一工具追踪。
- 数据库：新增 `knowledge_categories`、`knowledge_documents`、`knowledge_chunks`、`knowledge_import_jobs`、`tool_calls`、`coupon_issuances`、`customer_reviews`、`marketing_campaigns`、`marketing_events` 及对应约束和索引。
- 配置项：新增知识导入大小/行数、Jobs 轮询和营销轮询配置；MinIO 凭据显式传入各 Worker，未记录任何真实密钥。
- AI：未修改 `app/agent`；新增知识库向量化内部端口和受控工具契约，供 AI 工程师后续接入。

### 6.3 关键实现说明

- CSV/XLSX 上传先校验扩展名、大小和表头，原文件写入 MinIO 后返回 202；Jobs Worker 逐行导入并汇总成功/失败数。
- 向量字段固定 `vector(1536)`，指定文档版本切片使用原子替换；版本或状态不匹配的数据不会进入正式检索集合。
- 工具调用只保存请求哈希和脱敏输入/输出摘要，不保存 Token、渠道凭据、完整消息或完整地址。
- 地址 Mock 不修改 `orders` 权威地址；发券写入 `coupon_issuances` 并标记 `mocked=true`。
- 营销任务通过数据库锁防止并发重复认领，所有外部动作统一经工具执行层。
- 前端写操作生成幂等键；地址、发券和转人工具有二次确认，AI 模式明确展示等待接入。
- 应用启动集中注册 ORM metadata，解决 `tool_calls.agent_run_id` 跨模块外键在首次 flush 时无法解析的问题。
- 768px 平板断点将知识库/营销栅格降级，375/768/1024/1440 均无横向溢出。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| 依赖锁 | `uv lock --check` | 锁文件与配置一致 | 当前 124 个包解析成功 | 通过 |
| Python 静态检查 | `uv run ruff check .` | 无错误 | 全部通过 | 通过 |
| Python 格式 | `uv run ruff format --check app migrations scripts tests` | 无格式差异 | 当前 160 个文件已格式化 | 通过 |
| Python 类型 | `uv run mypy app scripts` | 无类型错误 | 当前 118 个源文件通过 | 通过 |
| 后端回归 | `uv run pytest -q` | 既有和新增测试通过 | 当前 109 项通过、4 项条件跳过、2 项第三方弃用警告 | 通过 |
| 依赖安全 | `uv audit --locked` | 无已知漏洞 | 当前 123 个包未发现已知漏洞或不良状态 | 通过 |
| 前端检查 | `npm run lint`、`npm run typecheck` | 无错误 | 全部通过 | 通过 |
| 前端测试 | `npm run test` | 交互和安全契约通过 | 当前 16 项通过 | 通过 |
| 前端构建 | `npm run build` | 生产构建成功 | 8 个路由构建成功，含知识库/营销/Agent | 通过 |
| Compose 配置 | `docker-compose config -q` | 配置合法 | 通过 | 通过 |
| 迁移可逆性 | 隔离库 009→015→009→015；当前库 `alembic current` | 升级、回退和恢复成功 | 正式复测通过，当前 `015_vector_ops (head)` | 通过 |
| 基础设施 | `docker-compose ps`、`/v1/health` | 前后端、数据库、Redis、MinIO 和双 Worker 可用 | 7 个服务运行，健康检查通过 | 通过 |
| Phase 3 运行链路 | `scripts/verify_phase3_runtime.py` | 知识、导入、工具和营销主链路成功 | 全部通过，夹具已清理 | 通过 |
| 浏览器响应式 | 实际页面 375/768/1024/1440 | 无溢出、主题/语言/状态正常 | 四断点通过，无控制台错误 | 通过 |
| 前端 Compose | `docker-compose ps` | 前端容器启动且健康 | `crm-frontend-1` 运行且 healthy | 通过 |

说明：本记录只保存全栈工程师的实施验证证据，不替代测试工程师的正式测试报告和验收结论。

## 8. 实施结果

- 完成项：Phase 3 迁移、FAQ 管理/导入、向量化交接端口、受控工具、Mock 地址/发券、营销编排、Jobs Worker、前端页面、正式 Phase 3 复测和文档同步；后续协作 Agent 已在独立记录中完成 BGE 混合检索和 Agent 工具安全接管。
- 未完成项：真实平台写操作、公开 `/suggest`、SSE 和 AI 营销文案；AI 工具安全接管独立复测已经完成并通过。
- 与原方案差异：本机 Python 基线继续使用 3.11；后续架构决策将知识向量升级为 BGE-M3 1024 维，并将迁移头推进到 015。
- 当前状态：Phase 3 M03 已由测试工程师第六次全量复测并在契约级 Mock 范围内通过；AI Phase 3 业务工具与安全接管也已完成独立测试并在同一 Mock 边界内通过。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-001 | 地址、发券和平台消息仍为 Mock，未完成真实平台写入联调 | P1 | 全栈开发工程师Agent | 真实平台接入任务 |
| R-002（已关闭） | AI 工具安全接管曾缺少独立安全、并发和端到端复测；现已形成 `Phase3-P3-00-AIAgent开发工程师Agent-M04-业务工具与安全接管-综合测试-001.md` 并通过 | P1 | 测试工程师Agent | 已于 2026-08-21 完成 |
| R-003 | 公开 `/suggest`、SSE、AI 营销内容和真实自动发送尚未接入 | P1 | 全栈开发工程师Agent、AIAgent开发工程师Agent | 后续工作台 AI 接入任务 |
| R-004 | pytest 存在 Starlette/httpx 与 argon2 两项第三方弃用警告 | P3 | 全栈开发工程师Agent | 依赖升级回归 |
| R-005 | 长期运行的 Next.js 开发容器可能保留旧编译缓存 | P3 | 全栈开发工程师Agent | 维持 `.next` 命名卷隔离，异常时重启前端容器 |
| R-006 | 模型、数据分布、GPU 或候选参数变化后，现有 BGE 阈值和容量结论需要重新评测 | P1 | AIAgent开发工程师Agent、测试工程师Agent | AI 模型变更门禁 |

## 10. 交接事项

- 交接给：AIAgent开发工程师Agent、测试工程师Agent、架构师Agent。
- 后续任务：AI 工具安全接管独立复测已完成；全栈与 AI 工程师后续接入受认证工作台 AI 建议入口、SSE、AI 营销文案和真实平台能力。
- 必须注意：不要修改或重写 `009_create_agent_runs.py`；AI 只能通过知识库端口和白名单工具接入，不能直接调用平台或绕过执行器写业务表；只有 `published + ready + 当前版本` 的切片可用于正式检索；`unknown` 写工具结果不得自动重试。

## 11. 文档同步

- [x] 已同步管理端接口 Phase 3 实现增量。
- [x] 已记录现有架构边界，未新增与架构文档冲突的决策。
- [x] 已同步 Phase 3 完成状态和实施记录索引。
- [x] 已更新 README、环境配置示例和 OpenAPI 路由。
- [x] Phase 3 M03 第六次正式复测及 AI 工具安全接管独立复测均已完成，权威报告和测试索引已经同步。

## 12. 后续向量契约更新

2026-08-21 架构师确认 ADR-002-AI 后，知识向量已由后续迁移 `014_bge_hybrid` 从 1536 维切换为 BGE-M3 1024 维，并新增 `pg_trgm` 混合召回与 `bge-reranker-large` 重排序；`015_vector_ops` 继续补充向量化队列和店铺状态汇总索引。本文第 6.3 节的 1536 维描述仅代表 Phase3 初始交付时点。当前实现和验证见总体架构 v1.3、BGE/运行面适配记录、Phase 3 M03 第六次正式复测及 AI 工具安全接管独立报告。

## 13. 权威测试结论同步

2026-08-21 根据测试工程师权威报告完成状态同步：

- M03 第六次独立复测在契约级 Mock 范围内通过，完整数据库测试 113 项、前端测试 16 项、迁移、运行态、OpenAPI 和四档浏览器回归均通过。
- M04 业务工具与安全接管独立测试通过，原 `R-002` 正式关闭。
- 当前锁定依赖已通过安全审计，原 `DEF-P3-013` 保持关闭；架构现状以 `ARCH-001-SYS-系统总体架构设计-v1.3.md` 为准。
- 真实平台写操作、公开 AI 回复、SSE 和 AI 营销文案仍不在本次通过范围。
