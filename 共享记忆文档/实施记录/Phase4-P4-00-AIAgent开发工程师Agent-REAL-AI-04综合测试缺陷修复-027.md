# REAL-AI-04 综合测试缺陷修复实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 `REAL-AI-04` |
| 模块编号 | M04 |
| 主责 Agent | AIAgent开发工程师Agent |
| 协作 Agent | 全栈开发工程师Agent、架构师Agent、测试工程师Agent |
| 实施状态 | 已完成 |
| 开始日期 | 2026-09-02 |
| 完成日期 | 2026-09-02 |
| 代码位置 | `CRM智能聊天系统/` |

> “已完成”仅表示两项 P1 的开发修复和工程验证完成。缺陷正式状态仍以测试工程师独立复测报告为准，生产 AI 和营销发送未放行。

## 2. 需求与依据

- 缺陷依据：`测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-REAL-AI-04回复翻译营销草稿-综合测试-001.md` 中 `DEF-REAL-AI04-001/002`。
- 产品需求：`共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md` 中 AI 回复、人工复核和主动营销边界。
- 接口依据：`共享记忆文档/智能客服平台 — 管理端接口文档.md` 中 SSE、营销事件和权限规则。
- 架构依据：`架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`、`AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md`。
- 验收依据：`共享记忆文档/MVP范围与验收标准.md` 中失败关闭、人工接管、可审计和禁止自动发送要求。
- 代码规范：`共享记忆文档/代码编写手册.md`、项目各级 `AGENTS.md` 及适用 Skill。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 修复 SSE 结果交付前断开仍保留单一成功终态的问题。
- 建立安全 AI 营销候选的持久化、店铺隔离查询、批准/拒绝和审计闭环。
- 关闭锁定依赖中的 Transformers 高危路径穿越公告，并验证真实 BGE CPU/GPU 推理兼容性。

### 3.2 实施范围

- Agent 运行交付失败补记、SSE 断开/取消/异常处理。
- 营销内容安全与发送授权语义拆分、Worker 待审核终态、审核 API 和管理端页面。
- `022_ai_marketing_review` 可逆迁移、Transformers 5.10.4 锁定、真实本地模型探针和自动化回归。

### 3.3 非目标

- 不执行真实平台消息、发券、修改地址或主动营销发送。
- 不开启公开 AI 回复、自动回复或生产翻译。
- 不替代测试工程师生成正式复测报告或修改原报告结论。
- 不完成真实 DeepSeek 质量评测、50 客户端 SSE 压测和五日稳定性观察。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单。
- [x] 已读取相关 PRD、接口、任务拆解、验收标准和测试结论。
- [x] 已读取代码编写手册、各级 `AGENTS.md` 和 Agent/Python/TDD/安全/Ponytail Skill。
- [x] 已确认 Phase、任务编号、模块编号和主责 Agent。
- [x] 已确认平台写操作、真实模型和生产开关继续保持关闭。

## 5. 实施方案

### 5.1 方案说明

SSE 保留工作流已经完成的低敏摘要，但在 `result` 交给传输层之前检测到断开、取消或异常时，把 `agent_runs.status` 改为 `failed`，写入 `SSE_DELIVERY_INTERRUPTED/CANCELLED/FAILED`，并在摘要中明确 `computation_status=succeeded` 与 `delivery_status=interrupted`，避免覆盖计算事实或虚报交付成功。

营销链路把“内容安全”和“可发送”拆开：`is_safe=true` 仅表示确定性安全检查与独立复核通过；`requires_human=true`、`send_performed=false` 永远保留。Worker 将安全候选写入营销事件后停在 `waiting_review`，清空重试时间并立即返回，审核前不会调用发券或消息工具。运营批准/拒绝接口只写审核字段和低敏审计，批准不执行平台动作。

依赖选择避开已撤回的 Transformers 5.10.0，锁定同一兼容分支 5.10.4；模型镜像使用只读 BGE 资产分别完成 CPU 和 GPU/FP16 单样本加载、Embedding 与 Rerank。

### 5.2 依赖关系

- 前置依赖：REAL-AI-01～03、现有 Agent 工作流、营销 Worker、店铺 RBAC、PostgreSQL 及 BGE 本地资产。
- 后续依赖：测试工程师独立复测、REAL-AI-05 真实模型评测、SSE 性能和稳定性门禁、后续独立营销发送工具。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 计算成功与交付成功混淆 | 指标和审计虚报 | 交付前失败改写终态，并在低敏摘要保留计算事实 |
| 内容安全被误解为发送授权 | 未经审核产生副作用 | 独立 `requires_human` 与事件审核状态；Worker 待审后立即停止 |
| 审核越过店铺边界 | 跨店铺草稿泄漏 | Repository 以资源 ID 和允许店铺集合联合查询，跨店铺返回 404 |
| 审核评论包含敏感信息 | 审计日志泄漏 | 不保存评论原文，只保存 SHA-256 摘要 |
| 依赖修复引发 BGE 不兼容 | 检索服务不可用 | 锁定 5.10.4，真实 CPU/GPU 权重加载和推理回归 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `CRM智能聊天系统/backend/app/chat/router.py` | 修改 | SSE 结果交付前断开、取消和异常补写交付失败 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/chat/service.py` | 修改 | 新增保留计算摘要的交付中断终态方法 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/marketing_generation.py` | 修改 | 拆分内容安全与发送授权语义 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/marketing/models.py` | 修改 | 增加 AI 草稿和审核字段 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/marketing/repository.py` | 修改 | 增加店铺隔离的营销事件查询 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/marketing/schemas.py` | 修改 | 增加审核请求和事件公开审核字段 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/marketing/service.py` | 修改 | 实现批准/拒绝与低敏审计，不执行发送 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/marketing/router.py` | 修改 | 新增草稿审核 API | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/marketing/worker.py` | 修改 | 安全候选持久化为 `waiting_review`，审核前停止副作用 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/migrations/versions/022_add_ai_delivery_and_marketing_review.py` | 新增 | 可逆增加草稿/审核字段、约束、索引和事件状态 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/pyproject.toml`、`backend/uv.lock` | 修改 | Transformers 5.5.4 升级到 5.10.4 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/scripts/verify_retrieval_model_runtime.py` | 新增 | 真实本地 BGE CPU/GPU 低敏探针 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_real_ai04_regressions.py` | 新增 | 两项 P1 的端到端语义回归 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_agent_phase4.py`、`test_retrieval_runtime_dependencies.py` | 修改 | 同步营销和安全依赖契约 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/frontend/lib/api.ts` | 修改 | 增加草稿字段和审核客户端 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/frontend/app/marketing/page.tsx`、`globals.css` | 修改 | 展示草稿、权限控制、二次确认和批准/拒绝 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/frontend/tests/phase3.test.mjs` | 修改 | 增加运营审核闭环源契约测试 | AIAgent开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：新增 `POST /v1/marketing/events/{event_id}/review`；`GET /v1/marketing/events` 增加草稿、AgentRun 关联和审核元数据。
- 数据库：新增迁移 `022_ai_marketing_review`；`marketing_events` 增加 `ai_draft_content`、`ai_draft_agent_run_id`、`ai_review_status`、`ai_reviewed_by`、`ai_reviewed_at`，以及审核约束、索引和 `waiting_review/approved/rejected` 状态。
- 配置项：不新增开关或密钥；生产 AI、营销和平台写开关保持关闭。
- AI：安全营销候选返回 `is_safe=true` 但固定人工复核和不发送；不安全候选继续隐藏正文。

### 6.3 关键实现说明

- SSE 仅在 `result` 交给 ASGI 传输层前补写中断；已经交给传输层后不推测网络 ACK。
- 营销审核端点要求 CSRF、`marketing.manage` 和 `Idempotency-Key`，Repository 再次校验店铺范围。
- 审核批准只表示文案审核通过，不产生 `tool_calls`，不调用平台适配器，也不发放优惠券。
- 订单支付或评价改善时，`waiting_review/approved` 事件可先转化，防止继续审核过时草稿。
- Transformers 修复版本依据 GitHub Advisory `GHSA-xrqw-3rrv-vx5w`；5.10.0 已撤回，因此使用 5.10.4。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| TDD 红测 | 新增 REAL-AI-04 回归并先运行 | 修复前稳定失败 | 缺少审核 Schema/接口，测试收集失败；确认缺口 | 通过 |
| 聚焦 AI/BGE 回归 | `pytest` 指定 REAL-AI-04、Phase4、BGE 测试 | 无回归 | `596 passed, 1 warning` | 通过 |
| 空库迁移和后端全量 | `scripts/run-postgres-integration-tests.ps1` | 空库到 022 且全量通过 | `1199 passed, 2 warnings`，隔离容器已删除 | 通过 |
| 开发库迁移往返 | `021 → 022 → 021 → 022` | 可升级、可回滚、恢复 head | 全部通过，当前 `022_ai_marketing_review` | 通过 |
| Python 质量 | Ruff check/format、mypy | 全部通过 | 223 文件格式通过，162 个源文件类型通过 | 通过 |
| 依赖锁与审计 | `uv lock --check`、`uv audit --locked` | 无已知漏洞 | 125 包解析；124 包无已知漏洞和不利状态 | 通过 |
| BGE CPU 真实探针 | 只读容器加载本地两套权重并推理 | 1024 维向量和有限分数 | Transformers 5.10.4 / Torch 2.13.0，CPU 通过 | 通过 |
| BGE GPU/FP16 真实探针 | `--gpus all` 只读容器同等探针 | CUDA 推理通过 | CUDA 可用，1024 维向量和有限分数 | 通过 |
| 前端测试 | `npm run test` | 无失败 | `32 passed` | 通过 |
| 前端类型与目标 lint | `npm run typecheck`、目标 ESLint | 无错误 | 全部通过 | 通过 |
| 前端生产构建 | `npm run build` | 构建成功 | Next.js 15.5.23，14 个静态路由生成 | 通过 |
| 正式独立复测 | 测试工程师新报告 | 关闭两项 P1 | 未执行，不能由开发 Agent 自行关闭 | 未执行 |

## 8. 实施结果

- 完成项：SSE 交付失败终态、营销草稿审核闭环、店铺隔离、权限、审计、迁移、管理端交互、依赖安全和真实 BGE 兼容验证。
- 未完成项：测试工程师独立复测、真实 DeepSeek 质量评测、公开 SSE/自动回复、真实营销发送、五日稳定性。
- 与原方案差异：为关闭跨模块 P1，新增 022 迁移、审核 API 和最小运营页面；仍未扩大任何发送权限。
- 当前状态：开发修复完成；`DEF-REAL-AI04-001/002` 维持原报告 Open，等待测试工程师独立复测。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-001 | 两项 P1 尚未由测试工程师独立复测 | P1 | 测试工程师Agent | Phase4 / REAL-AI-04 复测 |
| R-002 | 真实 DeepSeek 回复、翻译和营销质量未评测 | P1 | AIAgent开发工程师Agent、测试工程师Agent | Phase4 / REAL-AI-05 |
| R-003 | 审核批准当前刻意不发送，真实营销发送仍需独立工具和生产门禁 | P1 | 架构师Agent、全栈开发工程师Agent | Phase4 高风险工具灰度 |
| R-004 | 50 客户端 SSE 与五日稳定性未验证 | P1 | 全栈开发工程师Agent、测试工程师Agent | Phase4 生产门禁 |
| R-005 | 当前项目不是 Git 仓库，不能提供提交级不可变基线 | P2 | 架构师Agent、项目负责人 | 版本治理 |

## 10. 交接事项

- 交接给：测试工程师Agent、架构师Agent、全栈开发工程师Agent。
- 后续任务：测试工程师复测 SSE 断开/取消、营销安全/拒绝、店铺隔离、审核权限、迁移和无副作用；架构师确认生产门禁继续关闭。
- 必须注意：`is_safe=true` 不代表可发送；`approved` 也不代表平台已发送。任何真实发送必须经过后续独立受控工具和生产开关。

## 11. 文档同步

- [x] 已同步接口变化。
- [x] 已同步架构边界，未创建相互竞争的新 ADR。
- [x] 已同步任务状态为开发修复完成、待独立复测。
- [x] 已通知测试工程师需要覆盖的范围。
- [x] 测试报告索引将在正式测试完成后由测试工程师更新。
