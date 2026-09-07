# REAL-AI-04 业务 Prompt 注册缺陷修复实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 `REAL-AI-04` |
| 模块编号 | M04 |
| 主责 Agent | AIAgent开发工程师Agent |
| 协作 Agent | 架构师Agent、全栈开发工程师Agent、测试工程师Agent |
| 实施状态 | 已完成 |
| 开始日期 | 2026-09-05 |
| 完成日期 | 2026-09-05 |
| 代码位置 | `CRM智能聊天系统/` |

“已完成”仅表示 `DEF-REAL-AI04-005` 的开发整改和开发侧验证完成。缺陷正式关闭与生产放行必须由测试工程师递增序号独立报告和架构师门禁确认。

## 2. 需求与依据

- 产品需求：`共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md` 的 AI 回复、翻译和营销草稿边界。
- 接口依据：`共享记忆文档/智能客服平台 — 管理端接口文档.md` 第 11.8～11.18 节。
- 架构依据：`架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`、`架构师/ADR-005-AI-知识语义类型与发布审批边界-v1.0.md`。
- 任务依据：`AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md` 的 `REAL-AI-04`。
- 测试依据：`测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-REAL-AI-04回复翻译营销草稿-综合测试-005.md`。
- 验收依据：`共享记忆文档/MVP范围与验收标准.md` 和 005 号报告的 Provider 最终边界要求。
- 代码规范：`共享记忆文档/代码编写手册.md`。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 让意图、FAQ、工具回复、翻译和营销八类固定业务 Prompt 通过真实 Provider 最终安全边界。
- 保持未知、篡改、错场景、错 Schema 和敏感数据默认拒绝。
- 消除动态店铺配置进入系统 Prompt 的不稳定摘要和注入风险。

### 3.2 实施范围

- 业务 Prompt 注册元数据、Provider 请求场景绑定和业务 JSON 正向协议。
- 八类正式调用点、三类 Provider 的最终 Schema 校验。
- FAQ/工具回复配置的数据层迁移、专项测试和全量回归。

### 3.3 非目标

- 不修改公共 HTTP/SSE API、数据库或环境变量。
- 不调用真实 DeepSeek，不执行 TikTok、工具或平台写操作。
- 不处理 `.env` 价格配置、Compose 后端健康和前端依赖漏洞。
- 不修改测试工程师 005 号历史报告、证据和缺陷状态。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单。
- [x] 已读取相关 PRD、接口、任务拆解、团队职责和验收标准。
- [x] 已读取代码编写手册和适用 Agent/Python/TDD/安全 Skill。
- [x] 已确认 Phase4、P4-00、M04 和主责 Agent。
- [x] 已复现 005 号 13 项缺陷表征测试，并确认系统 Prompt 和业务 JSON 均缺少正向协议。

## 5. 实施方案

### 5.1 方案说明

新增无业务模块反向依赖的不可变注册表。每个业务场景登记稳定 ID、名称、版本、用途、系统 Prompt SHA-256、允许的用户载荷前缀、顶层字段和响应 Schema。`StructuredRequest` 同时验证系统正文摘要和业务 JSON；Provider 在 SDK 调用前再使用实际响应类型校验 Schema 绑定。

正式调用点必须显式选择场景 ID。无场景 ID 的业务 Prompt、正文篡改、借用其他场景、未知字段、重复 JSON 键、地址、联系方式、凭证形态和未脱敏业务标识全部失败关闭。REAL-AI-05 评测上下文与业务场景上下文互斥，不能作为生产旁路。

FAQ/工具的系统 Prompt 固定化；已校验的回复语言、语气和品牌名改为业务 JSON 字段。历史 `build_reply_system_prompt` 仅保留导入兼容，固定返回注册正文，不再拼接动态数据。

### 5.2 依赖关系

- 前置依赖：REAL-AI-01 Provider 最终门禁、REAL-AI-02 声明、REAL-AI-03 安全策略和 REAL-AI-04 草稿链路。
- 后续依赖：测试工程师对 `DEF-REAL-AI04-005` 独立复测；真实模型质量、SSE 和五日稳定性门禁。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 注册表退化为任意 Prompt 白名单 | 系统指令或客户数据越权外发 | 强制场景 ID、正文摘要、载荷结构和响应 Schema 同时匹配 |
| 动态品牌或语气改变系统 Prompt | 摘要失效或形成系统层注入 | 动态配置只进入已校验业务 JSON |
| 业务注册绕过 DLP | 地址、联系方式或业务标识外泄 | 场景协议前后执行地址、敏感标识、凭证和重复键检查 |
| 评测上下文被业务调用复用 | 普通业务获得合成评测授权 | 两类上下文显式互斥，冲突直接拒绝 |
| 开发验证被误作正式关闭 | 跳过独立测试和生产门禁 | 实施记录只声明开发整改完成，缺陷保持待复测 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `backend/app/agent/prompt_registry.py` | 新增 | 登记八类业务 Prompt 的 ID、版本、用途、摘要、输入和输出契约 | AIAgent开发工程师Agent |
| `backend/app/agent/security.py` | 修改 | 增加业务系统 Prompt 和业务 JSON 场景级安全判定 | AIAgent开发工程师Agent |
| `backend/app/agent/providers/base.py` | 修改 | `StructuredRequest` 增加业务场景并校验响应 Schema | AIAgent开发工程师Agent |
| `backend/app/agent/providers/deepseek_provider.py` | 修改 | SDK 前传入实际响应 Schema 名称 | AIAgent开发工程师Agent |
| `backend/app/agent/providers/openai_provider.py` | 修改 | SDK 前传入实际响应 Schema 名称 | AIAgent开发工程师Agent |
| `backend/app/agent/providers/anthropic_provider.py` | 修改 | SDK 前传入实际响应 Schema 名称 | AIAgent开发工程师Agent |
| `backend/app/agent/service.py` | 修改 | 意图分类选择注册场景 | AIAgent开发工程师Agent |
| `backend/app/agent/workflow.py` | 修改 | FAQ 与工具生成/复核选择注册场景和固定系统 Prompt | AIAgent开发工程师Agent |
| `backend/app/agent/workflow_prompt.py` | 修改 | 固定系统 Prompt；动态回复配置移入低敏 JSON；升级回复 Prompt 版本 | AIAgent开发工程师Agent |
| `backend/app/agent/translation.py` | 修改 | 翻译调用选择注册场景 | AIAgent开发工程师Agent |
| `backend/app/agent/marketing_generation.py` | 修改 | 营销生成和复核选择独立注册场景 | AIAgent开发工程师Agent |
| `backend/tests/test_business_prompt_registry.py` | 新增 | 覆盖注册元数据、八类信封、篡改、错场景、错 Schema 和敏感数据 | AIAgent开发工程师Agent |
| `backend/tests/test_agent_providers.py` | 修改 | 验证真实 DeepSeek 适配层可接收翻译信封且错 Schema 零调用 | AIAgent开发工程师Agent |
| `backend/tests/test_agent_workflow.py` | 修改 | 验证 FAQ/工具固定系统 Prompt 和场景绑定 | AIAgent开发工程师Agent |
| `backend/tests/test_agent_phase4.py` | 修改 | 验证翻译、营销生成与复核业务场景已放行 | AIAgent开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：无公共 API 变化。
- 数据库：无迁移。
- 配置项：无新增环境变量；所有生产 AI 开关保持关闭。
- AI：新增八类业务 Prompt 注册契约；`WORKFLOW_PROMPT_VERSION` 升级为 `faq-agent-workflow-v1.7.0`，FAQ 和工具回答 Prompt 分别升级为 `faq-answer-v1.6.0`、`tool-answer-v1.6.0`；其他 Prompt 正文和版本不变。

### 6.3 关键实现说明

- 注册表不导入业务 Prompt 模块，仅保存审计摘要，避免 Provider 基础层与业务模块形成循环依赖。
- 系统 Prompt 只有场景 ID 与 SHA-256 同时匹配才允许；直接传入已知正文但不提供场景仍默认拒绝。
- 业务载荷必须命中场景前缀和顶层字段集合，并通过递归地址与敏感标识检查。
- FAQ chunk、工具调用和声明证据只允许在明确技术引用字段中保留 UUID；其他长业务标识必须先脱敏。
- Provider 使用实际 Pydantic 输出类型复核注册的 Schema，错配在 SDK 调用前返回 `LLM_REFUSAL`。
- 不改变 `requires_human=true`、`send_performed=false` 和平台工具所有权边界。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| TDD RED | 新增注册表专项测试后先运行 | 现有实现缺少目标行为 | 收集阶段 `ModuleNotFoundError: app.agent.prompt_registry` | 通过 |
| 注册表与 Provider 聚焦测试 | `.venv/Scripts/python.exe -m pytest -q tests/test_business_prompt_registry.py tests/test_agent_providers.py ...` | 八类合法信封通过，错误信封零 SDK 调用 | 97 passed | 通过 |
| 后端全量 | `LLM_LIVE_EVAL=false; .venv/Scripts/python.exe -m pytest -q --basetemp=.pytest-ai04-005-20260905-101` | 无功能回归 | 1316 passed，12 skipped，2 个既有弃用警告 | 通过 |
| Ruff | `.venv/Scripts/python.exe -m ruff check app tests scripts migrations` | 无规则错误 | All checks passed | 通过 |
| 格式 | `.venv/Scripts/python.exe -m ruff format --check app tests scripts migrations` | 全部格式正确 | 233 files already formatted | 通过 |
| mypy | `LLM_LIVE_EVAL=false; .venv/Scripts/python.exe -m mypy app scripts` | 无类型错误 | 166 source files 通过 | 通过 |
| 编译 | `.venv/Scripts/python.exe -m compileall -q app scripts tests` | 无编译错误 | 退出码 0 | 通过 |
| 固定安全评测 | `.venv/Scripts/python.exe -m scripts.evaluate_phase4 ...` | 零危险逃逸 | 237 条；安全与原因码准确率 1.0；危险逃逸 0；passed=true | 通过 |
| 锁文件 | `uv lock --check` | 锁文件一致 | Resolved 125 packages | 通过 |
| 依赖审计 | `uv audit --locked`、`uv audit --locked --offline` | 查询 OSV 并完成审计 | 在线调用持续重试；离线缓存缺少 OSV 响应，未得到本轮结论 | 未执行完成 |

首次全量 pytest 的断言执行到 100%，但清理用户全局 `pytest-current` 时遇到 Windows `WinError 5`。改用项目内独立 `--basetemp` 后以退出码 0 完成相同全量回归。依赖审计受当前网络/缓存限制；005 号报告已有同一锁文件的通过结论，本记录不冒充新的审计成功。

## 8. 实施结果

- 完成项：业务 Prompt 注册表、八类场景绑定、业务 JSON 正向协议、动态系统 Prompt 移除、Provider Schema 复核和自动化回归。
- 未完成项：测试工程师独立复测、真实 DeepSeek 语言质量、SSE 50 客户端和五日稳定性。
- 与原方案差异：除报告指出的系统 Prompt 注册外，同时修复了业务 `user_prompt` 仍为 `uncertain` 的第二层阻断；否则只加系统白名单仍无法进入 SDK。
- 当前状态：开发整改完成，`DEF-REAL-AI04-005` 等待测试工程师正式复测；生产能力未放行。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-032-001 | `DEF-REAL-AI04-005` 尚未由测试工程师独立复测关闭 | P1 | 测试工程师Agent | Phase4 / REAL-AI-04 第六次复测 |
| R-032-002 | 当前网络和本机缓存不能完成本轮 OSV 依赖审计 | P2 | 环境运维人员、测试工程师Agent | 恢复网络后复测 |
| R-032-003 | 真实 DeepSeek 回复、翻译和营销语言质量仍需独立开放集验证 | P1 | AIAgent开发工程师Agent、测试工程师Agent | Phase4 / REAL-AI-05 |
| R-032-004 | 公开 SSE、50 客户端和五日稳定性仍未验收 | P1 | 全栈开发工程师Agent、测试工程师Agent | Phase4 / REAL-FS-05 |
| R-032-005 | `.env`、backend 容器和前端依赖问题未纳入本次 AI 缺陷修复 | P2 | 全栈开发工程师Agent、环境运维人员 | 真实环境联合验收 |

## 10. 交接事项

- 交接给：测试工程师Agent、架构师Agent、全栈开发工程师Agent。
- 后续任务：测试工程师使用递增序号报告复测八类真实 Provider 信封、篡改/错场景/错 Schema、DLP 和零平台副作用；全栈继续环境与 SSE 门禁。
- 必须注意：历史 005 号证据未携带业务场景 ID，直接调用系统 Prompt 仍应失败关闭；正式业务服务才有权选择注册场景。不得以开发侧通过开启公开回复、营销发送或自动回复。

## 11. 文档同步

- [x] 已同步接口变化：无公共接口变化，登记内部 Provider 契约。
- [x] 已同步架构决策：落实既有 ADR 的 Prompt 精确注册和数据层边界，不新增跨模块决策。
- [x] 已同步任务状态：开发整改完成，正式缺陷待独立复测。
- [x] 已通知测试工程师需要覆盖八类信封、DLP、Schema 绑定和零 SDK/平台副作用。
- [x] 测试报告索引将在测试工程师正式复测完成后更新。
