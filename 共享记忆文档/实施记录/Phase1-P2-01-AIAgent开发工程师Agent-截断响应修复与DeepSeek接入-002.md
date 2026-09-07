# 截断响应修复与 DeepSeek 接入实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase1（AI Agent 工程计划） |
| 任务编号 | P2-01；关联 P2-02 |
| 模块编号 | M04 |
| 主责 Agent | AIAgent开发工程师Agent |
| 协作 Agent | 架构师Agent、测试工程师Agent |
| 实施状态 | 部分完成 |
| 开始日期 | 2026-08-20 |
| 完成日期 | 未完成（待真实模型质量门禁） |
| 代码位置 | `CRM智能聊天系统/backend/` |

## 2. 需求与依据

- 缺陷依据：`测试工程师/Phase1-P2-01-AIAgent开发工程师Agent-M02-模型适配与意图识别-AI评测-001.md` 的 DEF-AI-001。
- 复测依据：`测试工程师/Phase1-P2-01-AIAgent开发工程师Agent-M01-模型适配与意图识别-AI评测-002.md`。
- 架构依据：`架构师/ADR-001-AI-模型适配与意图识别模块编号确认为M04-v1.0.md`。
- 代码规范：`共享记忆文档/代码编写手册.md`。
- 外部模型配置依据：DeepSeek 官方 API 文档的 OpenAI 兼容地址和 JSON Output 约束。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 拒绝 OpenAI `max_output_tokens`、Claude `max_tokens` 和 DeepSeek `finish_reason=length` 截断响应。
- 增加 DeepSeek OpenAI 兼容 Chat Completions Provider，并支持主/备用模型配置。
- 修正项目文档中模块编号为正式编号 M04。

### 3.2 实施范围

- Provider 截断判断和回归测试。
- DeepSeek JSON Output 适配器、错误映射、Token 统计和工厂配置。
- 根目录 `.env` 本地配置；密钥不进入代码、文档、日志或测试报告。

### 3.3 非目标

- 不执行 130 条真实模型评测；该操作需测试工程师按正式报告流程执行。
- 不实现 `/suggest`、RAG、工具调用、自动回复、SSE 或前端改动。

## 4. 实施前确认

- [x] 已读取共享记忆文档、PRD、接口文档、任务拆解、团队职责和测试索引。
- [x] 已读取代码编写手册、AI 工程规范和 DEF-AI-001 权威报告。
- [x] 已确认模块编号为 M04。
- [x] 已确认 DeepSeek 使用 OpenAI 兼容 Chat Completions，不能直接复用 Responses API。

## 5. 实施方案

### 5.1 方案说明

OpenAI Provider 在读取 `output_parsed` 前检查 `incomplete_details.reason`；Claude Provider 在读取 `parsed_output` 前检查 `stop_reason`。截断统一抛出可重试的 `LLM_OUTPUT_INVALID`，由现有三次调用预算和结构重生成策略处理。

DeepSeek 单独使用 OpenAI SDK 的 Chat Completions，设置 `base_url=https://api.deepseek.com` 和 `response_format={"type":"json_object"}`，收到内容后执行 JSON 解析和 Pydantic 校验。Chat Completions 的 `finish_reason=length` 直接视为截断。

### 5.2 依赖关系

- 前置依赖：Phase1 Agent Provider、错误码、分类服务和 130 条评测集。
- 后续依赖：测试工程师 M04-003 复测报告和真实 DeepSeek 评测门禁。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 截断 JSON 恰好可解析 | 错误意图进入后续流程 | 先检查供应商终止状态，再读取结构化结果 |
| DeepSeek JSON Output 偶发空内容 | 分类失败 | 空内容转 `LLM_OUTPUT_INVALID`，触发有限重试 |
| API Key 泄露 | 安全事件 | Key 仅写入被 `.gitignore` 忽略的本地 `.env`，不输出值 |
| 真实质量未验证 | 不能完成最终验收 | 保持 live gate 独立，交测试工程师执行正式评测 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `backend/app/agent/providers/openai_provider.py` | 修改 | 增加 OpenAI 截断响应拒绝 | AIAgent开发工程师Agent |
| `backend/app/agent/providers/anthropic_provider.py` | 修改 | 增加 Claude `max_tokens` 截断拒绝 | AIAgent开发工程师Agent |
| `backend/app/agent/providers/deepseek_provider.py` | 新增 | DeepSeek JSON Output Provider | AIAgent开发工程师Agent |
| `backend/app/agent/providers/factory.py` | 修改 | 增加 DeepSeek Provider 工厂分支 | AIAgent开发工程师Agent |
| `backend/app/shared/config/settings.py` | 修改 | 增加 DeepSeek Key 和 Base URL 类型配置 | AIAgent开发工程师Agent |
| `backend/tests/test_agent_providers.py` | 修改 | 增加 OpenAI/Claude/DeepSeek 截断回归测试 | AIAgent开发工程师Agent |
| `backend/.env.example` | 修改 | DeepSeek 配置模板和默认模型 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/.env` | 新增 | 本地 DeepSeek 配置；真实 Key 不写入文档和日志 | AIAgent开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：无新增 HTTP API。
- 数据库：无变更，继续使用 `agent_runs`。
- 配置：`LLM_PRIMARY_PROVIDER=deepseek`、`LLM_PRIMARY_MODEL=deepseek-v4-flash`、`LLM_FALLBACK_PROVIDER=deepseek`、`LLM_FALLBACK_MODEL=deepseek-v4-pro`、`DEEPSEEK_BASE_URL=https://api.deepseek.com`。
- 密钥：真实 `DEEPSEEK_API_KEY` 仅存在本地 `.env`，不在本记录中复制。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| Provider 回归 | `pytest -q` | 截断被拒绝，正常响应通过 | 45 passed | 通过 |
| Ruff | `ruff check app migrations scripts tests` | 无错误 | 通过 | 通过 |
| mypy | `mypy app scripts` | 无错误 | 100 个源文件无错误 | 通过 |
| 格式 | `ruff format --check app migrations scripts tests` | 全部格式正确 | 130 files already formatted | 通过 |
| 模块编号 | 检查 ADR、索引和实施记录 | 统一 M04 | 已统一，历史文件名保留 | 通过 |
| DeepSeek live 调用 | 未执行 | 使用授权 Key 验证联网调用 | 未执行，避免未经确认的外部调用和费用 | 未执行 |
| 130 条真实评测 | 未执行 | 达到 85%/90% 门禁 | 待测试工程师执行 | 未执行 |

## 8. 实施结果

- 完成项：DEF-AI-001 代码修复、OpenAI/Claude/DeepSeek 截断回归、DeepSeek 配置和 M04 编号统一。
- 未完成项：真实 DeepSeek 质量评测和正式复测报告。
- 与原方案差异：DeepSeek 使用 Chat Completions JSON Output，不复用 OpenAI Responses API。
- 当前状态：部分完成；代码缺陷已修复，最终验收仍等待测试工程师复测和真实质量门禁。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-001 | 真实 DeepSeek 130 条评测尚未执行 | P0 | 测试工程师Agent | Phase1/P2-02 |
| R-002 | DeepSeek API 余额、网络和权限尚未验证 | P1 | 测试工程师Agent | M04-003 复测 |

## 10. 交接事项

- 交接给：测试工程师Agent、架构师Agent。
- 后续任务：使用 M04 和序号 003 生成复测报告；配置 `LLM_LIVE_EVAL=true` 后执行真实评测。
- 必须注意：不得在报告、日志或命令输出中打印 API Key；历史 M01/M02 报告文件名不修改。

## 11. 文档同步

- [x] 已同步 DEF-AI-001 修复内容。
- [x] 已同步 DeepSeek Provider 和模型配置边界。
- [x] 已同步模块编号 M04。
- [x] 已交接测试工程师进行 M04-003 复测。
