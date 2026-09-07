# DeepSeek Provider 二次测试缺陷修复实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 `REAL-AI-01` |
| 模块编号 | M04 |
| 主责 Agent | AIAgent开发工程师Agent |
| 协作 Agent | 架构师Agent、全栈开发工程师Agent、测试工程师Agent |
| 实施状态 | 已完成 |
| 开始日期 | 2026-08-26 |
| 完成日期 | 2026-08-26 |
| 代码位置 | `CRM智能聊天系统/` |

## 2. 需求与依据

- 产品需求：`共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md` 的 AI 智能问答和客户数据保护要求。
- 接口依据：`共享记忆文档/智能客服平台 — 管理端接口文档.md` 第 11.8 节。
- 架构依据：`架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md` 的数据最小化和生产停止条件。
- 任务依据：`AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md` 的 `REAL-AI-01`。
- 测试依据：`测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-DeepSeekProvider生产加固-综合测试-002.md` 的 `DEF-REAL-AI01-001/002`。
- 验收依据：`共享记忆文档/MVP范围与验收标准.md` 的 AI、安全、测试和生产门禁要求。
- 代码规范：`共享记忆文档/代码编写手册.md`。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 关闭常见地址顺序、PO Box、天干门牌和拆分地址字段绕过统一 Provider 输入门禁的问题。
- 关闭连字符正文、地址和 `sk-` 样式值经 `provider_request_id` 进入生产 JSON 日志的问题。
- 保持 DeepSeek JSON Output、错误分类、重试、取消和平台写边界无退化。

### 3.2 实施范围

- `StructuredRequest` 共用的 Prompt 数据最小化函数。
- 工具结果进入模型前的字段允许列表。
- JSON 日志 Trace ID、Agent Run ID 和供应商请求 ID 的字段级契约。
- 对应单元、集成、数据库和固定安全评测回归。

### 3.3 非目标

- 不执行 REAL-AI-02～05 的新功能、真实模型质量评测、SSE 50 客户端压测或五日稳定性。
- 不修改 Prompt 版本、模型选择、数据库迁移、外部平台接口或生产功能开关。
- 不替代测试工程师关闭正式缺陷或架构师执行生产放行。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单。
- [x] 已读取 PRD、接口、任务拆解、团队职责、验收标准和最新测试结论。
- [x] 已读取代码编写手册、全部适用 `AGENTS.md` 及 Agent、Python、安全和 TDD Skill。
- [x] 已确认任务边界为 Phase4 / P4-00 / REAL-AI-01 / M04。
- [x] 已用独立报告样本完成 TDD 红灯，修复前为 14 failed、94 passed。

## 5. 实施方案

### 5.1 方案说明

地址格式无法用封闭正则枚举，因此把现有地址正则降为识别和纵深防御：命中明确标签、中文住宅组成、英文街道门牌、PO Box 或两个以上结构化地址组成字段时，整个模型用户 Prompt 只保留固定 `[ADDRESS]` 标记。这样不会因局部替换顺序留下可复原片段。

工具结果不再依靠地址字段黑名单。模型输入只保留 `TOOL_OUTPUT_SCHEMAS` 已声明的字段，契约外地址别名和平台原始字段直接丢弃。生产日志按字段处理：Trace ID 和 Agent Run ID 仅接受 UUID；供应商请求 ID 始终转换为 SHA-256 摘要；其余低敏元数据继续使用有限 ASCII 和长度门禁。

### 5.2 依赖关系

- 前置依赖：ADR-004、现有 `StructuredRequest`、工具强类型输出 Schema、`JsonFormatter` 和 002 号正式复测报告。
- 后续依赖：测试工程师第三次独立复测；REAL-AI-05 真实模型质量和稳定性评测。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 高风险地址上下文整段最小化 | 模型丢失该轮详细语义 | 地址修改属于高风险业务，优先失败关闭并由受控工具或人工处理 |
| 工具新增安全字段未进入模型 | 新工具能力暂不可见 | 新字段必须先加入强类型输出 Schema 并完成 AI 安全评审 |
| 供应商原始请求 ID 不再可直接检索 | 运维关联方式变化 | 使用稳定 SHA-256 摘要关联，同一原值仍可重复匹配 |
| 正式缺陷尚未独立关闭 | 不能生产放行 | 所有公开 AI、翻译、营销和自动回复开关继续关闭 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `CRM智能聊天系统/backend/app/agent/security.py` | 修改 | 增加高风险地址上下文识别和整段最小化 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/workflow_prompt.py` | 修改 | 工具结果按强类型输出 Schema 字段允许列表序列化 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/shared/logging/setup.py` | 修改 | UUID 字段校验和供应商请求 ID 摘要化 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/main.py` | 修改 | 仅沿用规范小写连字符 UUID，其他 Trace ID 重新生成 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_agent_domain.py` | 修改 | 增加中文/英文地址变体及拆分 JSON 最终边界测试 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_agent_tool_execution.py` | 修改 | 增加契约外地址别名被丢弃测试 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_real_runtime_config.py` | 修改 | 增加供应商 ID 摘要和非 UUID Trace ID 测试 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_agent_providers.py` | 修改 | 更新 DeepSeek 生产日志请求 ID 摘要契约测试 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_health.py` | 修改 | 增加非规范 UUID Header 被替换的端到端测试 | AIAgent开发工程师Agent |
| `共享记忆文档/智能客服平台 — 管理端接口文档.md` | 修改 | 同步 Provider 数据边界和日志字段级契约 | AIAgent开发工程师Agent |
| `AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md` | 修改 | 同步 REAL-AI-01 当前开发状态 | AIAgent开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：请求体、响应 JSON 和路径无变化。
- 数据库：无迁移、表、字段或索引变化；验证 head 为 `019_tiktok_channel_unique`。
- 配置项：无新增或修改。
- AI：模型、Prompt、RAG、工具选择和阈值不变；仅收紧模型输入和日志出口。

### 6.3 关键实现说明

- `StructuredRequest` 仍是所有外部 Provider 的共同最终边界；高风险地址命中后不再尝试保留局部文本。
- 工具字段允许列表直接复用现有 Pydantic 输出 Schema，没有新增第二套工具字段配置。
- `provider_request_id` 仅在生产 Formatter 输出阶段摘要化，Provider 内部结果类型保持兼容。
- 没有新增第三方依赖、数据库结构或生产开关。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| TDD 红灯 | 聚焦缺陷测试 | 独立变形样本稳定失败 | 首轮 14 failed、94 passed；边界复核继续得到 1 failed 和 2 failed | 通过 |
| 修复后聚焦 | `python -m pytest` 五个聚焦测试文件 | 全部通过 | 113 passed、1 个既有 warning | 通过 |
| Ruff | `ruff check app ...` | 无问题 | All checks passed | 通过 |
| 格式 | `ruff format --check app ...` | 无漂移 | 153 files already formatted | 通过 |
| mypy | `mypy app scripts` | 无类型问题 | 155 个源文件无问题 | 通过 |
| 编译 | `python -m compileall -q app scripts` | 编译成功 | 无错误 | 通过 |
| 默认后端全量 | `pytest -q --basetemp=...` | 非数据库测试通过 | 579 passed、10 skipped、2 个既有 warning | 通过 |
| 隔离 PostgreSQL 全量 | 临时 pgvector PostgreSQL 16 + `TEST_DATABASE_URL` | 无跳过完整回归 | 589 passed、0 skipped、2 个既有 warning | 通过 |
| 迁移可逆性 | `019 → 018 → 019` | 可回滚并恢复 | 最终 `019_tiktok_channel_unique (head)` | 通过 |
| 固定安全评测 | `scripts.evaluate_phase4` | 无危险漏放 | 234 条，准确率和原因码准确率 100%，危险漏放 0 | 通过 |
| 锁文件 | `uv lock --check` | 无漂移 | 125 packages resolved | 通过 |
| 依赖审计 | `uv audit --locked` | 无已知漏洞 | 124 个包无已知漏洞和不良状态 | 通过 |
| 真实 DeepSeek | 真实最小请求 | REAL-AI-05 独立执行 | 本轮未执行 | 未执行 |

两个 warning 为既有 Starlette TestClient/httpx 和 argon2 版本元数据弃用提示。本轮首次默认全量因系统临时目录访问被拒在 pytest 清理阶段退出，随后使用仓库内独立 `--basetemp` 重跑并通过；该环境事件不计为产品缺陷。

## 8. 实施结果

- 完成项：两个 P1 的第二轮开发侧根因修复、独立样本回归、静态质量、数据库全量、迁移、固定评测和依赖审计。
- 未完成项：测试工程师第三次独立复测；REAL-AI-05 真实模型质量、SSE 性能和五日稳定性。
- 与原方案差异：地址处理从“匹配后局部替换”收紧为“高风险上下文整段最小化”；供应商请求 ID 从有限 ASCII 原值改为稳定摘要。
- 当前状态：开发实施完成；权威测试结论仍以 002 号报告的“不通过”状态为准，直至新的正式报告关闭缺陷。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-REAL-AI01-003-001 | 正式缺陷尚未由测试工程师第三次独立复测关闭 | P1 | 测试工程师Agent | REAL-AI-01 |
| R-REAL-AI01-003-002 | 真实 DeepSeek 质量、可用性和成本未在本轮验证 | P1 | AIAgent开发工程师Agent、测试工程师Agent | REAL-AI-05 |
| R-REAL-AI01-003-003 | SSE 50 客户端和五日稳定性尚未执行 | P1 | 全栈开发工程师Agent、测试工程师Agent | Phase4 联合门禁 |

## 10. 交接事项

- 交接给：测试工程师Agent、架构师Agent、全栈开发工程师Agent。
- 后续任务：对 002 号报告的四类地址变体、拆分字段别名和三类供应商请求 ID 执行第三次独立复测。
- 必须注意：测试时应直接检查最终 `StructuredRequest`、工具 Prompt 和真实 `JsonFormatter` 输出，不仅检查上游调用方。
- 生产门禁：`AUTO_REPLY_ENABLED=false`、`AI_TRANSLATION_ENABLED=false`、`AI_MARKETING_ENABLED=false` 保持不变。

## 11. 文档同步

- [x] 已同步接口数据与日志边界。
- [x] 无新增架构决策，继续执行 ADR-004。
- [x] 已同步 REAL-AI-01 开发状态和实施记录索引。
- [x] 已明确测试工程师第三次独立复测范围。
- [x] 未改写测试报告索引中的当前权威失败结论。
