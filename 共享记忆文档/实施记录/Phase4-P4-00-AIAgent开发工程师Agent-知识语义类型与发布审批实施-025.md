# 知识语义类型与发布审批实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 `REAL-AI-03` |
| 模块编号 | M04 |
| 主责 Agent | AIAgent开发工程师Agent |
| 协作 Agent | 架构师Agent、全栈开发工程师Agent、测试工程师Agent |
| 实施状态 | 已完成 |
| 开始日期 | 2026-09-01 |
| 完成日期 | 2026-09-01 |
| 代码位置 | `CRM智能聊天系统/` |

> “已完成”仅表示架构批准后的工程实施和开发验证完成。`DEF-P4-AI-008/009` 仍保持
> Reopened，必须由测试工程师使用未进入开发集的新开放样本独立复测；本记录不构成正式测试报告或生产放行。

## 2. 需求与依据

- 产品需求：`共享记忆文档/客户服务 PRD（AI 智能客服）.md` 中知识库、人工接管和安全回复边界。
- 接口依据：`共享记忆文档/智能客服平台 — 管理端接口文档.md` 第 11.16 节。
- 架构依据：`架构师/ADR-005-AI-知识语义类型与发布审批边界-v1.0.md`。
- 任务依据：`AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md` 的 `REAL-AI-03`。
- 缺陷依据：`测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-REAL-AI-03缺陷关闭-综合测试-008.md`。
- 跨模块契约：`AI agent 开发工程师/AI-006-SAFETY-知识语义类型与发布审批架构评审请求-v1.0.md`。
- 验收依据：`共享记忆文档/MVP范围与验收标准.md` 中 AI 安全、人工接管和审计要求。
- 代码规范：`共享记忆文档/代码编写手册.md`。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 用运营人员审批的结构化知识元数据替代开放文本白名单承担安全授权。
- 确保未分类、未审批、跨店铺、版本漂移或切片元数据被伪造时统一失败关闭。
- 确保客户实例事实没有同店铺当次真实工具证据时转人工并隐藏草稿。
- 保持 FAQ 永不自动发送，合法技术资产和非断言文本最多进入人工复核。

### 3.2 实施范围

- 知识文档语义类型、客户范围、审批状态、审批人、审批时间和版本绑定。
- 知识创建、编辑、发布、导入、向量化、Dense/Hybrid 检索和 Agent 工作流。
- 管理端知识编辑/发布交互、API 类型、接口文档和自动化测试。
- Alembic `020_knowledge_safety` 迁移及存量数据失败关闭策略。

### 3.3 非目标

- 不关闭测试工程师权威缺陷状态。
- 不启用公开 AI 回复、自动回复、AI 营销或真实 TikTok 写操作。
- 不调用真实 DeepSeek 模型，不执行真实平台写入。
- 不自动推断、批量回填或批准存量 FAQ。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单。
- [x] 已读取相关 PRD、接口、任务拆解和验收标准。
- [x] 已读取代码编写手册、各级 `AGENTS.md` 和适用 Skill。
- [x] 已确认 Phase4、`REAL-AI-03`、M04 和主责 Agent。
- [x] 已确认依赖、风险、生产停止条件和验收方式。
- [x] 架构师已批准 `AI-006-SAFETY`，并形成 `ADR-005-AI`。

## 5. 实施方案

### 5.1 方案说明

知识文档是语义和审批的权威来源。发布操作只批准当前精确版本供内部 AI 复核；正文或语义字段变化会递增
`document_version`、撤销审批、回到 `draft + pending`。向量 Worker 只复制权威元数据，Dense/Hybrid 检索同时
读取文档权威字段和切片副本；两者缺失、不一致或损坏时降级为 `unknown + draft`。

Agent 工作流按确定性矩阵处理：政策、技术资产和非断言知识最多保留人工草稿；客户实例事实必须绑定同店铺、
当次、非 Mock 的查询工具证据，否则转人工并隐藏草稿；未知或未审批知识直接失败关闭。文本规则只作为旧入口
兼容和纵深告警，不再为已审批知识授予权限。

### 5.2 依赖关系

- 前置依赖：`ADR-005-AI`、现有知识库、BGE 向量链路、Agent 结构化业务声明和人工接管工作流。
- 后续依赖：测试工程师新开放集独立复测、存量 FAQ 人工分类审批、重新向量化、真实模型质量评测。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 存量知识没有新字段 | 可能被旧流程误当安全知识 | 迁移统一写入 `unknown + none + draft`，查询和 Agent 均失败关闭 |
| 切片 JSON 被伪造或版本漂移 | 非法提升知识权限 | 检索时与文档权威字段逐项比较，不一致降级为未审批 |
| 客户事实写入 FAQ | 产生订单、退款或资金幻觉 | 强制真实同店铺工具证据；FAQ 路径无证据时转人工并隐藏草稿 |
| 合法技术文本被词法误杀 | 降低客服可用性 | 经人工分类审批后由结构化类型决定可保留草稿，文本白名单不再授权 |
| 公开发送被意外扩大 | 真实客户收到未验证内容 | FAQ 固定 `send_performed=false`；自动回复、营销和平台写入开关保持关闭 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `架构师/ADR-005-AI-知识语义类型与发布审批边界-v1.0.md` | 新增 | 记录架构批准、语义矩阵、迁移和回滚边界 | 架构师Agent |
| `AI agent 开发工程师/AI-006-SAFETY-知识语义类型与发布审批架构评审请求-v1.0.md` | 修改 | 同步批准和实施状态 | AIAgent开发工程师Agent |
| `AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md` | 修改 | 同步 REAL-AI-03 工程状态和停止条件 | AIAgent开发工程师Agent |
| `共享记忆文档/智能客服平台 — 管理端接口文档.md` | 修改 | 增加知识语义、审批和版本契约 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/migrations/versions/020_add_knowledge_safety_approval.py` | 新增 | 增加权威语义和人工审批字段、外键及约束 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/knowledge_base/models.py` | 修改 | 扩展知识文档 ORM 字段 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/knowledge_base/schemas.py` | 修改 | 增加枚举、审批 DTO、组合与版本校验 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/knowledge_base/service.py` | 修改 | 实现创建审计、发布审批、变更撤销和先校验后修改 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/knowledge_base/router.py` | 修改 | 补充 OpenAPI 权限、缺省值和发布限制 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/knowledge_base/importer.py` | 修改 | 禁止导入文件直接发布知识 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/knowledge_base/vector_port.py` | 修改 | 认领/检索审批过滤、切片防伪和失败关闭 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/vectorization.py` | 修改 | 复制当前文档版本的审批元数据到切片 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/reply_safety.py` | 修改 | 按结构化矩阵和真实工具证据执行确定性门禁 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/workflow.py` | 修改 | 把检索命中的安全元数据传入 FAQ 安全判定 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_knowledge_safety_metadata.py` | 新增 | 覆盖结构化组合、审批、伪造、版本、店铺和 008 样本 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_agent_vectorization.py` | 修改 | 验证向量元数据逐版本复制 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_agent_rag.py` | 修改 | 更新检索 DTO 和失败关闭断言 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_agent_workflow.py` | 修改 | 覆盖完整工作流结构化语义矩阵 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_bge_fullstack.py` | 修改 | 更新审批后的向量重试夹具 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/tests/integration/test_agent_rag_postgres.py` | 修改 | 用真实 PostgreSQL 验证审批过滤、防伪、存量拒绝和并发认领 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/frontend/lib/api.ts` | 修改 | 增加知识语义和审批 API 类型 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/frontend/app/knowledge/page.tsx` | 修改 | 增加语义选择、审批状态、发布确认和禁止自动发送提示 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/frontend/tests/phase3.test.mjs` | 修改 | 验证发布前分类和非自动化提示 | AIAgent开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：知识条目创建、更新和响应增量支持 `statement_type`、`customer_scope`、`publication_approval`、
  `semantic_schema_version`、`approved_by`、`approved_at`；草稿缺省为 `unknown + none`，发布前必须明确分类。
- 数据库：新增可逆迁移 `020_knowledge_safety`，下游版本为 `019_tiktok_channel_unique`；存量行不提升权限。
- 配置项：无新增环境变量，无依赖或锁文件变化。
- AI：`KnowledgeRetrievalHit` 强制携带 `KnowledgeSafetyMetadata`；FAQ 安全判定改用审批类型、店铺、版本和工具
  证据矩阵。FAQ 仍不具备自动发送资格。

### 6.3 关键实现说明

- 创建条目时预先生成 UUID，保证 `knowledge.create` 审计绑定真实资源。
- 更新先校验候选语义组合，再修改 ORM 对象；失败请求不污染当前会话。
- 发布校验通过后才修改状态，审批只绑定当前文档版本；正文或语义变化立即撤销审批。
- 写入向量前校验每个切片携带的元数据与当前文档完全一致。
- Dense/Hybrid 检索以文档字段为权威，切片副本只用于一致性验证，不能自行提升权限。
- 客户实例事实只接受同店铺、当次、非 Mock 的 `query_order/query_logistics/query_customer_profile` 证据。
- 无真实工具证据、未知、未审批、跨店铺或版本不一致时均转人工并隐藏草稿。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| 锁文件 | `uv lock --check` | 锁文件一致 | 125 个包解析一致 | 通过 |
| Python 规范 | `uv run ruff check app migrations scripts tests` | 无问题 | All checks passed | 通过 |
| Python 格式 | `uv run ruff format --check app migrations scripts tests` | 已格式化 | 217 files already formatted | 通过 |
| Python 类型 | `uv run mypy app scripts` | 无类型错误 | 160 个源文件无问题 | 通过 |
| Python 编译 | `uv run python -m compileall -q app scripts` | 编译成功 | 退出码 0 | 通过 |
| 安全切片 | `uv run pytest tests/test_knowledge_safety_metadata.py tests/test_agent_workflow.py -q` | 全通过 | 102 passed | 通过 |
| 无测试库回归 | `uv run pytest -q` | 既有回归通过 | 1157 passed，10 skipped | 通过 |
| 空库迁移 | 临时 `postgres-test` 执行 `uv run alembic upgrade head` | 001 到 020 成功 | 完整升级成功 | 通过 |
| 真实 PostgreSQL 全量回归 | 设置隔离 `TEST_DATABASE_URL` 后执行 `uv run pytest -q` | 无跳过、无失败 | 1167 passed | 通过 |
| 迁移回滚恢复 | `alembic downgrade -1`、`current`、`upgrade head`、`current` | 020→019→020 | 最终 `020_knowledge_safety (head)` | 通过 |
| 依赖漏洞审计 | `uv audit --locked` | 无已知漏洞 | 124 个包无已知漏洞和不良项目状态 | 通过 |
| 前端 lint | `npm run lint` | 无错误 | 退出码 0 | 通过 |
| 前端类型 | `npm run typecheck` | 无错误 | 退出码 0 | 通过 |
| 前端测试 | `npm run test` | 全通过 | 30 passed | 通过 |
| 前端生产构建 | `npm run build` | 构建成功 | Next.js 15.5.23 构建成功 | 通过 |
| Compose 配置 | `docker-compose config --quiet` | 配置有效 | 退出码 0 | 通过 |
| 运行数据库版本 | 容器内 `alembic current` | 020 head | `020_knowledge_safety (head)` | 通过 |
| 服务健康 | `GET http://127.0.0.1:8000/v1/health` | HTTP 200 | `status=ok`，版本 0.1.0 | 通过 |
| 运行服务 | `docker-compose ps` | 核心服务正常 | backend/frontend/postgres/redis/minio 健康，worker/jobs 运行 | 通过 |
| 生产停止条件 | 仅输出布尔配置 | 对外写入与自动化关闭 | TikTok 读/写/Webhook、高风险写、自动回复、AI 营销、Mock 均为 false | 通过 |

环境观察：宿主机通过 `127.0.0.1:5432` 单次读取开发库版本时出现 Windows `WinError 64` 连接重置；随后从
运行中的后端容器确认开发库为 020 head，并在独立 5433 测试库完成全迁移和全部数据库测试。该现象未影响
应用健康或迁移结论，但后续测试仍优先使用隔离测试库或容器内连接。

## 8. 实施结果

- 完成项：架构决策、可逆迁移、知识审批、向量防伪、结构化 Agent 门禁、管理端交互、接口文档和全量验证。
- 未完成项：测试工程师独立新开放集复测、存量知识人工回填、真实 DeepSeek 模型质量与生产稳定性门禁。
- 与原方案差异：管理端允许先创建 `unknown + none` 草稿以兼容现有工作流，但发布前强制分类；未实现自动
  回填脚本，避免迁移或模型推断提升权限。
- 当前状态：工程实施完成，生产未放行，正式缺陷状态不变。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-001 | `DEF-P4-AI-008/009` 尚未由独立新开放集关闭 | P1 | 测试工程师Agent | Phase4 / REAL-AI-03 独立复测 |
| R-002 | 存量知识为 `unknown + draft`，正式检索前需人工分类、审批和重新向量化 | P1 | 全栈开发工程师Agent、业务运营 | Phase4 / 知识迁移 |
| R-003 | 真实 DeepSeek 回复、翻译、营销评测未执行 | P1 | AIAgent开发工程师Agent、测试工程师Agent | Phase4 / REAL-AI-04～05 |
| R-004 | 50 客户端 SSE 和五日稳定性门禁未完成 | P1 | 全栈开发工程师Agent、测试工程师Agent | Phase4 / 生产门禁 |
| R-005 | 项目目录不是 Git 仓库，无法提供不可变提交号 | P2 | 项目负责人、架构师Agent | 版本治理 |

## 10. 交接事项

- 交接给：测试工程师Agent、全栈开发工程师Agent。
- 后续任务：测试工程师使用不在开发集中的样本独立复测；全栈工程师准备存量 FAQ 人工回填和重新向量化流程。
- 冻结代码集：本次 19 个核心代码/测试文件的 SHA-256 聚合值为
  `1a905397abea85a25204a08dab629ba02e737add27636d6d1efd2a0300fd5284`。
- 测试必须覆盖：所有结构化组合、缺失/损坏/伪造元数据、审批版本漂移、跨店铺、真实工具证据、Dense/Hybrid、
  并发认领、导入绕过、编辑撤销审批和完整工作流。
- 必须注意：不得把开发固定样本通过当作缺陷关闭证据；FAQ 全部保持 `send_performed=false`。任何漏放均停止
  后续真实模型和生产放行。

## 11. 文档同步

- [x] 已同步接口变化。
- [x] 已同步架构决策。
- [x] 已同步任务状态。
- [x] 已明确测试工程师需要覆盖的范围。
- [x] 已保持正式测试报告与实施记录的职责边界。
- [ ] 测试报告索引将在测试工程师正式独立复测后更新。
