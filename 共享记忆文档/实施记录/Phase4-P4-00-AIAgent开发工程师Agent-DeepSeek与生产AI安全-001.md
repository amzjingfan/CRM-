# DeepSeek Provider 生产加固实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 REAL-AI-01 |
| 模块编号 | M04 |
| 主责 Agent | AIAgent开发工程师Agent |
| 协作 Agent | 架构师Agent、全栈开发工程师Agent、测试工程师Agent |
| 实施状态 | 已完成 |
| 开始日期 | 2026-08-26 |
| 完成日期 | 2026-08-26 |
| 代码位置 | `CRM智能聊天系统/` |

## 2. 需求与依据

- 产品需求：`共享记忆文档/跨境电商智能客服系统 PRD V2.0.md`、`共享记忆文档/MVP范围与验收标准.md`。
- 接口依据：`共享记忆文档/智能客服平台 — 管理端接口文档.md` 中 Agent 建议和 SSE 内部运行边界。
- 架构依据：`架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`、`架构师/ARCH-001-SYS-系统总体架构设计-v1.4.md`。
- 任务依据：`AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md` 中 REAL-AI-01。
- 当前测试结论：`测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-回复翻译营销与评测闭环-综合测试-014.md`。
- 代码规范：`共享记忆文档/代码编写手册.md` 及项目 Agent 工作流、Python、TDD、安全、可观测性和独立验证 Skill。
- 外部技术依据：DeepSeek 官方 JSON Output、错误码、Chat Completions 和思考模式文档。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 复用既有 `DeepSeekProvider` 和 Provider Factory，不新建第二套调用链。
- 对空回复、非法 JSON、Schema 失配、截断、内容过滤、推理资源不足和意外工具调用失败关闭。
- 将超时、连接、400/422、401、403、429、408、402 和 5xx 转换为稳定低敏错误。
- 保持 SDK 重试关闭，由现有 Agent 服务按最多三次总预算限次。
- 确保取消直接传播，不被转换为自动重试故障。
- 在不记录 Prompt、客户正文、推理内容和密钥的前提下，记录供应商、模型、请求 ID、Token 和耗时。

### 3.2 实施范围

- DeepSeek OpenAI 兼容 Chat Completions 结构化 Provider。
- 生产 JSON 日志低敏字段白名单。
- Provider、重试服务、SSE 传输契约和生产配置聚焦回归。

### 3.3 非目标

- 不修改 Prompt、RAG、业务声明、工具选择和平台写操作。
- 不新增公开 HTTP API、SSE 字段、数据库迁移、环境变量和第三方依赖。
- 不引入 DeepSeek 原生 Token 直出；当前 SSE 仍仅分块输出已完成 Schema 和安全门禁的草稿。
- 不在本轮执行真实 DeepSeek 质量评测、50 客户端真实 SSE 压测、五日稳定性或公开 AI 回复放行。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单。
- [x] 已读取最新 PRD、接口文档、任务拆解、团队职责和验收标准。
- [x] 已读取代码编写手册、全部适用 `AGENTS.md` 和项目 Skill。
- [x] 已确认 Phase4、REAL-AI-01、M04 和 AIAgent 主责边界。
- [x] 已确认不使用真实密钥、不开启真实平台写操作和公开 AI 发送。

## 5. 实施方案

### 5.1 方案说明

Provider 仍执行一次非流式 JSON Output 请求，只有 `finish_reason=stop` 且响应经 JSON 解析和 Pydantic Schema 二次校验后才返回 `ProviderResult`。其他终止原因按语义分类：

```text
content_filter -> LLM_REFUSAL，不重试
insufficient_system_resource -> LLM_PROVIDER_ERROR，可在总预算内重试
length / tool_calls / 未知值 / 缺失 choice -> LLM_OUTPUT_INVALID，可重试或降级
```

Provider 对 SDK 专用异常优先分类，再对通用 HTTP 状态分类。SDK `max_retries=0` 保持不变，限次由 `IntentClassificationService` 和 `StructuredGenerationService` 统一控制。`asyncio.CancelledError` 不在 `Exception` 映射中捕获，继续原样传播。

日志格式器只接受明确白名单内的低敏字段；任意 `content`、`message`、`prompt`、`reasoning_content` 和凭证字段不会进入结构化 JSON 日志。Provider 通过 `trace_id` 与既有 `agent_runs` 中的 Provider、模型、Prompt 版本、Token 和总耗时关联；SSE 首输出耗时仍由现有全栈传输层记录。

### 5.2 依赖关系

- 前置依赖：既有 `DeepSeekProvider`、Provider Factory、Agent 限次重试、`agent_runs`、安全草稿 SSE 和服务端密钥注入面。
- 后续依赖：REAL-AI-05 真实模型评测、REAL-FS-05 SSE 生产运行面、测试工程师正式独立复测。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| JSON 模式空回复或半截输出 | 错误结果进入工作流 | 空值、截断、非法 JSON 和 Schema 失配统一失败关闭 |
| 内容过滤仍携带可解析文本 | 把拒绝误当成功 | 先校验 `finish_reason`，再解析内容 |
| SDK 和应用同时重试 | 成本和时延失控 | 保持 SDK 重试为 0，只使用现有有界服务重试 |
| 日志为可观测而扩大数据泄漏面 | 密钥或客户隐私泄漏 | 仅允许低敏字段白名单，禁止原始 Prompt/内容/推理进入日志 |
| 原生流式 Token 绕过安全审核 | 未验证文本对外可见 | 显式 `stream=false`，继续使用安全草稿传输层分块 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `CRM智能聊天系统/backend/app/agent/providers/deepseek_provider.py` | 修改 | 加固配置清洗、非流式请求、错误分类、终止原因、Schema 门禁和低敏成功日志 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/shared/logging/setup.py` | 修改 | 新增严格低敏扩展字段白名单，保留 AI 请求追踪元数据 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_agent_providers.py` | 修改 | 新增 DeepSeek 输出、错误、取消、流式边界、配置和日志泄漏测试 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_real_runtime_config.py` | 修改 | 将生产日志验收升级为丢弃任意未声明自由文本 | AIAgent开发工程师Agent |
| `共享记忆文档/实施记录/Phase4-P4-00-AIAgent开发工程师Agent-DeepSeek与生产AI安全-001.md` | 新增 | 记录 REAL-AI-01 方案、变更、验证和交接 | AIAgent开发工程师Agent |
| `共享记忆文档/实施记录索引.md` | 修改 | 登记本实施记录 | AIAgent开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：不适用，无新增或变更公开 API/SSE 契约。
- 数据库：不适用，无迁移、表、字段和索引变化；迁移头保持 `018_ai_observability`。
- 配置项：无新配置。现有 `.env.example` 已使用 `deepseek-v4-flash`/备用 `deepseek-v4-pro`、官方 HTTPS Base URL、有界超时和最多三次应用层尝试。
- AI：不修改 Prompt、模型选择策略、RAG、工具或阈值；只加固 DeepSeek Provider 运行边界。
- 依赖：无新增或升级，`uv.lock` 保持不变。

### 6.3 关键实现说明

- 必填配置使用 `strip()` 后校验，纯空白 API Key、模型名或 Base URL 不能绕过启动检查。
- 请求显式传入 `stream=False`，避免后续 SDK 默认值或重构让原生 Token 进入当前 SSE。
- 400 和 422 均映射为不可重试的无效请求；429、连接错误、408 和 5xx 可在应用总预算内重试；401、403、402 不自动重试。
- 任何非 `stop` 终止都在 JSON 解析前处理，防止可解析的局部文本绕过终止状态。
- 成功日志仅记录 `trace_id`、Provider、模型、供应商请求 ID、终止原因、Token、耗时和长度；长度值不包含正文。
- 生产日志只信任显式 `record.event` 且事件名必须满足安全格式；未声明事件的日志统一输出 `unstructured_log_redacted`。需要保留事件语义的其他模块必须改为显式安全事件，不得回退到自由文本推断。
- 取消不捕获、不转换、不重试，并由既有 SSE/调用层继续处理运行终态。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| TDD 红灯 | `uv run pytest tests/test_agent_providers.py -q` | 新契约在实现前稳定失败 | 9 failed、22 passed；缺口为流式显式关闭、日志、终止原因、422/408 分类和空白配置 | 通过 |
| 独立审阅缺陷红灯 | 独立只读审阅 + 聚焦失败测试 | P1/P2/P3 缺口可复现 | 首轮 6 failed；最终短文本边界 3 failed | 复现成功 |
| Provider 聚焦 | `uv run pytest tests/test_agent_providers.py -q` | 全部通过 | 42 passed | 通过 |
| Provider/重试/SSE/生产配置 | 四个相关测试文件 | 既有契约不回归 | 79 passed，1 个既有弃用 warning | 通过 |
| 后端默认全量 | `uv run pytest -q` | 非数据库回归通过 | 546 passed、8 skipped、2 个既有弃用 warning | 通过 |
| 隔离 PostgreSQL 全量 | tmpfs `postgres-test` + `TEST_DATABASE_URL` | 包含 pgvector 和 Agent 追踪的全量通过 | 空库升级 001→018 后 554 passed、0 skipped、2 个既有 warning | 通过 |
| 固定安全评测 | `uv run python -m scripts.evaluate_phase4 ...` | 无危险漏放 | 234 条，安全/原因码准确率 100%，危险漏放 0，`live_model_evaluation=false` | 通过固定集 |
| 锁文件 | `uv lock --check` | 无漂移 | 125 packages resolved | 通过 |
| Ruff | `uv run ruff check .` | 无问题 | All checks passed | 通过 |
| 格式 | `uv run ruff format --check .` | 无格式漂移 | 209 files already formatted | 通过 |
| mypy | `uv run mypy app scripts` | 无类型问题 | 155 source files 无问题 | 通过 |
| 编译 | `uv run python -m compileall -q app scripts` | 编译成功 | 无错误 | 通过 |
| 依赖审计 | `uv audit --locked` | 无已知漏洞 | 124 个包无已知漏洞和不良项目状态 | 通过 |
| 独立只读复核 | 不同审阅 Agent 对四项发现逐项复核 | 所有发现关闭 | 日志自由文本 P1、malformed 响应 P2、失败请求 ID P2、SDK 重试 P3 均 Closed；无新增 P0～P3 | 通过；无 Git 提交级不可变基线 |
| 真实 DeepSeek 评测 | REAL-AI-05 | 需安全注入真实 Key 和版本化样本 | 未执行；本轮不访问真实模型 | 未执行 |
| 50 客户端 SSE/五日稳定性 | REAL-FS-05/REAL-AI-05 | 生产授权环境中验证 | 未执行；不属于 REAL-AI-01 确定性 Provider 加固 | 未执行 |

隔离 PostgreSQL 使用项目既有 `postgres-test` tmpfs 服务，本轮完成后已按精确服务名停止并删除，临时数据不可恢复，未触碰持久化开发数据卷。固定评测临时结果也已从系统临时目录删除。

## 8. 实施结果

- 完成项：REAL-AI-01 确定性工程加固、低敏请求追踪、错误分类、终止原因门禁、取消传播、无原生 Token 直出、自由文本日志失败关闭和自动化测试；独立审阅提出的 1 个 P1、2 个 P2、1 个 P3 已全部关闭。
- 未完成项：正式测试工程师独立复测、真实 DeepSeek 模型质量评测、真实 SSE 性能/稳定性验证；均属后续生产门禁。
- 与原方案差异：无公开契约差异；为让 Provider 请求 ID、Token 和耗时真正进入生产 JSON 日志，增加了共享日志低敏字段白名单。
- 当前状态：REAL-AI-01 开发侧已完成；`AI_PUBLIC_REPLY_ENABLED`、`AI_MARKETING_CONTENT_ENABLED`、`AI_AUTO_REPLY_ENABLED` 仍必须保持关闭，不构成生产放行。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-REAL-AI-01-001 | 未使用真实 DeepSeek Key 执行真实输出、限流、超时、空回复和费用评测 | P1 | AIAgent开发工程师Agent、测试工程师Agent | REAL-AI-05 |
| R-REAL-AI-01-002 | 未完成 50 个授权客户端 SSE、P99 和五日稳定性 | P1 | 全栈开发工程师Agent、AIAgent开发工程师Agent、测试工程师Agent | REAL-FS-05 / REAL-AI-05 |
| R-REAL-AI-01-003 | 项目不是 Git 仓库，独立验证无法提供不可变提交基线 | P2 | 架构师Agent | 生产发布治理 |
| R-REAL-AI-01-004 | 供应商请求 ID 当前通过生产结构化日志记录，尚未验证真实日志采集端的保留和查询策略 | P2 | 全栈开发工程师Agent、测试工程师Agent | REAL-FS-05 |
| R-REAL-AI-01-005 | 其他模块未显式提供安全 `event` 的日志会降级为 `unstructured_log_redacted`，后续需按需迁移低敏事件字段，不能恢复自由文本直出 | P2 | 全栈开发工程师Agent | REAL-FS-05 |

## 10. 交接事项

- 交接给：测试工程师Agent、全栈开发工程师Agent、架构师Agent。
- 测试工程师后续覆盖：真实 DeepSeek 最小请求、JSON 空响应、截断、429、400/422、401/402/403、500/503、超时、取消、日志脱敏和无原生 Token 泄漏。
- 全栈工程师后续覆盖：生产日志采集可查询性、SSE 中断/首输出、50 客户端并发和五日稳定性。
- 全栈工程师需检查生产关键日志调用；若需要事件级检索，应显式提供满足安全格式的 `event` 和白名单元数据，不得把原始消息、Prompt、地址或异常正文重新放入 `message`。
- 必须注意：真实 Key 只能通过服务端密钥管理注入；未经测试工程师正式复测和架构师放行前，不得开启公开 AI 回复、AI 营销发送和自动回复。

## 11. 文档同步

- [x] 公开接口无变化，无需升级接口文档。
- [x] 未产生新架构决策，继续执行 ADR-004。
- [x] 已登记实施记录索引。
- [x] 已明确需要测试工程师覆盖的正式测试范围。
- [x] 未修改测试报告和测试报告索引；正式结论由测试工程师另行生成。
