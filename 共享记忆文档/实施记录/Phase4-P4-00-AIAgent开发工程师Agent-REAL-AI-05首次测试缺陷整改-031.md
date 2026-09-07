# REAL-AI-05 首次测试缺陷整改实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 `REAL-AI-05` |
| 模块编号 | M04 |
| 主责 Agent | AIAgent开发工程师Agent |
| 协作 Agent | 架构师Agent、全栈开发工程师Agent、测试工程师Agent |
| 实施状态 | 已完成 |
| 开始日期 | 2026-09-04 |
| 完成日期 | 2026-09-04 |
| 代码位置 | `CRM智能聊天系统/` |

“已完成”只表示首次报告三项缺陷的开发整改和开发侧验证完成。缺陷正式关闭、REAL-AI-05 独立验收和生产放行仍由测试工程师、架构师及人类责任人决定。

## 2. 需求与依据

- 产品需求：`共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md` 的 AI 回复、翻译和营销边界。
- 接口依据：`共享记忆文档/智能客服平台 — 管理端接口文档.md` 第 11.16、11.18 节。
- 架构依据：`架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`。
- 任务依据：`AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md` 的 `REAL-AI-05`。
- 测试依据：`测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-REAL-AI-05版本化真实模型评测-AI评测-001.md`。
- 验收依据：`共享记忆文档/MVP范围与验收标准.md` 和 REAL-AI-05 固定质量门禁。
- 代码规范：`共享记忆文档/代码编写手册.md`。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 修复独立开放集无法在不改产品代码的情况下调用真实 Provider 的问题。
- 修复 DeepSeek 结构化输出契约不稳定和危险事实决策质量问题。
- 让 Token 成本明确区分“未配置”和真实估算，并绑定价格版本、币种和口径。
- 保持普通生产 DLP、工具边界和 `send_performed=false` 不变。

### 3.2 实施范围

- 真实模型评测数据集清单、加载器、安全上下文、环境限制和 CLI。
- REAL-AI-05 Prompt、确定性温度、DeepSeek Provider 参数转发和判分报告。
- LLM 计价配置、低敏结果字段、自动化回归和开发冻结集真实运行。
- AI 规范、README、计划状态和共享实施记录。

### 3.3 非目标

- 不创建测试工程师的正式独立开放集，不替测试工程师作出缺陷关闭结论。
- 不修改原 `real-model-v1.0.0` 的 18 条样本或期望标签。
- 不开放公开 AI 回复、生产翻译、营销发送、自动回复或平台写操作。
- 不实施原生 Token 流式、50 客户端 SSE 或五日稳定性测试。
- 不初始化 Git 或伪造提交级不可变候选。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单。
- [x] 已读取相关 PRD、接口、任务拆解和验收标准。
- [x] 涉及代码时已读取代码编写手册和适用 Skill。
- [x] 已确认 Phase4、P4-00、M04 和主责 Agent。
- [x] 已确认 Provider、DLP、评测、计价、测试和生产关闭边界。

## 5. 实施方案

### 5.1 方案说明

独立数据集不再依赖产品代码中的固定版本 Literal 和逐条摘要表，而是由测试工程师持有的数据集与低敏清单共同冻结。加载器复算数据集摘要，校验版本、样本数、18 类覆盖、样本唯一性和 PII/DLP，再派生只对该已验证数据集有效的载荷哈希集合。独立集仅允许在 `integration/staging` 运行，普通请求没有评测安全上下文，生产 DLP 不会因此放宽。

DeepSeek 结构失败的根因是模型返回了 Schema 未允许的近义原因码，而 Prompt v1.0.1 没有枚举完整合法值和映射。修复最终将 Prompt 升级到 v1.2.2，明确全部原因码、决策约束、九维声明、否定与引用边界、条件政策和翻译术语，并把真实评测温度固定为 0。没有修改冻结标签。

成本估算改为可空值和显式状态；启用真实评测时，模型、正数输入/输出单价、价格版本、币种和计价口径必须整体命中批准登记项。报告记录两项费率及 `pricing_version`、`pricing_currency`、`pricing_basis`、`cost_status`，禁止用 0 或任意极小正数冒充已批准成本。

### 5.2 依赖关系

- 前置依赖：REAL-AI-01 Provider、REAL-AI-02 声明、REAL-AI-03 安全门禁、REAL-AI-04 草稿链路。
- 后续依赖：测试工程师未见开放集独立复测、Git 不可变候选、全栈 SSE 50 客户端与五日稳定性、架构师生产放行。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 独立评测入口成为生产 DLP 旁路 | 任意文本可能被外发 | 清单摘要、逐条 PII/DLP、本轮哈希上下文、环境限制和无公开 API；普通请求回归为拒绝 |
| Prompt 调整过拟合开发集 | 开放集质量仍可能失败 | 不修改标签；开发结论只标记待独立复测；测试工程师持有未见开放集 |
| 成本价格随供应商调整 | 估算失真 | 保存价格版本、币种和计价口径；配置值不等于账单 |
| 真实结果被误作生产批准 | 跳过 SSE/稳定性/人类审批 | 文档和实施记录明确所有生产开关继续关闭 |
| 工作区无 Git | 无法证明提交级不可变候选 | 保留文件哈希；生产验收前建立 Git 候选和受保护审批 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `backend/app/agent/real_model_evaluation.py` | 修改 | 增加清单、独立集验证、安全上下文、计价字段和环境门禁 | AIAgent开发工程师Agent |
| `backend/app/agent/security.py` | 修改 | 增加评测安全上下文；Prompt 升级到 v1.2.0 | AIAgent开发工程师Agent |
| `backend/app/agent/providers/base.py` | 修改 | 结构化请求增加可选温度和评测安全上下文 | AIAgent开发工程师Agent |
| `backend/app/agent/providers/deepseek_provider.py` | 修改 | 向 DeepSeek 转发评测温度 | AIAgent开发工程师Agent |
| `backend/app/shared/config/settings.py` | 修改 | 增加价格版本、币种、口径及 live eval 启动校验 | AIAgent开发工程师Agent |
| `backend/app/shared/config/llm_pricing.py` | 新增 | 登记并校验可审计的 DeepSeek 模型计价元组 | AIAgent开发工程师Agent |
| `backend/scripts/evaluate_real_model.py` | 修改 | 接受 `--manifest`，输出低敏稳定错误码并排他创建结果 | AIAgent开发工程师Agent |
| `backend/evals/real-model-v1.0.0.manifest.json` | 新增 | 冻结开发数据集版本、摘要、样本数和来源 | AIAgent开发工程师Agent |
| `backend/evals/results/real-model-v1.0.0-deepseek-20260904-004.json` | 新增 | Prompt v1.1.0 的中间低敏诊断证据 | AIAgent开发工程师Agent |
| `backend/evals/results/real-model-v1.0.0-deepseek-20260904-005.json` | 新增 | Prompt v1.2.0 的低敏通过证据 | AIAgent开发工程师Agent |
| `backend/evals/results/real-model-v1.0.0-deepseek-20260904-006.json` | 新增 | 首次九维严格判分后的低敏失败证据 | AIAgent开发工程师Agent |
| `backend/evals/results/real-model-v1.0.0-deepseek-20260904-007.json` | 新增 | 多语言条件声明修正后的低敏失败证据 | AIAgent开发工程师Agent |
| `backend/evals/results/real-model-v1.0.0-deepseek-20260904-008.json` | 新增 | Prompt v1.2.2 严格判分下的低敏通过证据 | AIAgent开发工程师Agent |
| `backend/tests/test_real_model_evaluation_remediation.py` | 新增 | 三项报告缺陷及审查发现的环境、九维声明、低敏错误、计价绑定和排他落盘回归 | AIAgent开发工程师Agent |
| `backend/tests/test_real_model_evaluation.py` | 修改 | 运行器改用已验证数据集并覆盖计价元数据 | AIAgent开发工程师Agent |
| `backend/tests/test_agent_providers.py` | 修改 | 验证 DeepSeek 温度参数转发 | AIAgent开发工程师Agent |
| `.env.example` | 修改 | 增加带版本和口径的保守计价示例 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/README.md` | 修改 | 更新清单、开放集、计价和当前开发结果说明 | AIAgent开发工程师Agent |
| `AI agent 开发工程师/AI-005-REPLY-回复翻译营销与评测规范-v1.5.md` | 新增 | 固化整改后的真实评测契约和边界 | AIAgent开发工程师Agent |
| `AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md` | 修改 | 同步 REAL-AI-05 开发整改状态 | AIAgent开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：无公共 API 变化。
- 数据库：无迁移；隔离 PostgreSQL 从空库升级至 `023_marketing_review_idempotency` 后完成全量测试。
- 配置项：新增 `LLM_PRICING_VERSION`、`LLM_PRICING_CURRENCY`、`LLM_PRICING_BASIS`；真实密钥未写入文件。
- AI：Prompt 从 `real-model-eval-v1.0.1` 升级为 `real-model-eval-v1.2.2`，评测固定 `temperature=0`；数据集和期望标签未变。

### 6.3 关键实现说明

- 清单与数据集均拒绝重复 JSON 键，防止后值覆盖。
- 独立数据集不得冒用开发冻结版本；开发清单必须同时命中代码登记版本和摘要。
- PII/DLP 在 Provider 前执行；评测上下文只授权当前清单派生的精确载荷。
- 环境门禁由运行器在 Provider 循环前强制执行，配置层同时禁止生产环境启用离线真实模型评测。
- `send_performed` 仍为 `Literal[False]`，评测执行器没有工具、数据库或平台写入路径。
- 转人工结果同时禁止正文和业务声明；其他声明按对象、引用、动作、时态、极性、条件、证据类型、证据 ID 和置信度逐项判分。
- CLI 不回显 Pydantic `input_value` 或异常正文；结果文件使用 `x` 模式排他创建，消除并发覆盖历史证据的窗口。
- 价格未配置时 `estimated_cost_usd=null`、`cost_status=not_configured`，且真实评测门禁失败；已配置费率必须命中批准登记表并随报告落盘。
- 当前价格示例采用 `deepseek-v4-flash` 2026-08-16 后峰值 cache-miss 的保守估算口径；运行前需由全栈/架构师复核最新价格。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| TDD RED | 新增整改测试后先运行 | 缺少目标行为时测试先失败 | 首轮 ImportError；Prompt/温度失败；审查回归因缺少运行器门禁、九维判分和排他写入而失败；条件政策语义测试先失败 | 通过 |
| 聚焦回归 | `uv run pytest -q tests/test_real_model_evaluation.py tests/test_real_model_evaluation_remediation.py tests/test_agent_providers.py tests/test_security.py` | 相关契约通过 | 105 passed，1 个既有弃用警告 | 通过 |
| Ruff | `uv run ruff check app tests scripts migrations` | 无规则错误 | All checks passed | 通过 |
| 格式 | `uv run ruff format --check app tests scripts migrations` | 全部格式正确 | 231 files already formatted | 通过 |
| mypy | `uv run mypy app scripts` | 无类型错误 | 165 source files 通过 | 通过 |
| 默认全量 | `uv run pytest -q` | 无回归 | 1292 passed，12 skipped，2 warnings | 通过 |
| 隔离 PostgreSQL 全量 | `scripts/run-postgres-integration-tests.ps1` | 空库迁移后执行数据库测试 | 1304 passed，2 warnings；测试容器已删除 | 通过 |
| 编译 | `uv run python -m compileall -q app scripts tests` | 无编译错误 | 退出码 0 | 通过 |
| 锁文件 | `uv lock --check` | 锁文件一致 | 125 packages resolved | 通过 |
| 依赖审计 | `uv audit --locked` | 无已知漏洞 | 124 packages 无已知漏洞或不良状态 | 通过 |
| 真实 DeepSeek 中间运行 | 004 号低敏结果 | 验证结构契约修复 | 11/18；结构失败、危险漏放均为 0；仍未达到准确率 | 通过诊断 |
| 真实 DeepSeek 严格判分中间运行 | 006、007 号低敏结果 | 暴露九维判分语义偏差 | 均为 15/18；危险漏放、合法误拦截和 Provider 失败均为 0；正确拒绝放行 | 通过诊断 |
| 真实 DeepSeek 最终开发运行 | 008 号低敏结果 | 达到冻结集和九维声明门禁 | 16/18；危险漏放 0；合法误拦截 0；Provider 失败 0；passed=true；结果 SHA-256 `966780242801641533845ca3987d1162400528d292b1f11852343467f42d8395` | 通过 |
| 低敏证据扫描 | 禁止字段名与密钥形态扫描 | 无正文、Prompt、凭证 | 0 命中 | 通过 |
| 独立代码审查 | 只读审查并对五项 Important 逐项复核 | 无未解决 Critical/Important | `Critical: None; Important: None; Ready: Yes` | 通过 |

两项 pytest 警告仍为既有 Starlette/httpx 与 argon2 兼容弃用提示。本轮首次 Docker 验证因沙箱无法读取用户 Docker 配置而失败；获准使用本机 Docker 后，相同项目脚本成功完成迁移、1285 项测试和隔离容器清理。

## 8. 实施结果

- 完成项：`DEF-REAL-AI05-001～003` 的开发整改、自动化回归、计价配置、文档和真实 DeepSeek 冻结集验证。
- 未完成项：测试工程师未见开放集正式复测、样本扩容、Git 不可变候选、SSE 50 客户端和五日稳定性。
- 与原方案差异：没有修改任何冻结标签；先以 Prompt v1.1.0 验证结构根因，再升级 v1.2.2 收紧九维业务边界和条件政策语义。
- 当前状态：已完成开发整改，三项缺陷等待测试工程师通过递增序号正式报告确认；生产能力未放行。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-031-001 | 独立未见开放集尚未复测，不能证明泛化 | P1 | 测试工程师Agent | Phase4 / REAL-AI-05 独立复测 |
| R-031-002 | 当前 18 条开发集规模不足，翻译和营销覆盖偏少 | P1 | 测试工程师Agent、AIAgent开发工程师Agent | Phase4 / REAL-AI-05 数据集扩容 |
| R-031-003 | 当前目录无 Git，缺少提交级不可变候选 | P1 | 架构师Agent、全栈开发工程师Agent | 生产发布治理 |
| R-031-004 | SSE 50 客户端和五日稳定性未完成 | P1 | 全栈开发工程师Agent、测试工程师Agent | Phase4 / REAL-FS-05 |
| R-031-005 | Token 单价可能变化，当前值仅为版本化保守估算 | P2 | 全栈开发工程师Agent、架构师Agent | 每次生产评测前复核 |

## 10. 交接事项

- 交接给：测试工程师Agent、架构师Agent、全栈开发工程师Agent。
- 后续任务：测试工程师创建不提前暴露给开发 Prompt 的分层开放集与清单，在 `integration/staging` 复测三项缺陷；全栈继续 SSE 和稳定性；架构师维护生产关闭门禁。
- 必须注意：开发侧 16/18 通过不是独立验收；不得开启 `AI_PUBLIC_REPLY_ENABLED`、`AI_MARKETING_CONTENT_ENABLED`、`AI_AUTO_REPLY_ENABLED` 或 `AUTO_REPLY_ENABLED`。

## 11. 文档同步

- [x] 已同步接口变化：无公共接口变化。
- [x] 已同步架构决策：未改变 ADR 边界，新增实现级安全上下文。
- [x] 已同步任务状态：开发整改完成、正式缺陷待独立复测。
- [x] 已通知测试工程师需要覆盖独立集、DLP、质量、成本和低敏证据。
- [x] 测试报告索引将在测试工程师递增序号正式复测完成后更新。
