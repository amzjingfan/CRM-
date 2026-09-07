# DeepSeek Provider 第三次测试缺陷修复实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 `REAL-AI-01` |
| 模块编号 | M04 |
| 主责 Agent | AIAgent开发工程师Agent |
| 协作 Agent | 全栈开发工程师Agent、架构师Agent、测试工程师Agent |
| 实施状态 | 已完成 |
| 开始日期 | 2026-08-26 |
| 完成日期 | 2026-08-26 |
| 代码位置 | `CRM智能聊天系统/` |

## 2. 需求与依据

- 产品需求：`共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md` 的 AI 智能问答与客户隐私要求。
- 接口依据：`共享记忆文档/智能客服平台 — 管理端接口文档.md` 第 11.8 节。
- 架构依据：`架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md` 的数据最小化、低敏日志和停止条件。
- 任务依据：`AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md` 的 `REAL-AI-01`。
- 测试依据：`测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-DeepSeekProvider生产加固-综合测试-003.md` 的 `DEF-REAL-AI01-001/003/004`。
- 历史上下文：用户所附 `Phase4-P4-00-AIAgent开发工程师Agent-M04-回复翻译营销与评测闭环-综合测试-001.md` 仅作为旧版 M04 证据，不覆盖上述直接测试基线。
- 验收依据：`共享记忆文档/MVP范围与验收标准.md` 的 AI、安全、测试和生产门禁。
- 代码规范：`共享记忆文档/代码编写手册.md`。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 阻断香港地址、英文拼写门牌和 Rural Route 完整地址进入外部 Provider。
- 保留消费券、商品规格、物流中转站和商品系列等合法业务语义。
- 在不放宽 UUID-only 日志门禁的前提下恢复应用、Webhook、营销和 Worker 的 Trace ID 关联能力。

### 3.2 实施范围

- `StructuredRequest` 共用的最终 Prompt 数据最小化规则。
- 应用生命周期、请求异常、Webhook、营销、Jobs Worker、Webhook Worker 和 Agent Worker 的 Trace ID 生产者。
- 003 号报告正例、负例和跨模块生产者回归测试。

### 3.3 非目标

- 不修改 DeepSeek API 契约、Provider 错误分类、Prompt 版本、模型、数据库或生产开关。
- 不执行 REAL-AI-02～05、真实模型质量评测、SSE 50 客户端压测或五日稳定性。
- 不替代测试工程师关闭正式缺陷，也不替代架构师和产品负责人生产放行。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单及最新测试报告索引。
- [x] 已读取 PRD、接口、任务拆解、团队职责、验收标准和 003 号权威报告。
- [x] 已读取代码编写手册、全部适用 `AGENTS.md` 及 Agent、Python、安全、独立验证和 TDD Skill。
- [x] 已确认任务边界为 Phase4 / P4-00 / REAL-AI-01 / M04。
- [x] 已用 003 号报告正反样本完成 TDD 红灯，修复前为 14 failed、73 passed。

## 5. 实施方案

### 5.1 方案说明

地址边界继续使用项目现有的零依赖最终脱敏入口，但不再扩大“地区词 + 任意数字 + 号”规则。明确地址标签和寄送语境直接失败关闭；道路门牌增加香港常见“道”；英文寄送语境支持 `send it to`，并补充拼写门牌和 Rural Route。住宅规则只在存在小区/公寓等住宅载体且后续出现楼栋、单元、楼层或房间组成时判定，避免抹除普通业务编号。

日志出口保持标准 UUID 校验和供应商请求 ID 摘要不变。内部生产者改为生成 UUID，Webhook 和营销业务运行直接复用事件 UUID；进程级启动和 Worker 使用单次随机 UUID，语义写入受控 `event` 字段。

### 5.2 依赖关系

- 前置依赖：ADR-004、现有 `StructuredRequest`、`JsonFormatter`、003 号正式测试报告。
- 后续依赖：测试工程师第四次独立复测；REAL-AI-02～05 和联合生产门禁。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 自由文本地址形式仍可能出现新变体 | 可能造成隐私出境 | 明确地址/寄送语境失败关闭，保留最终 Provider 边界和独立变形复测 |
| 地址高召回规则误伤业务语义 | 意图识别质量下降 | 正例与消费券、规格、中转站负例成对测试，不使用宽泛地区数字规则 |
| Trace ID 生产者迁移影响跨模块关联 | 日志难以追踪 | 事件 UUID 直接作为 Trace ID，业务语义保留在 `event`，全量回归覆盖跨模块代码 |
| 当前正式报告仍不通过 | 不能生产放行 | 公开 AI、翻译、营销和自动回复继续关闭，等待独立复测 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `CRM智能聊天系统/backend/app/agent/security.py` | 修改 | 补充国际地址和寄送语境，收窄中文住宅误杀规则 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/main.py` | 修改 | 生命周期、校验和内部异常使用 UUID Trace ID 与受控事件 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/integrations/service.py` | 修改 | Webhook Agent 任务复用事件 UUID | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/integrations/worker.py` | 修改 | Webhook Worker 使用进程级 UUID 与受控事件 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/jobs/worker.py` | 修改 | Jobs Worker 使用进程级 UUID 与受控事件 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/chat/worker.py` | 修改 | Agent Worker 使用进程级 UUID 与受控事件 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/marketing/worker.py` | 修改 | 营销生成与写工具复用营销事件 UUID | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_agent_domain.py` | 修改 | 增加 003 地址正例与合法业务负例 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_real_runtime_config.py` | 修改 | 增加旧式非 UUID Trace 生产者回归门禁 | AIAgent开发工程师Agent |
| `共享记忆文档/智能客服平台 — 管理端接口文档.md` | 修改 | 同步地址与内部追踪边界 | AIAgent开发工程师Agent |
| `AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md` | 修改 | 同步第三轮开发修复状态 | AIAgent开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：路径、请求体、响应 JSON 和错误码无变化。
- 数据库：无迁移、表、字段或索引变化；当前 head 为 `019_tiktok_channel_unique`。
- 配置项：无新增或修改。
- AI：模型、Prompt、RAG、工具选择和阈值不变；仅修复外部模型输入和低敏追踪边界。

### 6.3 关键实现说明

- 地址判断以明确寄送语境和结构组成为主，不把单个地区词或“数字 + 号”视为完整地址。
- `provider_request_id` 摘要化、UUID-only Formatter 和客户端 Trace ID 重生成规则保持不变，避免回退已关闭的 `DEF-REAL-AI01-002`。
- Webhook/营销事件本身已经是 UUID，直接复用比新增映射表更简单，且保留事件到 Agent/工具日志的关联能力。
- 未新增第三方依赖、数据库结构、模型调用或平台写操作。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| TDD 红灯 | 地址正反例与 Trace 生产者聚焦测试 | 003 缺陷可复现 | 14 failed、73 passed | 通过 |
| 修复后最终聚焦 | 相同两文件聚焦测试（含新增合法寄送语境负例） | 全部通过 | 89 passed | 通过 |
| Provider/安全聚焦 | 五个 Provider、安全、工具、配置和健康测试文件 | 全部通过 | 148 passed、1 个既有 warning | 通过 |
| Ruff | `uv run ruff check app migrations scripts tests` | 无问题 | All checks passed | 通过 |
| 格式 | `uv run ruff format --check app migrations scripts tests` | 无漂移 | 208 files already formatted | 通过 |
| mypy | `uv run mypy app scripts` | 无类型问题 | 155 个源文件无问题 | 通过 |
| 编译 | `uv run python -m compileall -q app scripts` | 编译成功 | 无错误 | 通过 |
| 默认后端全量 | `uv run pytest -q` | 非数据库测试通过 | 620 passed、10 skipped、2 个既有 warning | 通过 |
| 隔离 PostgreSQL 全量 | 临时 pgvector PostgreSQL 16 + `TEST_DATABASE_URL` | 无跳过完整回归 | 630 passed、0 skipped、2 个既有 warning | 通过 |
| 空库迁移 | `uv run alembic upgrade head` | `001→019` 成功 | 成功 | 通过 |
| 当前迁移可逆性 | `019→018→019` | 可回滚并恢复 | 最终 `019_tiktok_channel_unique (head)` | 通过 |
| 固定安全评测 | `scripts.evaluate_phase4` | 无危险漏放 | 234 条，准确率和原因码准确率 100%，危险漏放 0 | 通过 |
| 锁文件 | `uv lock --check` | 无漂移 | 125 packages resolved | 通过 |
| 依赖审计 | `uv audit --locked` | 无已知漏洞 | 124 个包无已知漏洞和不良状态 | 通过 |
| 真实 DeepSeek | 真实最小请求 | 不重复消费外部模型 | 本轮未执行；003 号报告已在同日对前序快照完成一次合成非流式冒烟 | 未执行 |

数据库全量首次在未迁移空库运行时得到 10 项 `stores` 不存在失败；执行正式 Alembic 全量升级并补齐两项合法寄送语境负例后，最终代码快照以 630 项、0 跳过通过。随后完成 `019 → 018 → 019` 回滚恢复，最终版本为 `019_tiktok_channel_unique (head)`。两个 warning 为既有 Starlette TestClient/httpx 和 argon2 元数据弃用提示。

## 8. 实施结果

- 完成项：003 报告三个开放缺陷的开发侧修复、正反样本回归、静态质量、数据库全量、迁移、固定评测和依赖审计。
- 未完成项：测试工程师第四次独立复测；REAL-AI-02～05、真实 SSE 性能和五日稳定性。
- 与原方案差异：无 API、数据库或 Provider 行为扩展；只修复最新地址识别与跨模块追踪兼容性。
- 当前状态：开发实施完成；正式权威状态继续保持 003 号报告“不通过”，不得由本实施记录自行关闭缺陷。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-REAL-AI01-004-001 | `DEF-REAL-AI01-001/003/004` 尚未由测试工程师第四次独立复测 | P1 | 测试工程师Agent | REAL-AI-01 |
| R-REAL-AI01-004-002 | 项目仍无 Git/签名制品级不可变审查目标 | P2 | 架构师Agent、全栈开发工程师Agent | 生产发布基线 |
| R-REAL-AI01-004-003 | 真实 DeepSeek 质量、SSE 50 客户端和五日稳定性未在本轮执行 | P1 | AIAgent开发工程师Agent、全栈开发工程师Agent、测试工程师Agent | REAL-AI-05/联合门禁 |

## 10. 交接事项

- 交接给：测试工程师Agent、架构师Agent、全栈开发工程师Agent。
- 后续任务：使用未进入开发测试的新国际地址正例、合法业务负例和跨模块日志链路执行第四次独立复测。
- 必须注意：复测应直接检查最终 `StructuredRequest` 和生产 `JsonFormatter`，并确认 Webhook/营销/各 Worker 的 Trace ID 可关联且不泄漏原始正文。
- 生产门禁：公开回复、翻译、营销内容、自动回复和真实高风险写操作继续关闭。

## 11. 文档同步

- [x] 已同步接口数据与日志边界。
- [x] 无新增架构决策，继续执行 ADR-004。
- [x] 已同步 REAL-AI-01 开发状态和实施记录索引。
- [x] 已明确测试工程师第四次独立复测范围。
- [x] 未修改测试报告索引，继续保留 003 号正式失败结论。
