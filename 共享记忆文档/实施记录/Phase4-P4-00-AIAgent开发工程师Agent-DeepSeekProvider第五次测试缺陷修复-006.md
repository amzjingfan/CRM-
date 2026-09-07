# DeepSeek Provider 第五次测试缺陷修复实施记录

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

- 产品需求：`共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md` 的 AI 客服和客户隐私边界。
- 接口依据：`共享记忆文档/智能客服平台 — 管理端接口文档.md` 的 11.8～11.9 节。
- 架构依据：`架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`。
- 任务依据：`AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md` 的 `REAL-AI-01`。
- 测试依据：`测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-DeepSeekProvider生产加固-综合测试-005.md` 的 `DEF-REAL-AI01-001/003`。
- 验收依据：`共享记忆文档/MVP范围与验收标准.md` 的 AI、安全、测试和生产门禁。
- 代码规范：`共享记忆文档/代码编写手册.md`。
- 用户所附回复、翻译、营销报告只作为历史上下文，不替代 005 号 REAL-AI-01 最新权威结论。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 不再把“未命中已知国家地址正则”当作允许外发证明。
- 将自由文本安全结论建模为 `allowed | blocked | uncertain`，未知或低置信度定位文本失败关闭。
- 保留合法业务正文供本地转人工，避免把 SKU、仓位和活动文本静默折叠为地址标记。
- 在外部 SDK 调用前统一拒绝 `blocked/uncertain`，并提供不含客户正文的可观测原因码。

### 3.2 实施范围

- `app/agent/security.py` 的版本化本地 DLP、结构化 JSON 递归检查和三态结果。
- `StructuredRequest` 的最终状态、策略版本和统一外发门禁。
- DeepSeek、OpenAI 和 Anthropic Provider 的 SDK 前置门禁。
- 生产日志低敏字段白名单及 005 正反例、未知语言和 SDK 零调用回归。

### 3.3 非目标

- 不修改 Prompt、模型选择、公开 API、数据库、生产开关或平台写操作。
- 不实施 `REAL-AI-02～05`、真实模型质量评测、SSE 50 客户端或五日稳定性。
- 不由开发 Agent 关闭测试工程师登记的缺陷，也不替代架构师和产品负责人生产放行。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单。
- [x] 已读取 PRD、接口、任务拆解、团队职责、验收标准和 005 号权威报告。
- [x] 已读取全部适用 `AGENTS.md`、代码编写手册及 Agent、Python、TDD、安全、可观测性和独立验证 Skill。
- [x] 已确认 Phase4、P4-00、M04 和主责 Agent。
- [x] 已确认真实客户地址禁止出境、失败关闭、独立复测和人工放行边界。

## 5. 实施方案

### 5.1 方案说明

- 引入 `prompt-dlp-v1.0.0` 和三态 `PromptSafetyDecision`。已确认完整地址为 `blocked`；位置与业务语义冲突、未知文字系统或低置信度地址形态为 `uncertain`；其余经确定性标识脱敏后才为 `allowed`。
- 对带前缀 JSON Prompt 解析尾部 JSON，递归检查字段名、列表和字符串值；结构化地址字段默认拒绝，防止 JSON 包装绕过边界。
- `blocked` 使用固定地址标记；`uncertain` 保留经邮箱、电话和长标识脱敏后的正文，只供本地人工接管，不进入供应商。
- 上游已替换成 `[ADDRESS]` 的内容在最终请求边界继续保持 `blocked`，不会因原文消失而恢复为 `allowed`。
- `StructuredRequest.ensure_safe_for_external_provider()` 是所有 Provider 的共同外发门禁；DeepSeek、OpenAI 和 Anthropic 均在 SDK 调用前执行。
- 门禁命中记录策略版本、状态、原因码和 UUID Trace ID，不记录 Prompt 或客户正文。

### 5.2 依赖关系

- 前置依赖：005 号测试报告、现有 `StructuredRequest`、三类 Provider、`JsonFormatter` 和既有 `LLM_REFUSAL` 人工接管语义。
- 后续依赖：测试工程师第六次独立复测、架构师数据最小化复核、`REAL-AI-02～05` 和联合生产门禁。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 地址格式属于开放集合 | 新语言或新排版可能绕过已知格式 | 未知文字系统、无门牌地址和低置信度定位形态进入 `uncertain`，默认拒绝外发 |
| 高召回门禁误伤业务语义 | AI 建议减少 | 业务歧义不静默替换，保留低敏正文并转人工；公开 AI 开关继续关闭 |
| 调用方绕过预处理 | 客户隐私出境 | Provider SDK 前强制检查 `StructuredRequest` 三态，三类 Provider 均失败关闭 |
| 安全日志形成泄漏副本 | Prompt 或地址进入日志 | 日志字段固定允许列表，仅保存策略版本、枚举状态和原因码 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `CRM智能聊天系统/backend/app/agent/security.py` | 修改 | 新增版本化三态 DLP、未知语言/低置信度失败关闭和 JSON 递归检查 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/providers/base.py` | 修改 | 保存门禁状态/原因/版本并统一拒绝非 allowed 请求 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/providers/deepseek_provider.py` | 修改 | DeepSeek SDK 前执行共同门禁 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/providers/openai_provider.py` | 修改 | OpenAI SDK 前执行共同门禁 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/providers/anthropic_provider.py` | 修改 | Anthropic SDK 前执行共同门禁 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/shared/logging/setup.py` | 修改 | 允许输出三项低敏门禁元数据 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_agent_domain.py` | 修改 | 覆盖 005 地址、业务负例、未知文字和结构化 JSON | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_agent_providers.py` | 修改 | 验证非 allowed 请求零 SDK 调用和日志无正文 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/README.md` | 修改 | 同步三态门禁运行契约 | AIAgent开发工程师Agent |
| `AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md` | 修改 | 同步 005 权威结论和第五轮开发修复状态 | AIAgent开发工程师Agent |
| `共享记忆文档/智能客服平台 — 管理端接口文档.md` | 修改 | 增加 11.9 内部 Provider 数据边界增量 | AIAgent开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：无公开路径、请求体、响应体或错误码变化；内部 Provider 继续使用 `LLM_REFUSAL`。
- 数据库：无迁移、表、字段或索引变化；验证 head 为 `019_tiktok_channel_unique`。
- 配置项：无新增；未读取、输出或保存真实密钥。
- AI：新增内部策略版本 `prompt-dlp-v1.0.0`；不改变模型、Prompt 或输出 Schema。

### 6.3 关键实现说明

- 地址明确命中时整段阻断；地址与业务词冲突时不做危险二选一，而是以 `uncertain` 交给本地人工路径。
- 未知文字系统使用 Unicode 名称的“受支持文字允许集合”判断，不再逐一枚举所有未知文字块。
- JSON 仅在可完整解析时按结构检查；解析失败则回到自由文本低置信度门禁，不因格式异常放行。
- Provider 门禁异常不可重试，避免备用供应商成为绕过路径；现有工作流将其视为模型拒绝并失败关闭。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| TDD 红灯 | 新增 005 正反例和 Provider 零调用测试 | 现有代码不能提供三态门禁 | 首次收集因缺少新类型失败；分步实现后仍有 2 个地址用例失败 | 通过 |
| 005/Provider 聚焦 | 六个 Provider、安全、工具、配置、健康和评测文件 | 全部通过 | 193 passed、1 个既有 warning | 通过 |
| Ruff | `uv run ruff check app scripts tests migrations` | 无问题 | All checks passed | 通过 |
| Ruff Format | `uv run ruff format --check app scripts tests migrations` | 无差异 | 208 files already formatted | 通过 |
| mypy | `uv run mypy app scripts` | 无类型错误 | 155 个源文件无错误 | 通过 |
| 编译 | `uv run python -m compileall -q app scripts` | 编译成功 | 无错误 | 通过 |
| 默认后端全量 | `uv run pytest -q --basetemp .tmp/pytest-ai01-006-default-postmarker` | 非数据库测试通过 | 662 passed、10 skipped、2 个既有 warning | 通过 |
| 隔离 PostgreSQL 全量 | 临时 pgvector PostgreSQL 16 + `TEST_DATABASE_URL` | 无跳过完整回归 | 671 passed、0 skipped、2 个既有 warning | 通过 |
| 固定安全评测 | `scripts/evaluate_phase4.py` | 无危险漏放 | 234 条，准确率和原因码准确率 100%，危险漏放 0 | 通过 |
| 锁文件 | `uv lock --check` | 可复现解析 | 125 个包 | 通过 |
| 依赖审计 | `uv audit --locked` | 无已知漏洞 | 124 个包无已知漏洞或不良状态 | 通过 |
| 空库迁移 | `uv run alembic upgrade head` | 001→019 | 成功 | 通过 |
| 迁移可逆性 | `019 → 018 → 019` | 恢复 head | `019_tiktok_channel_unique (head)` | 通过 |

两个 warning 为既有 Starlette TestClient/httpx 和 argon2 元数据弃用提示。`ruff format --check .` 会扫描两个 2026-08-24 遗留且当前进程无访问权的 pytest 临时目录并触发 Ruff 崩溃，因此按正式代码范围显式检查 `app/scripts/tests/migrations` 并通过。真实 DeepSeek 未重复调用：005 已有一次无客户数据成功冒烟，本轮只增加 SDK 前本地门禁，真实模型质量与性能仍属于 `REAL-AI-05` 和独立复测。

## 8. 实施结果

- 完成项：005 报告两个开放缺陷的开发侧根因修复、三态外发门禁、结构化递归检查、低敏日志和全量验证。
- 未完成项：测试工程师第六次独立复测；架构师最终数据最小化复核；`REAL-AI-02～05`、真实 SSE 性能和五日稳定性。
- 与原方案差异：无公开 API 和数据库变化；内部 Provider 请求增加安全状态、原因码和策略版本。
- 当前状态：开发实施完成；正式权威状态仍以 005 号报告“不通过”为准，本记录不关闭 `DEF-REAL-AI01-001/003`。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-REAL-AI01-006-001 | `DEF-REAL-AI01-001/003` 尚未由测试工程师第六次独立复测 | P1 | 测试工程师Agent | REAL-AI-01 |
| R-REAL-AI01-006-002 | 无 Git/签名制品，无法建立不可变独立验证目标 | P2 | 架构师Agent、全栈开发工程师Agent | 生产发布基线 |
| R-REAL-AI01-006-003 | 三态门禁对未知文本会主动降级，需在真实质量评测中统计转人工率 | P2 | AIAgent开发工程师Agent、测试工程师Agent | REAL-AI-05 |
| R-REAL-AI01-006-004 | 真实模型质量、SSE 50 客户端和五日稳定性未执行 | P1 | AIAgent开发工程师Agent、全栈开发工程师Agent、测试工程师Agent | REAL-AI-05/联合门禁 |

## 10. 交接事项

- 交接给：测试工程师Agent、架构师Agent、全栈开发工程师Agent。
- 后续任务：使用未进入开发测试的新文字系统、无门牌/无邮编地址、嵌套 JSON、业务歧义句和三类 Provider 客户端替身执行第六次独立复测。
- 必须注意：直接断言 `blocked/uncertain` 时外部 SDK 零调用，并检查生产 Formatter 只保留策略版本、状态和原因码；不得将开发测试自证视为正式关闭。

## 11. 文档同步

- [x] 已同步接口数据边界。
- [x] 架构边界未扩张，无新增 ADR；保留架构师最终数据最小化复核。
- [x] 已同步 REAL-AI-01 开发状态和实施记录索引。
- [x] 已通知测试工程师第六次独立复测范围。
- [x] 未修改测试报告索引，继续保留 005 号正式失败结论。
