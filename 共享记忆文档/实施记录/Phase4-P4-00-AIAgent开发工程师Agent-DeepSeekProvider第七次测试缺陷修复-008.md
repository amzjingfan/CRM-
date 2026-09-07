# DeepSeek Provider 第七次测试缺陷修复实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 `REAL-AI-01` |
| 模块编号 | M04 |
| 主责 Agent | AIAgent开发工程师Agent |
| 协作 Agent | 架构师Agent、全栈开发工程师Agent、测试工程师Agent |
| 实施状态 | 开发修复已完成；待第八次独立复测 |
| 开始日期 | 2026-08-27 |
| 完成日期 | 2026-08-27 |
| 代码位置 | `CRM智能聊天系统/backend/` |

## 2. 需求、边界与依据

- 任务依据：`AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md` 的 `REAL-AI-01`。
- 架构依据：`架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`，外部模型数据出境必须最小化并可立即关闭。
- 最新正式依据：`测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-DeepSeekProvider生产加固-综合测试-007.md`。
- 缺陷范围：`DEF-REAL-AI01-001/005/006`；`DEF-REAL-AI01-002/003/004` 不得回退。
- 实施范围：重复 JSON 键解析、可信控制 DTO 规范化、系统与用户 Prompt 完整信封门禁、开发回归和交接文档。
- 非目标：不实现业务 Prompt 注册表、本地 PII/DLP 模型、真实客户外发、`REAL-AI-02～05`、公开 AI 回复或平台写操作。

## 3. 实施前判断

007 号报告证明正向字段允许列表仍不能单独承担安全边界：默认 JSON 解码会隐藏重复键中的第一份原始值，且所有 Provider 都会发送未被检查的系统 Prompt。该问题位于共同外发边界，必须在 `StructuredRequest` 和标准解析器层一次性失败关闭，不能分别依赖三家 Provider 或继续扩充地址正则。

本轮选择最小可验证方案：不新增依赖或通用 Prompt 注册框架；只保留一个无客户数据的不可变工程控制系统提示作为正向协议。真实业务 Prompt 和动态店铺配置仍不可外发，等待架构师后续批准版本化注册表及本地 DLP 能力。

## 4. 实际变更

| 文件 | 变更 |
| --- | --- |
| `CRM智能聊天系统/backend/app/agent/security.py` | 升级 `prompt-dlp-v1.2.0`；任意层级重复键失败关闭；可信控制 DTO 规范化序列化；增加固定工程系统提示和系统层安全判定 |
| `CRM智能聊天系统/backend/app/agent/providers/base.py` | 同时清洗和合并系统、用户 Prompt 状态；完整信封仅在两者均可信时允许外发 |
| `CRM智能聊天系统/backend/tests/test_agent_domain.py` | 增加重复 operation/schema/nested key、规范化、可信与不可信系统提示回归 |
| `CRM智能聊天系统/backend/tests/test_agent_providers.py` | 验证重复键和系统层敏感文本在 DeepSeek、OpenAI、Anthropic 中均为零 SDK 调用 |
| `CRM智能聊天系统/backend/tests/test_agent_workflow.py` | 分离 Prompt 组合测试与最终外发清洗断言，避免测试替身把未注册系统 Prompt 当作可外发正文 |
| `CRM智能聊天系统/backend/app/agent/README.md` | 同步 v1.2 完整信封协议和业务文本失败关闭边界 |
| `AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md` | 同步 007 号结论、第七轮修复和第八次复测状态 |
| `共享记忆文档/智能客服平台 — 管理端接口文档.md` | 新增 11.11 内部完整信封门禁说明 |

接口与数据差异：无公开 API、数据库迁移、配置、模型或平台工具变化。新增内部稳定原因码 `JSON_DUPLICATE_KEY_REJECTED`、`SYSTEM_PROMPT_SENSITIVE_DATA_DETECTED`、`UNTRUSTED_SYSTEM_PROMPT_REQUIRES_REGISTRY` 和 `TRUSTED_PROMPT_ENVELOPE_ALLOWED`。

## 5. TDD 与验证记录

| 验证项 | 结果 |
| --- | --- |
| TDD 红灯 | 新增聚焦用例 `13 failed`，复现重复键、规范化缺失、系统 Prompt 绕过及三 Provider SDK 进入路径 |
| 新增安全回归 | `13 passed` |
| 安全/Provider 聚焦 | `167 passed` |
| Ruff | `All checks passed` |
| Ruff Format | `187 files already formatted` |
| mypy | 155 个源文件无错误 |
| compileall | 通过 |
| 默认后端全量 | `716 passed, 10 skipped`，2 个既有 warning |
| 隔离 PostgreSQL 全量 | 空库迁移后 `726 passed`，0 skipped，2 个既有 warning |
| 固定安全评测 | 234 条；安全准确率和原因码准确率 100%，危险漏放 0，`live_model_evaluation=false` |
| 锁文件 | 125 个包解析成功 |
| 依赖审计 | 124 个包无已知漏洞或不良状态；首次受沙箱网络限制失败，授权联网后通过 |
| 迁移 | 空库 `001→019`；`019→018→019` 成功，最终 `019_tiktok_channel_unique (head)` |

两个 warning 为既有 Starlette TestClient/httpx 和 argon2 元数据弃用提示。本轮未调用真实 DeepSeek，未发送地址、客户文本或密钥；007 号已有的真实无客户数据控制调用证据未被本轮冒充为新验证。

## 6. 结果、风险与交接

- 开发结果：报告中的重复键和系统 Prompt 绕过已在共同边界复现并修复；三 Provider 对新反例均保持零 SDK 调用。
- 正式状态：007 号报告仍是当前权威结论，`REAL-AI-01` 仍为不通过；开发 Agent 不关闭 `DEF-REAL-AI01-001/005/006`。
- 生产状态：公开回复、生产翻译、AI 营销、自动回复和真实高风险平台写操作继续关闭。
- 可用性风险：除固定工程控制信封外，所有真实业务 Prompt 均失败关闭。恢复外部模型业务调用前，必须完成版本化可信 Prompt 注册、本地 PII/DLP、开放集评测和架构审批。
- 独立性风险：项目不是 Git 仓库，无法冻结提交 SHA、树对象和 diff 哈希；开发侧自测不能称为不可变独立验证。
- 交接给测试工程师：使用未进入开发测试的新重复键变形、系统层动态字段和三类 Trap 客户端进行第八次独立复测，并确认原 `DEF-REAL-AI01-002/003/004` 无回退。

## 7. 规范检查

- [x] 已读取全部适用 `AGENTS.md`、共享记忆、代码编写手册、专项 Skill、计划和 007 号报告。
- [x] 使用测试先行并保留红灯、绿灯、全量、数据库、迁移、固定评测和依赖审计证据。
- [x] 未记录或发送密钥、Token、地址、完整客户文本或 Provider 原始响应。
- [x] 已同步计划、内部接口说明、Agent README 和实施记录索引。
- [x] 未修改 007 号正式测试报告或 `共享记忆文档/测试报告索引.md`。
