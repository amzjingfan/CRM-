# 结构化业务声明只读重放缺陷修复实施记录

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
- 缺陷依据：`测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-结构化业务声明-综合测试-003.md` 中 `DEF-REAL-AI02-004`。
- 验收依据：003 号报告的只读工具安全重试、低敏审计和结构化证据要求。
- 代码规范：`共享记忆文档/代码编写手册.md`。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 修复三个只读工具成功记录重放时被完整 DTO 校验器误判的问题。
- 保持低敏审计摘要可以恢复订单、物流和客户画像的对象级可信事实。
- 不为修复重放而扩大 `tool_calls.output_summary` 的敏感数据范围。
- 重放前重新校验当前权限，避免权限撤销后仍读取历史摘要。

### 3.2 实施范围

- 只读工具 v1 低敏重放 Schema、执行器重放分支及内部 `ToolResult` 版本标识。
- Agent 权威声明、可信工具证据和固定回复模板的重放数据复验。
- 产品回归、003 号独立证据、固定安全评测和后端全量验证。

### 3.3 非目标

- 不修改测试工程师正式报告或由开发侧关闭 `DEF-REAL-AI02-004`。
- 不修改公开 HTTP/SSE、前端、数据库结构、模型、Prompt 或生产开关。
- 不保存完整订单 DTO、外部订单号、物流单号、总消费、联系方式或地址。
- 不放行公开 AI 回复、生产翻译、AI 营销、自动回复或真实高风险平台写操作。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单。
- [x] 已读取相关 PRD、接口、任务拆解和验收标准。
- [x] 已读取代码编写手册和适用的 TDD、安全、缺陷诊断及最小实现 Skill。
- [x] 已确认 Phase、任务编号、模块编号和主责 Agent。
- [x] 已确认依赖、风险和验收方式。

## 5. 实施方案

### 5.1 方案说明

根因是执行器对所有成功重放统一调用完整 `TOOL_OUTPUT_SCHEMAS`。首次只读调用为降低审计敏感度，只保存订单 `order_id/status`、物流 `order_id/tracking_status`、客户画像 `customer_id/order_count`；这些字段本来足以恢复结构化状态事实，却不满足完整查询 DTO，因此被误判为 `TOOL_OUTPUT_INVALID`。

修复使用内部版本化低敏契约：

1. 为三个只读工具定义严格的 `READ_TOOL_REPLAY_OUTPUT_SCHEMAS` v1，拒绝缺失字段、额外字段和类型错误。
2. 成功只读重放通过 v1 Schema 后返回 `succeeded`，并显式设置 `replayed=true`、`replay_contract_version=1`。
3. Agent 渲染和证据边界仅在上述两个标识同时成立时使用低敏 Schema；其他结果继续使用完整 DTO Schema。
4. 权威声明仍绑定原 `tool_call_id`、业务对象和执行来源店铺；订单及物流模板只使用有限状态枚举。
5. 所有重放在返回数据前复核当前权限；拒绝重放不改写历史成功审计。

同一 Agent Run 使用稳定幂等键，因此恢复首次查询快照；新 Agent Run 使用新键并重新查询。该语义既支持工作流恢复，也避免测试替身或普通调用借 `replayed` 字段绕过完整结果校验。

### 5.2 依赖关系

- 前置依赖：REAL-AI-02 结构化声明、受控工具执行层、`tool_calls` 低敏摘要和执行来源店铺绑定。
- 后续依赖：测试工程师对 `DEF-REAL-AI02-004` 的再次独立复测；REAL-AI-03～05 的真实模型和生产门禁。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 为通过重放而持久化完整查询 DTO | 客户和订单敏感数据扩大落库 | 只定义三个最小低敏严格 Schema，不修改摘要生产字段 |
| 任意残缺字典被标记为重放后取得可信身份 | 模型生成错误业务事实 | 同时校验 `replayed`、版本号、工具名和严格 Schema |
| 权限撤销后仍返回历史摘要 | 越权读取店铺数据 | 重放出口先复核当前工具权限，拒绝时不返回数据 |
| 重放结果无法继续生成声明 | Agent 仍会失去证据并转人工 | Agent 权威声明和可信证据边界支持 v1 低敏契约 |
| 写工具误用只读重放契约 | 外部副作用被伪装成功 | 低敏映射只注册三项只读工具，写工具继续完整 Schema/unknown 策略 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `CRM智能聊天系统/backend/app/tools/contracts.py` | 修改 | 增加三个只读 v1 重放 Schema、校验器和结果版本字段 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/tools/executor.py` | 修改 | 分离读写重放校验并在重放前复核当前权限 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/reply_rendering.py` | 修改 | 允许经版本确认的低敏重放数据生成模板、声明和证据 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_tool_executor.py` | 修改 | 增加三类只读重放及权限撤销回归测试 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_agent_business_claims.py` | 修改 | 增加低敏物流重放恢复对象级声明和证据测试 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/evals/results/agent-phase4-real-ai02-read-replay-fix.json` | 新增 | 保存 237 条固定确定性安全评测摘要 | AIAgent开发工程师Agent |
| `AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md` | 修改 | 同步 003 号结论、004 缺陷及开发修复状态 | AIAgent开发工程师Agent |
| `共享记忆文档/智能客服平台 — 管理端接口文档.md` | 修改 | 同步只读 v1 重放、权限复核和敏感数据边界 | AIAgent开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：公开 HTTP/SSE 无变化；内部 `ToolResult` 增加可空 `replay_contract_version=1`。
- 数据库：无迁移、表、字段和索引变化；沿用现有低敏 `tool_calls.output_summary`。
- 配置项：无变化。
- AI：权威声明和可信证据新增只读重放 v1 数据入口；模型、Prompt、阈值和 Provider 均未修改。

### 6.3 关键实现说明

- 完整查询 DTO 和低敏恢复快照保持两个严格契约，避免把审计字段重新定义成公共业务 DTO。
- 低敏快照只证明订单状态、物流状态或画像订单数量，不证明未保存的金额、物流单号、标签等事实。
- `replay_contract_version` 缺失或未知时不会启用低敏证据路径，替代执行端口仍需明确遵守契约。
- 权限失败的新调用仍记录失败；权限失败的历史重放不覆盖原终态，保留审计真实性。
- TDD Skill 先稳定得到 5 个失败；安全 Skill 促使重放执行当前权限复核；缺陷诊断和最小实现 Skill 促使本轮不重查数据库、不扩大摘要、不新增迁移或第二套执行器。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| TDD 红灯 | `uv run pytest tests/test_tool_executor.py tests/test_agent_business_claims.py -q` | 新增只读重放与权限测试在修复前失败 | 82 通过、5 失败 | 通过 |
| 专项与 003 独立证据 | `uv run pytest tests/test_tool_executor.py tests/test_agent_business_claims.py ../../测试工程师/evidence/REAL-AI-02-003/test_real_ai02_third_retest.py -q` | 产品回归及独立证据全部通过 | 104 通过 | 通过 |
| 后端全量 | `uv run pytest --basetemp .pytest-tmp/real-ai02-004-full-3 -q` | 无产品失败 | 751 通过、10 跳过、2 个既有弃用 warning | 通过 |
| 固定安全评测 | `scripts/evaluate_phase4.py` + `evals/agent-phase4-v1.0.0.jsonl` | 危险漏放 0、原因码一致 | 237 条；安全/原因码 100%，危险漏放 0；非 live | 通过 |
| Ruff 检查 | `uv run ruff check app tests` | 无静态问题 | 通过 | 通过 |
| Ruff 格式 | `uv run ruff format --check app tests` | 全部已格式化 | 175 files already formatted | 通过 |
| mypy | `uv run mypy app scripts` | 无类型错误 | 155 个源文件无问题 | 通过 |
| compileall | `uv run python -m compileall -q app scripts` | 编译通过 | 退出码 0 | 通过 |
| 锁文件 | `uv lock --check` | 锁文件有效 | 125 个包解析成功 | 通过 |
| 依赖审计 | `uv audit --locked` | 无已知漏洞 | 124 个包无已知漏洞或不良状态 | 通过 |
| 数据库/真实模型 | 未执行 | 本轮无数据库变更且不应冒充真实模型验证 | 10 项数据库环境用例跳过；无 live 模型结论 | 未执行 |

补充说明：首次全量测试在系统临时目录清理时触发 Windows `WinError 5`，不能记为通过；第二次指定不存在的叶级 `basetemp` 时因父目录缺失产生 2 个环境错误。创建工作区父目录并使用新叶目录后，同一全量用例集正式通过。上述环境失败均未伪装成产品通过。

## 8. 实施结果

- 完成项：`DEF-REAL-AI02-004` 对应根因已在工具契约、执行器、Agent 声明/证据边界和自动化回归中完成开发修复。
- 未完成项：测试工程师尚未基于修复后快照再次独立复测并正式关闭缺陷。
- 与原方案差异：选择版本化低敏快照而非重查数据库；理由是同一 Agent Run 恢复应保持首次事实快照，且现有报告明确允许专用低敏版本契约。
- 当前状态：开发修复已完成；003 号独立证据在当前工作区为 15/15 通过，但 `DEF-REAL-AI02-004` 的权威状态仍为 Open。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-REAL-AI02-004-001 | 正式缺陷需测试工程师基于修复后快照独立复测关闭 | P2 | 测试工程师Agent | REAL-AI-02 再次综合测试 |
| R-REAL-AI02-004-002 | 真实 DeepSeek 的结构化声明服从率尚未执行开放集评测 | P1 | AIAgent开发工程师Agent、测试工程师Agent | REAL-AI-05 |
| R-REAL-AI02-004-003 | 低敏快照不能证明金额、物流单号、标签等未保存事实 | P2 | AIAgent开发工程师Agent | 保持失败关闭；需要这些事实时启动新 Agent Run 查询 |
| R-REAL-AI02-004-004 | 数据库集成用例在当前环境跳过 | P3 | 测试工程师Agent、环境维护者 | 独立复测环境 |

## 10. 交接事项

- 交接给：测试工程师Agent、全栈开发工程师Agent、架构师Agent。
- 后续任务：测试工程师重新执行 003 号 15 项独立证据，并增加重放版本缺失/未知、额外字段、当前权限撤销和跨店铺来源测试。
- 必须注意：不要修改历史 001～003 正式报告；不要把开发回归等同正式缺陷关闭。低敏重放不能扩展为未保存业务事实；公开 AI、营销和自动回复开关继续关闭。

## 11. 文档同步

- [x] 已同步接口变化。
- [x] 已同步架构决策；本轮未新增跨模块 ADR，只落实既有低敏、权限和证据边界。
- [x] 已同步任务状态。
- [x] 已通知测试工程师需要覆盖的范围。
- [x] 测试报告索引由测试工程师在正式复测后更新；本轮未改写权威测试结论。
