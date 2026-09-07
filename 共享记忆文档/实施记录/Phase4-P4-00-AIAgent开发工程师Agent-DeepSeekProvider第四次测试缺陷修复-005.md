# DeepSeek Provider 第四次测试缺陷修复实施记录

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
| 代码位置 | `CRM智能聊天系统/backend/` |

## 2. 需求与依据

- 产品需求：`共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md` 的 AI 客服与隐私边界。
- 接口依据：`共享记忆文档/智能客服平台 — 管理端接口文档.md` 的 11.8 节。
- 架构依据：`架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`。
- 任务依据：`AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md` 的 `REAL-AI-01`。
- 测试依据：`测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-DeepSeekProvider生产加固-综合测试-004.md` 的 `DEF-REAL-AI01-001/003/004`。
- 验收依据：`共享记忆文档/MVP范围与验收标准.md` 的 AI、安全、测试和生产门禁。
- 代码规范：`共享记忆文档/代码编写手册.md`。
- 用户所附 `Phase4-P4-00-AIAgent开发工程师Agent-M04-回复翻译营销与评测闭环-综合测试-001.md` 仅作为历史上下文，不替代 004 号直接复测基线。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 屏蔽 004 报告中的欧洲、香港和日本无标签完整地址。
- 保留含数字的客服层级、订单人工复核、队列和工单语义。
- 让真实意图评测入口使用生产日志可接受的规范 UUID Trace ID。

### 3.2 实施范围

- `StructuredRequest` 共用的最终自由文本脱敏边界。
- 真实意图评测脚本的 Trace ID 生成。
- 地址正反例、Trace ID 和生产日志格式化回归测试。

### 3.3 非目标

- 不修改 DeepSeek API 契约、Prompt、模型、数据库或生产开关。
- 不执行 `REAL-AI-02～05`、真实模型质量评测、SSE 50 客户端压测或五日稳定性。
- 不自行关闭测试工程师登记的缺陷，不代替架构师和产品负责人生产放行。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单。
- [x] 已读取 PRD、接口、任务拆解、团队职责、验收标准和 004 号权威报告。
- [x] 已读取全部适用 `AGENTS.md`、代码编写手册及 Agent、Python、测试、安全、可观测性 Skill。
- [x] 已确认 Phase4、P4-00、M04 和主责 Agent。
- [x] 已确认高风险隐私边界、独立复测和人工放行要求。

## 5. 实施方案

### 5.1 方案说明

- 地址失败关闭不枚举具体城市名称，而要求多个地址组成证据：门牌与邮编、住宅单元与楼座、日本行政区与丁目门牌链。
- 明确寄送语境不再把任意数字视为地址证据，只有道路、邮政信箱或住宅组成才触发整段屏蔽。
- 真实评测按合成 `case_id` 生成稳定 UUID5；`case_id` 继续作为独立低敏结果字段，不拼入 Trace ID。
- 结构化地址字段允许列表和 Provider 最终二次脱敏继续保留，形成纵深防御。

### 5.2 依赖关系

- 前置依赖：现有 `StructuredRequest`、`sanitize_prompt_text`、`JsonFormatter` 和 004 号正式测试报告。
- 后续依赖：测试工程师第五次独立复测、`REAL-AI-02～05` 和联合生产门禁。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 自由文本地址格式不存在封闭集合 | 新变体可能造成隐私出境 | 使用多组成证据、结构化字段屏蔽和 Provider 最终边界；继续独立变形复测 |
| 高召回地址规则误伤业务数字 | 意图和翻译质量下降 | 正例与客服层级、订单、队列、工单、版本和规格负例成对测试 |
| 评测 Trace ID 泄漏 case 语义 | 日志隐私与关联冲突 | UUID5 只承载关联，低敏 case_id 单独保存在评测结果 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `CRM智能聊天系统/backend/app/agent/security.py` | 修改 | 增加多证据裸地址失败关闭并收窄寄送语境 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/scripts/evaluate_intents.py` | 修改 | 使用稳定 UUID5 生成真实评测 Trace ID | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_agent_domain.py` | 修改 | 增加国际地址正例和业务数字负例 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_agent_evaluation.py` | 修改 | 验证评测 UUID 稳定性及生产 Formatter 兼容性 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_real_runtime_config.py` | 修改 | 禁止真实评测恢复 `live-eval-*` Trace ID | AIAgent开发工程师Agent |
| `AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md` | 修改 | 同步第四轮开发修复状态 | AIAgent开发工程师Agent |
| `共享记忆文档/智能客服平台 — 管理端接口文档.md` | 修改 | 同步 Provider 数据边界与 Trace 契约 | AIAgent开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：无路径、请求体、响应结构或错误码变化。
- 数据库：无迁移、表、字段或索引变化；验证 head 为 `019_tiktok_channel_unique`。
- 配置项：无新增或修改；未读取、输出或保存真实密钥。
- AI：不改变 Provider、模型、Prompt 或输出 Schema；只收紧模型输入隐私边界和评测追踪格式。

### 6.3 关键实现说明

- 客户文本在 Prompt 构造阶段脱敏，`StructuredRequest.__post_init__` 继续在所有外部 Provider 前执行第二次门禁。
- 多地址组成证据比“寄送动词后出现任意数字”更能区分真实位置和普通客服路由。
- UUID5 输入仅为版本化合成样本编号，不包含客户原文、Prompt、模型输出或密钥。
- 未新增依赖、并行 Provider、数据库结构或平台写操作。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| TDD 红灯 | 两个缺陷测试文件 | 004 缺陷可复现 | 11 failed、91 passed | 通过 |
| 修复聚焦 | 地址、运行配置和评测测试 | 全部通过 | 107 passed | 通过 |
| Provider/安全聚焦 | 六个 Provider、安全、工具、配置、健康和评测文件 | 全部通过 | 166 passed、1 个既有 warning | 通过 |
| Ruff | `uv run ruff check app migrations scripts tests` | 无问题 | All checks passed | 通过 |
| Ruff Format | `uv run ruff format --check app migrations scripts tests` | 无差异 | 208 files already formatted | 通过 |
| mypy | `uv run mypy app scripts` | 无类型错误 | 155 个源文件无错误 | 通过 |
| 编译 | `uv run python -m compileall -q app scripts` | 编译成功 | 无错误 | 通过 |
| 默认后端全量 | `uv run pytest` | 非数据库测试通过 | 634 passed、10 skipped、2 个既有 warning | 通过 |
| 隔离 PostgreSQL 全量 | 临时 pgvector PostgreSQL 16 + `TEST_DATABASE_URL` | 无跳过完整回归 | 644 passed、0 skipped、2 个既有 warning | 通过 |
| 固定安全评测 | `scripts.evaluate_phase4` | 无危险漏放 | 234 条，准确率 100%，危险漏放 0 | 通过 |
| 锁文件 | `uv lock --check` | 可复现解析 | 125 个包 | 通过 |
| 依赖审计 | `uv audit --locked` | 无已知漏洞 | 124 个包无已知漏洞或不良状态 | 通过 |
| 空库迁移 | `uv run alembic upgrade head` | 001→019 | 成功 | 通过 |
| 迁移可逆性 | `019 → 018 → 019` | 恢复 head | `019_tiktok_channel_unique (head)` | 通过 |

两个 warning 为既有 Starlette TestClient/httpx 和 argon2 元数据弃用提示。真实 DeepSeek 130 条质量评测未执行，因为属于 `REAL-AI-05`，本任务不以一次模型调用替代质量、性能和稳定性门禁。

## 8. 实施结果

- 完成项：004 报告三个开放缺陷的开发侧修复、复现测试、全量回归、数据库、迁移、安全评测和依赖审计。
- 未完成项：测试工程师第五次独立复测；`REAL-AI-02～05`、真实 SSE 性能和五日稳定性。
- 与原方案差异：无 API、数据库和 Provider 契约扩展；仅收紧隐私边界和追踪格式。
- 当前状态：开发实施完成；正式权威状态继续保持 004 号报告“不通过”，本记录不关闭测试缺陷。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-REAL-AI01-005-001 | `DEF-REAL-AI01-001/003/004` 尚未由测试工程师第五次独立复测 | P1 | 测试工程师Agent | REAL-AI-01 |
| R-REAL-AI01-005-002 | 无 Git/签名制品，无法建立不可变独立验证目标 | P2 | 架构师Agent、全栈开发工程师Agent | 生产发布基线 |
| R-REAL-AI01-005-003 | 真实模型质量、SSE 50 客户端和五日稳定性未执行 | P1 | AIAgent开发工程师Agent、全栈开发工程师Agent、测试工程师Agent | REAL-AI-05/联合门禁 |

## 10. 交接事项

- 交接给：测试工程师Agent、架构师Agent、全栈开发工程师Agent。
- 后续任务：使用未进入开发测试的新多语言地址、合法业务数字语句和真实评测日志链路执行第五次独立复测。
- 必须注意：直接检查最终 `StructuredRequest`、生产 `JsonFormatter` 和评测入口；不得把当前开发测试自证视为独立结论。

## 11. 文档同步

- [x] 已同步接口数据边界。
- [x] 架构决策无变化，无需新增 ADR。
- [x] 已同步 REAL-AI-01 开发状态和实施记录索引。
- [x] 已通知测试工程师第五次独立复测范围。
- [x] 未修改测试报告索引，继续保留 004 号正式失败结论。
