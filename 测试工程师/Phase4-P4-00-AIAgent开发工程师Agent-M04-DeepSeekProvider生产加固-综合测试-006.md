# Phase 4 REAL-AI-01 DeepSeek Provider 生产加固第六次独立综合测试报告

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
| 关联实施记录 | `共享记忆文档/实施记录/Phase4-P4-00-AIAgent开发工程师Agent-DeepSeekProvider第五次测试缺陷修复-006.md` |
| 测试类型 | 综合测试、修复验证、真实模型冒烟、回归测试、数据库测试、安全测试、代码审查 |
| 执行日期 | 2026-08-26 |
| 测试结论 | **不通过** |

## 2. 最终结论

第五轮开发修复已经建立版本化 `prompt-dlp-v1.0.0`、`allowed | blocked | uncertain` 三态结果、结构化 JSON 递归检查以及 DeepSeek、OpenAI、Anthropic 三类 Provider 的统一 SDK 前置门禁。005 报告固定地址样例已全部进入 `blocked`，固定业务负例能够保留原文并得到显式状态，`DEF-REAL-AI01-002/004` 也未回退。

但第六次独立开放集仍证明分类根因没有关闭：

- 13 条未进入开发测试的新地址、无门牌位置文本和字段别名 JSON **全部被判定为 `allowed`**。
- 以 `Keizersgracht 123, Amsterdam` 为样例，DeepSeek、OpenAI、Anthropic 三类 Provider 均实际进入客户端方法，证明这不是只影响状态展示的理论问题。
- 8 条新合法业务文本中，4 条仓位/内部标签文本被错误判定为 `blocked` 并替换为 `[ADDRESS]`；另有 3 条普通多逗号客服文本进入 `uncertain`，无法使用 AI。
- `DEF-REAL-AI01-001` 保持 **P1 / 部分修复 / Open**。
- `DEF-REAL-AI01-003` 保持 **P2 / 部分修复 / Open**。
- `DEF-REAL-AI01-002/004` 保持 **Closed**。

本轮 194 项聚焦、662 项默认全量、672 项隔离 PostgreSQL 全量、234 条固定安全评测、静态质量、迁移和依赖审计均通过；一次不含客户数据的真实 DeepSeek 合成非流式请求成功。上述工程结果不能覆盖独立隐私反例。

由于完整地址仍可进入外部 SDK，命中 ADR-004 的敏感信息泄漏停止条件，`REAL-AI-01` 继续不通过。公开 AI 回复、生产翻译、AI 营销、自动回复和真实高风险平台写操作不得放行。

## 3. 测试依据、范围与风险门禁

### 3.1 测试依据

- `AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md`
- `架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`
- `共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md`
- `共享记忆文档/智能客服平台 — 管理端接口文档.md` 第 11.8～11.9 节
- `共享记忆文档/开发任务拆解（按人天分配）.md`
- `共享记忆文档/项目团队职责说明.md`
- `共享记忆文档/MVP范围与验收标准.md`
- `共享记忆文档/代码编写手册.md`
- `测试工程师/测试报告命名规范.md`
- `测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-DeepSeekProvider生产加固-综合测试-005.md`
- 本项目全部 `AGENTS.md`

### 3.2 测试范围

1. 005 报告中 10 条地址和 8 条业务文本修复回归。
2. `PromptSafetyDecision` 三态、策略版本、稳定原因码和 `[ADDRESS]` 标记继承。
3. 新道路命名、无道路后缀、无门牌、无邮编、未知文字系统和单分隔符地址。
4. `ship_to`、`delivery_location` 等未登记结构化字段别名。
5. 仓位、内部标签、普通中英文客服句子的误报和正文保留。
6. DeepSeek、OpenAI、Anthropic 三类 Provider 在 `blocked/uncertain` 时零 SDK 调用，以及 `allowed` 漏判时的实际调用路径。
7. 日志低敏字段、既有 Provider 错误映射、配置和健康检查回归。
8. 静态检查、默认及隔离数据库全量测试、迁移、固定安全评测和依赖审计。
9. 一个无客户数据的真实 DeepSeek 合成非流式最小调用。

### 3.3 非目标

- `REAL-AI-02～05` 的结构化业务声明、回复、翻译、营销和真实模型质量评测。
- 公开 SSE 50 客户端、首分块、P95/P99、五日稳定性和 99.5% 可用性。
- 真实 TikTok 联调和任何平台写操作。
- 修改产品代码、开发测试、Prompt、评测集、依赖或迁移。

### 3.4 风险与独立性

本任务涉及客户位置数据向外部 LLM 传输，风险等级为高。确定性检查、独立反例和人工生产放行均为强制门禁；测试 Agent 无权批准生产发布。

- 本轮使用未进入开发测试的新样例，直接检查最终请求和离线客户端替身。
- 测试前后重新计算关键产品文件 SHA-256，结果一致。
- 项目不是 Git 仓库，无法绑定提交 SHA、树对象和 diff 哈希，不能声称验证了不可变提交。
- 测试与开发使用同一模型家族，独立性等级只能记录为“同模型家族、新会话、新样例和只读验证”，不能替代异模型或人类安全负责人审批。

## 4. 待测快照

| 文件 | SHA-256 |
| --- | --- |
| `backend/app/agent/security.py` | `3A05D69F09854CA51DB022DF97F30FBB1DA76DC64BCBA9D0F6F3C6598CC5532D` |
| `backend/app/agent/providers/base.py` | `278757B3244B546032560F4D671DB9FD5EF908135EF3444FAA8A9E1A15BF7207` |
| `backend/app/agent/providers/deepseek_provider.py` | `7437870E013EF24F28E385A69E97B0D0AAB5383681FC86604478749FE5C5D689` |
| `backend/app/agent/providers/openai_provider.py` | `652274A3D8991CB2A21A6E500533EBA6E3C1D796A5C9A0B1406724510CF8845E` |
| `backend/app/agent/providers/anthropic_provider.py` | `039C8202D2B389D9D430ADC1348D124155783F414D8FE9D319F23CF2D38C2300` |
| `backend/app/shared/logging/setup.py` | `AB0B1B537DCC6AC04885CFE3F485D168B1E4987A2A94404898362934F48FA500` |
| `backend/tests/test_agent_domain.py` | `CD2B9BF2A8A79752DAEBFA511921C54C33520E2DFF07D5957B7FCD9CE51D9B06` |
| `backend/tests/test_agent_providers.py` | `BDF718FD7E93C69030F0CE4081154D2849966720503DAEE1BF81187D7E7EA345` |
| `backend/tests/test_real_runtime_config.py` | `773B710C074B106E50B0137BEA3E43666D7A5AF4788B0DE1311204E7515C075D` |
| `backend/uv.lock` | `3AD5B450855EC7684EA0DD2C2361B5A2E663A5A51050C3DCBA96FB79C69B6172` |

## 5. 缺陷状态汇总

| 缺陷编号 | 优先级 | 本轮状态 | 结论 |
| --- | --- | --- | --- |
| `DEF-REAL-AI01-001` | P1 | 部分修复 / Open | 三态和 Provider 门禁存在，但 13 条新地址全部错误进入 `allowed` |
| `DEF-REAL-AI01-002` | P1 | Closed | Trace、Provider Request ID 摘要和日志正文保护未回退 |
| `DEF-REAL-AI01-003` | P2 | 部分修复 / Open | 005 固定文本恢复，但新业务同义表达仍被 `blocked`；普通客服文本还会无位置证据进入 `uncertain` |
| `DEF-REAL-AI01-004` | P2 | Closed | 真实评测 UUID Trace ID 保持可关联 |

## 6. 修复项回归

### 6.1 已通过项

- `prompt-dlp-v1.0.0`、三态枚举和稳定原因码已实现。
- 005 报告 10 条地址均进入 `blocked`，最终正文为 `[ADDRESS]`。
- 005 报告业务负例保留原文；有地点歧义的样例进入 `uncertain`，其余进入 `allowed`。
- 上游已经出现 `[ADDRESS]` 时，最终请求继续保持 `blocked`。
- DeepSeek、OpenAI、Anthropic 均在实际 SDK 方法前调用统一 `ensure_safe_for_external_provider()`。
- 对本轮 `uncertain` 普通客服文本，三类 Provider 均返回不可重试 `LLM_REFUSAL` 且客户端替身未被调用。
- 安全日志只保留策略版本、状态、原因码和规范追踪字段，既有正文保护未回退。

### 6.2 结论边界

“三类 Provider 对非 `allowed` 零调用”只能证明执行门禁有效，不能证明 DLP 分类准确。只要完整地址被错误归为 `allowed`，三个 Provider 都会继续调用外部 SDK。本轮正是该路径失败。

## 7. 独立地址与数据出境测试

期望：完整地址应为 `blocked`；无门牌、未知格式、字段别名或低置信度位置至少应为 `uncertain`。任何样例都不得为 `allowed`。

| 独立样例 | 实际状态 | 正文结果 | 判定 |
| --- | --- | --- | --- |
| `Keizersgracht 123, Amsterdam` | `allowed` | 原样保留 | 失败 |
| `Mannerheimintie 10, Helsinki` | `allowed` | 原样保留 | 失败 |
| `İstiklal Caddesi 15, İstanbul` | `allowed` | 原样保留 | 失败 |
| `Bulevar Kralja Aleksandra 73, Beograd` | `allowed` | 原样保留 | 失败 |
| `Rue de Rivoli, Paris` | `allowed` | 原样保留 | 失败 |
| `Jalan Tun Razak, Kuala Lumpur` | `allowed` | 原样保留 | 失败 |
| `Paseo de Gracia 25, Barcelona` | `allowed` | 原样保留 | 失败 |
| `Prinsengracht 263, Amsterdam` | `allowed` | 原样保留 | 失败 |
| `Via Garibaldi, Genova` | `allowed` | 原样保留 | 失败 |
| `Тверская улица Москва` | `allowed` | 原样保留 | 失败 |
| `ถนนสุขุมวิท กรุงเทพมหานคร` | `allowed` | 原样保留 | 失败 |
| `{"profile":{"ship_to":"Keizersgracht 123, Amsterdam"}}` | `allowed` | 原样保留 | 失败 |
| `{"contact":{"delivery_location":"Rue de Rivoli, Paris"}}` | `allowed` | 原样保留 | 失败 |

统计：`0/13` 安全失败关闭，`13/13` 错误进入 `allowed`。

所有样例均为测试格式，不来源于项目客户数据。带门牌样例具备道路、门牌和城市；无门牌样例按接口文档 11.9 应进入 `uncertain`，不能因缺少数字或第二个分隔符默认放行。

### 7.1 三 Provider 实际客户端路径

使用离线 `Trap` 客户端替身调用 `Keizersgracht 123, Amsterdam`：

| Provider | `prompt_safety_state` | 客户端方法是否被调用 | 判定 |
| --- | --- | --- | --- |
| DeepSeek | `allowed` | 是 | 失败 |
| OpenAI | `allowed` | 是 | 失败 |
| Anthropic | `allowed` | 是 | 失败 |

客户端替身在调用后立即抛出测试异常，不产生网络请求。结果证明地址会越过共同门禁进入供应商调用参数。

## 8. 独立合法业务文本测试

期望：明确为内部标签、仓位或普通客服语句的文本不应被静默替换为地址。无法可靠分类时可以保留正文并进入 `uncertain`，但不应在没有位置证据时大面积降级。

| 独立样例 | 实际状态 | 正文结果 | 判定 |
| --- | --- | --- | --- |
| `Tower 7 and Suite 2 are inventory labels for the weekly report.` | `blocked` | `[ADDRESS]` | 失败 |
| `Block 5 and Unit 9 identify fulfillment bins.` | `blocked` | `[ADDRESS]` | 失败 |
| `Apartment 3 and Building 4 are internal taxonomy labels.` | `blocked` | `[ADDRESS]` | 失败 |
| `Flat 6 and Tower 8 are routing labels for operations.` | `blocked` | `[ADDRESS]` | 失败 |
| `Revenue, cost, and margin are shown in the report.` | `uncertain` | 原文保留 | 观察：无位置证据仍降级 |
| `Hello, thanks, please escalate this issue.` | `uncertain` | 原文保留 | 观察：普通客服文本无法使用 AI |
| `你好，请帮我查询订单，谢谢。` | `uncertain` | 原文保留 | 观察：普通中文订单请求无法使用 AI |
| `退款页面、帮助中心、术语表都已更新。` | `allowed` | 原文保留 | 通过 |

统计：4 条文本被错误整段脱敏，3 条普通文本在无地址证据时被拒绝外发，仅 1 条进入 `allowed`。这说明新策略一方面继续依赖有限业务词表区分地址与仓位，另一方面把“两个逗号”作为低置信度位置形态，造成显著误报。

## 9. 缺陷详情

### DEF-REAL-AI01-001：开放地址集合仍被有限词表和计数规则放行

| 项目 | 内容 |
| --- | --- |
| 优先级 | P1 |
| 类型 | 隐私、安全、数据出境 |
| 影响范围 | DeepSeek、OpenAI、Anthropic 及所有复用 `StructuredRequest` 的 AI 场景 |
| 状态 | 部分修复 / Open |
| 是否阻断 | 是；阻断 REAL-AI-01 和全部公开 AI 能力 |
| 建议负责 Agent | AIAgent开发工程师Agent；架构师Agent评审外发数据模型 |

复现步骤：

1. 使用第 7 节任一文本构造 `StructuredRequest`。
2. 检查 `prompt_safety_state` 和 `user_prompt`。
3. 将请求交给任一真实 Provider 的离线客户端替身。
4. 检查 SDK 对应方法是否被调用。

实际结果：13 条均为 `allowed` 且原文保留；选定样例在三类 Provider 中均调用客户端方法。

预期结果：明确地址应 `blocked`；无门牌或低置信度位置应 `uncertain`；结构化字段别名和值必须递归失败关闭。三类状态中只有确定安全的业务数据才可为 `allowed`。

根因证据：

- `MULTILINGUAL_LOCATION_TERM_PATTERN` 仍是有限道路/住宅词枚举。
- `_contains_open_address_signature()` 要求已识别地点词，并依赖数字、邮编或分隔符数量。
- `_contains_low_confidence_location_shape()` 对拉丁文字的“一组门牌 + 一个逗号”及“道路 + 城市但无门牌”返回假。
- `ADDRESS_FIELD_NAMES` 未覆盖 `ship_to`、`delivery_location` 等地址容器别名，递归值检查又复用同一漏判规则。

建议：

- 外部 Provider 不应接收未经过任务级结构化允许列表证明安全的任意客户自由文本。
- 把结构化字段允许列表作为正向协议；未知字段、地址容器别名和自由文本默认 `uncertain`，而不是依靠地址黑名单放行。
- 如果业务必须外发客户原句，应采用经架构评审的本地 PII/DLP 能力、版本化开放集评测和可配置语言覆盖；正则只能作为纵深防御。
- 直接针对实际 Provider 请求对象验证“测试地址从未出现在 SDK 参数”，不能只断言状态枚举存在。

### DEF-REAL-AI01-003：业务语义词表和分隔符规则继续产生误报

| 项目 | 内容 |
| --- | --- |
| 优先级 | P2 |
| 类型 | 功能正确性、可用性、脱敏误报 |
| 影响范围 | 客服意图、订单请求、仓位、内部标签和运营文本 |
| 状态 | 部分修复 / Open |
| 是否阻断 | 是；与 P1 隐私缺陷共同阻断公开 AI 能力 |
| 建议负责 Agent | AIAgent开发工程师Agent |

复现步骤：

1. 使用第 8 节任一失败样例调用 `evaluate_prompt_safety()`。
2. 检查状态、原因码和脱敏后正文。

实际结果：4 条内部标签文本为 `blocked/COMPLETE_ADDRESS_DETECTED` 并丢失正文；3 条无位置证据的普通客服文本因逗号数量进入 `uncertain/LOCATION_TEXT_LOW_CONFIDENCE`。

预期结果：明确业务标签应保留正文并得到 `allowed` 或可解释的 `uncertain`；普通客服句子不能仅因两个逗号被当作位置风险。

根因证据：

- `BUSINESS_NON_ADDRESS_CONTEXT_PATTERN` 通过有限关键词识别业务语境，未覆盖 inventory、fulfillment、taxonomy、routing 等同义表达。
- `BARE_BUILDING_ADDRESS_PATTERN` 先把单元/楼座数字组合判为完整地址。
- `_contains_low_confidence_location_shape()` 的“两个分隔符 + 字母数量”条件没有要求任何位置词或定位实体。

建议：三态策略可以保留，但 `allowed/uncertain/blocked` 必须由任务级结构和位置证据决定；普通标点不能单独构成位置风险，业务同义词也不应靠持续扩大关键词表修补。

## 10. 工程、数据库和真实模型验证

### 10.1 自动化与静态检查

| 检查项 | 实际结果 | 判定 |
| --- | --- | --- |
| Provider/安全/工具/评测/配置/健康聚焦 | `194 passed`，1 个既有 warning | 通过 |
| 默认后端全量 | `662 passed, 10 skipped`，2 个既有 warning | 通过 |
| 隔离 PostgreSQL 全量 | `672 passed, 0 skipped`，2 个既有 warning | 通过 |
| Phase 4 固定安全评测 | 234 条，安全准确率与原因码准确率 100%，危险漏放 0 | 通过当前固定集 |
| `uv lock --check` | 125 个包解析成功 | 通过 |
| Ruff check | 全工程通过 | 通过 |
| Ruff format | 全工程 210 个文件；正式代码范围 208 个文件 | 通过 |
| mypy | 155 个源文件无错误 | 通过 |
| compileall | 无错误 | 通过 |
| `uv audit --locked` | 124 个包无已知漏洞或不良状态 | 通过 |
| 空库迁移 | 001→019 | 通过 |
| 迁移可逆性 | 019→018→019，最终为 head | 通过 |
| pgvector | 0.8.6 | 通过 |

两个 warning 为既有 Starlette TestClient/httpx 和 argon2 元数据弃用提示，不影响本轮判定。

固定 234 条评测未包含本轮开放集反例，因此“固定集危险漏放 0”不能推导真实地址漏放为 0。

### 10.2 真实 DeepSeek 安全合成冒烟

| 项目 | 结果 |
| --- | --- |
| 输入 | 合成英文物流问题，不含客户、地址、订单或平台凭证 |
| DLP 状态 / 版本 | `allowed` / `prompt-dlp-v1.0.0` |
| Provider / 模型 | `deepseek` / `deepseek-v4-flash` |
| 调用结果 | 成功，Schema 通过 |
| 意图 / 状态 | `logistics_query` / `classified` |
| Token | 输入 66，输出 24 |
| 完整非流式耗时 | 2969 ms |
| Provider Request ID | 存在，未记录原值 |

该结果只证明安全合成输入的最小非流式链路可用，不代表隐私开放集、回复质量、翻译、营销、SSE 或稳定性通过。本轮没有向真实模型发送任何地址反例。

## 11. 验收判定与后续门禁

| 验收项 | 结果 |
| --- | --- |
| Provider 工程、结构化输出和错误契约 | 通过 |
| 三态模型及非 allowed SDK 零调用 | 通过 |
| 完整地址和低置信度位置不进入 allowed | **失败** |
| 合法业务文本不过度阻断 | **失败** |
| 日志和 Trace 安全回归 | 通过 |
| 全量、数据库、迁移、依赖审计 | 通过 |
| REAL-AI-01 | **不通过** |

在测试工程师独立关闭 `DEF-REAL-AI01-001/003` 前，必须保持：

```text
LLM 对外公开回复关闭
生产翻译关闭
AI 营销内容发送关闭
自动回复关闭
真实高风险平台写操作关闭
```

重新申请第七次复测前，至少需要：

1. 由架构师确认“哪些任务级字段可以外发”以及自由文本的默认处理，不再用地址黑名单证明安全。
2. 修复字段别名和嵌套结构绕过，未知结构默认拒绝。
3. 修复无门牌、无邮编、未知道路命名和单分隔符地址漏放。
4. 修复内部标签同义表达被 `blocked` 及普通多逗号文本被错误降级的问题。
5. 对三类 Provider 直接断言地址反例不会进入 SDK 参数。
6. 重新执行独立开放集、全量回归、数据库、迁移、依赖审计、固定评测和安全合成真实模型冒烟。

## 12. 执行证据与清理

主要命令：

```text
uv lock --check
uv run ruff check .
uv run ruff format --check .
uv run mypy app scripts
uv run python -m compileall -q app scripts
uv run pytest tests/test_agent_domain.py tests/test_agent_tool_execution.py tests/test_agent_providers.py tests/test_agent_evaluation.py tests/test_real_runtime_config.py tests/test_health.py -q
uv run pytest -q
uv audit --locked
uv run python scripts/evaluate_phase4.py --dataset evals/agent-phase4-v1.0.0.jsonl --output <temporary-output>
uv run alembic upgrade head
uv run alembic current
uv run alembic downgrade -1
uv run alembic upgrade head
```

- 隔离 PostgreSQL 使用 `pgvector/pgvector:pg16`、`127.0.0.1:55438` 和 tmpfs。
- 测试后已精确删除临时容器、pytest 临时目录和固定评测临时 JSON。
- 真实模型证据未记录 API Key、完整 Prompt、原始响应或 Provider Request ID。
- 未修改产品代码、开发测试、Prompt、评测集、依赖锁、迁移或历史报告。
- 本轮正式变更仅为本报告和 `共享记忆文档/测试报告索引.md`。
