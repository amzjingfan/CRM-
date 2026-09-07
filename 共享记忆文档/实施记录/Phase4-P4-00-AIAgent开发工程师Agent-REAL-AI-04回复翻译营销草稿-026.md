# REAL-AI-04 回复、翻译和营销草稿实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 `REAL-AI-04` |
| 模块编号 | M04 |
| 主责 Agent | AIAgent开发工程师Agent |
| 协作 Agent | 全栈开发工程师Agent、架构师Agent、测试工程师Agent |
| 实施状态 | 已完成 |
| 开始日期 | 2026-09-02 |
| 完成日期 | 2026-09-02 |
| 代码位置 | `CRM智能聊天系统/` |

> 本记录的“已完成”仅表示 REAL-AI-04 确定性工程范围和回归验证完成，不代表真实 DeepSeek、公开 AI 回复、自动回复、营销发送或生产放行。

## 2. 需求与依据

- 产品需求：`共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md` 中 AI 回复、翻译、人工接管和主动营销边界。
- 接口依据：`共享记忆文档/智能客服平台 — 管理端接口文档.md` 中 Agent 建议、SSE 和营销 AI 边界。
- 架构依据：`AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md` 的 `REAL-AI-04`。
- AI 规范：`AI agent 开发工程师/AI-005-REPLY-回复翻译营销与评测规范-v1.3.md`。
- 安全架构：`AI agent 开发工程师/AI-006-SAFETY-知识语义类型与发布审批架构评审请求-v1.0.md`、`架构师/ADR-005-AI-知识语义类型与发布审批边界-v1.0.md`。
- 验收依据：`共享记忆文档/MVP范围与验收标准.md` 中 AI 安全、人工接管和不自动发送要求。
- 代码规范：`共享记忆文档/代码编写手册.md` 及当前项目各级 `AGENTS.md`。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 保持回复、翻译和营销生成使用现有结构化 Provider、Agent 工作流和结果契约。
- 为人工审核提供通过确定性检查和独立复核的营销候选草稿。
- 保证翻译输入脱敏、原文只以消息 ID 和 SHA-256 关联，公开结果不暴露 Provider、模型和 Token。
- 保证翻译模型失败、工作流取消或异常不会写成成功运行。

### 3.2 实施范围

- FAQ/工具回复继续由现有 RAG、结构化声明和安全策略决定；结果保持 `send_performed=false`。
- 跨语言时生成客户消息和客服草稿的独立翻译字段。
- 弃单挽回和中差评跟进的结构化营销候选文案、业务声明检查和人工审核状态。
- AI 营销结果保留安全候选正文，但固定 `is_safe=false`、`requires_human=true`，不能被 Worker 发送。
- 补充翻译失败终态和营销草稿可交付行为测试。

### 3.3 非目标

- 不实现真实 DeepSeek 质量评测、50 客户端 SSE 压测或五日稳定性观察。
- 不开启公开 AI 回复、自动回复、AI 营销发送或任何真实平台写操作。
- 不修改全栈工具执行、平台适配器、数据库迁移和 `agent_runs` 结构。
- 不生成正式测试工程师报告；正式报告仍由测试工程师Agent负责。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单和相关上下文。
- [x] 已读取 PRD、接口文档、任务拆解、MVP 验收标准和团队职责。
- [x] 已读取代码编写手册、各级 `AGENTS.md` 和适用 `ponytail` Skill。
- [x] 已确认 `REAL-AI-04` 依赖当前 Provider、Agent 工作流、RAG、安全策略和营销 Worker。
- [x] 已确认公开回复、自动回复和营销发送开关继续关闭。
- [x] 已先运行相关基线测试，确认修改前 806 项 AI 相关测试通过。

## 5. 实施方案

### 5.1 方案说明

回复链路继续使用既有 Agent 状态、RAG/工具安全判定、固定回复结果和 SSE 传输层。Agent 只产生结构化草稿和安全结果，
不调用平台发送；公共结果契约仍固定 `send_performed=false`。

翻译链路由 `TranslationService` 根据客户语言和客服工作语言决定是否调用模型。跨语言时只把脱敏后的客户消息和安全草稿
发送给结构化 Provider，结果使用触发消息 UUID 与原文 SHA-256 关联；语言相同时零模型调用。翻译输出目标语言和草稿存在性
由 Schema 约束，模型异常向工作流上抛，由工作流写入失败终态。

营销链路由 `MarketingCopyService` 生成结构化候选并执行确定性安全检查，再调用独立复核节点验证业务声明、触发事实和正文
一致性。只有无安全违规且独立复核通过的正文可以交给人工审核；返回结果仍然不可发送。存在业务承诺、语言不一致或复核失败
时隐藏正文。`MarketingCycleWorker` 只接受 `is_safe=true` 且有正文的结果，因 REAL-AI-04 结果固定人工审核，AI 营销不会进入
发券或平台消息副作用路径。

### 5.2 依赖关系

- 前置依赖：REAL-AI-01 Provider 生产加固、REAL-AI-02 结构化业务声明、REAL-AI-03 知识语义和安全门禁、全栈营销 Worker。
- 后续依赖：测试工程师独立复测、真实 DeepSeek 离线评测、SSE 性能门禁、人工审核闭环和生产开关评审。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 模型生成业务承诺 | 误导客户或形成未授权平台承诺 | 强制业务声明、安全策略和独立复核；违规正文隐藏并人工接管 |
| 营销草稿被误当作发送结果 | 产生平台副作用 | `is_safe=false`、`requires_human=true`、`send_performed=false`；Worker 发送前再次拒绝 |
| 翻译输入包含客户标识 | 产生数据泄漏 | Provider 前统一 `sanitize_prompt_text`，公开结果只保留哈希和低敏字段 |
| 翻译模型失败仍记为成功 | 运行追踪与 SSE 结果不一致 | 翻译异常不吞掉，由主工作流失败处理器记录失败/超时终态 |
| 当前开发测试通过被误认为生产质量 | 过早开启生产能力 | 明确真实模型评测、并发、稳定性和测试工程师正式报告仍是后续门禁 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `CRM智能聊天系统/backend/app/agent/marketing_generation.py` | 修改 | 通过双重安全检查的营销候选保留给人工审核；不安全候选继续隐藏，结果固定不可发送 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/workflow.py` | 修改 | 翻译 Provider 异常不再被吞掉，确保模型失败进入工作流失败终态 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_agent_phase4.py` | 修改 | 增加安全营销候选正文交付断言，保持危险文案隐藏和不发送断言 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_agent_workflow.py` | 修改 | 增加翻译超时不成功记账回归测试 | AIAgent开发工程师Agent |
| `AI agent 开发工程师/AI-005-REPLY-回复翻译营销与评测规范-v1.3.md` | 修改 | 同步当前代码实际使用的工作流、工具和营销 Prompt 版本 | AIAgent开发工程师Agent |
| `AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md` | 修改 | 同步 REAL-AI-04 当前工程状态和生产未放行边界 | AIAgent开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：不新增公开 HTTP 字段；既有建议/SSE 翻译公开字段继续隐藏 Provider、模型、Token 和原始模型响应。
- 数据库：不新增迁移、不修改表结构；营销 Agent 运行记录仍只保存低敏摘要。
- 配置项：不新增配置；`AI_TRANSLATION_ENABLED`、`AI_MARKETING_ENABLED` 和 LLM 总开关保持既有关闭策略。
- AI：营销候选正文仅在通过确定性检查和独立复核时交人工；结果仍不具备发送权；翻译目标语言、原文哈希和脱敏边界保持强类型约束。

### 6.3 关键实现说明

- 营销生成结果的 `is_safe` 表示可否进入发送链路，而不是是否值得人工查看；因此安全候选可以返回 `content`，但仍固定为 `is_safe=false` 和 `requires_human=true`。
- 业务承诺、语言不一致或独立复核失败时 `content=None`，避免人工审核界面误显示不安全候选。
- 翻译节点的 `LLMProviderError`、输出结构错误和取消信号均沿工作流异常路径处理；`AgentWorkflowService` 在成功完成前不会调用完成记录。
- 所有现有回复结果继续由全栈调用方负责权限、工具和平台副作用；AI 模块没有新增发送入口。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| 修改前 AI 基线 | `uv run pytest -q tests/test_agent_phase4.py tests/test_agent_workflow.py tests/test_agent_providers.py tests/test_agent_domain.py tests/test_agent_synthetic_demo.py` | 无回归基线 | `806 passed` | 通过 |
| TDD 红测：营销草稿 | `uv run pytest -q tests/test_agent_phase4.py::test_marketing_copy_generation_returns_safe_draft_without_sending` | 原实现应因正文为空失败 | `1 failed`，确认缺口 | 通过 |
| 营销草稿修复 | `uv run pytest -q tests/test_agent_phase4.py::test_marketing_copy_generation_returns_safe_draft_without_sending tests/test_agent_phase4.py::test_bad_review_copy_with_unapproved_compensation_fails_closed` | 安全候选可审核，危险候选隐藏 | `2 passed` | 通过 |
| TDD 红测：翻译失败 | `uv run pytest -q tests/test_agent_workflow.py::test_translation_model_failure_fails_workflow_without_success_record` | 原实现应错误完成 | `1 failed`，确认缺口 | 通过 |
| 翻译失败修复 | `uv run pytest -q tests/test_agent_workflow.py::test_translation_model_failure_fails_workflow_without_success_record tests/test_agent_workflow.py::test_workflow_returns_translation_linked_to_trigger_message tests/test_agent_phase4.py::test_marketing_copy_generation_returns_safe_draft_without_sending tests/test_agent_phase4.py::test_bad_review_copy_with_unapproved_compensation_fails_closed` | 失败不成功记账，正常翻译和营销安全边界通过 | `4 passed` | 通过 |
| Python 静态检查 | `uv run ruff check app tests` | 无 Ruff 错误 | `All checks passed!` | 通过 |
| Python 格式 | `uv run ruff format --check app tests` | 无格式差异 | `182 files already formatted` | 通过 |
| Python 类型 | `uv run mypy app` | 无类型错误 | `Success: no issues found in 146 source files` | 通过 |
| 后端全量回归 | `uv run pytest -q` | 无失败 | `1184 passed, 10 skipped, 2 warnings` | 通过 |
| 独立只读核验 | 读取实现并核验发送、脱敏、哈希、取消失败关键断言 | 关键边界存在且一致 | 9 项检查全部 PASS | 通过 |
| 真实模型评测 | 真实 DeepSeek 评测集和生产质量指标 | 通过后才可生产 | 未执行，当前不具备真实生产放行条件 | 未执行 |
| 50 客户端 SSE 与五日稳定性 | 生产门禁压测和观察 | 满足性能/稳定性阈值 | 未执行，交由后续联合阶段 | 未执行 |

## 8. 实施结果

- 完成项：回复链路不新增发送权；翻译脱敏、哈希关联、语言校验和失败终态；营销安全候选草稿、独立复核和人工审核门禁；对应 TDD 测试和全量回归。
- 未完成项：真实 DeepSeek 质量评测、公开 AI 回复、自动回复、AI 营销发送、SSE 生产并发和五日稳定性。
- 与原方案差异：营销结果从“安全候选也隐藏”调整为“安全候选保留给人工审核但不可发送”；不安全候选仍隐藏，未扩大任何副作用权限。
- 当前状态：REAL-AI-04 确定性工程范围已完成；生产能力未放行。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-001 | 真实 DeepSeek 回复、翻译和营销质量评测未执行 | P1 | AIAgent开发工程师Agent、测试工程师Agent | Phase4 / REAL-AI-05 |
| R-002 | 公开回复、自动回复和 AI 营销发送开关仍关闭 | P1 | 架构师Agent、全栈开发工程师Agent | Phase4 生产放行门禁 |
| R-003 | 营销候选正文当前没有独立运营审核持久化/发布接口 | P1 | 全栈开发工程师Agent、架构师Agent | 后续营销审核闭环 |
| R-004 | SSE 50 客户端并发、P99 和五日稳定性未验证 | P1 | 全栈开发工程师Agent、测试工程师Agent | Phase4 生产门禁 |
| R-005 | 当前项目不是 Git 仓库，不能提供提交级不可变基线 | P2 | 架构师Agent、项目负责人 | 版本治理 |

## 10. 交接事项

- 交接给：测试工程师Agent、全栈开发工程师Agent、架构师Agent。
- 后续任务：测试工程师独立复测安全候选正文、危险候选隐藏、翻译失败终态和脱敏；全栈评审营销人工审核结果的展示/持久化边界；架构师继续维护生产放行门禁。
- AI 工程师固定交接契约：营销结果必须先人工审核，`send_performed=false`；翻译结果只使用公开低敏字段；任何模型失败不得写成功终态。
- 当前最新测试结论仍以 `测试工程师/` 权威报告和 `共享记忆文档/测试报告索引.md` 为准；本记录不替代正式测试报告。

## 11. 文档同步

- [x] 已同步 REAL-AI-04 任务状态。
- [x] 已在实施记录索引登记本记录。
- [x] 已明确接口、数据和发送边界未扩大。
- [x] 已明确测试工程师需要覆盖的新增回归范围。
- [x] 已保持正式测试报告与实施记录的职责边界。
