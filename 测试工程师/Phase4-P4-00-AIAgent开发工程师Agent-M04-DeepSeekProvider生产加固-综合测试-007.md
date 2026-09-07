# Phase 4 REAL-AI-01 DeepSeek Provider 生产加固第七次独立综合测试报告

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
| 关联实施记录 | `共享记忆文档/实施记录/Phase4-P4-00-AIAgent开发工程师Agent-DeepSeekProvider第六次测试缺陷修复-007.md` |
| 测试类型 | 综合测试、修复验证、真实模型冒烟、回归测试、数据库测试、安全测试、代码审查 |
| 执行日期 | 2026-08-27 |
| 测试结论 | **不通过** |

## 2. 最终结论

第六轮修复将策略升级为 `prompt-dlp-v1.1.0`，把外发条件收紧为唯一的 Provider 工程控制协议。006 报告固定的 13 条地址已全部不再进入 `allowed`；本轮新增的 8 条地址/位置文本也全部失败关闭。006 报告中的内部标签误脱敏已修复，本轮 4 条新合法业务文本均保留正文并以 `uncertain` 进入本地人工路径。因此：

- `DEF-REAL-AI01-003` 本轮关闭。
- `DEF-REAL-AI01-002/004` 保持关闭。

但第七次独立测试发现正向协议和最终请求边界仍可被绕过：

1. Python `json.loads()` 会把重复 JSON 键折叠为最后一个值。3 条重复键探针中有 2 条被判定为 `allowed`，原始载荷中的合成完整地址仍被保留；选定样例在 DeepSeek、OpenAI、Anthropic 三类 Provider 中均进入 SDK 方法。
2. `StructuredRequest` 只检查 `user_prompt`，未检查同样会发送给供应商的 `system_prompt`。当 `user_prompt` 为合法控制载荷、`system_prompt` 含合成完整地址时，三类 Provider 均进入 SDK 方法。代码中的店铺 `brand_name` 会拼接到系统 Prompt，而其当前校验仅限制长度和控制字符，因此该入口不是纯理论接口误用。

据此：

- `DEF-REAL-AI01-001` 保持 **P1 / 部分修复 / Open**。
- 新增 `DEF-REAL-AI01-005`：重复 JSON 键绕过正向协议，**P1 / Open**。
- 新增 `DEF-REAL-AI01-006`：`system_prompt` 未纳入外发安全边界，**P1 / Open**。

235 项开发聚焦、703 项默认全量、713 项隔离 PostgreSQL 全量、234 条固定安全评测、静态质量、迁移和依赖审计均通过；一次不含客户数据的真实 DeepSeek 控制协议调用成功。这些工程证据不能覆盖两条独立隐私外发反例。

`REAL-AI-01` 继续不通过。公开 AI 回复、生产翻译、AI 营销、自动回复和真实高风险平台写操作不得放行。

## 3. 测试依据、范围与风险门禁

### 3.1 测试依据

- `AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md`
- `架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`
- `架构师/PLAN-001-REAL-真实平台与AI生产环境接入实施计划-v1.0.md`
- `共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md`
- `共享记忆文档/智能客服平台 — 管理端接口文档.md` 第 11.10 节
- `共享记忆文档/开发任务拆解（按人天分配）.md`
- `共享记忆文档/项目团队职责说明.md`
- `共享记忆文档/MVP范围与验收标准.md`
- `共享记忆文档/代码编写手册.md`
- `测试工程师/测试报告命名规范.md`
- `测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-DeepSeekProvider生产加固-综合测试-006.md`
- 本项目全部 `AGENTS.md`
- `开发工具/skills/agent-engineering-handbook--independent-verification/SKILL.md`
- `开发工具/skills/addyosmani-agent-skills--security-and-hardening/SKILL.md`

### 3.2 测试范围

1. 006 报告 13 条开放地址、4 条内部标签和4 条普通文本修复回归。
2. `prompt-dlp-v1.1.0` 正向协议、三态结果、稳定原因码和非 `allowed` SDK 零调用。
3. 未进入开发测试的新国际地址、无门牌位置、未知结构化别名和嵌套数组。
4. 未进入开发测试的新内部标签、普通中英文客服文本及正文保留。
5. JSON 重复键、后值覆盖、原始载荷保留及三类 Provider 最终客户端路径。
6. `system_prompt` 与 `user_prompt` 的完整外发边界，以及动态品牌名进入系统 Prompt 的代码路径。
7. 既有日志低敏字段、错误映射、配置、健康检查和 Provider 回归。
8. 静态质量、默认与隔离数据库全量测试、迁移、固定评测、锁文件和依赖审计。
9. 一个无客户数据的真实 DeepSeek 非流式控制协议最小调用。

### 3.3 非目标

- `REAL-AI-02～05` 的结构化业务声明、回复、翻译、营销和真实模型质量评测。
- 公开 SSE 50 客户端、首分块、P95/P99、五日稳定性和 99.5% 可用性。
- 真实 TikTok 联调、任何平台写操作或真实客户消息调用。
- 修改产品代码、开发测试、Prompt、评测集、依赖、迁移或历史测试报告。

### 3.4 风险和独立性

本任务涉及客户位置数据向外部 LLM 传输，风险等级为高。确定性检查、开放集反例、异主体复核和人工生产放行均为强制门禁。

- 本轮使用未进入开发测试的新样例和重复键变形，直接检查最终 `StructuredRequest` 和三类离线 Trap 客户端。
- 地址探针均为合成数据；未把地址、客户文本或测试攻击载荷发送给真实 DeepSeek。
- 测试前后重新计算关键产品文件 SHA-256，结果一致。
- 项目不是 Git 仓库，无法绑定提交 SHA、树对象和 diff 哈希，不能声称验证了不可变发布目标。
- 测试与开发使用同一模型家族，独立性等级只能记录为“同模型家族、新会话、新样例和只读验证”，不能替代异模型或人类安全负责人审批。

## 4. 测试环境与待测快照

### 4.1 环境

| 项目 | 值 |
| --- | --- |
| 操作系统 | Windows 10.0.19045 |
| Python | 3.11.15 |
| uv | 0.12.3 |
| Docker Client/Server | 29.7.2 / 29.7.2 |
| PostgreSQL | `pgvector/pgvector:pg16` 临时容器 |
| pgvector | 0.8.6 |
| 数据库迁移 head | `019_tiktok_channel_unique` |
| 真实模型 | DeepSeek `deepseek-v4-flash`；仅无客户数据控制协议冒烟 |

### 4.2 待测快照

| 文件 | SHA-256 |
| --- | --- |
| `backend/app/agent/security.py` | `C5A8C38006DC910A9DCCDC00555DB8DA6C156647EF6A9CC03C29707B35006C11` |
| `backend/app/agent/providers/base.py` | `278757B3244B546032560F4D671DB9FD5EF908135EF3444FAA8A9E1A15BF7207` |
| `backend/app/agent/providers/deepseek_provider.py` | `7437870E013EF24F28E385A69E97B0D0AAB5383681FC86604478749FE5C5D689` |
| `backend/app/agent/providers/openai_provider.py` | `652274A3D8991CB2A21A6E500533EBA6E3C1D796A5C9A0B1406724510CF8845E` |
| `backend/app/agent/providers/anthropic_provider.py` | `039C8202D2B389D9D430ADC1348D124155783F414D8FE9D319F23CF2D38C2300` |
| `backend/app/shared/logging/setup.py` | `AB0B1B537DCC6AC04885CFE3F485D168B1E4987A2A94404898362934F48FA500` |
| `backend/tests/test_agent_domain.py` | `E3914CDFADD63A6F3A50E57BBD68AC8F88145F641EE0CBF08DF8FE3DB4ADB582` |
| `backend/tests/test_agent_providers.py` | `DC413CCB726431476C92EA2A50A88F06D3724BFFA9D24D0224E4BF3C92484AAE` |
| `backend/tests/test_real_runtime_config.py` | `773B710C074B106E50B0137BEA3E43666D7A5AF4788B0DE1311204E7515C075D` |
| `backend/uv.lock` | `3AD5B450855EC7684EA0DD2C2361B5A2E663A5A51050C3DCBA96FB79C69B6172` |

测试后上述哈希全部一致。临时探针、评测 JSON 和 PostgreSQL 容器均已精确清理。

## 5. 缺陷状态汇总

| 缺陷编号 | 优先级 | 本轮状态 | 结论 |
| --- | --- | --- | --- |
| `DEF-REAL-AI01-001` | P1 | 部分修复 / Open | 普通自由文本已失败关闭，但正向协议重复键和未检查的系统 Prompt 仍可携带完整地址进入 Provider |
| `DEF-REAL-AI01-002` | P1 | Closed | Trace、Provider Request ID 摘要和日志正文保护未回退 |
| `DEF-REAL-AI01-003` | P2 | **Closed** | 新旧内部标签和普通业务文本均保留正文并进入明确的本地人工路径，不再被错误整段替换 |
| `DEF-REAL-AI01-004` | P2 | Closed | UUID Trace ID 关联未回退 |
| `DEF-REAL-AI01-005` | P1 | **Open / 新增** | JSON 重复键被后值覆盖后通过正向协议，原始敏感值仍随请求发送 |
| `DEF-REAL-AI01-006` | P1 | **Open / 新增** | `system_prompt` 未纳入安全判定，但三类 Provider 都会发送该字段 |

## 6. 修复项回归

### 6.1 通过项

- 006 报告 13 条地址均不再进入 `allowed`。
- 006 报告 4 条内部标签均保留正文并进入 `uncertain`。
- 006 报告 4 条普通文本均以 `UNTRUSTED_FREE_TEXT_REQUIRES_DLP` 失败关闭。
- 8 条本轮新地址、无门牌位置及未知字段 JSON 均不为 `allowed`。
- 4 条本轮新合法业务文本均保留原文，状态为 `uncertain`，原因码为 `UNTRUSTED_FREE_TEXT_REQUIRES_DLP`。
- 对正常的 `blocked/uncertain` 用户 Prompt，三类 Provider 的共同门禁和既有 SDK 零调用测试未回退。
- Provider 成功/失败日志继续只保留低敏状态、策略版本、原因码和规范追踪字段。

### 6.2 结论边界

“普通自由文本默认 `uncertain`”关闭了 006 报告中的地址开放集和业务误脱敏根因，但不能证明唯一 `allowed` 协议不可被构造绕过，也不能覆盖请求的其他外发字段。只有对整个供应商请求信封做正向验证，才可称为最终外发门禁。

## 7. 独立开放集结果

### 7.1 新地址与结构化位置

本轮共 8 条合成样例，覆盖新道路命名、无门牌位置、阿拉伯文/西里尔文和未知结构化字段。结果：`8/8` 不为 `allowed`，通过。

代表样例：

- `Laugavegur 28, Reykjavík`
- `Kärntner Straße 12, Wien`
- `Rua Augusta 150, Lisboa`
- `Orchard Road Singapore`
- `ул. Арбат Москва`
- `شارع التحلية الرياض`
- `recipient_location` 字段别名
- 列表中的 `dropoff` 嵌套字段

### 7.2 新合法业务文本

4 条内部标签、报表、中文订单请求和政策页面文本均为 `uncertain`，正文原样保留且原因码正确，`4/4` 通过。该结果表示它们可以进入本地人工路径，不表示允许发送给外部模型。

### 7.3 重复键正向协议绕过

| 载荷变形 | 实际状态 | SDK 路径 | 判定 |
| --- | --- | --- | --- |
| 第一个 `operation` 为合成地址，第二个为合法枚举 | `allowed` | 三类 Provider 均调用 | 失败 |
| 第一个 `schema_version` 为合成地址，第二个为 `1` | `allowed` | 未重复网络验证；状态已足以阻断 | 失败 |
| 第一个 `language` 为带 `Road` 的位置，第二个为 `en` | `blocked` | 未调用 | 通过；由纵深地址词规则偶然阻断 |

统计：2/3 重复键载荷绕过正向协议；选定样例在 DeepSeek、OpenAI、Anthropic 三类 Provider 中均调用离线 Trap 客户端方法。Trap 随即抛错，不产生网络请求。

根因证据：

- `backend/app/agent/security.py:255` 使用默认 `json.loads()`，重复键按最后值覆盖。
- `backend/app/agent/security.py:270` 只检查折叠后的 `set(payload)`，无法知道原始载荷出现过重复键。
- 通过后 `sanitized_text` 仍是原始字符串，因此被覆盖的第一份敏感值没有被删除。

### 7.4 `system_prompt` 外发绕过

使用合法控制 `user_prompt` 和含合成完整地址的 `system_prompt`：

| Provider | 用户 Prompt 状态 | 系统 Prompt 是否进入 SDK | 判定 |
| --- | --- | --- | --- |
| DeepSeek | `allowed` | 是 | 失败 |
| OpenAI | `allowed` | 是 | 失败 |
| Anthropic | `allowed` | 是 | 失败 |

根因证据：

- `backend/app/agent/providers/base.py:33` 仅对 `self.user_prompt` 调用安全判定。
- `backend/app/agent/providers/deepseek_provider.py:108`、`openai_provider.py:55`、`anthropic_provider.py:56` 均把 `request.system_prompt` 发送给供应商。
- `backend/app/agent/reply_policy.py:48-58` 的 `brand_name` 只限制长度和控制字符。
- `backend/app/agent/workflow_prompt.py:56-67` 会把 `brand_name` 拼接到系统 Prompt。

## 8. 自动化、数据库、迁移与真实模型证据

| 验证项 | 结果 | 结论 |
| --- | --- | --- |
| 独立临时探针 | 21 项：13 passed、8 failed | 失败；定位两类 P1 绕过 |
| Provider/安全聚焦 | 235 passed，1 个既有 warning | 通过 |
| 默认后端全量 | 703 passed、10 skipped，2 个既有 warning | 通过；跳过项为未提供隔离 DB |
| 隔离 PostgreSQL 全量 | 713 passed，0 skipped，2 个既有 warning | 通过 |
| Ruff | All checks passed | 通过 |
| Ruff Format | 211 files already formatted（执行时包含临时探针） | 通过 |
| mypy | 155 个源文件无错误 | 通过 |
| compileall | 通过 | 通过 |
| `uv lock --check` | 125 个包解析成功 | 通过 |
| `uv audit --locked` | 124 个包无已知漏洞或不良状态 | 通过 |
| 固定安全评测 | 234 条；安全与原因码准确率 100%，危险漏放 0 | 通过；不覆盖独立变形 |
| 空库迁移 | `001→019` | 通过 |
| 最新迁移回滚 | `019→018→019`，最终为 head | 通过 |
| pgvector | 0.8.6 | 通过 |
| 真实 DeepSeek 控制协议 | `deepseek-v4-flash`，61/17 Token，2346ms，结构化输出成功 | 通过；仅 Provider 冒烟 |

两个 warning 为既有 Starlette TestClient/httpx 和 argon2 元数据弃用提示。固定评测第一次误用直接脚本路径导致 `app` 无法导入，改用项目规定的模块命令后 234 条通过；该命令修正不属于产品缺陷。

真实 DeepSeek 调用仅发送固定工程控制载荷和固定系统指令，未发送地址、客户文本、Token、密钥、Provider Request ID 或模型原始响应。该结果不能证明真实回复、翻译、营销质量、SSE 性能或五日稳定性。

## 9. 缺陷详情

### DEF-REAL-AI01-005：JSON 重复键绕过 Provider 正向协议

| 项目 | 内容 |
| --- | --- |
| 优先级 | P1 |
| 类型 | 隐私、安全、数据出境、输入解析歧义 |
| 影响范围 | DeepSeek、OpenAI、Anthropic 及所有复用 `StructuredRequest` 的外部模型调用 |
| 状态 | Open |
| 是否阻断 | 是；阻断 REAL-AI-01 和全部公开 AI 能力 |
| 建议负责 Agent | AIAgent开发工程师Agent；架构师Agent评审正向协议序列化边界 |

复现步骤：

1. 构造包含两个同名 `operation` 字段的 JSON；第一个值放合成地址，第二个值为 `provider_contract_check`。
2. 其余字段设置为合法 `schema_version=1` 和 `language=en`。
3. 调用 `evaluate_prompt_safety()` 或构造 `StructuredRequest`。
4. 将请求传给任一 Provider 的离线 Trap 客户端。

实际结果：状态为 `allowed`，`sanitized_text` 保留完整原始载荷，三类 Provider 都进入 SDK。

预期结果：重复键属于解析歧义，必须失败关闭；即使验证成功，也只能发送由已验证对象重新序列化的规范控制载荷，不能发送原始字符串。

建议修复：

- JSON 解析使用 `object_pairs_hook` 或等价机制拒绝任意层级重复键。
- 正向协议验证通过后，以固定字段顺序重新序列化可信 DTO，禁止复用原始文本。
- 将重复键、Unicode 转义、空白、字段顺序和嵌套重复键加入独立回归。

### DEF-REAL-AI01-006：系统 Prompt 未纳入最终外发安全边界

| 项目 | 内容 |
| --- | --- |
| 优先级 | P1 |
| 类型 | 隐私、安全、信任边界不完整 |
| 影响范围 | DeepSeek、OpenAI、Anthropic；动态品牌配置和未来系统 Prompt 组合器 |
| 状态 | Open |
| 是否阻断 | 是；阻断 REAL-AI-01 和全部公开 AI 能力 |
| 建议负责 Agent | AIAgent开发工程师Agent；架构师Agent评审系统 Prompt 信任模型 |

复现步骤：

1. 构造合法工程控制 `user_prompt`。
2. 在 `system_prompt` 中放入合成完整地址。
3. 调用 DeepSeek、OpenAI、Anthropic 任一 Provider 的离线 Trap 客户端。
4. 检查客户端是否被调用及其参数。

实际结果：`user_prompt` 为 `allowed`，三类客户端均收到未检查的 `system_prompt`。

预期结果：最终外发门禁必须覆盖供应商请求中的所有文本字段。系统 Prompt 应来自版本化、不可变的可信注册表；动态店铺配置不得通过字符串拼接绕过数据分类和最小化。

建议修复：

- 将固定系统 Prompt 改为受控 `prompt_id/version/hash` 注册表，不接受任意字符串作为可信系统指令。
- 将 `brand_name` 等动态值作为独立、强类型、经过本地 DLP 的数据字段处理，不直接拼入系统层。
- 在 Provider 调用前验证完整外发信封，并增加各字段来源和低敏摘要审计。

## 10. 执行命令与清理

主要命令：

```text
uv run pytest .tmp/real-ai01-007/test_independent_provider_boundary.py -q
uv run ruff check .
uv run ruff format --check .
uv run mypy app scripts
uv run python -m compileall -q app scripts
uv run pytest tests/test_agent_domain.py tests/test_agent_tool_execution.py tests/test_agent_providers.py tests/test_agent_evaluation.py tests/test_real_runtime_config.py tests/test_health.py -q
uv run pytest -q
uv lock --check
uv audit --locked
uv run python -m scripts.evaluate_phase4 --dataset evals/agent-phase4-v1.0.0.jsonl --output <temporary-output>
uv run alembic upgrade head
uv run alembic current
uv run alembic downgrade -1
uv run alembic upgrade head
```

清理结果：

- 临时容器 `crm-real-ai01-007-postgres` 已删除；数据库使用 tmpfs，不含业务数据。
- 临时探针、`__pycache__` 和固定评测临时 JSON 已删除。
- 未修改产品代码、开发测试、Prompt、评测集、锁文件、迁移或历史报告。

## 11. 验收建议

当前不建议验收 `REAL-AI-01`，也不建议进入公开回复、生产翻译、AI 营销或自动回复阶段。再次复测前至少完成：

1. 关闭 `DEF-REAL-AI01-005`，拒绝重复键并只发送规范化后的控制 DTO。
2. 关闭 `DEF-REAL-AI01-006`，把系统 Prompt 和所有动态系统层数据纳入最终外发信封门禁。
3. 保持 `DEF-REAL-AI01-002/003/004` 已关闭状态，继续验证三类 Provider 对所有非 `allowed` 状态零 SDK 调用。
4. 重新执行开放集、235 项聚焦、713 项隔离数据库全量、234 条固定评测、迁移和依赖审计。
5. 建立 Git 或等价不可变发布基线，并由异模型/异主体和人类安全负责人完成高风险生产放行。

在上述 P1 缺陷关闭前，即使安全控制载荷真实调用成功，也不得把 `REAL-AI-01` 标记为通过。
