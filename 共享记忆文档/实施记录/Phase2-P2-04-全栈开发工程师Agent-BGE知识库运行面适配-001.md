# BGE 知识库运行面适配实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase2 |
| 任务编号 | P2-04；关联 P2-05、P4-11 |
| 模块编号 | M04 |
| 主责 Agent | 全栈开发工程师Agent |
| 协作 Agent | 架构师Agent、AIAgent开发工程师Agent、测试工程师Agent |
| 实施状态 | 部分完成 |
| 开始日期 | 2026-08-21 |
| 完成日期 | 未完成 |
| 代码位置 | `CRM智能聊天系统/` |

## 2. 需求与依据

- 产品需求：`共享记忆文档/CRM智能聊天系统产品需求文档.md` 的 FAQ 知识库与客服运营要求。
- 接口依据：`共享记忆文档/智能客服平台 — 管理端接口文档.md` 的知识库向量状态、失败重试和就绪探针增量契约。
- 架构依据：`架构师/ADR-002-AI-采用本地BGE检索模型-v1.0.md`、`ARCH-001-SYS-系统总体架构设计-v1.2.md`、`ARCH-003-DATA-数据库与向量库初版设计-v1.1.md`。
- 任务依据：`共享记忆文档/开发任务拆解（按人天分配）.md` 中 P2-04、P2-05、P4-11。
- 验收依据：`共享记忆文档/MVP范围与验收标准.md` 的知识库、权限、数据隔离和部署条目。
- 代码规范：`共享记忆文档/代码编写手册.md`。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 让全栈运行面完整承接 BGE-M3 1024 维、混合检索和 Reranker 方案，避免模型服务未就绪时 Worker 抢跑。
- 为运营人员提供店铺级向量化进度与失败重试能力，并补齐真实依赖就绪探针。

### 3.2 实施范围

- 知识库状态/重试 API、管理端状态面板、启动配置校验、Compose AI 覆盖、模型容器非 root、迁移 015 运维索引、README/架构/接口同步。

### 3.3 非目标

- 不修改 BGE 推理、Dense/词法召回、RRF、Reranker、Prompt、LangGraph 或置信度算法。
- 不新增 `/suggest`、SSE、自动发送或真实平台写入。
- 不替代测试工程师生成正式测试报告。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单。
- [x] 已读取相关 PRD、接口、任务拆解和验收标准。
- [x] 涉及代码时已读取代码编写手册和适用 Skill。
- [x] 已确认 Phase、任务编号、模块编号和主责 Agent。
- [x] 已确认依赖、风险和验收方式。

## 5. 实施方案

### 5.1 方案说明

基础 Compose 保持 AI 默认关闭；启用时叠加 `docker-compose.ai.yml`，让 backend/jobs 等待单实例模型服务健康。应用启动校验 BGE Provider、模型、1024 维、内部 URL 和 Token 强度。管理 API 按店铺统计已发布 FAQ 的四种向量状态，仅允许 `published + failed` 重新进入 pending，并写只包含状态/版本的审计日志。就绪探针并发检查数据库、Redis、MinIO 和可选模型契约。

### 5.2 依赖关系

- 前置依赖：AI 工程师已交付迁移 014、内部模型服务、BGE Provider、混合检索和固定模型资产。
- 后续依赖：测试工程师执行安全、质量、容量和 AI 叠加运行复核；AI 工程师评估受漏洞影响依赖的兼容升级。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| Worker 早于模型启动 | pending 文档被批量标记 failed | AI Compose 使用 `service_healthy` 依赖，失败条目提供受权限控制的人工重试 |
| 维度或 Provider 配错 | 新旧向量混写或运行失败 | 启用时强校验 local_bge、BGE-M3、1024 维和候选数量关系 |
| 内部服务弱认证 | 推理端点被越权调用 | Token 至少 32 字符、SecretStr、URL 禁止内嵌凭证、模型容器非 root |
| 依赖已知漏洞 | 模型加载或推理运行面受攻击 | 生产启用阻断，交由 AI 工程师评估 Transformers 5.x/PyTorch 修复兼容性并由测试工程师复核 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `backend/app/shared/health.py`、`main.py` | 新增/修改 | 真实就绪探针及 503 低敏响应 | 全栈开发工程师Agent |
| `backend/app/shared/config/settings.py` | 修改 | BGE 启用配置、维度、Token、URL和候选数量启动校验 | 全栈开发工程师Agent |
| `backend/app/knowledge_base/{schemas,repository,service,router}.py` | 修改 | 店铺级向量状态汇总和失败重试 | 全栈开发工程师Agent |
| `backend/migrations/versions/015_add_knowledge_vectorization_operations_indexes.py` | 新增 | Worker 队列和店铺状态汇总部分索引 | 全栈开发工程师Agent |
| `frontend/lib/api.ts`、`frontend/app/knowledge/page.tsx`、`frontend/app/globals.css` | 修改 | BGE 状态面板和失败重试入口 | 全栈开发工程师Agent |
| `docker-compose.ai.yml`、`Dockerfile.model-service`、`.env.example` | 新增/修改 | AI 启用编排、健康依赖、非 root 和就绪超时配置 | 全栈开发工程师Agent |
| `backend/tests/test_bge_fullstack.py`、前端测试 | 新增/修改 | 配置、服务、探针、OpenAPI、前端和 Compose TDD 覆盖 | 全栈开发工程师Agent |
| `README.md`、接口文档、架构增量文档 | 修改 | 当前启动方式、head、接口、安全门禁和职责边界 | 全栈开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：新增 `GET /v1/knowledge/vectorization/status`、`POST /v1/knowledge/entries/{entry_id}/vectorization/retry`；`GET /v1/health/ready` 改为真实依赖检查。
- 数据库：新增可逆迁移 `015_vector_ops`，仅创建两个知识文档部分索引，当前 head 为 015。
- 配置项：新增 `READINESS_TIMEOUT_SECONDS=3`；启用 Embedding 时新增跨字段启动校验。
- AI：不改变检索算法；全栈只消费 AI 工程师交付的内部模型健康和向量化契约。

### 6.3 关键实现说明

- 状态统计先执行 `ensure_store_access`，Repository 查询再次固定 store_id；跨店铺访问不泄露资源。
- 重试只接受已发布且失败的当前条目，AI 未启用或状态不符返回 40901；审计不保存 FAQ 正文。
- 就绪探针吞掉底层异常并只返回组件级 `ok/error/disabled`，不回显 URL、路径、凭证和堆栈。
- 迁移索引只覆盖 `status='published' AND deleted_at IS NULL`，降低队列认领与运营汇总扫描成本。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| TDD RED | 后端/前端聚焦测试 | 新契约在实现前失败 | 后端缺少 health 模块；前端缺少 AI Compose 与状态 API | 通过 |
| 后端全量 | `uv run pytest` | 全部回归通过 | 85 passed，2 skipped | 通过 |
| 后端静态检查 | Ruff、format、mypy、lock | 无错误且锁文件一致 | 155 文件格式通过，116 个源文件类型通过 | 通过 |
| 前端 | lint、typecheck、test、build | 全部通过 | 15 tests 通过，Next.js 生产构建通过 | 通过 |
| Compose | 基础、AI、GPU 组合配置检查 | 服务可解析且 jobs 等待模型健康 | 3 种组合均解析成功；Docker 用户配置有权限警告但退出码为 0 | 通过 |
| 迁移 | `014→015→014→015` | 可升级、回滚并回到 head | 全部成功，两个索引存在，最终 `015_vector_ops (head)` | 通过 |
| 数据库运行脚本 | `verify_bge_hybrid_runtime.py` | 隔离、混合检索、并发认领通过 | `BGE hybrid runtime verification passed` | 通过 |
| 基础就绪探针 | 调用 `/v1/health/ready` | 基础依赖正常，AI 关闭时 disabled | database/redis/object_storage 为 ok，retrieval_model 为 disabled | 通过 |
| 模型镜像与顺序门禁 | AI+GPU Compose build/up | 非 root 模型健康后再启动 backend/jobs | 优化 Dockerfile 后构建成功；模型先健康，backend/jobs 后启动 | 通过 |
| AI 就绪探针 | 启用 AI 后调用 `/v1/health/ready` | 四项依赖均正常 | database/redis/object_storage/retrieval_model 全部为 ok | 通过 |
| 模型身份与契约 | UID 和内部健康接口 | 非 root、BGE-M3、Reranker、1024 维 | UID 10001；模型 ID 与维度全部匹配 | 通过 |
| 依赖安全审计 | `uv audit --locked` | 无未处置高风险 | torch/transformers 共报告 9 项已知漏洞 | 失败 |

## 8. 实施结果

- 完成项：后端运维 API、前端运营面板、失败重试、启动配置门禁、Compose 顺序、非 root Dockerfile、迁移 015、基础就绪探针、全量代码回归和文档同步。
- 未完成项：AI 依赖漏洞处置；测试工程师正式安全/容量/质量报告；把至少 32 字符的正式内部 Token 安全写入部署环境。
- 与原方案差异：首次 Dockerfile 对大型虚拟环境递归改权导致冷构建超时，改为 `COPY --chown` 后构建、GPU 冷加载、健康门禁和服务启动均完成验证；本轮使用不落盘的一次性随机 Token，不修改用户 `.env`。
- 当前状态：部分完成；开发与基础运行验收完成，生产启用被依赖安全审计和模型镜像复核阻断。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-FS-BGE-001 | torch/transformers 锁定版本存在 9 项已知漏洞 | P0 | AIAgent开发工程师Agent、测试工程师Agent | P2-03 安全兼容升级与复测 |
| R-FS-BGE-002 | 本地 `.env` 的内部 Token 仍为空或过短；当前运行使用一次性随机 Token | P1 | 部署环境维护者、全栈开发工程师Agent | P4-11 部署配置 |
| R-FS-BGE-003 | 正式 Recall、P95、吞吐和 OOM 结论仍缺失 | P0 | 测试工程师Agent、AIAgent开发工程师Agent | P2-03/P4-10 |

## 10. 交接事项

- 交接给：AIAgent开发工程师Agent、测试工程师Agent、架构师Agent。
- 后续任务：AI 工程师评估升级到安全版本的依赖兼容性；测试工程师重建模型镜像并执行安全、GPU 容量和检索质量正式测试。
- 必须注意：生产不得在 P0 依赖漏洞关闭前启用 AI；启用必须使用 `docker-compose.ai.yml`，不得只给 jobs 设置 `EMBEDDING_ENABLED=true`。

## 11. 文档同步

- [x] 已同步管理端接口文档。
- [x] 已同步 README、架构和数据库当前 head。
- [x] 已登记实施记录和风险。
- [ ] 测试报告索引待测试工程师生成正式报告后更新。

## 12. AI Agent 交接处理更新（2026-08-21）

- `R-FS-BGE-001` 的工程处置已完成：模型运行时升级并锁定为 `torch 2.13.0`、`transformers 5.5.4`，`uv audit --locked` 未发现已知漏洞。
- 版本门禁、离线加载边界、Ruff、格式、mypy 和后端全量测试均通过；详细证据见 `共享记忆文档/实施记录/Phase2-P2-03-AIAgent开发工程师Agent-BGE推理依赖安全升级-003.md`。
- 新镜像 GPU 验证尚未完成：Docker/BuildKit 冷构建超过 20 分钟且没有进度输出，旧镜像未被覆盖。该项继续由测试工程师在可用构建环境执行，生产启用门禁保持关闭。
