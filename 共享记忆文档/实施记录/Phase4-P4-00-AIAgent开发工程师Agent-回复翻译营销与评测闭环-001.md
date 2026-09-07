# 回复、翻译、营销与评测闭环实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00 阶段汇总；关联 P2-09、P2-10、P3-11、P3-13、P4-08、P4-10 |
| 模块编号 | M04 |
| 主责 Agent | AIAgent开发工程师Agent |
| 协作 Agent | 全栈开发工程师Agent、架构师Agent、测试工程师Agent |
| 实施状态 | 部分完成 |
| 开始日期 | 2026-08-22 |
| 完成日期 | 2026-08-22 |
| 代码位置 | `CRM智能聊天系统/` |

## 2. 需求与依据

- 产品需求：`共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md` 中 AI 建议、响应速度、主动触达、转人工和 Phase 4 灰度目标。
- 接口依据：`共享记忆文档/智能客服平台 — 管理端接口文档.md` 中 3.4、11.3～11.6。
- 架构依据：`架构师/ARCH-001-SYS-系统总体架构设计-v1.3.md`、`架构师/ARCH-003-DATA-数据库与向量库初版设计-v1.1.md`、`AI agent 开发工程师/AI-002-RAG-FAQ检索与Agent工作流规范-v1.4.md` 和 `AI-004-TOOL-业务工具与安全接管规范-v1.0.md`。
- 任务依据：`AI agent 开发工程师/PLAN-001-AI-Agent工程实施计划-v1.0.md` 中 Phase 4，以及 `共享记忆文档/开发任务拆解（按人天分配）.md` 中 P2-09、P2-10、P3-11、P3-13、P4-08、P4-10。
- 验收依据：`共享记忆文档/MVP范围与验收标准.md` 中 AI 智能问答、客服工作台、主动触达和数据看板条目。
- 代码规范：`共享记忆文档/代码编写手册.md`。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 将店铺级语气、回复语言和品牌配置纳入 FAQ/工具回复 Prompt。
- 提供中英语言识别、可关联翻译和安全降级。
- 对客服回复和营销文案建立先于模型复核的确定性安全门禁。
- 为弃单和中差评生成可审核文案，通过已有 Worker/工具链路执行，不把 AI 节点变成平台写执行器。
- 建立 Phase 4 版本化安全回归集和质量/工具/延迟/Token/成本指标契约。

### 3.2 实施范围

- `backend/app/agent`：回复策略、语言识别、翻译、营销生成、安全门禁、工作流、追踪和指标。
- `backend/app/chat`：由可信店铺 Agent 配置解析 `reply_profile`。
- `backend/app/marketing` 与 `backend/app/jobs`：在显式开关下认领 `waiting_ai` 事件，先生成安全文案，再复用已有幂等工具链路。
- `backend/evals`、`backend/scripts`和测试：确定性回归与统一指标。
- README、AI 工程规范和共享接口文档。

### 3.3 非目标

- 不修改前端，不新增公开 HTTP API 或 SSE 事件。
- 不新增数据库迁移，迁移头保持 `017_phase4_metrics`。
- 不实现真实 TikTok/Shopee/Amazon 写入、营销合规策略或款项承诺授权。
- 不用 Fake Provider 代替真实模型、真实平台、50 并发或 5 天稳定性结论。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单。
- [x] 已读取相关 PRD、接口、任务拆解和验收标准。
- [x] 已读取代码编写手册、所有层级 `AGENTS.md` 和适用 Skill。
- [x] 已确认 Phase 4、P4-00 阶段汇总、M04 和 AIAgent开发工程师Agent 主责边界。
- [x] 已确认前置依赖为全栈 Phase 4 的 `/suggest`、SSE、Agent Worker、营销 Worker、`agent_configs`、`agent_runs`、`tool_calls` 和 `metric_daily`。

## 5. 实施方案

### 5.1 方案说明

```text
客户消息
→ 确定性语言识别 + 店铺回复策略
→ 意图 / RAG 或受控工具
→ 结构化回复
→ 确定性安全门禁
→ 模型依据复核
→ 代码置信度决策
→ 可选客服翻译
→ 安全草稿或转人工
```

```text
waiting_ai 营销事件
→ 最小可信触发摘要
→ AI 结构化文案
→ 确定性安全门禁
→ 安全：现有受控工具链路
  不安全：失败并人工处理，不自动重试
```

### 5.2 依赖关系

- 前置依赖：AI Phase 1～3、全栈 Phase 3～4、BGE-M3/Reranker 运行面、迁移 001～017。
- 后续依赖：全栈工程师可将翻译结果映射到公开契约，并提供店铺回复配置的授权编辑面；测试工程师执行真实模型、并发和稳定性门禁。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 翻译增加 SSE 时延 | 首输出变慢 | `AI_TRANSLATION_ENABLED=false` 默认关闭，开启后单独压测 |
| 模型伪造退款/订单/平台完成事实 | 客诉和合规风险 | 确定性门禁先于模型复核，失败清空草稿 |
| AI 营销文案与副作用顺序错误 | 文案失败但已发券 | 先生成并校验文案，再执行发券/发送 |
| 运行追踪泄露客户正文 | 隐私泄露 | 只保存语言、Prompt 版本、原因码、ID、Token 和时延 |
| Mock 被当作真实联调 | 错误发布判断 | 结果和文档持续明示 Mock，生产默认关闭 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `CRM智能聊天系统/backend/app/agent/reply_policy.py` | 新增 | 店铺回复策略、语言识别和安全解析 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/reply_safety.py` | 新增 | 确定性回复安全门禁 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/translation.py` | 新增 | 可关联中英翻译节点 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/marketing_generation.py` | 新增 | 弃单/中差评结构化文案服务 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/phase4_evaluation.py` | 新增 | 质量、工具、延迟、Token 和成本指标聚合 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/schemas.py` | 修改 | 工作流命令/结果增加回复策略、语言、翻译和安全原因码 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/workflow.py` | 修改 | LangGraph 增加语言解析、确定性门禁和可选翻译节点 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/workflow_prompt.py` | 修改 | 回复语气/语言 Prompt 与版本升级 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/repository.py` | 修改 | 低敏语言、翻译错误和安全原因追踪 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/factory.py` | 修改 | 装配翻译/营销服务，翻译默认不进关键路径 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/chat/service.py` | 修改 | 从可信 Agent 配置解析店铺回复策略 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/marketing/worker.py` | 修改 | 认领 AI 事件、最小上下文、安全降级和受控发送交接 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/jobs/worker.py` | 修改 | 向营销周期传入类型化配置 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/shared/config/settings.py` | 修改 | 增加翻译/营销开关及 LLM 总开关校验 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/scripts/evaluate_phase4.py` | 新增 | 不访网的安全回归命令 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/evals/agent-phase4-v1.0.0.jsonl` | 新增 | 24 条四类版本化合成样本 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_agent_phase4.py` | 新增 | Phase 4 策略、安全、翻译、营销与指标测试 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_agent_workflow.py` | 修改 | 店铺策略、安全拒绝和翻译工作流回归 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/README.md` | 新增 | 内部契约、Prompt 版本和评测说明 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/.env.example`、`CRM智能聊天系统/README.md` | 修改 | 补充开关、运行、评测和当前边界 | AIAgent开发工程师Agent |
| `AI agent 开发工程师/AI-005-REPLY-回复翻译营销与评测规范-v1.0.md` | 新增 | Phase 4 AI 正式规范 | AIAgent开发工程师Agent |
| `共享记忆文档/智能客服平台 — 管理端接口文档.md` | 修改 | 同步 AI 内部契约与营销开关差异 | AIAgent开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：未新增或修改公开 HTTP API/SSE Schema。内部 `AgentWorkflowCommand` 增加 `reply_profile`；`AgentWorkflowResult` 增加 `detected_language`、`reply_language`、`customer_translation` 和 `safety_reason_codes`。
- 数据库：无迁移、无表结构变更，迁移头保持 `017_phase4_metrics`。`agent_runs.output_summary` 仅在现有 JSON 摘要中增加低敏字段。
- 配置项：新增 `AI_TRANSLATION_ENABLED=false`、`AI_MARKETING_ENABLED=false`；开启时必须 `LLM_ENABLED=true`。
- AI：Prompt 升级至 `faq-agent-workflow-v1.2.0`、FAQ/工具回答与复核 v1.1.0；新增 `customer-translation-v1.0.0` 和 `marketing-copy-v1.0.0`。BGE-M3 1024 维、Reranker、RAG 阈值和七类工具契约未改变。

### 6.3 关键实现说明

- 所有新 Schema 禁止额外字段或使用有界长度/枚举，避免把配置扩展成 Prompt 注入通道。
- 回复安全判断由代码先执行，模型复核不能覆盖确定性拒绝。不安全草稿不进入翻译、SSE 或营销发送链路。
- 翻译是人工辅助能力，失败只记录稳定错误码，不伪造主回复失败或成功。
- AI 营销先生成安全文案再执行发券/发送副作用。安全拒绝是非重试错误；供应商瞬时错误保持最多三次的现有 Worker 上限。
- 营销事件没有必然的 `conversation_id`，不伪造 `agent_runs` 外键；使用 `marketing_events + tool_calls + 低敏结构化日志` 重建执行轨迹。
- 详细中文注释覆盖安全门禁、语言决策、翻译关联、营销副作用顺序和指标口径。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| 锁文件 | `uv --cache-dir ..\\.uv-cache lock --check` | 解析锁定依赖 | `Resolved 125 packages` | 通过 |
| Ruff | `uv ... run ruff check app migrations scripts tests` | 无违规 | `All checks passed` | 通过 |
| 格式 | `uv ... run ruff format --check app migrations scripts tests` | 无需格式化 | `195 files already formatted` | 通过 |
| 类型 | `uv ... run mypy app scripts` | 无类型错误 | `147 source files` 通过 | 通过 |
| Phase 4 聚焦测试 | `pytest tests/test_agent_phase4.py tests/test_agent_workflow.py` | 新能力通过 | `35 passed` | 通过 |
| 默认后端回归 | `uv ... run pytest --basetemp ... -q` | 全量通过 | `149 passed, 4 skipped, 2 warnings` | 通过 |
| PostgreSQL + pgvector | `.\\scripts\\run-postgres-integration-tests.ps1` | 001→017 升级且 DB 全量通过 | 升级到 `017_phase4_metrics`；`153 passed, 2 warnings` | 通过 |
| 确定性安全集 | `python -m scripts.evaluate_phase4 ...` | 无危险漏放 | 24 条，安全/原因码准确率 100%，漏放 0；`live_model_evaluation=false` | 通过 |
| 依赖安全 | `uv audit --locked` | 无已知漏洞 | 124 个可审计包无已知漏洞/不良状态 | 通过 |
| Compose | `docker compose config --quiet` / `--services` | 可解析 | 7 个基础服务成功列出 | 通过 |
| 前端回归 | `npm run lint/typecheck/test/build` | 未改动前端不回归 | 21 测试通过，Next.js 15.5.23 构建成功 | 通过 |
| 真实模型中英/营销评测 | 需真实密钥与隔离数据 | 正式质量结论 | 未执行；当前仅为确定性 Fake/合成回归 | 未执行 |
| 50 并发首输出/P99 | 需 50 组真实授权凭证和模型运行面 | 首输出 <3s、P99 <5s | 未执行；不使用单凭证或 Fake 冒充 | 未执行 |
| 5 天稳定性 | 内部灰度 | 稳定运行 5 天 | 未执行；需测试工程师与运维环境 | 未执行 |

两条现有告警为 Starlette `TestClient`/httpx2 迁移提示和 argon2 版本元数据弃用提示，本次未新增。本记录是开发验证证据，不是测试工程师正式测试报告。

## 8. 实施结果

- 完成项：店铺回复策略、中英语言识别/翻译、回复安全门禁、FAQ/工具 Prompt 升级、弃单/中差评 AI 文案、Worker 受控交接、低敏追踪、统一指标和版本化安全回归。
- 未完成项：真实模型翻译/营销质量门禁、真实平台写联调、公开翻译展示/店铺回复配置编辑面、50 并发首输出/P99 和 5 天灰度。
- 与原方案差异：当前项目已由架构 ADR 确定使用本地 BGE-M3 1024 维混合检索，本次未退回早期 OpenAI 1536 维方案；为保护 SSE 关键路径，翻译另设默认关闭开关。
- 当前状态：确定性工程范围已通过静态、单元、数据库、前端回归和依赖审计；由于 Phase 4 真实模型、性能和稳定性门禁尚未执行，按文档规范标记为“部分完成”。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-P4-AI-001 | 真实模型中英翻译、语气和营销质量未独立评测 | P1 | 测试工程师Agent、AIAgent开发工程师Agent | Phase4/P4-08 |
| R-P4-AI-002 | 50 并发真实 SSE 首输出 <3s 与 P99 <5s 未执行 | P1 | 测试工程师Agent | Phase4/P4-10 |
| R-P4-AI-003 | 翻译字段和店铺回复配置尚未映射到公开 API/前端 | P2 | 全栈开发工程师Agent | 后续全栈增量任务 |
| R-P4-AI-004 | 全平台写操作仍为 Mock，AI 营销不得认定为真实触达 | P0 | 架构师Agent、全栈开发工程师Agent | 真实平台接入任务 |
| R-P4-AI-005 | 翻译显式启用后增加一次结构化模型调用 | P2 | AIAgent开发工程师Agent、测试工程师Agent | Phase4/P4-10 |
| R-P4-AI-006 | 营销事件无必然会话外键，当前无独立 `agent_runs` 记录 | P2 | 架构师Agent | 后续追踪数据模型 ADR |

## 10. 交接事项

- 交接给：全栈开发工程师Agent、测试工程师Agent、架构师Agent。
- 后续任务：全栈增量任务映射翻译结果和店铺策略编辑面；P4-08 真实模型/安全评测；P4-10 真实 SSE 并发；真实平台认证与合规任务。
- 必须注意：公开调用方仍必须服务端加载消息/历史和店铺权限；不得接受客户正文中的资源 ID 作为权威上下文；不得将 `auto_reply` 或 `send_performed=false` 解读为已发送。

## 11. 文档同步

- [x] 已同步内部契约与共享接口文档；公开 API 无变更。
- [x] 已遵守 M04、模块化单体、工具边界和 BGE-M3 1024 维架构决策；无新 ADR。
- [x] 已在实施记录与索引中同步工程完成项和未完成生产门禁。
- [x] 已明确通知测试工程师覆盖翻译、语气、安全、营销、真实模型、50 并发和 5 天稳定性。
- [ ] 测试报告索引将在测试工程师生成正式报告后更新。
