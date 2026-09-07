# Phase 4 REAL-AI-01 DeepSeek Provider 生产加固第五次独立综合测试报告

## 1. 报告信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase 4 |
| 任务编号 | P4-00；专项任务 `REAL-AI-01` |
| 模块编号 | M04 |
| 被测模块 | DeepSeek Provider 生产加固 |
| 被测主责 Agent | AIAgent开发工程师Agent |
| 测试 Agent | 测试工程师Agent |
| 测试类型 | 综合测试、修复验证、真实模型冒烟、回归测试、数据库测试、安全测试、代码审查 |
| 报告序号 | 005 |
| 测试日期 | 2026-08-26 |
| 最终结论 | **不通过** |

## 2. 测试结论摘要

本轮对 004 号报告提出的 `DEF-REAL-AI01-001/003/004` 进行第五次独立复测。开发侧新增的欧洲邮编链、住宅单元链、日本地址链和 UUID5 Trace ID 修复均已进入代码并通过既有回归；但独立多语言样例证明地址识别仍是有限格式正则，完整或足以定位客户的地址仍可穿过所有外部 Provider 共用的 `StructuredRequest` 最终边界。

结论如下：

- `DEF-REAL-AI01-002` 保持 **Closed**：日志正文和供应商请求 ID 未发现回退。
- `DEF-REAL-AI01-004` 由 **部分修复 / Open** 更新为 **Closed**：真实意图评测生成稳定规范 UUID，生产 `JsonFormatter` 可保留该标识用于关联。
- `DEF-REAL-AI01-001` 保持 **部分修复 / P1 / Open**：10 条新完整地址仅 3 条整段阻断，另 7 条完整或主要地址组成仍可进入模型请求。
- `DEF-REAL-AI01-003` 保持 **部分修复 / P2 / Open**：8 条新合法业务文本中 2 条被整段误脱敏。
- Provider 工程、166 项聚焦测试、634 项默认全量、644 项隔离 PostgreSQL 全量、234 条固定安全评测、迁移、静态质量和依赖审计通过。
- 一次无客户数据的真实 DeepSeek 合成非流式最小调用成功；该结果不代表回复质量、SSE 性能或生产稳定性通过。

`DEF-REAL-AI01-001` 命中 ADR-004 的客户完整地址禁止出境和敏感信息泄漏停止条件。因此 `REAL-AI-01` 仍不能验收，公开 AI 回复、生产翻译、AI 营销和自动回复不得放行。

## 3. 测试依据与边界

### 3.1 测试依据

- `AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md`
- `架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`
- `共享记忆文档/产品需求文档-PRD-v2.0.md`
- `共享记忆文档/管理端接口文档.md`
- `共享记忆文档/MVP范围与验收标准.md`
- `共享记忆文档/代码编写手册.md`
- `共享记忆文档/实施记录/Phase4-P4-00-AIAgent开发工程师Agent-DeepSeekProvider第四次测试缺陷修复-005.md`
- `测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-DeepSeekProvider生产加固-综合测试-004.md`
- 项目级及各一级目录全部 `AGENTS.md`

### 3.2 本轮目标

1. 复核 004 号报告的国际裸地址、合法数字业务文本和评测 Trace ID 修复。
2. 使用未进入开发测试的新国家、语言和排版形式验证修复是否解决根因。
3. 直接检查最终 `StructuredRequest.user_prompt`，不把上游调用方测试代替 Provider 边界测试。
4. 验证真实意图评测 Trace ID 的稳定性、规范 UUID 格式和最终日志可关联性。
5. 回归 Provider 结构化输出、错误映射、配置门禁、日志脱敏、工具调用和健康检查。
6. 验证锁文件、静态质量、默认及真实 PostgreSQL 全量测试、迁移与固定安全评测。
7. 在不包含客户、地址、订单、平台凭证和密钥的条件下执行一次真实 DeepSeek 最小调用。

### 3.3 非目标

- `REAL-AI-02～05` 的业务事实安全、回复、翻译、营销和版本化真实质量评测。
- 真实模型公开 SSE 50 客户端并发、首分块、P95/P99 和五日稳定性。
- 真实 TikTok 平台联调和任何平台写操作。
- 修改产品代码、开发测试、Prompt、迁移或历史测试报告。

## 4. 独立性、环境与快照

### 4.1 独立性说明

- 测试样例由测试工程师在阅读修复后重新设计，未写入开发测试集。
- 测试先冻结关键文件 SHA-256，结束后再次计算，哈希保持一致。
- 本轮未修改产品代码、开发测试、依赖锁和数据库迁移。
- 当前项目不是 Git 仓库，无法证明不可变提交、提交者隔离或从干净提交复现；本结论仅对应下列可变工作区快照。
- 测试 Agent 与开发 Agent 属于同一模型家族，因此不能声称组织意义上的完全人员独立；本轮独立性来自新样例、直接边界检查、隔离数据库和可复算证据。

### 4.2 测试环境

| 项目 | 实际环境 |
| --- | --- |
| 操作系统 | Windows，PowerShell |
| Python | 项目 `uv` 锁定环境 |
| 锁文件 | 125 个包解析成功 |
| Docker Client / Server | 29.7.2 / 29.7.2 |
| Docker Compose | v5.3.1 |
| 隔离 PostgreSQL | `pgvector/pgvector:pg16`，仅绑定 `127.0.0.1:55437`，数据目录为 tmpfs |
| pgvector | 0.8.6 |
| 数据库迁移 | `019_tiktok_channel_unique (head)` |
| 真实模型 | `deepseek-v4-flash`；仅执行一个合成非流式请求 |

### 4.3 关键快照 SHA-256

| 文件 | SHA-256 |
| --- | --- |
| `backend/app/agent/security.py` | `9013076DBD93BAEAA66851D4AED08E1B7EFF669DA3172028E5A258DF912C9E38` |
| `backend/app/agent/providers/base.py` | `EC8C3B9E0E148596300EB021C3BB3EDDCF75F9853BEC99EE597418BF58F25B2E` |
| `backend/app/agent/providers/deepseek_provider.py` | `33C3A5BD6FC9EFAC972C2F49E5F00C56D57A0731E35BB5F1FF3F876580816083` |
| `backend/app/shared/logging/setup.py` | `7E5B484EDF6A391F185D451BF49557F2DE7005F5DA22B8644ADB4711413F2553` |
| `backend/scripts/evaluate_intents.py` | `F47FA877D62AD92511DF8FFB090DD4629B1E6F5414CBE9B6E7D35D1086CBFE1D` |
| `backend/tests/test_agent_domain.py` | `4D6420563D3B2280EC9D8866861646C24EE6E1A44E34C9EA9488951089964552` |
| `backend/tests/test_agent_evaluation.py` | `BF6FEAF4643E2B0CC46FC8787A460C83D771F266491753174E583615AB0E90AC` |
| `backend/tests/test_real_runtime_config.py` | `773B710C074B106E50B0137BEA3E43666D7A5AF4788B0DE1311204E7515C075D` |
| `backend/uv.lock` | `3AD5B450855EC7684EA0DD2C2361B5A2E663A5A51050C3DCBA96FB79C69B6172` |

## 5. 缺陷状态汇总

| 缺陷编号 | 优先级 | 本轮状态 | 结论 |
| --- | --- | --- | --- |
| `DEF-REAL-AI01-001` | P1 | 部分修复 / Open | 004 固定样例已阻断；10 条新地址仅阻断 3 条，7 条仍泄漏 |
| `DEF-REAL-AI01-002` | P1 | Closed | 日志元数据白名单、UUID Trace ID 和供应商请求 ID 摘要未回退 |
| `DEF-REAL-AI01-003` | P2 | 部分修复 / Open | 004 固定负例已恢复；8 条新合法文本中 2 条仍被整段误脱敏 |
| `DEF-REAL-AI01-004` | P2 | **Closed** | 评测 Trace ID 为稳定规范 UUID，最终日志保持可关联 |

## 6. 修复回归与独立安全测试

### 6.1 004 固定样例回归

由开发测试和本轮聚焦回归共同确认：

| 场景 | 实际结果 | 判定 |
| --- | --- | --- |
| Calle de Alcalá、Rue de Rivoli、Unter den Linden、香港住宅、日本丁目及 Via Roma | 整段替换为 `[ADDRESS]` | 通过固定样例 |
| Level 2 support、order 12345、2 号客服队列、3 号售后工单 | 保留业务语义 | 通过固定样例 |
| 应用主要运行路径 UUID Trace ID | 规范 UUID | 通过 |
| 真实意图评测 Trace ID | UUID5；稳定且可由 Formatter 保留 | 通过，关闭 `DEF-REAL-AI01-004` |

### 6.2 新完整地址正例

期望：完整或足以定位客户的地址在最终 Provider 边界整段失败关闭为 `[ADDRESS]`。

| 独立样例 | 最终结果摘要 | 判定 |
| --- | --- | --- |
| `Avenida Paulista, 1578 - Bela Vista, São Paulo - SP, 01310-200` | 街道、门牌、区域、城市和州保留，仅邮编被替换 | 失败 |
| `Flat 12B, Lotus Residency, MG Road, Bengaluru 560001` | 原样保留 | 失败 |
| `Blk 123, #08-45, Orchard Road, Singapore 238888` | `[ADDRESS]` | 通过 |
| `Av. Paseo de la Reforma 222, Juárez, 06600 Ciudad de México` | 原样保留 | 失败 |
| `서울특별시 강남구 테헤란로 152, 12층` | 原样保留 | 失败 |
| `大阪府大阪市北区梅田3-1-1` | 原样保留 | 失败 |
| `1600 Amphitheatre Parkway Mountain View CA 94043` | `[ADDRESS]` | 通过 |
| `221B Baker Street London NW1 6XE` | `[ADDRESS]` | 通过 |
| `Karl-Marx-Allee 93 10243 Berlin` | 原样保留 | 失败 |
| `12 Jalan Ampang, Kuala Lumpur 50450` | 原样保留 | 失败 |

统计：`3/10` 整段阻断，`7/10` 失败。首条虽然替换了邮编，但仍保留足以识别实际位置的主要地址组成，不符合 ADR-004 的完整地址禁止出境要求。

### 6.3 新合法业务负例

期望：不包含客户地址的商品、版本、队列、仓位和工单语义应保留。

| 独立样例 | 实际结果 | 判定 |
| --- | --- | --- |
| `Avenida Paulista 1578 is the product collection code, not a delivery address.` | 保留 | 通过 |
| `Compare build 1578 with release 01310 in the incident report.` | 保留 | 通过 |
| `Flat 12B and Tower 3 are warehouse shelf labels, not customer addresses.` | `[ADDRESS]` | 失败 |
| `The Singapore 238888 campaign code should be escalated to Level 2 support.` | 保留 | 通过 |
| `订单12345和工单67890都需要人工复核。` | 保留 | 通过 |
| `大阪府活动第3期与版本1-1需要客服确认。` | 保留 | 通过 |
| `Please send order 1600 to queue 94043 for manual review.` | 保留 | 通过 |
| `Block 123 and unit 08-45 are SKU names in this catalog.` | `[ADDRESS]` | 失败 |

统计：`6/8` 正确保留，`2/8` 误拦截。

### 6.4 Trace ID 独立验证

使用未进入开发测试的 `case_id=independent-case-005` 连续生成两次评测 Trace ID：

- 生成值：`49714179-93c0-5094-9cc3-c2f63fb70405`。
- 可由 `uuid.UUID` 解析并规范化为相同字符串。
- 同一合成 case ID 两次生成结果一致。
- 生产 `JsonFormatter` 输出保持同一 Trace ID，不再替换为 `[INVALID_LOG_METADATA]`。

结论：`DEF-REAL-AI01-004` 已解决并关闭。

## 7. 工程、数据库和真实模型结果

### 7.1 工程与回归

| 检查项 | 实际结果 | 判定 |
| --- | --- | --- |
| Provider/安全/工具/评测/配置/健康聚焦 | `166 passed`，1 个既有 warning | 通过 |
| 默认后端全量 | `634 passed, 10 skipped`，2 个既有 warning | 通过 |
| 隔离 PostgreSQL 全量 | `644 passed, 0 skipped`，2 个既有 warning | 通过 |
| Phase 4 固定安全评测 | 234 条；安全准确率和原因码准确率 100%，危险漏放 0 | 通过当前固定集 |
| Ruff | All checks passed | 通过 |
| Ruff format | 210 个文件符合格式 | 通过 |
| mypy | 155 个源文件无错误 | 通过 |
| compileall | 无错误 | 通过 |
| `uv lock --check` | 125 个包解析成功 | 通过 |
| `uv audit --locked` | 124 个包，无已知漏洞或不良状态 | 通过 |
| 空库 Alembic | 001→019 | 通过 |
| 当前迁移可逆性 | 019→018→019，最终为 head | 通过 |
| pgvector | 扩展存在，版本 0.8.6 | 通过 |

两个既有 warning 为 Starlette TestClient/httpx 弃用提示和 argon2 版本元数据弃用提示，不影响本轮缺陷判定。

### 7.2 真实 DeepSeek 最小冒烟

| 项目 | 结果 |
| --- | --- |
| 输入 | 合成英文物流问题，不含客户、地址、订单、平台凭证或密钥 |
| 调用结果 | 成功 |
| Provider / 模型 | `deepseek` / `deepseek-v4-flash` |
| Schema | 通过 |
| 意图 / 状态 | `logistics_query` / `classified` |
| Provider Request ID | 存在；未记录原值 |
| Token | 输入 73，输出 24 |
| 完整非流式耗时 | 1968 ms |

该调用只证明当前快照可以完成一次最小结构化请求，不代表真实回复、翻译、营销质量、SSE 首分块、P95/P99 或五日稳定性通过。

## 8. 缺陷详情

### DEF-REAL-AI01-001：多语言完整地址仍可穿过 Provider 最终边界

| 项目 | 内容 |
| --- | --- |
| 优先级 | P1 |
| 类型 | 隐私、安全、数据出境 |
| 影响范围 | 所有复用 `StructuredRequest` 的 DeepSeek 意图、回复、翻译、FAQ、工具解释和营销调用 |
| 状态 | 部分修复 / Open |
| 是否阻断 | 是；阻断 `REAL-AI-01` 和所有公开 AI 能力 |
| 建议负责 Agent | AIAgent开发工程师Agent；架构师Agent评审数据最小化方案 |

复现步骤：

1. 使用 6.2 中任一失败样例构造 `StructuredRequest`。
2. 读取完成 `__post_init__` 后的 `user_prompt`。
3. 检查街道、门牌、行政区、城市、邮编、楼层等组成是否仍可识别或重新组合。

实际结果：巴西、印度、墨西哥、韩国、日本、德国和马来西亚等 7 条样例仍保留完整或主要地址组成。

预期结果：完整地址不得进入外部模型；最终边界应整段失败关闭，或只发送由明确允许列表产生且无法重新定位客户的结构化业务语义。

根因判断：`security.py` 仍通过有限道路词、逗号/邮编顺序、住宅关键词和日本丁目格式枚举地址。地址格式不存在可安全穷举的封闭集合，增加已知正则只能修复固定样例，不能证明“未知地址格式不会出境”。

修复建议：

- 不再把“能否由正则识别为地址”作为允许外发原始客户文本的安全证明。
- 对外部模型输入建立按任务定义的结构化字段允许列表；地址、自由文本工具结果和未知字段默认拒绝。
- 必须传递客户消息的场景，引入可版本化、可评测的本地 PII/DLP 门禁，并对未知语言或低置信度结果失败关闭或转人工。
- 建立覆盖国家、语言、顺序、标点、无邮编和无道路后缀的独立地址评测集；固定样例测试不能代替开放集风险评测。
- 在独立复测关闭前保持 `AI_PUBLIC_REPLY_ENABLED/AI_TRANSLATION_ENABLED/AI_MARKETING_CONTENT_ENABLED/AI_AUTO_REPLY_ENABLED` 对应现有服务端能力开关关闭。

### DEF-REAL-AI01-003：住宅关键词组合仍误拦截合法业务文本

| 项目 | 内容 |
| --- | --- |
| 优先级 | P2 |
| 类型 | 功能正确性、可用性、脱敏误报 |
| 影响范围 | 客服意图、仓库标签、商品规格和运营文本 |
| 状态 | 部分修复 / Open |
| 是否阻断 | 是；与 P1 地址门禁共同阻断公开 AI 能力 |
| 建议负责 Agent | AIAgent开发工程师Agent |

复现步骤：

1. 将 `Flat 12B and Tower 3 are warehouse shelf labels, not customer addresses.` 或 `Block 123 and unit 08-45 are SKU names in this catalog.` 构造为 `StructuredRequest.user_prompt`。
2. 读取最终 `user_prompt`。

实际结果：两条文本均被整体替换为 `[ADDRESS]`。

预期结果：明确为仓位或 SKU 的合法业务语义应保留；如果门禁无法可靠判断，应返回显式安全状态供业务转人工，而不是把不同业务内容静默折叠成同一地址标记。

根因判断：`BARE_BUILDING_ADDRESS_PATTERN` 仅要求住宅单元词、楼座词和任意数字同时出现，未识别否定、商品、仓库和编码语境。

修复建议：将自由文本门禁结果建模为 `allowed | blocked | uncertain` 并携带内部原因码；生产外发只接受 `allowed`，`uncertain` 转人工。地址识别和业务语义识别应由版本化策略组合，不继续依赖单条整段正则同时承担隐私召回率和业务精度。

## 9. 验收与放行判定

| 验收项 | 结果 | 说明 |
| --- | --- | --- |
| DeepSeek Provider 配置、结构化输出和错误契约 | 通过 | 聚焦及真实最小调用通过 |
| 密钥和日志边界 | 通过当前测试范围 | `DEF-REAL-AI01-002` 保持关闭 |
| 客户完整地址禁止出境 | **失败** | 10 条独立样例中 7 条失败 |
| 合法业务文本不过度脱敏 | **失败** | 8 条独立样例中 2 条失败 |
| 真实评测 Trace ID 可关联 | 通过 | `DEF-REAL-AI01-004` 关闭 |
| 全量回归、数据库、迁移和依赖审计 | 通过 | 644 项隔离数据库全量通过 |
| 真实模型最小成功链路 | 通过 | 单次非流式合成请求，不代表质量和性能 |
| REAL-AI-01 独立验收 | **不通过** | 1 个 P1、1 个 P2 仍 Open |

必须继续保持关闭：

```text
公开 AI 回复
生产翻译
AI 营销内容发送
AI 自动回复
真实高风险平台写操作
```

后续重新申请复测前，至少需要：

1. 用结构化允许列表或经架构评审的本地 PII/DLP 门禁替代“穷举地址格式即可安全外发”的假设。
2. 将本报告正例、负例加入回归，但同时补充未公开的新语言和新格式验证，避免再次只修固定样例。
3. 由架构师确认外部模型最小数据集、未知语言失败策略和人工接管路径。
4. 重新执行全量、隔离数据库、迁移、依赖审计、固定评测和无客户数据真实模型冒烟。

## 10. 执行命令与证据摘要

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

真实 DeepSeek 冒烟通过项目代码直接构造一个合成 `StructuredRequest` 并调用统一 Provider。证据中未输出 API Key、完整 Prompt、模型原始响应或 Provider Request ID 原值。

隔离 PostgreSQL 容器在测试前确认名称不存在，使用 tmpfs 启动；测试后精确删除。所有本轮 pytest 临时目录和固定评测临时 JSON 已清理。

## 11. 文件变更与测试声明

- 未修改任何产品代码、开发测试、Prompt、评测集、依赖锁、数据库迁移或历史测试报告。
- 测试前后关键产品文件 SHA-256 一致。
- 本轮正式变更仅包含本报告和 `共享记忆文档/测试报告索引.md`。
- 004 号报告继续保留历史证据，本报告作为 `REAL-AI-01` 最新权威测试结论。
