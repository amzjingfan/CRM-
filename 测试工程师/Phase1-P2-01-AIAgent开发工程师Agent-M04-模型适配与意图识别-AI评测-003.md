# AI Agent Phase 1 模型适配与意图识别复测报告

## 1. 测试基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase1（AI Agent 工程计划） |
| 任务编号 | P2-01；关联 P2-02 |
| 模块编号 | M04 |
| 模块名称 | 模型适配与意图识别 |
| 被测主责 Agent | AIAgent开发工程师Agent |
| 被测协作 Agent | 架构师Agent、测试工程师Agent |
| 测试执行 Agent | 测试工程师 Agent |
| 关联实施记录 | `共享记忆文档/实施记录/Phase1-P2-01-AIAgent开发工程师Agent-截断响应修复与DeepSeek接入-002.md` |
| 关联初始报告 | `测试工程师/Phase1-P2-01-AIAgent开发工程师Agent-M02-模型适配与意图识别-AI评测-001.md`、`测试工程师/Phase1-P2-01-AIAgent开发工程师Agent-M01-模型适配与意图识别-AI评测-002.md` |
| 测试类型 | AI评测、回归测试、安全测试、集成测试 |
| 执行日期 | 2026-08-20 |
| 测试结论 | 阻塞；代码复测通过，真实模型质量门禁未执行 |

## 2. 复测目的和范围

本次复测验证上轮 `DEF-AI-001` 截断响应缺陷修复，并覆盖当前实施记录新增的 DeepSeek Provider：

- OpenAI Responses API：结构化输出、Token 统计、截断和拒绝。
- Anthropic Claude Messages API：结构化输出、Token 统计、截断和拒绝。
- DeepSeek OpenAI 兼容 Chat Completions：JSON Output、Pydantic 校验、`finish_reason=length` 截断和错误映射。
- 五类意图、拒判状态、置信度动作、脱敏、运行追踪和评测集。
- 工程质量、依赖安全、数据库迁移、Compose 和健康检查回归。
- 真实模型评测开关和密钥存在性只做安全检查，不在未显式开启 live gate 时发起外部调用。

本轮不修改产品代码，不执行 RAG、工具调用、自动回复、`/suggest`、SSE 或前端测试。

## 3. 测试环境和配置安全

| 项目 | 结果 |
| --- | --- |
| Python | 3.11.15 |
| pytest | 9.1.1 |
| pytest-asyncio | 1.4.0 |
| OpenAI SDK | 2.54.0 |
| Anthropic SDK | 0.120.2 |
| Provider | OpenAI、Anthropic、DeepSeek |
| 数据库 | PostgreSQL 16 + pgvector |
| 数据库迁移头 | `013_marketing`；009 Agent 迁移位于链路中 |
| `LLM_LIVE_EVAL` | 本地配置为 false，未发起公网模型调用 |
| API Key | 本地配置存在性已检查；未读取、打印或写入报告 |

## 4. 测试执行结果

### 4.1 工程质量和自动化回归

| 验证项 | 命令或方法 | 实际结果 | 状态 |
| --- | --- | --- | --- |
| Ruff | `ruff check app migrations scripts tests` | All checks passed | 通过 |
| 格式 | `ruff format --check app migrations scripts tests` | 130 files already formatted | 通过 |
| 类型 | `mypy app scripts` | 100 个源文件无错误 | 通过 |
| 编译 | `python -m compileall -q app migrations scripts tests` | 通过 | 通过 |
| 自动化测试 | `pytest` | 45 passed，2 条非阻断弃用警告 | 通过 |
| 依赖审计 | `uv audit --locked` | 65 个包无已知漏洞 | 通过 |

### 4.2 Provider 和截断复测

| Provider | 场景 | 预期 | 实际 | 状态 |
| --- | --- | --- | --- | --- |
| OpenAI | `incomplete_details.reason=max_output_tokens` | `LLM_OUTPUT_INVALID` 且可重试 | `LLM_OUTPUT_INVALID; RETRIABLE=True` | 通过 |
| Claude | `stop_reason=max_tokens` | `LLM_OUTPUT_INVALID` 且可重试 | `LLM_OUTPUT_INVALID; RETRIABLE=True` | 通过 |
| DeepSeek | `finish_reason=length` | `LLM_OUTPUT_INVALID` 且可重试 | 自动化测试通过 | 通过 |
| OpenAI | 正常结构化响应 | 返回统一 ProviderResult | 自动化测试通过 | 通过 |
| Claude | 正常结构化响应 | 返回统一 ProviderResult | 自动化测试通过 | 通过 |
| DeepSeek | 正常 JSON Output | Pydantic 校验后返回 | 自动化测试通过 | 通过 |

复现日志：

```text
openai_TRUNCATION=LLM_OUTPUT_INVALID;RETRIABLE=True
anthropic_TRUNCATION=LLM_OUTPUT_INVALID;RETRIABLE=True
```

上轮 `DEF-AI-001` 已修复，本轮未发现新的 Provider 截断缺陷。

### 4.3 数据库、Compose 和应用回归

| 验证项 | 方法 | 实际结果 | 状态 |
| --- | --- | --- | --- |
| Compose 配置 | `docker-compose config --quiet` | 通过 | 通过 |
| 迁移升级 | `alembic upgrade head` | 008→009→010→011→012→013 成功 | 通过 |
| 迁移回滚 | `alembic downgrade 008_webhooks_audit` | 013→008 成功 | 通过 |
| 迁移重升 | `alembic upgrade head` | 008→013 成功 | 通过 |
| 当前版本 | PostgreSQL 查询 `alembic_version` | `013_marketing` | 通过 |
| 健康检查 | `GET /v1/health` | HTTP 200，`code=0` | 通过 |

### 4.4 安全和评测门禁

| 场景 | 预期 | 实际 | 状态 |
| --- | --- | --- | --- |
| PII 脱敏 | 邮箱、手机号、订单/物流标识不进入模型 Prompt | 自动化测试通过 | 通过 |
| API Key 保护 | 不进入日志和报告 | 仅检查存在性，未输出值 | 通过 |
| Prompt 注入 | 不改变分类规则 | Prompt 和样本覆盖 | 通过 |
| 高置信度分类 | 仍为 `human_review` | 自动化测试通过 | 通过 |
| 低置信度/拒判 | `transfer_human` 且空意图 | 自动化测试通过 | 通过 |
| live gate | 未显式开启时不访问公网 | 退出码 2，未生成报告 | 通过 |
| 130 条真实评测 | 五类准确率 ≥85%，拒判率 ≥90% | `LLM_LIVE_EVAL=false`，未执行 | 阻塞 |

## 5. 通过项

- 上轮 OpenAI/Claude 截断响应缺陷已修复并有回归测试。
- DeepSeek Provider 已实现 JSON Output、Pydantic 二次校验、Token 统计、错误映射和截断拒绝。
- Provider 配置、错误分类、三次调用预算和保守拒判行为保持通过。
- 45 项自动化测试全部通过，覆盖 Agent 领域、Provider、分类服务、Repository、Phase 3 回归和安全测试。
- 009 Agent 迁移与后续 010–013 迁移链路升级、回滚、重升通过。
- Ruff、格式、mypy、compileall 和依赖安全审计通过。
- AI 默认/评测开关安全有效，没有在未授权状态下访问外部模型。

## 6. 未完成项和风险

### DEF-AI-002：真实模型质量门禁未执行

| 项目 | 内容 |
| --- | --- |
| 优先级 | P0，验收阻塞 |
| 状态 | 待授权环境执行 |
| 责任 Agent | 测试工程师Agent、AIAgent开发工程师Agent |
| 当前原因 | 本地 `LLM_LIVE_EVAL=false`；本轮遵守显式 live gate，未发起外部模型调用 |
| 验收标准 | 130 条真实评测；五类准确率 ≥85%；30 条边界样本正确拒判率 ≥90% |

执行命令：

```powershell
cd CRM智能聊天系统/backend
uv run python -m scripts.evaluate_intents --output evals/results/intent-classifier-live.md
```

只有在授权配置、模型名和 `LLM_LIVE_EVAL=true` 同时满足后执行。报告不得包含 API Key、客户原文、Prompt 或模型完整响应。

## 7. 回归结论

本轮确认 Phase 1 AI Agent 代码质量和上轮缺陷修复通过，且未破坏既有 Phase 1、Phase 2、Phase 3 工程回归。当前仍不能把 Phase 1 标记为最终完成，唯一验收阻塞为真实模型质量门禁尚未产生证据。

## 8. 验收建议

当前建议：阻塞，不建议最终验收。

转为“有条件通过”或“已完成”前必须：

1. 在合规授权环境将 `LLM_LIVE_EVAL` 显式设置为 true。
2. 运行 130 条真实模型评测，生成测试工程师正式 AI 评测报告。
3. 达到五类准确率 ≥85% 和边界正确拒判率 ≥90%。
4. 如模型、Prompt 或 DeepSeek 主备配置发生变化，重新执行本报告对应的回归范围。

## 9. 交接事项

- 交给 AIAgent开发工程师Agent：当前 Provider 截断修复和 DeepSeek 自动化回归已通过，等待真实质量数据。
- 交给架构师Agent：M04 已由 ADR-001 正式确认，本报告使用正式编号。
- 交给测试工程师Agent：取得授权配置后执行 live gate，并以序号 004 生成后续报告，不覆盖本报告。

## 10. 证据路径

- 实施记录：`共享记忆文档/实施记录/Phase1-P2-01-AIAgent开发工程师Agent-截断响应修复与DeepSeek接入-002.md`
- 初始报告：`测试工程师/Phase1-P2-01-AIAgent开发工程师Agent-M02-模型适配与意图识别-AI评测-001.md`
- 复测报告：`测试工程师/Phase1-P2-01-AIAgent开发工程师Agent-M01-模型适配与意图识别-AI评测-002.md`
- Provider 测试：`CRM智能聊天系统/backend/tests/test_agent_providers.py`
- 评测集：`CRM智能聊天系统/backend/evals/intent-classifier-v1.0.0.jsonl`
