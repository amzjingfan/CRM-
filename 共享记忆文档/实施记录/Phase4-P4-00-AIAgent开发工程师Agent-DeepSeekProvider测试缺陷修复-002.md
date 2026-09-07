# DeepSeek Provider 测试缺陷修复实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 `REAL-AI-01` |
| 模块编号 | M04 |
| 主责 Agent | AIAgent开发工程师Agent |
| 协作 Agent | 全栈开发工程师Agent、架构师Agent、测试工程师Agent |
| 实施状态 | 已完成；待测试工程师独立复测 |
| 开始日期 | 2026-08-26 |
| 完成日期 | 2026-08-26 |
| 代码位置 | `CRM智能聊天系统/` |

## 2. 需求与依据

- 产品需求：`共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md` 中 AI 智能问答和数据安全边界。
- 接口依据：`共享记忆文档/智能客服平台 — 管理端接口文档.md` 中 Phase 4 AI 内部契约及 REAL-AI-01 安全增量。
- 架构依据：`架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md` 第 3.3、5、7 节。
- 任务依据：`AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md` 的 `REAL-AI-01`。
- 测试依据：`测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-DeepSeekProvider生产加固-综合测试-001.md` 中 `DEF-REAL-AI01-001/002`。
- 验收依据：`共享记忆文档/MVP范围与验收标准.md` 的 AI、安全、回归和生产门禁要求。
- 代码规范：`共享记忆文档/代码编写手册.md`。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 阻止完整地址通过消息、历史、翻译、营销、工具结果或遗漏脱敏的调用方进入外部 Provider。
- 阻止客户端 Trace ID 和供应商请求 ID 等日志元数据夹带任意正文、Unicode、控制字符或超长值。
- 保持既有 Provider JSON Schema、错误分类、重试、Prompt、数据库和平台写边界不变。

### 3.2 实施范围

- AI Prompt 共用脱敏函数和统一 `StructuredRequest` Provider 边界。
- 工具结果结构化地址字段脱敏。
- 生产 JSON 日志元数据门禁。
- HTTP 请求 Trace ID 入口校验。
- 单元、集成、数据库和固定安全评测回归。

### 3.3 非目标

- 不执行 REAL-AI-02～05 的结构化声明、真实模型质量评测、50 客户端 SSE 或五日稳定性。
- 不修改模型、Prompt 版本、RAG、数据库迁移或平台写操作。
- 不替代测试工程师关闭正式缺陷。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单。
- [x] 已读取最新 PRD、接口、任务拆解、团队职责和验收标准。
- [x] 已读取代码编写手册、全部适用 `AGENTS.md` 和 Agent/Python/安全/测试 Skill。
- [x] 已确认 Phase4、P4-00、REAL-AI-01、M04 和 AIAgent 主责边界。
- [x] 已复现两个 P1；修复前聚焦测试为 10 failed、42 passed。

## 5. 实施方案

### 5.1 方案说明

地址保护采用三层纵深防御：共用文本脱敏识别中文、英文、地址标签和邮编；工具结果按地址字段名整体替换；冻结的 `StructuredRequest` 在所有外部 Provider 的共同边界再次脱敏。这样即使未来某个 Prompt 构造器遗漏显式调用，也不能把已识别的完整地址原样交给 Provider。

日志保护不再使用敏感词正则证明白名单字段值安全。生产 Formatter 仅接受长度不超过 100 的有限 ASCII 元数据；其他值统一替换。HTTP 中间件只沿用标准 UUID 形式的客户端 `X-Trace-Id`，非法值由服务端新生成 UUID，阻断其继续进入 Agent 运行记录、响应头和日志。

### 5.2 依赖关系

- 前置依赖：ADR-004、既有 Prompt 构造器、`StructuredRequest`、`JsonFormatter` 和 FastAPI Trace ID 中间件。
- 后续依赖：测试工程师对 `DEF-REAL-AI01-001/002` 的 002 号独立复测；REAL-AI-05 真实模型评测。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 地址模式误伤普通业务文本 | 分类或回复语义受损 | 增加普通物流路线和商品名称负向样本，不匹配时保持原文 |
| 分段工具地址可重新拼接 | 完整地址出境 | 按 `shipping_address/street/city/postal_code` 等字段语义整体屏蔽 |
| 非法 Trace ID 失去关联 | 诊断困难 | 服务端生成并返回新的标准 UUID，而不是静默删除 |
| 供应商异常字段夹带正文 | 生产日志泄漏 | 最终 Formatter 统一执行字符集和长度门禁 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `CRM智能聊天系统/backend/app/agent/security.py` | 修改 | 增加中文、英文、标签地址和邮编脱敏及结构化地址字段识别 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/providers/base.py` | 修改 | 在所有 Provider 共用的 `StructuredRequest` 构造边界再次脱敏 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/workflow_prompt.py` | 修改 | 工具结果中的结构化地址字段整体替换 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/shared/logging/setup.py` | 修改 | 对生产日志字符串元数据增加格式、字符集和长度门禁 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/main.py` | 修改 | 客户端 Trace ID 仅接受标准 UUID，否则生成服务端 UUID | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_agent_domain.py` | 修改 | 增加中英文地址、楼栋/房间/邮编、Provider 边界和负向样本 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_agent_tool_execution.py` | 修改 | 增加结构化工具地址不可进入 Prompt 的回归测试 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_real_runtime_config.py` | 修改 | 增加日志正文、Unicode、控制字符和超长标识负向测试 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_health.py` | 修改 | 增加不可信客户端 Trace ID 被替换的端到端测试 | AIAgent开发工程师Agent |
| `共享记忆文档/智能客服平台 — 管理端接口文档.md` | 修改 | 同步 Provider 数据边界和 Trace ID 安全约束 | AIAgent开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：请求体和响应 JSON 不变；`X-Trace-Id` 只沿用标准 UUID，非法值返回服务端新 UUID。
- 数据库：无迁移、表、字段或索引变化；当前验证 head 为 `019_tiktok_channel_unique`。
- 配置项：无新增或变化。
- AI：不修改 Prompt、模型、RAG、工具选择和阈值；只收紧模型输入数据边界。

### 6.3 关键实现说明

- 地址脱敏优先于电话和长数字脱敏，防止只隐藏门牌号却留下可复原街道和楼栋。
- `StructuredRequest` 为冻结数据类，`__post_init__` 使用受控赋值完成最终脱敏，调用后不能再修改 Prompt 绕过边界。
- 工具结果只对明确地址字段整体屏蔽，不把物流事件 `location` 误当客户地址。
- 日志非法元数据统一为 `[INVALID_LOG_METADATA]`，不记录原始值或可逆编码。
- 无新增依赖，不创建第二套 Provider、脱敏服务或日志框架。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| TDD 红灯 | 四个聚焦测试文件 | 两个缺陷可稳定复现 | 10 failed、42 passed | 通过 |
| 修复后聚焦 | `uv run pytest tests/test_agent_domain.py tests/test_agent_tool_execution.py tests/test_real_runtime_config.py tests/test_health.py -q` | 全部通过 | 55 passed、1 个既有 warning | 通过 |
| AI 聚焦回归 | 全部 `test_agent_*.py` 加日志和健康测试 | 无既有 AI 契约回归 | 477 passed、1 个既有 warning | 通过 |
| Ruff | `uv run ruff check app tests scripts` | 无问题 | All checks passed | 通过 |
| 格式 | `uv run ruff format --check app tests scripts` | 无漂移 | 187 files already formatted | 通过 |
| mypy | `uv run mypy app scripts` | 无类型问题 | 155 个源文件无问题 | 通过 |
| 编译 | `uv run python -m compileall -q app scripts` | 编译成功 | 无错误 | 通过 |
| 锁文件 | `uv lock --check` | 无漂移 | 125 packages resolved | 通过 |
| 隔离 PostgreSQL 全量 | tmpfs PostgreSQL 16 + `TEST_DATABASE_URL` | 无跳过完整回归 | 573 passed、0 skipped、2 个既有 warning | 通过 |
| 迁移可逆性 | `019 → 018 → 019` | 当前迁移可回滚并恢复 | 最终 `019_tiktok_channel_unique (head)` | 通过 |
| 固定安全评测 | `scripts.evaluate_phase4` | 无危险漏放 | 234 条，准确率和原因码准确率 100%，危险漏放 0 | 通过固定集 |
| 真实 DeepSeek 复测 | 测试工程师独立执行 | 正式最小请求和地址不出境 | 本轮未执行；开发修复不使用真实客户数据或替代独立复测 | 未执行 |

## 8. 实施结果

- 完成项：`DEF-REAL-AI01-001/002` 开发侧根因修复、回归测试、全量数据库验证和文档同步。
- 未完成项：测试工程师独立复测和正式缺陷关闭；REAL-AI-05 真实模型质量、SSE 性能与五日稳定性。
- 与原方案差异：为阻断客户端 Header 到 Agent 运行记录的完整链路，除 Formatter 外同步收紧了 `X-Trace-Id` 入口。
- 当前状态：开发修复已完成；权威测试结论仍为不通过，等待 002 号报告。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-REAL-AI01-FIX-001 | 地址识别属于纵深防御，不能替代上游结构化最小化；新国家地址格式仍需持续扩充独立样本 | P2 | AIAgent开发工程师Agent、测试工程师Agent | REAL-AI-05 |
| R-REAL-AI01-FIX-002 | 真实 DeepSeek 最小请求、真实日志采集和密钥轮换未在本轮执行 | P1 | 测试工程师Agent、全栈开发工程师Agent | REAL-AI-05 / REAL-FS-05 |
| R-REAL-AI01-FIX-003 | 公开 AI、翻译、营销、自动回复仍受既有生产门禁限制 | P1 | 架构师Agent | 最终生产放行 |

## 10. 交接事项

- 交接给：测试工程师Agent、全栈开发工程师Agent、架构师Agent。
- 后续任务：生成 `Phase4-P4-00-AIAgent开发工程师Agent-M04-DeepSeekProvider生产加固-综合测试-002.md`，独立复测两个 P1。
- 必须覆盖：中英文地址、楼栋/房间/邮编、历史消息、工具拆分地址、客户端非法/超长/Unicode/控制字符 Trace ID、供应商请求 ID 负向样本、生产 Formatter 和正式 DeepSeek 最小请求。
- 必须注意：测试工程师关闭缺陷和架构师放行前，`AUTO_REPLY_ENABLED=false`、`AI_TRANSLATION_ENABLED=false`、`AI_MARKETING_ENABLED=false` 保持不变。

## 11. 文档同步

- [x] 已同步接口安全约束。
- [x] 无新增架构决策，继续执行 ADR-004。
- [x] 已同步开发修复状态，未改写测试工程师权威结论。
- [x] 已通知测试工程师独立复测范围。
- [x] 正式测试报告索引将在测试工程师完成 002 号报告后更新。
