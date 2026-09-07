# 结构化业务声明幂等重放缺陷修复实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 REAL-AI-02 |
| 模块编号 | M04 |
| 主责 Agent | AIAgent开发工程师Agent |
| 协作 Agent | 全栈开发工程师Agent、架构师Agent、测试工程师Agent |
| 实施状态 | 已完成 |
| 开始日期 | 2026-08-27 |
| 完成日期 | 2026-08-27 |
| 代码位置 | `CRM智能聊天系统/backend/` |

## 2. 需求与依据

- 产品需求：`共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md`。
- 接口依据：`共享记忆文档/智能客服平台 — 管理端接口文档.md` 第 11.13 节。
- 架构依据：`架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`。
- 任务依据：`AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md` 的 REAL-AI-02。
- 缺陷依据：`测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-结构化业务声明-综合测试-002.md` 中 `DEF-REAL-AI02-003`。
- 验收依据：报告 002 的幂等重放预期、独立证据和 REAL-AI-02 失败关闭要求。
- 代码规范：`共享记忆文档/代码编写手册.md`。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 修复地址修改、发券和平台消息三类 Mock 写工具幂等重放丢失结构化失败关闭语义的问题。
- 阻止低敏审计摘要被无校验地解释成完整成功业务结果。
- 为历史不完整摘要和未来新写入同时建立失败关闭边界。

### 3.2 实施范围

- 受控工具执行器的成功摘要持久化校验与幂等重放恢复。
- Agent Mock 结果无结构化声明时的确定性安全门禁。
- Mock 写动作进入人工复核而不暴露不安全草稿的工作流终态兼容。
- 产品回归、测试工程师独立证据、固定评测、全量和隔离 PostgreSQL 验证。

### 3.3 非目标

- 不修改正式测试报告或由开发侧自行关闭 `DEF-REAL-AI02-003`。
- 不修改公开 HTTP/SSE、前端或公共业务 DTO。
- 不新增数据库迁移、依赖、模型、Prompt 或生产开关。
- 不持久化完整地址、完整消息、凭证或客户隐私。
- 不放行公开 AI 回复、生产翻译、AI 营销、自动回复或真实高风险平台写操作。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单。
- [x] 已读取相关 PRD、接口、任务拆解和验收标准。
- [x] 已读取代码编写手册和适用的 TDD、安全、缺陷诊断及最小实现 Skill。
- [x] 已确认 Phase、任务编号、模块编号和主责 Agent。
- [x] 已确认依赖、风险和验收方式。

## 5. 实施方案

### 5.1 方案说明

根因链路为：首次写工具返回完整内存 `data`，但数据库只保存字段不足的 `output_summary`；幂等重放直接把该审计摘要作为成功 `ToolResult.data`；Agent 对完整输出 Schema 复验时丢弃摘要，导致权威声明和可信证据为空；未命中文本兼容词表的措辞因此没有安全原因码。

修复采用三层边界：

1. 新写操作在成功摘要持久化前使用对应工具输出 Schema 校验；校验失败记录 `unknown/TOOL_RESULT_UNKNOWN`，不制造不可恢复的成功终态。
2. 历史成功记录重放时再次校验摘要；写工具摘要缺失或不完整时返回 `unknown/TOOL_RESULT_UNKNOWN`，不返回 `succeeded` 且禁止自动重试。
3. Agent 观察到 Mock 结果但无法形成非空权威声明时直接返回 `MOCK_COMPLETION_CLAIM`，不再依赖自然语言词表发现风险。

地址、发券和平台消息的新摘要只补足现有输出 Schema 所需的最小字段。完整地址和消息正文仍不落入 `output_summary`；没有引入第二套版本化 DTO、数据库迁移或新依赖。

### 5.2 依赖关系

- 前置依赖：REAL-AI-02 既有结构化声明、全栈受控工具契约、`tool_calls` 幂等记录和 019 迁移基线。
- 后续依赖：测试工程师对 `DEF-REAL-AI02-003` 的再次独立复测；REAL-AI-03～05 的真实模型、安全和质量门禁。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 审计摘要被当成完整业务 DTO | Mock 完成事实可能失去结构化阻断 | 持久化前和重放出口使用同一输出 Schema 校验 |
| 历史摘要无法安全恢复 | 错误成功或重复外部写操作 | 返回 `unknown/TOOL_RESULT_UNKNOWN` 并禁止自动重试 |
| 修复摘要时保存敏感正文 | 地址、消息或客户隐私泄漏 | 仅补充强类型最小字段，不保存完整地址和消息 |
| 安全门禁依赖措辞词表 | 同义表达绕过 Mock 阻断 | Mock 结果无权威声明时无条件返回稳定原因码 |
| 安全失败改变既有人工处理语义 | Mock 会话被不必要地自动转接 | 仅有 `MOCK_COMPLETION_CLAIM` 且工具成功时进入人工复核；不安全草稿仍不对客暴露 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `CRM智能聊天系统/backend/app/tools/executor.py` | 修改 | 校验重放摘要、历史不完整写摘要返回 unknown、补全三类最小低敏摘要 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/reply_safety.py` | 修改 | Mock 结果无结构化声明时返回 `MOCK_COMPLETION_CLAIM` | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/workflow.py` | 修改 | 仅有 Mock 完成阻断且工具成功时保留人工复核，不暴露不安全草稿 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_tool_executor.py` | 修改 | 增加历史重放和持久化前摘要校验测试 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_agent_business_claims.py` | 修改 | 增加三类不完整 Mock 重放失败关闭测试 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/evals/agent-phase4-v1.0.0.jsonl` | 修改 | 增加地址、发券和平台消息三条幂等重放固定样本 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/evals/results/agent-phase4-real-ai02-replay-fix.json` | 新增 | 保存 237 条固定确定性评测摘要 | AIAgent开发工程师Agent |
| `AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md` | 修改 | 同步 001/002 关闭和 003 开发修复状态 | AIAgent开发工程师Agent |
| `共享记忆文档/智能客服平台 — 管理端接口文档.md` | 修改 | 同步低敏摘要、重放 unknown 和 Mock 无声明失败关闭契约 | AIAgent开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：不适用；公开 HTTP/SSE 契约未变化。
- 数据库：无迁移、表、字段和索引变化；沿用 `tool_calls.output_summary`。
- 配置项：无变化。
- AI：新增内部重放失败关闭语义；没有修改模型、Prompt、阈值或 Provider。

### 6.3 关键实现说明

- `output_summary` 明确定位为低敏审计字段，只有通过对应工具输出 Schema 才能作为重放数据使用。
- 写工具新产生的不完整摘要在落库成功终态前即降级为 `unknown`，避免继续生成历史坏数据。
- 既有坏记录不尝试猜测缺失字段，也不自动重放真实副作用。
- Agent 安全门禁以服务端 Mock 状态和结构化声明是否存在为依据，不以模型文本命中关键词作为授权条件。
- TDD 先得到 6 个既有链路失败和 1 个持久化前校验失败，再完成最小修复；安全 Skill 促使历史数据和替代端口统一失败关闭，最小实现 Skill 促使本轮不新增迁移、依赖或第二套执行器。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| TDD 红灯：报告根因 | 工具重放与 Agent 安全新增测试 | 三类 Mock 重放在修复前失败 | 75 通过、6 失败 | 通过 |
| TDD 红灯：写入前防复发 | 单独运行不完整新摘要测试 | 修复前错误返回 succeeded | 1 失败 | 通过 |
| Agent/工具聚焦回归 | `uv run pytest` 五个相关测试文件 | 无回归 | 402 通过 | 通过 |
| 测试工程师 002 独立证据 | `uv run pytest -c pyproject.toml ../../测试工程师/evidence/REAL-AI-02-002/test_real_ai02_retest.py -q` | 15 项全部通过 | 15 通过 | 通过 |
| 固定安全评测 | `python -m scripts.evaluate_phase4` | 三类重放受阻、危险漏放 0 | 237 条；安全/原因码 100%，危险漏放 0；非 live | 通过 |
| 默认后端全量 | `uv run pytest --basetemp .pytest-tmp-real-ai02` | 无产品失败 | 744 通过、10 跳过、2 warning | 通过 |
| 隔离 PostgreSQL 全量 | `DATABASE_URL/TEST_DATABASE_URL` 指向 `postgres-test` 后执行全量 | 无跳过 | 754 通过、2 warning | 通过 |
| 迁移回滚与恢复 | 隔离库 `upgrade head → downgrade base → upgrade head` | 恢复 head | `019_tiktok_channel_unique (head)` | 通过 |
| Ruff 检查 | `uv run ruff check .` | 产品代码无问题 | 通过；存在既有 ACL warning | 通过 |
| Ruff 格式 | `uv run ruff format --check app scripts tests migrations` | 产品源文件已格式化 | 208 files already formatted | 通过 |
| mypy | `uv run mypy app scripts` | 无类型错误 | 155 个源文件无问题 | 通过 |
| compileall | `uv run python -m compileall -q app scripts` | 编译通过 | 退出码 0 | 通过 |
| 锁文件 | `uv lock --check` | 锁文件有效 | 125 个包解析成功 | 通过 |
| 依赖审计 | `uv audit --locked` | 无已知漏洞 | 124 个包无已知漏洞或不良状态 | 通过 |

补充说明：`ruff format --check .` 在遍历当前 Windows 工作区 ACL 受限条目时触发 Ruff 自身 panic；对全部产品 Python 目录的显式检查通过。默认 pytest 首次完成用例后因用户临时目录 ACL 在清理 `pytest-current` 时退出异常，改用工作区 `--basetemp` 后同一用例集通过。两项均未被伪装为产品测试通过。

## 8. 实施结果

- 完成项：`DEF-REAL-AI02-003` 对应根因已在执行器、Agent 安全门禁、工作流和固定评测中完成开发修复。
- 未完成项：测试工程师尚未基于修复后快照再次独立复测并正式关闭缺陷。
- 与原方案差异：除修复报告指向的历史重放出口外，额外增加新摘要持久化前校验，防止同类坏数据继续产生。
- 当前状态：开发修复已完成；002 号证据在当前工作区为 15/15 通过，但权威 `DEF-REAL-AI02-003` 仍保持 Open。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-REAL-AI02-003-001 | 正式缺陷需测试工程师基于修复后快照独立复测关闭 | P2 | 测试工程师Agent | REAL-AI-02 再次综合测试 |
| R-REAL-AI02-003-002 | 真实 DeepSeek 的结构化声明服从率尚未执行开放集评测 | P1 | AIAgent开发工程师Agent、测试工程师Agent | REAL-AI-05 |
| R-REAL-AI02-003-003 | 历史不完整成功摘要只能返回 unknown，无法恢复原始完整结果 | P2 | 全栈开发工程师Agent | 后续数据治理；禁止自动重试 |
| R-REAL-AI02-003-004 | `ruff format --check .` 受当前 Windows ACL/Ruff panic 影响 | P3 | 开发环境维护者 | 工具环境治理 |

## 10. 交接事项

- 交接给：测试工程师Agent、全栈开发工程师Agent、架构师Agent。
- 后续任务：测试工程师重新执行报告 002 的 15 项独立证据，并增加“首次生成完整可重放摘要”和“历史不完整摘要返回 unknown”测试；REAL-AI-05 继续验证真实模型声明完整性。
- 必须注意：不要修改历史 001/002 正式报告；不要把当前开发回归等同正式缺陷关闭。历史 unknown 写记录禁止自动重试；公开 AI、营销和自动回复开关继续关闭。

## 11. 文档同步

- [x] 已同步接口变化。
- [x] 已同步架构决策；本轮没有新增跨模块 ADR，只落实既有失败关闭与低敏边界。
- [x] 已同步任务状态。
- [x] 已通知测试工程师需要覆盖的范围。
- [x] 测试报告索引由测试工程师在正式复测后更新；本轮未改写权威测试结论。
