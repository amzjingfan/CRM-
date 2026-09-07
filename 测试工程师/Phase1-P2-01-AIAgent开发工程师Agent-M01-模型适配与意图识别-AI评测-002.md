# AI Agent Phase 1 模型适配与意图识别复测报告

## 1. 测试基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase1（AI Agent 工程计划） |
| 任务编号 | P2-01；关联 P2-02 |
| 模块编号 | M01（依据最新 AI 实施记录；架构文档仍需正式确认） |
| 模块名称 | 模型适配与意图识别 |
| 被测主责 Agent | AIAgent开发工程师Agent |
| 被测协作 Agent | 架构师Agent、全栈开发工程师Agent |
| 测试执行 Agent | 测试工程师 Agent |
| 关联初始报告 | `测试工程师/Phase1-P2-01-AIAgent开发工程师Agent-M02-模型适配与意图识别-AI评测-001.md` |
| 关联实施记录 | `共享记忆文档/实施记录/Phase1-P2-01-AIAgent开发工程师Agent-模型适配与意图识别-001.md` |
| 测试类型 | AI评测、回归测试、安全测试、集成测试 |
| 执行日期 | 2026-08-20 |
| 测试结论 | 阻塞；产品缺陷尚未修复，真实模型门禁未执行 |

## 2. 复测目的和范围

本次复测针对初始报告中的 `DEF-AI-001` Provider 截断响应缺陷和 `DEF-AI-002` 真实模型评测门禁进行复核，覆盖：

- OpenAI `incomplete_details.reason=max_output_tokens`。
- Claude `stop_reason=max_tokens`。
- 30 项既有自动化回归测试。
- Ruff、格式检查、mypy、编译检查。
- 009 迁移、Compose、健康检查。
- 真实模型密钥和 live 评测配置是否已注入。

本轮不修改产品代码。依据 `测试工程师/AGENTS.md`，产品缺陷应交由 AI Agent 开发工程师修复。

## 3. 环境和密钥检查

| 项目 | 结果 |
| --- | --- |
| Python | 3.11.15 |
| pytest | 9.1.1 |
| OpenAI SDK | 2.54.0 |
| Anthropic SDK | 0.120.2 |
| `OPENAI_API_KEY` | 未注入进程环境，`.env` 无配置项 |
| `ANTHROPIC_API_KEY` | 未注入进程环境，`.env` 无配置项 |
| `LLM_ENABLED` | 未注入进程环境，`.env` 无配置项 |
| `LLM_LIVE_EVAL` | 未注入进程环境，`.env` 无配置项 |
| `LLM_PRIMARY_MODEL` | 未注入进程环境，`.env` 无配置项 |
| `LLM_FALLBACK_MODEL` | 未注入进程环境，`.env` 无配置项 |

密钥检查只输出存在性，不读取或记录密钥值。

## 4. 复测结果

### 4.1 工程回归

| 验证项 | 命令或方法 | 实际结果 | 状态 |
| --- | --- | --- | --- |
| Ruff | `ruff check app migrations scripts tests` | All checks passed | 通过 |
| 格式 | `ruff format --check app migrations scripts tests` | 99 files already formatted | 通过 |
| 类型 | `mypy app scripts` | 74 个源文件无错误 | 通过 |
| 编译 | `python -m compileall -q app migrations scripts tests` | 通过 | 通过 |
| 自动化测试 | `pytest` | 30 passed，2 条非阻断弃用警告 | 通过 |
| 依赖审计 | `uv audit --locked` | 无已知漏洞 | 通过 |
| 迁移 | 009 升级、回滚、重新升级 | 当前版本 `009_agent_runs` | 通过 |
| 健康检查 | `GET /v1/health` | HTTP 200，`code=0` | 通过 |

### 4.2 截断响应复测

| Provider | 模拟终止状态 | 预期 | 实际 | 状态 |
| --- | --- | --- | --- | --- |
| OpenAI | `incomplete_details.reason=max_output_tokens` | 转为 `LLM_OUTPUT_INVALID` | 返回成功 `ProviderResult` | 失败 |
| Claude | `stop_reason=max_tokens` | 转为 `LLM_OUTPUT_INVALID` | 返回成功 `ProviderResult` | 失败 |

复现日志：

```text
OpenAI: TRUNCATION_ACCEPTED=True
Claude: TRUNCATION_ACCEPTED=True
```

缺陷 `DEF-AI-001` 未修复，仍然存在。

### 4.3 真实模型评测复测

执行命令：

```powershell
cd CRM智能聊天系统/backend
python -m scripts.evaluate_intents --output evals/results/intent-classifier-live.md
```

实际结果：

```text
退出码：2
评测未完成：真实模型评测未启用，请显式设置 LLM_LIVE_EVAL=true
未生成评测报告
```

由于当前没有授权密钥、模型名和 live 开关，本次没有访问 OpenAI/Claude，也没有使用 Fake Provider 冒充正式评测。

## 5. 缺陷和处理要求

### DEF-AI-001：Provider 接受截断结构化响应

- 优先级：P1。
- 当前状态：未修复，复测失败。
- 责任 Agent：AIAgent开发工程师Agent。
- 修复要求：Provider 在读取解析结果前检查 OpenAI `incomplete_details.reason` 和 Claude `stop_reason`；截断必须转换为 `LLM_OUTPUT_INVALID`，并补充 OpenAI/Claude 两个回归测试。
- 验收标准：两种截断场景均拒绝；正常 `completed/end_turn` 结构化响应仍通过；重试次数不超过三次。

### DEF-AI-002：真实模型质量门禁未执行

- 优先级：P0，验收阻塞。
- 当前状态：环境未提供密钥，无法执行。
- 责任 Agent：测试工程师Agent、AIAgent开发工程师Agent。
- 验收标准：五类意图准确率不低于 85%，30 条边界样本正确拒判率不低于 90%，生成正式评测报告。

## 6. 验收结论

本轮复测结论：阻塞，不建议把 Phase 1 标记为“已完成”。

必须完成以下事项后重新复测：

1. AI Agent 开发工程师修复 `DEF-AI-001` 并提交对应回归测试。
2. 提供经过授权的 `OPENAI_API_KEY` 或 `ANTHROPIC_API_KEY`、模型名，并显式设置 `LLM_ENABLED=true`、`LLM_LIVE_EVAL=true`。
3. 重新执行 130 条真实模型评测并达到 85%/90% 门禁。
4. 架构师最终确认模块编号；本报告依据最新实施记录暂使用 `M01`。

## 7. 交接事项

- 交给：AIAgent开发工程师Agent：修复截断响应处理并补充回归测试。
- 交给：架构师Agent：确认 AI 模块正式编号。
- 交给：测试工程师Agent：修复后生成下一序号复测报告并执行真实模型评测。
- 安全要求：测试输出不得打印 API Key、模型完整响应、Prompt 或客户原文。
