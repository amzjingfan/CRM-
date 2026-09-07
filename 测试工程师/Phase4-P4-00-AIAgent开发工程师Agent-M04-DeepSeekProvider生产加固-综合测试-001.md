# Phase 4 REAL-AI-01 M04 DeepSeek Provider 生产加固综合测试报告

## 1. 测试基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 `REAL-AI-01` |
| 模块编号 | M04 |
| 模块名称 | DeepSeek Provider 生产加固 |
| 被测主责 Agent | AIAgent开发工程师Agent |
| 被测协作 Agent | 架构师Agent、全栈开发工程师Agent |
| 测试执行 Agent | 测试工程师Agent |
| 关联实施记录 | `共享记忆文档/实施记录/Phase4-P4-00-AIAgent开发工程师Agent-DeepSeek与生产AI安全-001.md` |
| 前序权威报告 | `测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-回复翻译营销与评测闭环-综合测试-014.md` |
| 测试类型 | 综合测试、真实模型冒烟、回归测试、数据库测试、安全测试、代码审查 |
| 执行日期 | 2026-08-26 |
| 测试结论 | **不通过 REAL-AI-01 独立验收；真实最小请求和 Provider 工程主体通过，但存在 2 个 P1 数据安全缺陷** |

用户请求中写为 `REAL-FS-01`，但 `PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md` 不包含该任务；AI Agent 实际任务和实施记录均为 `REAL-AI-01：DeepSeek Provider 生产加固`。本报告按已确认的实际任务测试，不把全栈 `REAL-FS-01` 基础设施任务混入被测范围。

## 2. 测试依据、目标与边界

### 2.1 测试依据

- 项目根目录、AI Agent、代码目录、全栈、共享记忆、开发工具、架构师和测试工程师目录中的全部适用 `AGENTS.md`。
- `共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md`、`MVP范围与验收标准.md`、管理端接口文档、任务拆解、团队职责和代码编写手册。
- `AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md` 中 `REAL-AI-01`。
- `架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`、`ARCH-001-SYS-系统总体架构设计-v1.4.md`。
- `AI agent 开发工程师/AI-005-REPLY-回复翻译营销与评测规范-v1.3.md`。
- DeepSeek 官方 [Chat Completions](https://api-docs.deepseek.com/api/create-chat-completion/)、[JSON Output](https://api-docs.deepseek.com/guides/json_mode/)、[Thinking Mode](https://api-docs.deepseek.com/guides/thinking_mode/) 和 [Error Codes](https://api-docs.deepseek.com/quick_start/error_codes/) 文档。

### 2.2 本轮目标

1. 审查是否复用既有 `DeepSeekProvider` 和 Provider Factory，且 SDK 重试保持关闭。
2. 验证 JSON Output、Schema 二次校验、空响应、截断、内容过滤、意外工具调用和供应商异常的失败关闭。
3. 验证 400/422、401/402/403、408、429、500/503、超时、连接和取消的稳定错误分类。
4. 验证 `stream=false`，确保原生 Token 不绕过完整草稿 Schema 和安全门禁。
5. 验证 Provider 输入脱敏、生产日志低敏字段和请求追踪不泄漏客户隐私或凭证。
6. 使用已安全注入的真实 DeepSeek 配置执行一次不含客户数据的正式 Prompt 最小请求。
7. 执行 AI 聚焦、后端全量、隔离 PostgreSQL、迁移、固定安全评测、静态质量和依赖安全回归。

### 2.3 非目标

- 不修改产品代码、Prompt、开发测试或固定评测集。
- 不执行真实平台写操作、公开 AI 回复、自动回复或 AI 营销发送。
- 不把一次真实模型冒烟等同于 REAL-AI-05 质量评测。
- 不替代真实模型 50 个授权 SSE 客户端、首输出/P99 和五日稳定性测试。
- 不验证前端页面；本任务没有前端交付。

## 3. 被测快照与环境

### 3.1 环境

| 项目 | 实际环境 |
| --- | --- |
| 操作系统 | Microsoft Windows NT 10.0.19045.0 |
| PowerShell | 7.6.4 |
| Python | 3.11.15 |
| uv | 0.12.3 |
| Docker / Compose | 29.7.2 / 5.3.1 |
| PostgreSQL / pgvector | 独立容器、端口 55433、tmpfs、`pgvector/pgvector:pg16` |
| 当前 Alembic head | `019_tiktok_channel_unique` |
| Git | 不可用；产品目录不是 Git 仓库 |
| 真实 LLM 开关 | `LLM_ENABLED=true`、`LLM_LIVE_EVAL=true`；Key 仅确认已配置，不读取、不输出 |
| 高风险开关 | `AUTO_REPLY_ENABLED=false`、`AI_TRANSLATION_ENABLED=false`、`AI_MARKETING_ENABLED=false` |

### 3.2 AI 关键文件冻结摘要

| 文件 | SHA-256 |
| --- | --- |
| `backend/app/agent/providers/deepseek_provider.py` | `33C3A5BD6FC9EFAC972C2F49E5F00C56D57A0731E35BB5F1FF3F876580816083` |
| `backend/app/shared/logging/setup.py` | `48424780201913F3CE84D40F937D882C1C1F30DF2C89885A25B79963899AB821` |
| `backend/tests/test_agent_providers.py` | `08DB7C654B10491E1CC6791133C79480D7F0CC253175BAFED5E2D43005A62DD4` |
| `backend/tests/test_real_runtime_config.py` | `B1332D1381199C8EE961437F6249887B2608B3DF2C3F4EED8F48DE8C17D7E9E2` |
| `backend/uv.lock` | `3AD5B450855EC7684EA0DD2C2361B5A2E663A5A51050C3DCBA96FB79C69B6172` |

测试期间另一个全栈任务并发修改 TikTok OAuth 代码、测试和迁移，导致共享 `postgres-test` 容器被清理。最终数据库结论来自独立容器名和独立端口的最终复跑；AI 关键文件哈希在测试开始和结束时一致。

## 4. 代码与官方契约审查

| 审查点 | 实际实现 | 结论 |
| --- | --- | --- |
| Provider 复用 | 继续使用 `DeepSeekProvider` 和统一 Factory | 通过 |
| API 契约 | Chat Completions、`response_format=json_object`、V4 模型名和 thinking 开关与当前官方文档一致 | 通过 |
| SDK 重试 | `AsyncOpenAI(max_retries=0)` | 通过 |
| 流式边界 | 请求显式 `stream=False` | 通过；当前不是原生 Token 流 |
| 完整输出 | 仅 `finish_reason=stop` 继续解析 | 通过 |
| 结构校验 | `json.loads` 后执行 Pydantic Schema 校验 | 通过 |
| 终止原因 | `content_filter` 拒绝；资源不足可重试；length/tool_calls/未知值失败关闭 | 通过 |
| SDK 错误 | 认证、权限、参数、限流、超时、连接和 5xx 映射为稳定低敏错误 | 通过 |
| 取消 | `asyncio.CancelledError` 原样传播 | 通过 |
| 输入脱敏 | 邮箱、电话和长 ID 被替换，但地址不处理 | **失败，见 DEF-REAL-AI01-001** |
| 日志出口 | 正文扩展字段被丢弃，但白名单字符串没有格式/长度约束 | **失败，见 DEF-REAL-AI01-002** |

## 5. 自动化、真实请求与回归结果

### 5.1 Provider 与真实 DeepSeek

| 场景 | 实际结果 | 状态 |
| --- | --- | --- |
| Provider 精确测试 | `42 passed` | 通过 |
| Provider/服务/工作流/运行配置聚焦 | `89 passed` | 通过 |
| 正式版本化 Prompt 真实最小请求 | `deepseek-v4-flash` 返回 `logistics_query/classified`，Schema 有效，请求 ID 存在，输入 548 Token、输出 19 Token、总耗时 3056ms | 通过最小请求 |
| 简化非正式 Prompt 真实请求 | 返回 `LLM_OUTPUT_INVALID`，未放行原始输出 | 通过失败关闭；不作为产品 Prompt 质量失败 |
| 空响应、非法 JSON、Schema 失配、截断 | 离线契约测试均转 `LLM_OUTPUT_INVALID` | 通过 |
| 内容过滤 | 转 `LLM_REFUSAL` 且不可重试 | 通过 |
| 429、超时、连接、408、5xx | 转稳定可重试错误 | 通过 Mock 契约 |
| 400/422、401/402/403 | 转稳定不可重试错误 | 通过 Mock 契约 |
| 取消 | 原样传播，不转换、不重试 | 通过 |

单次 3056ms 是非流式完整结构化结果的总耗时，不是 SSE 首输出指标；样本量为 1，不能据此判定 `<3s` 首输出或 P95/P99 性能通过。

### 5.2 工程与数据库回归

| 测试项 | 实际结果 | 状态 |
| --- | --- | --- |
| `uv lock --check` | 125 个包解析成功 | 通过 |
| Ruff / 格式 | All checks passed；187 files already formatted | 通过 |
| mypy | 155 个源文件无问题 | 通过 |
| compileall | 无错误 | 通过 |
| 默认后端全量 | `551 passed、10 skipped、2 warnings` | 通过；10 项数据库用例随后补跑 |
| 独立 PostgreSQL 全量 | `561 passed、0 skipped、2 warnings` | 通过 |
| 空库迁移 | `001_enable_pgvector → 019_tiktok_channel_unique` | 通过 |
| 当前迁移可逆性 | `019 → 018 → 019` | 通过 |
| 固定确定性安全评测 | 234 条，准确率和原因码准确率 100%，危险漏放 0，`live_model_evaluation=false` | 通过固定集 |
| 锁定依赖审计 | 124 个包无已知漏洞和不良项目状态 | 通过 |

两项 warning 分别来自 Starlette TestClient/httpx 和 argon2 版本元数据弃用，不影响本轮 Provider 结论。

## 6. 独立安全测试

### 6.1 模型出境地址测试

使用正式 `ClassificationCommand → build_intent_user_prompt → DeepSeekProvider` 路径，输入合成地址：

```text
北京市朝阳区建国路88号A座1201室
```

一次性独立脚本只输出布尔证据：

```json
{"complete_address_reached_provider_request": true}
```

测试没有调用真实模型，也没有保存完整 Provider 请求；上述地址为专门构造的虚拟测试数据。

### 6.2 日志自由文本测试

对生产 `JsonFormatter` 注入没有敏感字段名的自由文本 `trace_id` 和 `provider_request_id`，实际结果：

```json
{
  "trace_text_retained_in_log": true,
  "request_text_retained_in_log": true
}
```

当前 `main.py` 又直接接受客户端 `X-Trace-Id` 并传播到 Agent，因此该问题不是只能由内部代码触发的理论场景。

## 7. 缺陷

### DEF-REAL-AI01-001：完整地址未脱敏即进入 DeepSeek 请求

| 项目 | 内容 |
| --- | --- |
| 优先级 | **P1** |
| 类型 | 数据出境、客户隐私、模型边界 |
| 影响范围 | 意图分类、FAQ/工具 Prompt、翻译和营销等复用 `sanitize_prompt_text` 的模型调用 |
| 是否阻断 | **是，阻断 REAL-AI-01 和生产 AI 放行** |
| 建议负责 Agent | AIAgent开发工程师Agent；架构师Agent评审脱敏边界 |

复现步骤：

1. 构造包含完整中文地址的 `ClassificationCommand.message`。
2. 调用正式 `build_intent_user_prompt`。
3. 将结果交给带捕获客户端的 `DeepSeekProvider.generate_structured`。
4. 检查实际 Chat Completions `messages[1].content`。

实际结果：完整地址原样存在于 Provider 请求中。`sanitize_prompt_text` 当前仅处理邮箱、电话和长 ID；工具结果递归脱敏也复用同一函数。

预期结果：ADR-004 明确禁止完整地址发送给模型。进入任何外部 Provider 前必须对完整地址执行结构化裁剪或可靠脱敏；无法确认是否为地址时应最小化上下文或失败关闭，而不是原样出境。

### DEF-REAL-AI01-002：低敏日志白名单允许不可信标识夹带任意正文

| 项目 | 内容 |
| --- | --- |
| 优先级 | **P1** |
| 类型 | 日志隐私、输入验证、生产可观测性 |
| 影响范围 | `JsonFormatter`、请求 `trace_id`、DeepSeek 成功/失败请求追踪 |
| 是否阻断 | **是，阻断 REAL-AI-01 和生产日志放行** |
| 建议负责 Agent | AIAgent开发工程师Agent、全栈开发工程师Agent |

复现步骤：

1. 创建带安全 `event` 的 `LogRecord`。
2. 将不含 `address=`、`message=` 等字段名的任意客户文本写入 `trace_id` 或 `provider_request_id`。
3. 使用生产 `JsonFormatter` 格式化。
4. 检查输出 JSON。

实际结果：两个自由文本值均原样进入日志。`redact_log_text` 只能识别有限字段名/Token 模式，不能证明白名单字符串本身是低敏标识；客户端 `X-Trace-Id` 又未经格式和长度约束直接进入请求状态。

预期结果：`trace_id`、供应商请求 ID、模型名等白名单标识必须执行严格格式、字符集和长度校验；不符合标识契约的值应拒绝、替换或仅记录不可逆摘要。日志出口不能依赖自由文本正则证明低敏。

## 8. 观察与文档状态

### OBS-REAL-AI01-001：实施记录的迁移 head 已被并发全栈任务推进

实施记录和架构 v1.4 仍写 `018_ai_observability`，本轮当前代码和空库迁移 head 已为 `019_tiktok_channel_unique`。本次 AI 实现没有数据库迁移，差异来自并发 TikTok OAuth 任务，不归责于 AI Provider；架构师和共享记忆文档 Agent 应按当前全栈交付同步权威 head，同时保留历史实施记录原始证据。

现有共享索引还记录 `DEF-REAL-FS01-006` 日志事件语义折叠为 Open。本轮没有关闭该缺陷；DEF-REAL-AI01-002 是另一个“自由文本可穿过标识字段”的泄漏路径，不能相互替代。

## 9. 通过项、失败项与风险汇总

### 9.1 通过项

- 正式 DeepSeek Prompt 的真实最小请求成功且 Schema 有效。
- JSON Output、终止原因、错误映射、取消和应用级有限重试契约通过。
- 原生 Token 未直出，当前仍为完整安全草稿后的 SSE 分块边界。
- Provider 测试、后端默认全量、独立 PostgreSQL 全量、迁移、固定评测、静态质量和依赖审计通过。
- 高风险公开功能开关保持关闭。

### 9.2 失败项

- 完整地址会进入 DeepSeek 请求，违反明确数据出境禁令。
- 不可信标识字符串会进入生产日志，违反低敏日志要求。

### 9.3 尚未完成的生产门禁

- REAL-AI-05 真实回复、翻译、营销和结构化声明版本化评测。
- 真实 SSE 50 个授权客户端首输出、P99、取消和断线恢复。
- 五日连续稳定性和 99.5% 可用性。
- 密钥轮换、真实日志采集查询策略和不可变发布基线。
- 真实 TikTok 平台只读、Webhook 和人工写操作联调。

## 10. 最终结论与验收建议

**最终结论：不通过 REAL-AI-01 独立验收。**

DeepSeek Provider 的工程主体已通过：正式 Prompt 的真实最小请求成功；42 项 Provider 测试、89 项聚焦测试、551 项默认后端回归、561 项独立 PostgreSQL 回归、234 条固定安全评测、迁移、静态检查和依赖审计均通过。非法输出、截断、供应商错误和取消能够失败关闭。

但两个 P1 直接命中计划停止条件：完整地址可原样进入外部模型请求；不可信 `trace_id/provider_request_id` 可把任意正文带入生产日志。在测试工程师独立复测关闭 DEF-REAL-AI01-001/002 前，不得将 REAL-AI-01 标记为验收通过，也不得扩大到公开 AI 回复、AI 翻译、AI 营销或自动回复。

必须继续保持：

```text
AUTO_REPLY_ENABLED=false
AI_TRANSLATION_ENABLED=false
AI_MARKETING_ENABLED=false
```

修复后至少回归：中英文地址、带楼栋/门牌/邮编地址、工具结果中的地址、历史消息地址、客户端自定义 Trace ID、超长/Unicode/控制字符标识、供应商请求 ID 负向样本、生产 Formatter 和正式 DeepSeek 最小请求。

## 11. 测试清理

- 本轮独立 PostgreSQL 容器使用固定测试名称、独立端口和 tmpfs；已停止并删除，临时数据库不可恢复且不包含生产数据。
- 工作区内本轮创建的 pytest `--basetemp` 目录已按已验证绝对路径精确删除。
- 没有删除或修改持久化开发数据库卷。
- 没有修改产品代码、Prompt、开发测试、固定评测集或锁文件。
- 本轮只新增本正式测试报告并更新共享测试报告索引。
