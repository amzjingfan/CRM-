# REAL-AI-05 版本化真实模型评测实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 `REAL-AI-05` |
| 模块编号 | M04 |
| 主责 Agent | AIAgent开发工程师Agent |
| 协作 Agent | 架构师Agent、全栈开发工程师Agent、测试工程师Agent |
| 实施状态 | 部分完成 |
| 开始日期 | 2026-09-04 |
| 完成日期 | 2026-09-04 |
| 代码位置 | `CRM智能聊天系统/` |

## 2. 需求与依据

- 产品需求：`共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md` 的 AI 准确率、首输出和转人工要求。
- 接口依据：`共享记忆文档/智能客服平台 — 管理端接口文档.md` 第 11.16、11.18 节；本任务不新增公共 HTTP API。
- 架构依据：`架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`、`架构师/ADR-005-AI-知识语义类型与发布审批边界-v1.0.md`。
- 任务依据：`AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md` 的 `REAL-AI-05`。
- AI 规范：`AI agent 开发工程师/AI-005-REPLY-回复翻译营销与评测规范-v1.4.md`。
- 验收依据：`共享记忆文档/MVP范围与验收标准.md`、REAL-AI-04 004 号正式测试报告。
- 代码规范：`共享记忆文档/代码编写手册.md`。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 建立版本化合成数据集和可重复执行的真实 DeepSeek 评测 CLI。
- 保存计划规定的版本、哈希、决策、原因、时延、Token 和成本指标。
- 执行一次当前模型真实评测并据实输出放行结论。

### 3.2 实施范围

- 18 类、18 条冻结合成样本；17 条真实 Provider 调用和 1 条模型超时故障注入。
- 精确载荷 SHA-256 DLP 登记、结构化 Schema、确定性判分、低敏 JSON 结果。
- 默认后端、隔离 PostgreSQL、确定性安全集、静态质量和依赖审计回归。

### 3.3 非目标

- 不使用真实客户、店铺、订单或消息数据。
- 不修改公共 API、数据库、前端或平台工具。
- 不执行真实 TikTok 写操作，不开启公开回复、翻译、营销或自动回复。
- 不替代测试工程师独立报告、50 客户端 SSE 或五日稳定性测试。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单。
- [x] 已读取 PRD、接口、任务拆解、团队职责、验收标准和最新测试索引。
- [x] 已读取代码编写手册、全部相关 `AGENTS.md` 和 Agent/Python/安全/测试/独立验证 Skill。
- [x] 已确认 Phase4、P4-00、M04 和主责 Agent。
- [x] 已确认 DeepSeek 服务端配置存在；未读取或输出 Key。

## 5. 实施方案

### 5.1 方案说明

评测数据集的期望标签不发送给模型。模型只接收任务、目标语言、合成消息、合成证据和依赖状态。每个规范化外发载荷在 DLP 中登记 SHA-256；任意字符变化会失败关闭。

模型结果先通过 Pydantic Schema，再由冻结标签确定性判分。原始 Prompt、样本和模型正文只在进程内存在，落盘仅保存输入/输出哈希、枚举状态、稳定错误码、时延和 Token。真实 Provider 输出不合法时记为 `LLM_OUTPUT_INVALID`，不伪装成质量通过。

### 5.2 依赖关系

- 前置依赖：REAL-AI-01 Provider、REAL-AI-02 声明、REAL-AI-03 缺陷关闭、REAL-AI-04 草稿链路。
- 后续依赖：AI Prompt/模型质量整改、测试工程师独立复测、全栈 SSE 50 客户端和五日稳定性、架构师生产放行。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 评测载荷旁路 DLP | 真实自由文本可能出境 | 只允许冻结载荷逐字 SHA-256，变形测试失败关闭 |
| 结果文件泄漏正文 | 形成第二份敏感数据 | 只落盘 SHA-256、枚举、时延和 Token，并执行字段扫描 |
| 为通过而修改标签 | 评测失真 | 数据集摘要冻结，Prompt 升级但不改标签 |
| 网络超时不可重复 | 超时场景证据不稳定 | 单独使用显式故障注入并从真实 Provider 样本数中区分 |
| 当前模型结构输出不稳定 | 生产回复不可控 | 门禁失败，公开 AI 和平台副作用保持关闭 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `CRM智能聊天系统/backend/app/agent/real_model_evaluation.py` | 新增 | 数据集模型、输出 Schema、运行器、判分和指标聚合 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/security.py` | 修改 | 登记真实评测 Prompt 和 18 个冻结载荷摘要 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/scripts/evaluate_real_model.py` | 新增 | 真实 DeepSeek 评测 CLI，拒绝覆盖历史证据 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_real_model_evaluation.py` | 新增 | 覆盖类别、DLP 变形、无副作用、低敏报告和判分回归 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/evals/real-model-v1.0.0.jsonl` | 新增 | 18 类冻结合成评测集 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/evals/results/real-model-v1.0.0-deepseek-20260904-001.json` | 新增 | 受限网络下的连接失败证据 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/evals/results/real-model-v1.0.0-deepseek-20260904-002.json` | 新增 | Prompt v1.0.0 真实模型失败证据 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/evals/results/real-model-v1.0.0-deepseek-20260904-003.json` | 新增 | 当前 Prompt v1.0.1 真实模型结果 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/evals/results/agent-phase4-real-ai05-deterministic.json` | 新增 | 237 条确定性安全回归结果 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/README.md` | 修改 | 增加 REAL-AI-05 命令、门禁和当前结论 | AIAgent开发工程师Agent |
| `AI agent 开发工程师/AI-005-REPLY-回复翻译营销与评测规范-v1.4.md` | 新增 | 固化真实评测版本、安全边界和当前结果 | AIAgent开发工程师Agent |
| `AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md` | 修改 | 同步 REAL-AI-03/04 权威状态和 REAL-AI-05 结果 | AIAgent开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：无公共 API 变化。
- 数据库：无迁移；隔离库验证当前 head 为 `023_marketing_review_idempotency`。
- 配置项：复用 `LLM_ENABLED`、`LLM_LIVE_EVAL`、DeepSeek Provider 和 Token 单价配置，不新增密钥项。
- AI：新增 Prompt `real-model-eval-v1.0.1`、数据集 `real-model-v1.0.0`、DLP 策略仍为 `prompt-dlp-v1.3.0`。

### 6.3 关键实现说明

- `send_performed` 使用 `Literal[False]`，模型不能声明平台副作用。
- 转人工结果必须 `content=null`；非转人工结果必须有内部草稿。
- 报告门禁为准确率 `>=85%`、危险漏放 0、合法误拦截 0、真实 Provider 失败 0。
- 当前非原生流式 Provider 的首输出定义为首个通过 Schema 和安全校验的完整结果。
- Token 单价当前为 0，成本字段不能解释为真实计费。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| TDD RED | `pytest tests/test_real_model_evaluation.py` | 新模块不存在时失败 | `ModuleNotFoundError` | 通过 |
| 聚焦测试 | `python -m pytest tests/test_real_model_evaluation.py -q` | 评测契约通过 | 5 passed | 通过 |
| Ruff | `python -m ruff check app tests scripts migrations` | 无规则错误 | All checks passed | 通过 |
| 格式 | `python -m ruff format --check app tests scripts migrations` | 全部格式正确 | 229 files formatted | 通过 |
| mypy | `python -m mypy app scripts` | 无类型错误 | 164 source files 通过 | 通过 |
| 默认全量 | `python -m pytest -q --basetemp ...` | 无回归 | 1264 passed, 12 skipped, 2 warnings | 通过 |
| 隔离 PostgreSQL 全量 | 迁移到 023 后设置 `TEST_DATABASE_URL` 运行 pytest | 全部数据库用例通过 | 1276 passed, 2 warnings | 通过 |
| Alembic | 临时 pgvector 库 `alembic upgrade head/current` | 到达当前 head | `023_marketing_review_idempotency` | 通过 |
| 固定安全评测 | `python -m scripts.evaluate_phase4 ...` | 危险漏放 0 | 237/237，unsafe escape 0 | 通过 |
| 锁文件 | `uv lock --check` | 锁文件一致 | 125 packages resolved | 通过 |
| 依赖审计 | `uv audit --locked` | 无已知漏洞 | 124 packages 无已知漏洞/不良状态 | 通过 |
| 真实 DeepSeek | `python -m scripts.evaluate_real_model ...003.json` | 达到 REAL-AI-05 门禁 | 4/18；危险漏放 1；合法误拦截 1；Provider 失败 10 | 失败 |
| 低敏结果检查 | 解析三个结果文件并检查字段 | 无正文/Prompt/输出字段 | 未发现原始字段 | 通过 |

默认全量的 12 个跳过项在隔离 PostgreSQL 运行中全部执行并通过。两项警告为既有 Starlette/httpx 与 argon2 弃用提示。第一次隔离库运行因未先执行 Alembic 出现 12 个 `stores` 不存在错误；完成迁移后同库重跑为 1276 通过，不登记产品缺陷。

## 8. 实施结果

- 完成项：版本化数据集、Prompt、DLP 摘要登记、CLI、低敏证据、指标、测试和真实 DeepSeek 执行。
- 未完成项：当前模型未达到质量门禁；测试工程师独立复测、SSE 50 客户端和五日稳定性仍待执行。
- 与原方案差异：模型超时采用显式故障注入；当前 Provider 非原生流式，因此首输出是首个安全结构化结果。
- 当前状态：部分完成。评测系统和真实证据已交付，但模型质量验收失败，不能标记 REAL-AI-05 或生产 AI 已放行。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-AI05-001 | 10/17 在线样本为 `LLM_OUTPUT_INVALID` | P1 | AIAgent开发工程师Agent | REAL-AI-05 Prompt/模型整改 |
| R-AI05-002 | 当前真实结果有 1 条危险漏放 | P1 | AIAgent开发工程师Agent | REAL-AI-05 安全质量整改 |
| R-AI05-003 | 当前真实结果有 1 条合法误拦截 | P2 | AIAgent开发工程师Agent | REAL-AI-05 可用性整改 |
| R-AI05-004 | Token 单价为 0，无法给出真实成本 | P2 | 全栈开发工程师Agent | 生产配置准备 |
| R-AI05-005 | 当前目录不是 Git 仓库，缺少不可变发布候选 | P1 | 架构师Agent、全栈开发工程师Agent | 生产发布基线 |

## 10. 交接事项

- 交接给：测试工程师Agent、全栈开发工程师Agent、架构师Agent。
- 后续任务：测试工程师独立评测；AI Agent 修复结构输出与危险漏放；全栈补价格并完成 SSE/稳定性；架构师继续拒绝生产放行。
- 必须注意：不得修改冻结标签追求通过，不得将开发结果当作正式测试报告，不得开启任何公开或平台副作用开关。

## 11. 文档同步

- [x] 已同步接口变化（无公共接口变化，README 增加命令）。
- [x] 已同步架构决策（未改变 ADR 边界）。
- [x] 已同步任务状态。
- [x] 已通知测试工程师需要覆盖真实模型和低敏证据范围。
- [x] 测试报告索引将在测试工程师正式测试完成后更新。

## 12. 临时资源清理

- 已删除 `crm-real-ai05-test-001` 临时 pgvector 容器；其数据库位于 tmpfs，只含合成测试数据，删除后不可恢复。
- 已删除本轮三个 pytest `--basetemp` 临时目录。
- 现有项目 Compose 服务未重启、未删除，真实店铺和业务数据未参与本轮测试。
