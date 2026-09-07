# Phase4-P4-00-AIAgent开发工程师Agent-M04-DeepSeekProvider生产加固-综合测试-009

## 1. 测试基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 `REAL-AI-01` |
| 模块编号 | M04 |
| 模块名称 | DeepSeek Provider 生产加固 |
| 被测 Agent | AIAgent开发工程师Agent |
| 测试 Agent | 测试工程师Agent |
| 测试日期 | 2026-08-27 |
| 测试类型 | 综合测试、修复验证、真实模型冒烟、回归测试、数据库测试、安全测试、代码审查 |
| 前序报告 | `Phase4-P4-00-AIAgent开发工程师Agent-M04-DeepSeekProvider生产加固-综合测试-008.md` |
| 重点缺陷 | `DEF-REAL-AI01-007` |
| 测试结论 | **有条件通过当前 REAL-AI-01 Provider 工程范围** |

## 2. 最终结论

第八轮开发修复有效关闭了 008 号报告中的 DeepSeek JSON Output 正向链路阻断：

- 固定工程 Prompt 已升级为 `provider-contract-v1.1.0`，安全策略升级为 `prompt-dlp-v1.3.0`。
- 唯一可信系统 Prompt 明确包含字面量 `json`，并提供不含客户或业务数据的固定 JSON 格式示例。
- DeepSeek 仍固定使用 `response_format={"type":"json_object"}`，最终出站信封满足供应商前置条件。
- 真实 `deepseek-v4-flash` 最小控制请求成功，返回结果通过 Pydantic Schema 校验；本轮输入 70 Token、输出 5 Token、总耗时 2684 ms。
- 系统 Prompt 仍按精确值注册；大小写、BOM、零宽字符、尾随换行和动态追加文本均失败关闭。
- 用户控制 DTO 仍只允许固定三个字段和值；未知字段、前缀包装、任意层级重复键和 Unicode 等价重复键均不能进入外部 Provider。
- DeepSeek、OpenAI、Anthropic 对非可信完整信封均在 SDK 调用前拒绝，未因兼容 JSON Output 而回退 001～006 的安全边界。

据此：

- `DEF-REAL-AI01-007` 本轮 **Closed**。
- `DEF-REAL-AI01-001～006` 保持 **Closed**。
- 本轮未发现新的 `REAL-AI-01` 缺陷。

31 项独立开放集、267 项 Provider/安全/工作流聚焦测试、716 项默认后端全量、726 项隔离 PostgreSQL 全量、234 条固定安全评测、静态质量、迁移和依赖审计均通过。

`REAL-AI-01` 可在本报告 SHA-256 快照范围内标记为“有条件通过当前 Provider 工程范围”。该结论不代表真实生产 AI 联合验收完成，也不放行 `REAL-AI-02～05`、公开 AI 回复、生产翻译、AI 营销、自动回复、原生 Token SSE、50 客户端并发或五日稳定性门禁。

## 3. 测试依据、范围与边界

### 3.1 测试依据

- `AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md`
- `架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`
- `架构师/PLAN-001-REAL-真实平台与AI生产环境接入实施计划-v1.0.md`
- `共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md`
- `共享记忆文档/管理端接口文档.md`
- `共享记忆文档/代码编写手册.md`
- `测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-DeepSeekProvider生产加固-综合测试-008.md`
- `共享记忆文档/实施记录/Phase4-P4-00-AIAgent开发工程师Agent-DeepSeekProvider第八次测试缺陷修复-009.md`

### 3.2 测试范围

1. `DEF-REAL-AI01-007` 的固定 Prompt、策略版本和 DeepSeek JSON Output 前置条件修复。
2. 固定系统 Prompt 是否显式包含 `json`，且不包含运行时插值、客户、订单、地址或营销正文。
3. 合法控制 DTO 的规范化序列化，以及未知字段、前缀、Unicode 等价键和嵌套重复键失败关闭。
4. 系统 Prompt 精确注册及换行、BOM、零宽字符、大小写、动态文本变形。
5. DeepSeek、OpenAI、Anthropic 三类 Provider 的非可信信封 SDK 零调用。
6. DeepSeek 真实模型最小控制请求、结构化输出和低敏指标。
7. Provider、日志、安全、工作流、配置、全量回归、数据库、迁移、固定评测和依赖审计。

### 3.3 非目标

- `REAL-AI-02～05` 的结构化业务声明、`DEF-P4-AI-008/009`、真实回复、翻译、营销草稿和版本化真实模型质量评测。
- 真实客户文本、完整地址、订单、消息、攻击载荷或生产业务数据的外部模型调用。
- 公开 SSE 50 客户端并发、首分块、P95/P99、断线恢复、五日稳定性和 99.5% 可用性。
- TikTok OAuth、真实平台只读、Webhook 或任何平台写操作。
- 生产开关变更、生产密钥轮换、部署放行和人类安全负责人审批。

### 3.4 独立性与安全边界

- 本轮独立开放集未写入产品测试，且使用开发测试未直接覆盖的 Unicode 等价键、嵌套数组重复键、系统 Prompt 变形和未知 `format=json` 字段。
- 所有负向探针只进入离线 Trap 客户端；未向真实 DeepSeek 发送地址、客户文本或攻击载荷。
- 真实调用只发送固定工程控制信封，测试证据不记录 API Key、Provider Request ID、请求正文或模型原始响应。
- 项目不是 Git 仓库，无法绑定提交 SHA、树对象或签名 Tag；测试结论仅绑定本报告记录的文件 SHA-256。
- 测试与开发使用同一模型家族，独立性为新会话、新样例和测试工程师只读复核，不能替代异模型或人类安全负责人审批。

## 4. 测试环境与待测快照

### 4.1 环境

| 项目 | 值 |
| --- | --- |
| 操作系统 | Windows 10.0.19045 |
| PowerShell | 7.6.4 |
| Python | 3.11.15 |
| uv | 0.12.3 |
| Docker | 29.7.2 |
| PostgreSQL | `pgvector/pgvector:pg16`，本轮独立 tmpfs 容器 |
| pgvector | 0.8.6 |
| Alembic head | `019_tiktok_channel_unique` |
| 应用环境 | 本地 `development` 真实模型评测环境，不是生产部署证据 |

### 4.2 待测快照

| 文件 | SHA-256 |
| --- | --- |
| `backend/app/agent/security.py` | `FE886AAD66001447E95C717C0881517715BE0B9145A9B8ECCE2409AF9076AED5` |
| `backend/app/agent/providers/base.py` | `71EEF1342A3F99BBD8D7624476D467497E1B0AC884E04DF970B3950B6351A081` |
| `backend/app/agent/providers/deepseek_provider.py` | `7437870E013EF24F28E385A69E97B0D0AAB5383681FC86604478749FE5C5D689` |
| `backend/app/agent/providers/openai_provider.py` | `652274A3D8991CB2A21A6E500533EBA6E3C1D796A5C9A0B1406724510CF8845E` |
| `backend/app/agent/providers/anthropic_provider.py` | `039C8202D2B389D9D430ADC1348D124155783F414D8FE9D319F23CF2D38C2300` |
| `backend/app/shared/logging/setup.py` | `AB0B1B537DCC6AC04885CFE3F485D168B1E4987A2A94404898362934F48FA500` |
| `backend/tests/test_agent_domain.py` | `F62AFEBF761F0BC33CB150F82406A864EB455B94B07141F62D0BB83C6E544150` |
| `backend/tests/test_agent_providers.py` | `F3E06EDFAD3D5BCC55F434D737628B17698EFAD3BD146E6CA3D3310A405A5BAD` |
| `backend/tests/test_agent_workflow.py` | `E0AABDCB22BEF0E8D5E4E67D737D34B072CE79A45A5325FEC75604C50317C594` |
| `backend/uv.lock` | `3AD5B450855EC7684EA0DD2C2361B5A2E663A5A51050C3DCBA96FB79C69B6172` |

测试后上述关键哈希一致。测试工程师未修改产品代码、开发测试、Prompt、配置、依赖、数据库迁移或历史报告。

## 5. 缺陷状态汇总

| 缺陷编号 | 优先级 | 本轮状态 | 结论 |
| --- | --- | --- | --- |
| `DEF-REAL-AI01-001` | P1 | Closed | 仅固定工程控制信封可外发；地址、自由文本、未知结构和完整信封变形继续失败关闭 |
| `DEF-REAL-AI01-002` | P1 | Closed | 日志正文保护、Trace 与 Provider Request ID 摘要化未回退 |
| `DEF-REAL-AI01-003` | P2 | Closed | 合法非地址业务文本保持本地人工路径，不因本轮修复扩大外发范围 |
| `DEF-REAL-AI01-004` | P2 | Closed | UUID 与内部 Trace 关联能力未回退 |
| `DEF-REAL-AI01-005` | P1 | Closed | Unicode 等价键、嵌套对象和数组内重复键继续失败关闭，原始载荷不外发 |
| `DEF-REAL-AI01-006` | P1 | Closed | 系统与用户 Prompt 继续共同校验，非注册系统 Prompt 三类 Provider SDK 零调用 |
| `DEF-REAL-AI01-007` | P1 | **Closed** | 固定 Prompt 已满足 JSON Output 契约，真实最小请求成功并通过 Schema 校验 |

本轮无新增缺陷。上述关闭状态仅适用于当前固定工程控制信封。未来增加业务 Prompt 注册表、本地 DLP、真实客户文本、原生流式 Token 或其他允许协议时，必须重新执行开放集和完整出站信封安全测试。

## 6. 修复验证与独立开放集

### 6.1 JSON Output 正向契约

- `security.py:27-31` 固定策略为 `prompt-dlp-v1.3.0`，Prompt 版本为 `provider-contract-v1.1.0`。
- 固定系统 Prompt 同时包含 `json object` 要求和 `{"result":"ok"}` 的无业务数据格式示例。
- `DeepSeekProvider` 在安全门禁通过后才调用 SDK，并继续使用 `response_format={"type":"json_object"}`、`stream=false`。
- 离线 Trap 捕获的系统和用户消息与固定信封完全一致，SDK 只调用一次。
- 真实 DeepSeek 返回 `stop` 结果，并通过 `ContractOutput` Pydantic 校验。

### 6.2 正向协议未扩张

合法 DTO 的字段顺序、外层空白和 Unicode 键编码被重新构造成唯一规范文本：

```json
{"operation":"provider_contract_check","schema_version":"1","language":"en"}
```

以下变体均未进入 `allowed`：

- Unicode 转义后与 `operation` 相同的重复键。
- 未知嵌套对象中的 Unicode 等价重复键。
- 数组内对象的 Unicode 等价重复键。
- 追加未知 `format=json` 字段。
- 在合法 JSON 前追加文本前缀。

### 6.3 完整信封与三 Provider 零调用

对 DeepSeek、OpenAI、Anthropic 分别验证以下完整信封变形：

- 固定系统 Prompt 尾随换行。
- 系统 Prompt 前置 BOM。
- 系统 Prompt 尾随零宽字符。
- 将首个 `json` 改为 `JSON`。
- 追加动态品牌文本。
- 用户 DTO 追加 `format=json`。
- 用户 DTO 出现重复 `operation`。

结果：21 组 Provider/变形组合全部在共同门禁处返回不可重试 `LLM_REFUSAL`，Trap SDK 调用次数均为 0。

独立临时探针合计 31/31 通过。

## 7. 自动化、数据库、迁移与真实模型证据

| 验证项 | 实际结果 | 结论 |
| --- | --- | --- |
| 独立 JSON 契约与完整信封开放集 | 31 passed | 通过 |
| Provider/安全/工作流聚焦 | 267 passed，1 个既有 warning | 通过 |
| 默认后端全量 | 716 passed、10 skipped，2 个既有 warning | 通过；跳过项为未提供隔离 DB |
| 隔离 PostgreSQL 全量 | 726 passed、0 skipped，2 个既有 warning | 通过 |
| Ruff 全项目检查 | All checks passed | 通过 |
| Ruff 格式检查 | 208 files already formatted | 通过 |
| mypy | 155 个源文件无错误 | 通过 |
| compileall | 退出码 0 | 通过 |
| `uv lock --check` | 125 个包解析成功 | 通过 |
| `uv audit --locked` | 124 个包无已知漏洞或不良状态 | 通过 |
| 固定安全评测 | 234 条；安全准确率 100%，原因码准确率 100%，危险漏放 0 | 通过 |
| 空库迁移 | `001→019` | 通过 |
| 最新迁移回滚 | `019→018→019`，最终恢复 head | 通过 |
| pgvector | 0.8.6 | 通过 |
| 真实 DeepSeek 控制信封 | 成功；70 输入 Token、5 输出 Token、2684 ms、Schema 有效 | 通过 |

两个全量 warning 为既有 Starlette TestClient/httpx 和 argon2 元数据弃用提示，不属于本轮回归。

真实冒烟首次直接执行临时脚本时因 Python 模块搜索路径未包含项目根目录而得到 `ModuleNotFoundError: app`；明确 `PYTHONPATH=.` 后同一脚本成功。该问题发生在临时测试脚本启动方式，不是产品 Provider 缺陷，也未被计入产品通过证据。

本地 `.env` 的 `APP_ENV=development`，为经授权的真实模型评测配置；`LLM_ENABLED`、`LLM_LIVE_EVAL` 和翻译能力开关开启，自动回复与 AI 营销关闭。该本地状态只用于本次受控验证，不能作为生产公开回复或生产翻译已放行的证据。

## 8. 执行命令与清理

主要命令：

```text
uv run pytest .tmp/real-ai01-009/test_independent_json_contract.py -q
uv run pytest tests/test_agent_domain.py tests/test_agent_tool_execution.py tests/test_agent_providers.py tests/test_agent_evaluation.py tests/test_real_runtime_config.py tests/test_health.py tests/test_agent_workflow.py -q
uv run ruff check .
uv run ruff format --check app scripts tests migrations
uv run mypy app scripts
uv run python -m compileall -q app scripts
uv lock --check
uv audit --locked
uv run pytest -q --basetemp .tmp/real-ai01-009/pytest-default
uv run python -m scripts.evaluate_phase4 --dataset evals/agent-phase4-v1.0.0.jsonl --output .tmp/real-ai01-009/phase4-evaluation.json
uv run alembic upgrade head
uv run alembic current
uv run pytest -q --basetemp .tmp/real-ai01-009/pytest-db
uv run alembic downgrade -1
uv run alembic upgrade head
uv run python .tmp/real-ai01-009/live_deepseek_control_smoke.py
```

清理结果：

- 专用容器 `crm-real-ai01-009-postgres` 已删除；数据库使用 tmpfs，不含业务数据且不可恢复。
- `backend/.tmp/real-ai01-009` 中的独立探针、真实冒烟脚本、评测输出和 pytest 临时数据已精确删除。
- 第一次普通权限清理因 pytest 临时目录 ACL 被拒绝；确认绝对路径位于 `backend/.tmp/real-ai01-009` 后提升权限精确删除成功。

## 9. 验收建议与后续门禁

建议将 `REAL-AI-01` 标记为“有条件通过当前 Provider 工程范围”，并关闭 `DEF-REAL-AI01-007`。条件和后续要求如下：

1. 该结论绑定本报告 SHA-256 快照；代码变化后必须重新验证，建立 Git 或等价不可变发布基线后才能形成可审计发布候选。
2. 当前固定控制信封不能被扩展为真实客户业务 Prompt；新增允许协议必须单独经过架构评审、DLP、开放集和数据出境评审。
3. `REAL-AI-02～05`、`DEF-P4-AI-008/009`、真实回复/翻译/营销质量评测仍须独立完成，不能由本报告替代。
4. 公开 AI 回复、生产翻译、AI 营销和自动回复继续保持未放行；任何平台发送必须经过全栈工具层、人工门禁、幂等和审计。
5. 原生流式 Token、50 个授权客户端并发、首分块、P95/P99、断线恢复和五日稳定性仍待后续正式测试。
6. 生产前由架构师、异主体安全复核和人类安全负责人完成最终签署，并核对生产开关、密钥、日志和回滚方案。

本报告只关闭 `REAL-AI-01` Provider 工程缺陷，不构成真实生产 AI 联合放行记录。
