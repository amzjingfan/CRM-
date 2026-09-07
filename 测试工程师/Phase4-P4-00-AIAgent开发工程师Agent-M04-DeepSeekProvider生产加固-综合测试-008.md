# Phase 4 REAL-AI-01 DeepSeek Provider 生产加固第八次独立综合测试报告

## 1. 测试基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 `REAL-AI-01` |
| 模块编号 | M04 |
| 模块名称 | DeepSeek Provider 生产加固 |
| 被测主责 Agent | AIAgent开发工程师Agent |
| 被测协作 Agent | 全栈开发工程师Agent、架构师Agent |
| 测试执行 Agent | 测试工程师Agent |
| 关联实施记录 | `共享记忆文档/实施记录/Phase4-P4-00-AIAgent开发工程师Agent-DeepSeekProvider第七次测试缺陷修复-008.md` |
| 测试类型 | 综合测试、修复验证、真实模型冒烟、回归测试、数据库测试、安全测试、代码审查 |
| 执行日期 | 2026-08-27 |
| 测试结论 | **不通过** |

## 2. 最终结论

第七轮开发修复已有效关闭 007 号报告中的完整信封隐私绕过：

- Unicode 转义等价键、三次同名键、不同空白和数组内嵌对象重复键均以 `JSON_DUPLICATE_KEY_REJECTED` 失败关闭，外发正文固定为 `[UNTRUSTED_JSON]`。
- 合法控制 DTO 会从已验证字段重新按固定顺序序列化，原始空白、字段顺序和 Unicode 转义不再进入 Provider。
- `system_prompt` 与 `user_prompt` 已同时进入共同门禁；精确注册的工程系统 Prompt 以外，换行、BOM、零宽字符、大小写、动态品牌/业务文本和地址文本均失败关闭。
- DeepSeek、OpenAI、Anthropic 对重复键、非注册系统 Prompt 和修复请求均保持 SDK 零调用；只有精确可信信封能够进入离线 Trap 客户端。

据此：

- `DEF-REAL-AI01-001/005/006` 本轮 **Closed**。
- `DEF-REAL-AI01-002/003/004` 保持 **Closed**。

但真实 DeepSeek 最小成功链路出现新的确定性阻断：当前唯一允许的系统 Prompt 和规范用户控制 DTO 都不包含字面量 `json`，而 `DeepSeekProvider` 固定使用 `response_format={"type":"json_object"}`。真实 `deepseek-v4-flash` 请求因此返回 HTTP 400，并被稳定映射为不可重试的 `LLM_INVALID_REQUEST`。在当前正向协议下，调用方不能加入 `json` 而仍保持 `allowed`，所以不存在可成功执行的真实 DeepSeek 放行请求。

新增：

- `DEF-REAL-AI01-007`：可信工程控制信封与 DeepSeek JSON Output 前置条件不兼容，**P1 / Open**。

32 项独立开放集、267 项 Provider/安全/工作流聚焦测试、716 项默认后端全量、726 项隔离 PostgreSQL 全量、234 条固定安全评测、静态质量、迁移和依赖审计均通过；这些证据证明隐私门禁修复有效，但不能替代失败的真实 Provider 最小正向链路。

`REAL-AI-01` 第八次复测仍不通过。公开 AI 回复、生产翻译、AI 营销、自动回复和真实高风险平台写操作继续不得放行。

## 3. 测试依据、范围与边界

### 3.1 测试依据

- `AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md`
- `架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`
- `架构师/PLAN-001-REAL-真实平台与AI生产环境接入实施计划-v1.0.md`
- `共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md`
- `共享记忆文档/智能客服平台 — 管理端接口文档.md` 第 11.11 节
- `共享记忆文档/开发任务拆解（按人天分配）.md`
- `共享记忆文档/项目团队职责说明.md`
- `共享记忆文档/MVP范围与验收标准.md`
- `共享记忆文档/代码编写手册.md`
- `测试工程师/测试报告命名规范.md`
- `测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-DeepSeekProvider生产加固-综合测试-007.md`
- 本项目全部 `AGENTS.md`
- `开发工具/skills/agent-engineering-handbook--independent-verification/SKILL.md`
- `开发工具/skills/addyosmani-agent-skills--security-and-hardening/SKILL.md`

### 3.2 测试范围

1. 007 报告的重复 JSON 键、原始载荷复用和 `system_prompt` 外发绕过修复。
2. Unicode 转义同名键、任意层级重复键、三次重复键、空白和字段顺序变形。
3. 控制 DTO 规范化序列化及非字符串、非对象、前后缀和多 JSON 文档失败关闭。
4. 固定系统 Prompt 的精确匹配，以及换行、BOM、零宽字符、大小写和动态文本变形。
5. 普通请求和 `is_repair=true` 请求的完整信封合并规则。
6. DeepSeek、OpenAI、Anthropic 三类 Provider 的非可信信封 SDK 零调用和可信信封正向路径。
7. DeepSeek 真实模型最小控制请求及错误映射。
8. 静态质量、默认与隔离数据库全量测试、迁移、固定评测、锁文件和依赖审计。

### 3.3 非目标

- `REAL-AI-02～05` 的结构化业务声明、回复、翻译、营销和真实模型质量评测。
- 公开 SSE 50 客户端并发、首分块、P95/P99、五日稳定性和 99.5% 可用性。
- 真实 TikTok 联调、平台 OAuth 或任何平台写操作。
- 业务 Prompt 注册表、本地 PII/DLP 新能力或真实客户文本调用。
- 修改产品代码、开发测试、Prompt、评测集、依赖、迁移或历史测试报告。

### 3.4 风险和独立性

本任务位于客户数据向外部 LLM 发送的高风险边界。确定性门禁、开放集反例、异主体复核和人工生产放行均为强制要求。

- 本轮使用未进入开发测试的新 Unicode 等价键、三次重复键、BOM、零宽字符、大小写和修复请求变形。
- 所有隐私探针均为合成数据，只进入离线 Trap；未把地址、客户文本或攻击载荷发送给真实 DeepSeek。
- 真实 DeepSeek 只接收固定工程控制信封，不含客户数据、地址、订单、消息、Token 或凭证。
- 测试前后关键产品文件 SHA-256 一致。
- 项目不是 Git 仓库，无法绑定提交 SHA、树对象和 diff 哈希，不能声称验证了不可变发布目标。
- 测试与开发使用同一模型家族，独立性仅为“同模型家族、新会话、新样例和只读验证”，不能替代异模型或人类安全负责人审批。

## 4. 测试环境与待测快照

### 4.1 环境

| 项目 | 值 |
| --- | --- |
| 操作系统 | Windows 10.0.19045 |
| Python | 3.11.15 |
| uv | 0.12.3 |
| Docker Client/Server | 29.7.2 / 29.7.2 |
| PostgreSQL | `pgvector/pgvector:pg16` 临时 tmpfs 容器 |
| pgvector | 0.8.6 |
| 数据库迁移 head | `019_tiktok_channel_unique` |
| 真实模型 | DeepSeek `deepseek-v4-flash`；仅无客户数据控制信封冒烟 |

### 4.2 待测快照

| 文件 | SHA-256 |
| --- | --- |
| `backend/app/agent/security.py` | `C6F502E62689AD35E2391D5C3D8088283EE526A38031E2337DFE2EAFFEE737C4` |
| `backend/app/agent/providers/base.py` | `71EEF1342A3F99BBD8D7624476D467497E1B0AC884E04DF970B3950B6351A081` |
| `backend/app/agent/providers/deepseek_provider.py` | `7437870E013EF24F28E385A69E97B0D0AAB5383681FC86604478749FE5C5D689` |
| `backend/app/agent/providers/openai_provider.py` | `652274A3D8991CB2A21A6E500533EBA6E3C1D796A5C9A0B1406724510CF8845E` |
| `backend/app/agent/providers/anthropic_provider.py` | `039C8202D2B389D9D430ADC1348D124155783F414D8FE9D319F23CF2D38C2300` |
| `backend/app/shared/logging/setup.py` | `AB0B1B537DCC6AC04885CFE3F485D168B1E4987A2A94404898362934F48FA500` |
| `backend/tests/test_agent_domain.py` | `73888BBC4AE3E4F6ADC7126C691334858342C0781ED7D9F51F5F8B8DE4F018D1` |
| `backend/tests/test_agent_providers.py` | `C47858C4CE277A3FC154A5E32A818075F61149955FA6142352805B8B83C37C24` |
| `backend/tests/test_agent_workflow.py` | `E0AABDCB22BEF0E8D5E4E67D737D34B072CE79A45A5325FEC75604C50317C594` |
| `backend/tests/test_real_runtime_config.py` | `773B710C074B106E50B0137BEA3E43666D7A5AF4788B0DE1311204E7515C075D` |
| `backend/uv.lock` | `3AD5B450855EC7684EA0DD2C2361B5A2E663A5A51050C3DCBA96FB79C69B6172` |

测试后上述关键哈希一致。临时探针、评测输出和 PostgreSQL 容器均已精确清理。

## 5. 缺陷状态汇总

| 缺陷编号 | 优先级 | 本轮状态 | 结论 |
| --- | --- | --- | --- |
| `DEF-REAL-AI01-001` | P1 | **Closed** | 当前仅固定工程控制信封可外发；新旧地址、自由文本、未知结构和完整信封变形均失败关闭 |
| `DEF-REAL-AI01-002` | P1 | Closed | 日志正文保护、Trace 和 Provider Request ID 摘要化未回退 |
| `DEF-REAL-AI01-003` | P2 | Closed | 合法业务文本继续保留低敏正文并进入本地人工路径 |
| `DEF-REAL-AI01-004` | P2 | Closed | UUID Trace ID 关联未回退 |
| `DEF-REAL-AI01-005` | P1 | **Closed** | 任意对象层级重复键失败关闭，原始重复键载荷不再外发 |
| `DEF-REAL-AI01-006` | P1 | **Closed** | 系统与用户 Prompt 已共同校验，非注册系统 Prompt 三类 Provider SDK 零调用 |
| `DEF-REAL-AI01-007` | P1 | **Open / 新增** | 唯一可信信封不含 `json`，真实 DeepSeek JSON Output 请求固定返回 400，最小成功链路不可用 |

`DEF-REAL-AI01-001/005/006` 的关闭只适用于当前不可变工程控制信封。未来一旦增加业务 Prompt 注册表、本地 DLP、真实客户文本或其他允许协议，必须重新执行开放集和完整外发信封安全测试。

## 6. 修复回归与独立开放集

### 6.1 重复键和规范化

独立样例覆盖：

- `operation`、`schema_version`、`language` 的 Unicode 转义等价键。
- 同一字段连续出现三次。
- 数组内嵌对象重复键。
- 多行和不同空白下的重复键。

结果：6/6 均为 `uncertain + JSON_DUPLICATE_KEY_REJECTED`，正文固定为 `[UNTRUSTED_JSON]`，合成隐藏值未保留。

另有 3 个合法控制 DTO 变形均重建为唯一规范字符串：

```text
{"operation":"provider_contract_check","schema_version":"1","language":"en"}
```

前缀 BOM、尾随文本、连续两个 JSON 文档、`NaN`、布尔版本值和数组顶层结构均未进入 `allowed`。

### 6.2 系统 Prompt 和完整信封

固定系统 Prompt 的换行、BOM、零宽字符、大小写变化、动态业务指令和合成地址均失败关闭，系统正文替换为 `[SYSTEM_PROMPT_BLOCKED]`。

三类 Provider 分别验证：

- Unicode 重复键用户 Prompt：SDK 0 次调用。
- 固定系统 Prompt 尾随换行：SDK 0 次调用。
- `is_repair=true` 动态系统 Prompt：SDK 0 次调用。
- 精确注册系统 Prompt + 可规范化控制 DTO：离线 Trap 恰好调用 1 次，外发用户正文为规范字符串。

统计：独立临时探针 32/32 通过，无新的隐私外发反例。

### 6.3 静态调用面审查

当前 Provider 调用点使用代码内静态 Pydantic 响应 Schema；未发现 HTTP 或数据库数据可直接构造运行时 Schema 类型。模型名、超时和密钥来自类型化服务端配置，密钥未输出到测试证据。

## 7. 新增缺陷详情

### DEF-REAL-AI01-007：可信控制信封与 DeepSeek JSON Output 前置条件不兼容

| 项目 | 内容 |
| --- | --- |
| 优先级 | P1 |
| 类型 | 功能阻断、真实 Provider 契约、正向链路不可用 |
| 影响范围 | `DeepSeekProvider` 的所有当前可放行请求；REAL-AI-01 最小请求验收 |
| 状态 | Open |
| 是否阻断 | 是；阻断 REAL-AI-01 和后续真实模型阶段 |
| 建议负责 Agent | AIAgent开发工程师Agent；架构师Agent评审可信 Prompt 版本变更 |

复现步骤：

1. 使用当前配置的 `deepseek-v4-flash` 和服务端 Secret 配置，不输出 Key。
2. 以 `TRUSTED_PROVIDER_CONTRACT_SYSTEM_PROMPT` 和规范控制 DTO 构造 `StructuredRequest`。
3. 确认信封状态为 `allowed + TRUSTED_PROMPT_ENVELOPE_ALLOWED`。
4. 调用 `DeepSeekProvider.generate_structured()`，响应 Schema 使用只要求 JSON 对象的本地 Pydantic `RootModel`。

实际结果：

- 系统 Prompt 和用户 Prompt 均不包含字面量 `json`。
- `DeepSeekProvider` 固定发送 `response_format={"type":"json_object"}`。
- DeepSeek 返回 HTTP 400，说明 JSON Object 模式要求 Prompt 明确包含 `json`。
- 应用正确映射为 `LLM_INVALID_REQUEST` 且 `retriable=false`，但正向调用失败。

代码证据：

- `backend/app/agent/security.py:28-30`：唯一可信系统 Prompt 只要求 “structured output”，没有 `json`。
- `backend/app/agent/security.py:175-177`：唯一可信用户协议字段和值也没有 `json`。
- `backend/app/agent/security.py:436-440`：系统 Prompt 必须精确匹配，调用方不能自行补充 `json`。
- `backend/app/agent/providers/deepseek_provider.py:105-118`：请求固定启用 `json_object`。

预期结果：唯一允许的工程控制信封应同时满足本地安全注册和 DeepSeek JSON Output 契约，真实最小请求返回可通过 Pydantic 校验的 JSON 对象。

建议修复：

1. 将不可变工程系统 Prompt 明确改为要求返回 JSON 对象，并同步 Prompt 版本、接口文档和哈希/注册信息。
2. 增加离线契约测试：只要启用 `json_object`，最终发送的系统或用户 Prompt 至少一处必须包含 `json`，且仍不得承载动态业务数据。
3. 增加带显式授权的真实 DeepSeek 最小成功冒烟门禁；开发自测若未执行真实调用，交接文档必须明确标记。
4. 修复后重新执行 32 项独立开放集，防止为兼容 Provider 而放宽系统 Prompt 精确注册或用户 DTO 正向协议。

## 8. 自动化、数据库、迁移与真实模型证据

| 验证项 | 结果 | 结论 |
| --- | --- | --- |
| 独立临时开放集 | 32 passed | 通过；未发现新的隐私信封绕过 |
| Provider/安全/工作流聚焦 | 267 passed，1 个既有 warning | 通过 |
| 默认后端全量 | 716 passed、10 skipped，2 个既有 warning | 通过；跳过项为未提供隔离 DB |
| 隔离 PostgreSQL 全量 | 726 passed、0 skipped，2 个既有 warning | 通过 |
| Ruff | All checks passed | 通过 |
| Ruff Format | 212 files already formatted（执行时包含 2 个临时文件） | 通过 |
| mypy | 155 个源文件无错误 | 通过 |
| compileall | 通过 | 通过 |
| `uv lock --check` | 125 个包解析成功 | 通过 |
| `uv audit --locked` | 124 个包无已知漏洞或不良状态 | 通过 |
| 固定安全评测 | 234 条；安全和原因码准确率 100%，危险漏放 0 | 通过 |
| 空库迁移 | `001→019` | 通过 |
| 最新迁移回滚 | `019→018→019`，最终为 head | 通过 |
| pgvector | 0.8.6 | 通过 |
| 真实 DeepSeek 控制信封 | HTTP 400；`LLM_INVALID_REQUEST`；不可重试 | **失败；新增 DEF-REAL-AI01-007** |

两个 warning 为既有 Starlette TestClient/httpx 和 argon2 元数据弃用提示。

新建隔离数据库第一次全量执行前尚未迁移，716 项通过、10 项因 `stores` 不存在失败；按正确验收顺序执行 `001→019` 后重新运行，726 项全部通过。该次环境准备顺序修正不计为产品缺陷。

真实调用没有发送客户数据、地址、订单、消息、攻击载荷、Token、密钥、Provider Request ID 或模型原始响应。失败发生在请求参数校验阶段，未取得模型有效输出或 Token 用量。

## 9. 执行命令与清理

主要命令：

```text
uv run pytest .tmp/real-ai01-008/test_independent_provider_envelope.py -q
uv run pytest tests/test_agent_domain.py tests/test_agent_tool_execution.py tests/test_agent_providers.py tests/test_agent_evaluation.py tests/test_real_runtime_config.py tests/test_health.py tests/test_agent_workflow.py -q
uv run ruff check .
uv run ruff format --check .
uv run mypy app scripts
uv run python -m compileall -q app scripts
uv run pytest -q
uv lock --check
uv audit --locked
uv run python -m scripts.evaluate_phase4 --dataset evals/agent-phase4-v1.0.0.jsonl --output <temporary-output>
uv run alembic upgrade head
uv run alembic current
uv run alembic downgrade -1
uv run alembic upgrade head
uv run python .tmp/real-ai01-008/live_deepseek_control_smoke.py
```

清理结果：

- 临时容器 `crm-real-ai01-008-postgres` 已删除；数据库使用 tmpfs，不含业务数据。
- 临时探针、真实冒烟脚本、`__pycache__` 和固定评测临时 JSON 已删除。
- 未修改产品代码、开发测试、Prompt、评测集、锁文件、迁移或历史报告。

## 10. 验收建议

当前不建议验收 `REAL-AI-01`，也不建议进入公开回复、生产翻译、AI 营销或自动回复阶段。再次复测前至少完成：

1. 关闭 `DEF-REAL-AI01-007`，使唯一可信工程控制信封满足 DeepSeek JSON Output 契约并完成真实最小成功请求。
2. 保持 `DEF-REAL-AI01-001～006` 已关闭状态，不得通过放宽系统 Prompt 精确匹配、允许任意前缀或扩大用户 DTO 字段来修复正向链路。
3. 重新执行 Unicode 重复键、系统 Prompt 变形、三类 Provider SDK 零调用、267 项聚焦、726 项隔离数据库全量和 234 条固定评测。
4. 在修复后的不可变待测快照上再次执行无客户数据的真实 DeepSeek 最小冒烟。
5. 建立 Git 或等价不可变发布基线，并由异模型/异主体和人类安全负责人完成高风险生产放行。

即使 `DEF-REAL-AI01-007` 关闭，本报告也只覆盖 `REAL-AI-01` Provider 工程范围；真实回复、翻译、营销质量、SSE 性能和五日稳定性仍需后续独立门禁。
