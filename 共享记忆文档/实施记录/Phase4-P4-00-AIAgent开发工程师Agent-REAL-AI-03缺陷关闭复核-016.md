# REAL-AI-03 缺陷关闭复核实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 `REAL-AI-03` |
| 模块编号 | M04 |
| 主责 Agent | AIAgent开发工程师Agent |
| 协作 Agent | 架构师Agent、全栈开发工程师Agent、测试工程师Agent |
| 实施状态 | 已完成 |
| 开始日期 | 2026-08-31 |
| 完成日期 | 2026-08-31 |
| 代码位置 | `CRM智能聊天系统/backend/app/agent/`；本轮未修改产品代码 |

## 2. 需求与依据

- 产品需求：`共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md` 中关于有依据回复、人工接管和禁止虚构业务结果的要求。
- 接口依据：`共享记忆文档/智能客服平台 — 管理端接口文档.md` 第 11.4、11.6 节内部 Agent 契约。
- 架构依据：`架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md` 的业务事实证据绑定、失败关闭和生产开关边界。
- 任务依据：`AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md` 的 `REAL-AI-03`。
- AI 规范：`AI agent 开发工程师/AI-005-REPLY-回复翻译营销与评测规范-v1.3.md`。
- 权威测试依据：`测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-回复翻译营销与评测闭环-综合测试-014.md`。
- 工程规范：项目级及各职责目录 `AGENTS.md`、`共享记忆文档/代码编写手册.md` 和 `共享记忆文档/实施记录文档规范.md`。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 确认 `DEF-P4-AI-008/009` 当前代码无回归，并同步 REAL-AI-03 的权威状态。
- 确认高风险退款事实与页面、按钮、FAQ、文档、流程图、表单、入口和术语表状态保持区分。
- 确认模型自由文本不能取得自动交付授权，合法草稿仍可进入人工复核。

### 3.2 实施范围

- 审计当前退款事实安全策略、回复安全策略、工作流三态决策和结构化业务声明边界。
- 运行历史回归、数据库全量回归、静态检查和版本化确定性安全评测。
- 更新 REAL-AI-03 计划状态、实施索引和本实施记录。

### 3.3 非目标

- 不实现或放行真实 DeepSeek 开放集质量、公开 AI 回复、生产翻译、AI 营销发送、自动回复或真实平台写操作。
- 不修改 `app/agent` 产品代码、公共 API、数据库迁移、Prompt、固定评测集或测试工程师正式报告。
- 不覆盖历史实施记录，不修改测试报告索引的权威结论。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单及相关最新上下文。
- [x] 已读取 PRD、接口、任务拆解、团队职责、MVP、架构决策和测试结论。
- [x] 已读取代码编写手册、AI-005 v1.3、全部适用 `AGENTS.md` 和相关安全/TDD/独立验证 Skill。
- [x] 已确认本任务为 REAL-AI-03，主责为 AIAgent开发工程师Agent。
- [x] 已确认 M04-014 已正式关闭 008/009；本轮重点为当前代码复核和状态同步。

## 5. 实施方案

### 5.1 方案说明

复用现有结构化业务声明和三态工作流，不增加新的词表或第二套安全框架。当前授权边界如下：

```text
模型自由文本 / FAQ
→ 最多 HUMAN_REVIEW，保留草稿，不获得自动交付权限

真实查询工具成功 + 服务端权威声明 + 单一已知状态固定模板 + 独立安全复核
→ AUTO_REPLY_READY，send_performed=false

确定性阻断、跨对象证据、Mock、未知状态或工具失败
→ TRANSFERRED 或 HUMAN_REVIEW，禁止成功话术
```

退款文本规则仅作为纵深防御：它识别高风险事实和非业务技术对象，不能为自然语言授予业务权限。最终自动权限由服务端可信工具结果和工作流状态共同决定。

### 5.2 依赖关系

- 前置依赖：M04-014 的结构化声明根修复、REAL-AI-01 Provider 工程范围和现有 Agent 工作流。
- 后续依赖：REAL-AI-05 真实 DeepSeek 评测、SSE 并发和稳定性门禁；测试工程师后续正式回归仍保持独立。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 自然语言新增表达绕过文本规则 | 高风险事实可能漏报 | 自由文本和 FAQ 不具备自动授权；结构化声明与可信工具绑定作为主门禁 |
| 合法页面或文档状态被误判为退款事实 | 合法草稿被错误转人工 | 对技术对象执行独立识别；历史合法样本和 M04-010 样本回归 |
| 测试结论与计划文档不同步 | 后续 Agent 错判工作状态 | 只引用测试工程师正式报告，更新计划状态，不改历史证据 |
| 工程测试通过被误解为生产放行 | 未完成真实模型和稳定性门禁 | 计划和记录明确 `live_model_evaluation=false`，生产开关继续关闭 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md` | 修改 | 同步 REAL-AI-02 已正式关闭和 REAL-AI-03 当前关闭范围 | AIAgent开发工程师Agent |
| `共享记忆文档/实施记录索引.md` | 修改 | 登记本实施记录 | AIAgent开发工程师Agent |
| `共享记忆文档/实施记录/Phase4-P4-00-AIAgent开发工程师Agent-REAL-AI-03缺陷关闭复核-016.md` | 新增 | 记录本轮复核、验证和生产边界 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/evals/results/agent-phase4-real-ai03-deterministic.json` | 新增 | 仅保存确定性评测统计，不保存样本正文 | AIAgent开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：不适用，本轮没有公共接口变化。
- 数据库：不适用，本轮没有迁移、表、字段或索引变化；隔离数据库仅用于测试。
- 配置项：不适用；`AUTO_REPLY_ENABLED`、`AI_TRANSLATION_ENABLED`、`AI_MARKETING_ENABLED` 等生产开关保持关闭。
- AI：不新增 Prompt、模型或安全框架；复核现有结构化声明和三态授权边界。

### 6.3 关键实现说明

- `ReplySafetyPolicy` 将模型自由文本与 FAQ 的 `automatic_delivery_allowed` 固定为 false；即使自然语言安全检查未命中，也只能进入人工复核路径。
- `RefundFactPolicy` 对退款资金/审批结果和页面、表单、帮助文档等技术对象分开判断；模型声明不能替代服务端权威声明。
- `workflow.py` 只允许真实查询工具固定模板在权威声明、工具安全复核和置信度均满足时进入 `AUTO_REPLY_READY`，且返回 `send_performed=false`。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| REAL-AI-03 聚焦回归 | `uv run pytest -q tests/test_agent_phase4.py tests/test_agent_business_claims.py tests/test_agent_workflow.py` | 历史退款/业务声明/工作流不回归 | 384 passed | 通过 |
| 静态规则 | `uv run ruff check app migrations scripts tests` | 无规则错误 | All checks passed | 通过 |
| 代码格式 | `uv run ruff format --check app migrations scripts tests` | 全部已格式化 | 215 files already formatted | 通过 |
| 类型检查 | `uv run mypy app scripts` | 无类型错误 | 160 source files 无问题 | 通过 |
| Python 编译 | `uv run python -m compileall -q app scripts` | 编译成功 | 退出码 0 | 通过 |
| 后端默认全量 | `uv run pytest -q --basetemp .pytest-real-ai03-default` | 无产品失败 | 786 passed、10 skipped、2 warnings | 通过；跳过项为未提供 TEST_DATABASE_URL 的集成项 |
| 隔离 PostgreSQL 全量 | 设置 `TEST_DATABASE_URL` 后执行 `uv run pytest -q --basetemp .pytest-real-ai03-postgres-full` | 无跳过、迁移和数据库回归通过 | 796 passed、2 warnings | 通过 |
| 数据库迁移 | `uv run alembic upgrade head`、`uv run alembic current` | 空库升级到 head | `019_tiktok_channel_unique (head)` | 通过 |
| 版本化确定性评测 | `uv run python -m scripts.evaluate_phase4 --dataset evals/agent-phase4-v1.0.0.jsonl --output evals/results/agent-phase4-real-ai03-deterministic.json` | 危险漏放为 0，原因码一致 | 237 条；安全准确率 100%，原因码准确率 100%，危险漏放 0；`live_model_evaluation=false` | 通过固定集 |
| 独立模型自由文本边界 | 只读调用 `ReplySafetyPolicy` 检查新中文/英文样本 | 模型内容不能自动交付 | 3/3 `automatic_delivery_allowed=false`，合法和危险表达均保留人工边界 | 通过工程复核 |
| 临时数据库清理 | `docker stop crm-real-ai03-pg` | 不触碰持久化业务库 | 一次性 tmpfs 容器已停止 | 通过 |

正式缺陷关闭依据仍为测试工程师 M04-014；本记录不替代测试报告。

## 8. 实施结果

- 完成项：当前代码复核、历史安全回归、数据库全量回归、静态检查、确定性评测和 REAL-AI-03 状态同步。
- 未完成项：真实 DeepSeek 开放集质量、公开 AI 回复、生产翻译、AI 营销、SSE 50 并发、五日稳定性和真实平台写操作。
- 与原方案差异：无产品代码变更；REAL-AI-03 的安全根修复已在 M04-014 前置实施并由测试工程师正式确认，本轮完成复核和交接状态同步。
- 当前状态：确定性工程范围已完成；生产接入仍未放行。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-REAL-AI03-001 | 真实 DeepSeek 对开放集业务声明和回复质量尚未评测 | P1 | AIAgent开发工程师Agent、测试工程师Agent | REAL-AI-05 |
| R-REAL-AI03-002 | 真实模型 SSE 并发、首包、P99 和五日稳定性尚未完成 | P1 | AIAgent开发工程师Agent、全栈开发工程师Agent、测试工程师Agent | REAL-AI-05；REAL-FS-05 |
| R-REAL-AI03-003 | 测试报告结论属于确定性工程范围，不构成生产放行 | P1 | 架构师Agent | Phase4 生产放行门禁 |

## 10. 交接事项

- 交接给：架构师Agent、测试工程师Agent、全栈开发工程师Agent。
- 后续任务：测试工程师继续以 M04-014 为权威缺陷结论；AI/全栈工程师在 REAL-AI-05 执行真实模型、SSE、稳定性和平台联合门禁。
- 必须注意：不得把 `AUTO_REPLY_READY` 解释为已发送；`send_performed=false`、生产开关关闭、真实模型评测未完成。任何模型失败、安全失败、工具未知或证据不足均须失败关闭。

## 11. 文档同步

- [x] 已同步 REAL-AI-03 计划状态。
- [x] 已同步实施记录索引。
- [x] 已引用测试工程师 M04-014，不修改测试报告或测试报告索引。
- [x] 已明确生产门禁和未完成项。
- [x] 已通知后续 Agent 保持公开回复、翻译、营销和自动回复关闭。
