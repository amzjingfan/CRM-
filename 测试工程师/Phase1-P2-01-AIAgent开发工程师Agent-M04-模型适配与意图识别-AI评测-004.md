# AI Agent Phase 1 真实模型评测报告

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
| 关联上一轮报告 | `测试工程师/Phase1-P2-01-AIAgent开发工程师Agent-M04-模型适配与意图识别-AI评测-003.md` |
| 测试类型 | AI评测、回归测试、安全测试、集成测试 |
| 执行日期 | 2026-08-20 |
| 测试结论 | 不通过；真实模型评测因 Provider 输出无效中止，未达到质量门禁 |

## 2. 测试目标和范围

本轮重点验证用户开启 `LLM_LIVE_EVAL=true` 后的真实模型质量门禁，并复核上一轮工程测试：

- 130 条版本化评测集：五类意图各 20 条，拒判样本 30 条。
- DeepSeek 主模型和备用模型配置、联网探针、真实结构化分类调用。
- 五类准确率 ≥85%、边界正确拒判率 ≥90%。
- OpenAI、Claude、DeepSeek Provider 截断回归。
- 45 项自动化测试、静态检查、数据库迁移、Compose 和健康检查。

本轮不测试 RAG、工具调用、自动回复、`/suggest`、SSE 或前端页面。

## 3. 环境与配置安全

| 项目 | 结果 |
| --- | --- |
| Python | 3.11.15 |
| pytest | 9.1.1 |
| OpenAI SDK | 2.54.0 |
| Anthropic SDK | 0.120.2 |
| Provider | DeepSeek（主/备用均为 DeepSeek 配置） |
| Base URL | `https://api.deepseek.com` |
| `LLM_ENABLED` | true |
| `LLM_LIVE_EVAL` | true |
| API Key | 本地配置存在；未读取、打印或写入报告 |
| 网络探针 | 最小 JSON 请求成功，返回请求 ID 存在 |

密钥值、模型完整响应、Prompt 和客户样本原文均未写入日志或报告。

## 4. 测试结果

### 4.1 工程回归

| 验证项 | 命令或方法 | 实际结果 | 状态 |
| --- | --- | --- | --- |
| Ruff | `ruff check app migrations scripts tests` | All checks passed | 通过 |
| 格式 | `ruff format --check app migrations scripts tests` | 130 files already formatted | 通过 |
| 类型 | `mypy app scripts` | 100 个源文件无错误 | 通过 |
| 编译 | `python -m compileall -q app migrations scripts tests` | 通过 | 通过 |
| 自动化测试 | `pytest` | 45 passed，2 条非阻断弃用警告 | 通过 |
| 依赖审计 | `uv audit --locked` | 65 个包无已知漏洞 | 通过 |
| Compose | `docker-compose config --quiet` | 通过 | 通过 |
| 数据库迁移 | 013→008→013 | 成功，当前 `013_marketing` | 通过 |
| 健康检查 | `GET /v1/health` | HTTP 200，`code=0` | 通过 |

### 4.2 Provider 截断回归

| Provider | 场景 | 实际结果 | 状态 |
| --- | --- | --- | --- |
| OpenAI | `incomplete_details.reason=max_output_tokens` | `LLM_OUTPUT_INVALID`，可重试 | 通过 |
| Claude | `stop_reason=max_tokens` | `LLM_OUTPUT_INVALID`，可重试 | 通过 |
| DeepSeek | `finish_reason=length` | 自动化测试拒绝截断 | 通过 |

### 4.3 真实模型评测

执行命令：

```powershell
python -m scripts.evaluate_intents `
  --dataset backend/evals/intent-classifier-v1.0.0.jsonl `
  --output backend/evals/results/intent-classifier-live-20260820.md
```

实际过程：

1. `.env` 中 `LLM_LIVE_EVAL=true` 已生效。
2. DeepSeek 最小联网探针成功，确认网络、Base URL、Key 存在性和模型服务可达。
3. 130 条评测正式启动。
4. 多次模型调用出现 `llm_call_failed`。
5. 达到应用层有限重试后，评测以退出码 2 终止。
6. 最终稳定错误为：DeepSeek 输出为空或达到 Token 上限而截断，归类为 `LLM_OUTPUT_INVALID`。
7. 未生成聚合评测报告，因此没有准确率、拒判率、F1 或混淆矩阵结果。

安全日志证据：

```text
PROVIDER_PROBE=success;MODEL=deepseek-v4-flash;ID_PRESENT=True
评测未完成：DeepSeek 输出为空或因达到 Token 上限而截断
LIVE_EVAL_EXIT=2
```

## 5. 通过项

- 用户开启的 live gate 被正确识别，真实模型调用确实执行。
- DeepSeek 网络探针成功，未出现认证或连接错误。
- OpenAI、Claude、DeepSeek 截断回归全部通过。
- 45 项自动化测试、Ruff、mypy、compileall、依赖安全审计通过。
- PostgreSQL 迁移完整回滚和重升通过，应用健康检查正常。
- 测试过程没有泄露 API Key、Prompt、客户原文或模型完整响应。

## 6. 失败项和缺陷

### DEF-AI-003：真实 DeepSeek 评测因输出为空或截断中止

| 项目 | 内容 |
| --- | --- |
| 优先级 | P0，Phase 1 质量门禁阻塞 |
| 状态 | 待 AI Agent 工程师调查和修复/配置调整 |
| 责任 Agent | AIAgent开发工程师Agent |
| 影响 | 130 条评测无法完成，无法证明五类准确率和拒判率门槛；线上分类可能频繁进入失败/重试路径 |

复现步骤：

1. 在项目根目录 `.env` 配置 `LLM_ENABLED=true`、`LLM_LIVE_EVAL=true`，使用当前 DeepSeek 主/备用模型。
2. 执行 `python -m scripts.evaluate_intents` 并传入版本化 130 条 JSONL 数据集。
3. 观察到多次 `llm_call_failed`。
4. 应用层重试耗尽后返回 `LLM_OUTPUT_INVALID`，退出码为 2，未生成聚合报告。

当前无法仅凭稳定错误判断根因是模型输出长度、模型兼容性、JSON Output 行为、模型名称或 Prompt/Token 配置；不得把它直接归因于单一原因。

建议排查顺序：

- 在不记录正文的前提下增加结构化诊断字段：`finish_reason`、输出长度、请求 ID、Provider、模型和错误码。
- 对单条脱敏分类样本验证主模型和备用模型分别的正常结构化输出。
- 核实当前 DeepSeek 模型是否支持 JSON Output、指定模型名称和 `max_tokens=256`。
- 若模型确实需要更多输出预算，评估调整 `LLM_MAX_OUTPUT_TOKENS`，并重新执行截断和成本测试。
- 修复后必须重新执行全量 130 条评测，不能使用探针成功代替质量门禁。

## 7. 验收结论

本轮结论：不通过，暂不建议 Phase 1 最终验收。

理由：真实模型质量门禁已被实际触发，但没有完成评测并生成聚合指标。工程回归通过不等于意图识别质量验收通过。

通过条件：

1. 解决 DEF-AI-003，或完成经架构师确认的 Provider/模型配置调整。
2. 130 条真实评测完整运行并生成正式指标报告。
3. 五类意图准确率 ≥85%。
4. 30 条边界样本正确拒判率 ≥90%。
5. 保留本报告作为失败证据，后续以序号 005 生成复测报告，不覆盖本报告。

## 8. 交接事项

- 交给 AIAgent开发工程师Agent：调查 DeepSeek 真实结构化输出为空/截断问题，补充不泄露正文的诊断和修复。
- 交给架构师Agent：确认 DeepSeek 当前主备模型和 Token 预算是否符合架构基线。
- 交给测试工程师Agent：修复后重新执行 130 条 live 评测并生成序号 005 报告。

## 9. 证据路径

- 上一轮复测：[M04-模型适配与意图识别-AI评测-003](测试工程师/Phase1-P2-01-AIAgent开发工程师Agent-M04-模型适配与意图识别-AI评测-003.md)
- 实施记录：`共享记忆文档/实施记录/Phase1-P2-01-AIAgent开发工程师Agent-截断响应修复与DeepSeek接入-002.md`
- 评测脚本：`CRM智能聊天系统/backend/scripts/evaluate_intents.py`
- 评测集：`CRM智能聊天系统/backend/evals/intent-classifier-v1.0.0.jsonl`
- Provider 测试：`CRM智能聊天系统/backend/tests/test_agent_providers.py`
