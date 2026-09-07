# DeepSeek 真实评测稳定性修复实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase1（AI Agent 工程计划） |
| 任务编号 | P2-01；关联 P2-02 |
| 模块编号 | M04 |
| 主责 Agent | AIAgent开发工程师Agent |
| 协作 Agent | 架构师Agent、测试工程师Agent |
| 实施状态 | 已完成 |
| 开始日期 | 2026-08-20 |
| 完成日期 | 2026-08-20 |
| 代码位置 | `CRM智能聊天系统/backend/` |

## 2. 需求与依据

- 缺陷依据：`测试工程师/Phase1-P2-01-AIAgent开发工程师Agent-M04-模型适配与意图识别-AI评测-004.md` 的 DEF-AI-003。
- 架构依据：`架构师/ADR-001-AI-模型适配与意图识别模块编号确认为M04-v1.0.md`。
- 任务依据：`AI agent 开发工程师/PLAN-001-AI-Agent工程实施计划-v1.0.md` 的 Phase 1。
- 验收依据：五类准确率不低于 85%，边界正确拒判率不低于 90%，真实评测能够完整生成报告。
- 代码规范：`共享记忆文档/代码编写手册.md`。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 修复 DeepSeek V4 返回空内容或 `finish_reason=length` 导致真实评测提前终止的问题。
- 让单条 Provider 失败可审计且不阻断剩余评测，同时禁止把失败误算成正确拒判。
- 完成 130 条真实 DeepSeek 工程评测并达到质量门禁。

### 3.2 实施范围

- DeepSeek 思考模式配置、安全诊断、Prompt v1.0.1、评测统计和回归测试。
- 根目录环境文件加载路径修正和配置模板同步。
- 真实模型工程评测证据生成；正式测试结论仍由测试工程师发布。

### 3.3 非目标

- 不实现 RAG、工具调用、自动回复、`/suggest`、SSE 或前端能力。
- 不修改测试工程师 M04-004 权威报告。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单和相关 PRD、接口、任务、职责资料。
- [x] 已读取代码编写手册、AI 工程规范和 M04-004 测试报告。
- [x] 已确认正式模块编号为 M04，历史 M01/M02 文件名不修改。
- [x] 已确认本次只处理模型适配、意图评测和安全配置。

## 5. 实施方案

### 5.1 方案说明

DeepSeek V4 默认思考模式会先生成推理 Token。短分类请求的 256 Token 预算可能在最终 JSON 生成前耗尽，表现为内容为空且 `finish_reason=length`。本模块默认向 DeepSeek 传入 `thinking.type=disabled`，并保留可校验的显式配置项。

Provider 对截断、空内容和结构无效记录安全诊断字段：Provider、模型、请求 ID、终止原因、内容长度、推理长度和稳定错误码，不记录 Prompt、消息正文、模型正文或 API Key。

评测器按样本捕获稳定模型错误，继续完成其余样本；错误进入混淆矩阵 `error` 列和错误码分布，且任一 Provider 失败都会使门禁失败。Prompt v1.0.1 明确 mixed、insufficient_context、unknown 的优先级和唯一合法 JSON 组合。

### 5.2 依赖关系

- 前置依赖：DeepSeek Provider、五类意图 Schema、130 条版本化评测集。
- 后续依赖：测试工程师按 M04-005 执行独立复测并发布正式测试结论。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 开启思考模式再次耗尽预算 | 空 JSON、评测失败 | 分类任务默认关闭，变更后必须重新执行 130 条评测 |
| 单条异常掩盖整体质量 | 报告不完整或误通过 | 继续评测、错误单独计数、错误数必须为 0 |
| 诊断日志泄露数据 | 隐私或密钥风险 | 仅记录长度、枚举、请求 ID 和稳定错误码 |
| 模型输出存在随机性 | 复测结果波动 | 保留 Prompt 版本和门禁，正式结论由测试工程师独立复测 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `backend/app/agent/providers/deepseek_provider.py` | 修改 | 关闭分类思考模式并增加安全诊断 | AIAgent开发工程师Agent |
| `backend/app/agent/providers/factory.py` | 修改 | 下发 DeepSeek 思考模式配置 | AIAgent开发工程师Agent |
| `backend/app/shared/config/settings.py` | 修改 | 增加思考模式配置并固定根目录 `.env` 加载路径 | AIAgent开发工程师Agent |
| `backend/app/agent/prompt.py` | 修改 | Prompt 升级到 v1.0.1，收紧拒判和 JSON 契约 | AIAgent开发工程师Agent |
| `backend/app/agent/evaluation.py` | 修改 | Provider 错误、错误矩阵和合成用例定位统计 | AIAgent开发工程师Agent |
| `backend/scripts/evaluate_intents.py` | 修改 | 单条失败继续、质量门禁和安全报告增强 | AIAgent开发工程师Agent |
| `backend/tests/test_agent_providers.py` | 修改 | 验证关闭思考模式和截断行为 | AIAgent开发工程师Agent |
| `backend/tests/test_agent_evaluation.py` | 修改 | 验证 Provider 失败不会被算作正确拒判 | AIAgent开发工程师Agent |
| `.env.example`、`README.md` | 修改 | 同步配置和评测说明 | AIAgent开发工程师Agent |
| `backend/evals/results/intent-classifier-live-20260820-fixed-v2.md` | 新增 | 130 条真实模型工程评测聚合证据 | AIAgent开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：无变更。
- 数据库：无变更。
- 配置项：新增 `DEEPSEEK_THINKING_ENABLED=false`；项目配置从代码仓库根目录 `.env` 加载。真实密钥不写入本文档。
- AI：Prompt 从 `intent-classifier-v1.0.0` 升级为 `intent-classifier-v1.0.1`；门禁新增 Provider 失败数必须为 0。

### 6.3 关键实现说明

- `finish_reason=length` 仍严格作为 `LLM_OUTPUT_INVALID`，没有放宽 DEF-AI-001 的安全规则。
- 关闭思考模式是任务级选择，不改变 OpenAI、Anthropic Provider，也不影响后续需要推理能力的独立工作流。
- 评测报告只包含聚合数据以及合成 case ID/标签，不包含样本原文和模型原始输出。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| 单条真实探针 | 脱敏 DeepSeek 分类调用 | 返回合法 JSON，不截断 | `logistics_query/classified`，19 输出 Token | 通过 |
| 130 条真实评测 | `python -m scripts.evaluate_intents ...fixed-v2.md` | 85%/90%，错误数 0 | 分类 85.00%，拒判 96.67%，Provider 失败 0 | 通过 |
| Ruff | `ruff check app migrations scripts tests` | 无错误 | All checks passed | 通过 |
| 格式 | `ruff format --check app migrations scripts tests` | 格式正确 | 130 files already formatted | 通过 |
| mypy | `mypy app scripts` | 无类型错误 | 100 个源文件无错误 | 通过 |
| pytest | `python -m pytest -q` | 全部通过 | 46 passed，2 个第三方弃用警告 | 通过 |
| Compose | `docker-compose config --quiet` | 配置可解析 | 退出码 0；本机 Docker 配置文件权限警告不影响解析 | 通过 |

## 8. 实施结果

- 完成项：DEF-AI-003 根因修复、安全诊断、评测不中断、Prompt v1.0.1、130 条真实评测和完整回归。
- 未完成项：测试工程师独立复测与正式 M04-005 测试报告。
- 与原方案差异：为避免 Provider 单点故障导致没有报告，新增失败计数和错误门禁。
- 当前状态：开发实施已完成；工程评测达到既定门槛，等待测试工程师独立确认正式验收结论。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-001 | 真实模型存在随机性，需独立复测确认稳定性 | P1 | 测试工程师Agent | Phase1/P2-02，M04-005 |
| R-002 | 当前分类准确率恰好达到 85% 门槛，后续应扩充样本并持续校准 | P1 | AIAgent开发工程师Agent | 后续评测迭代 |

## 10. 交接事项

- 交接给：测试工程师Agent、架构师Agent。
- 后续任务：按 M04-005 重新执行真实 DeepSeek 评测和截断/安全回归。
- 必须注意：复测必须保持 `DEEPSEEK_THINKING_ENABLED=false`，不得输出真实密钥；正式测试结论只写入测试工程师目录。

## 11. 文档同步

- [x] 已同步 AI Provider 和 Prompt 变化。
- [x] 已同步配置、评测门禁和实施状态。
- [x] 已通知测试工程师覆盖 M04-005 独立复测。
- [x] 测试报告索引将在正式复测完成后由测试工程师更新。
