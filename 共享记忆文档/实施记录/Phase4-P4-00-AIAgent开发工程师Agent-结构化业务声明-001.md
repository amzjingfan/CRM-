# REAL-AI-02 结构化业务声明实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 `REAL-AI-02` |
| 模块编号 | M04 |
| 主责 Agent | AIAgent开发工程师Agent |
| 协作 Agent | 架构师Agent、全栈开发工程师Agent、测试工程师Agent |
| 实施状态 | 已完成 |
| 开始日期 | 2026-08-27 |
| 完成日期 | 2026-08-27 |
| 代码位置 | `CRM智能聊天系统/backend/` |

## 2. 需求与依据

- 产品需求：`共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md` 的 AI 智能问答、订单与工具调用要求。
- 接口依据：`共享记忆文档/智能客服平台 — 管理端接口文档.md` 第 11.13 节。
- 架构依据：`架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md` 的业务事实、证据和失败关闭边界。
- 任务依据：`AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md` 的 `REAL-AI-02`。
- 权威测试基线：M04 回复闭环 014 号报告、DeepSeek Provider 009 号报告。
- 代码规范：`共享记忆文档/代码编写手册.md`。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 用内部强类型声明表达订单、物流、退款、优惠、地址和承诺时间等高风险业务命题。
- 只允许本次运行、同店铺、同对象、同工具的可信证据支持实例事实。
- 对时态不一致、否定/条件作用域不明确、冲突命题和无证据承诺失败关闭。

### 3.2 实施范围

- Agent 内部声明 Schema、证据策略、服务端权威工具声明、回复/营销 Prompt 和自动化测试。
- Prompt 版本、Agent README、内部接口说明和实施计划状态同步。

### 3.3 非目标

- 不修改公开 API、SSE、公共业务 DTO、数据库或 Alembic 迁移。
- 不新增退款或时效工具，不调用真实平台，不执行业务写操作。
- 不放行公开回复、生产翻译、AI 营销、自动回复或真实模型质量门禁。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单。
- [x] 已读取 PRD、接口、任务拆解、职责、MVP、架构决策和最新测试结论。
- [x] 已读取代码编写手册、全部适用 `AGENTS.md` 和 Agent/Python/TDD/安全/独立验证 Skill。
- [x] 已确认 Phase、任务编号、模块编号、依赖和验收方式。
- [x] 未发现需要暂停并提交架构师确认的公共契约或数据库冲突。

## 5. 实施方案

### 5.1 方案说明

复用现有 `BusinessClaim` 和 `BusinessClaimPolicy`，不新建第二套声明框架。模型输出仍属于不可信数据，只能增加安全门禁；服务端从强类型成功工具结果生成对象级权威声明。声明先校验主体动作、对象、证据、店铺和 Mock 属性，再校验作用域与时态，最后决定草稿是否失败关闭。

### 5.2 依赖关系

- 前置依赖：REAL-AI-01 当前 Provider 工程范围、现有全栈工具契约、M04 014 已关闭缺陷。
- 后续依赖：测试工程师 REAL-AI-02 独立复测、REAL-AI-03/04 回归、REAL-AI-05 真实模型评测。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 模型省略或伪造声明 | 高风险事实绕过 | 模型声明不授予自动交付；工具事实由服务端生成 |
| 订单 A 证据支持订单 B | 跨对象泄漏或误答 | 同时校验 `tool_call_id`、工具名、对象 ID 和 `store_id` |
| 否定/条件作用域不清 | 错把非事实当完成事实 | 客户实例非 `affirmed + actual` 一律返回 `AMBIGUOUS_BUSINESS_CLAIM_SCOPE` |
| 当前状态被扩展成未来承诺 | 虚假时效或结果 | 动作与时态白名单；时效承诺没有专用工具时失败关闭 |
| Mock 写被描述为真实完成 | 客户误导 | Mock 写仍生成声明，并返回 `MOCK_COMPLETION_CLAIM` |
| 替代执行端口绕过工具输出校验 | 残缺结果被提升为权威事实 | 声明、模板和证据生成点均再次执行 `TOOL_OUTPUT_SCHEMAS` 校验 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `CRM智能聊天系统/backend/app/agent/business_claims.py` | 修改 | 增加承诺时效主体/动作、实例对象约束、冲突清单、作用域和时态门禁 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/reply_rendering.py` | 修改 | 扩展强类型工具结果的服务端权威声明 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/workflow_prompt.py` | 修改 | 固化高风险声明、时态与作用域规则并升级版本 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/marketing_generation.py` | 修改 | 营销 Prompt 增加承诺时效和作用域规则并升级版本 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_agent_business_claims.py` | 修改 | 新增作用域、时态、承诺、冲突和工具覆盖 TDD 用例 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_agent_workflow.py` | 修改 | 将可信工具工作流夹具升级为完整强类型物流输出 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_agent_phase4.py` | 修改 | 同步营销 Prompt 版本断言 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/README.md` | 修改 | 同步内部声明与 Prompt 版本 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/README.md` | 修改 | 同步当前 Prompt 版本 | AIAgent开发工程师Agent |
| `AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md` | 修改 | 同步 REAL-AI-01 权威结论和 REAL-AI-02 开发状态 | AIAgent开发工程师Agent |
| `共享记忆文档/智能客服平台 — 管理端接口文档.md` | 修改 | 新增 11.13 内部契约，不改变公开 API | AIAgent开发工程师Agent |

### 6.2 接口、数据和配置变更

- API/SSE：无公开变化。
- 数据库：无迁移、表、字段或索引变化；迁移 head 保持 `019_tiktok_channel_unique`。
- 配置/依赖：无新增环境变量、依赖或锁文件变化。
- AI：新增 `promise_time/promise`；工作流 `v1.6.0`，FAQ/工具 Prompt `v1.5.0`，营销 Prompt `v1.3.0`。

### 6.3 关键实现说明

- 声明仍包含计划要求的九个字段，并拒绝未知字段。
- 客户实例主体必须提供脱敏占位或服务端可信对象 ID；FAQ 政策可以不带实例 ID。
- 同一主体和动作跨证据或时态出现重复/冲突命题时，Schema 直接拒绝，不能用不同引用拆分冲突。
- 服务端权威声明覆盖订单、物流、客户画像、地址请求、优惠券和平台消息；退款资金与承诺时效因没有可信工具端口而失败关闭。
- 所有客户实例事实都必须存在明确工具映射；FAQ 不能证明退款申请提交、实例查询或优惠展示。声明、模板和证据生成点会再次校验完整工具输出 Schema。
- 文本规则只负责发现声明遗漏和兼容旧入口，不能授予自动回复。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| TDD 红灯 | 运行新增作用域、时态、承诺、冲突用例 | 旧代码失败 | 5 failed、51 passed | 通过 |
| 工具覆盖红灯 | 运行权威声明参数化用例 | 旧代码无法覆盖四类工具 | 4 failed | 通过 |
| 独立复核红灯 | 新鲜上下文只读复核初版代码 | 发现边界遗漏 | 1 项 P1、2 项 P2，结论 `NEEDS_REVISION` | 通过（真实记录） |
| 复核缺陷 TDD 红灯 | 跨证据冲突、FAQ 实例事实、查询时态、残缺工具输出 | 修复前失败 | 9 failed、59 passed | 通过 |
| 聚焦回归 | `uv run pytest` 五个 Agent 相关文件 | 全部通过 | 392 passed | 通过 |
| 默认全量 | `uv run pytest -q --basetemp .pytest-real-ai02-review-fix` | 无产品失败 | 733 passed、10 skipped；数据库项后续实测 | 通过 |
| 隔离 PostgreSQL | tmpfs `postgres-test` 空库迁移后全量 | 无跳过 | 743 passed、0 skipped | 通过 |
| 迁移回滚 | `019 → 018 → 019` | 恢复 head | `019_tiktok_channel_unique (head)` | 通过 |
| 静态质量 | Ruff、format、mypy、compileall | 无问题 | 全部通过 | 通过 |
| 固定评测 | `scripts.evaluate_phase4` 234 条 | 危险漏放为 0 | 安全/原因码 100%，危险漏放 0；非 live | 通过固定集 |
| 依赖审计 | `uv audit --locked` | 无已知漏洞 | 124 个包无已知漏洞或不良状态 | 通过 |
| 独立二次复核 | 对修复后 4 个固定哈希文件只读复核 | 原 3 项关闭，无新增高优先级问题 | 4/4 哈希一致；`PASS_WITH_NOTES`；生产 `INCONCLUSIVE` | 通过工程复核 |

## 8. 实施结果

- 完成项：内部声明、可信工具绑定、作用域/时态/冲突门禁、Prompt/文档和自动化测试。
- 未完成项：测试工程师正式独立复测、真实 DeepSeek 业务声明开放集评测。
- 与原方案差异：无公共 DTO 或数据库变更；承诺时间采用内部 `promise_time/promise` 显式失败关闭。
- 当前状态：REAL-AI-02 开发实现完成，独立代码复核为 `PASS_WITH_NOTES`；不构成测试工程师正式结论或生产放行。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-REAL-AI02-001 | 真实 DeepSeek 对新增声明枚举的开放集服从率未评测 | P1 | AIAgent开发工程师Agent、测试工程师Agent | REAL-AI-05 |
| R-REAL-AI02-002 | 项目不是 Git 仓库，无法绑定提交级不可变独立审查 | P2 | 架构师Agent、全栈开发工程师Agent | 生产发布基线 |
| R-REAL-AI02-003 | 当前没有退款资金与承诺时效可信工具端口 | P2 | 架构师Agent、全栈开发工程师Agent | 新工具专项评审 |

## 10. 交接事项

- 交接给：测试工程师Agent、架构师Agent。
- 后续任务：对六类高风险命题执行独立变形测试，并在 REAL-AI-05 使用真实模型评测 Schema 服从率。
- 必须注意：不得把开发自测、固定评测或独立 AI 代码复核视为测试工程师正式报告或生产批准；公开 AI 和平台写开关继续关闭。

## 11. 文档同步

- [x] 已同步内部接口契约。
- [x] 已同步任务状态；未产生新的跨模块架构决策。
- [x] 已同步 Prompt 版本和 Agent README。
- [x] 已通知测试工程师需要覆盖的范围。
- [x] 测试报告索引将在正式测试完成后由测试工程师更新。
