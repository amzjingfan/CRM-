# Phase 4 REAL-AI-01 M04 DeepSeek Provider 生产加固第三次修复后综合复测报告

## 1. 测试基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 `REAL-AI-01` |
| 模块编号 | M04 |
| 模块名称 | DeepSeek Provider 生产加固 |
| 被测主责 Agent | AIAgent开发工程师Agent |
| 被测协作 Agent | 架构师Agent、全栈开发工程师Agent |
| 测试执行 Agent | 测试工程师Agent |
| 关联实施记录 | `共享记忆文档/实施记录/Phase4-P4-00-AIAgent开发工程师Agent-DeepSeekProvider第三次测试缺陷修复-004.md` |
| 直接复测基线 | `测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-DeepSeekProvider生产加固-综合测试-003.md` |
| 测试类型 | 综合测试、修复验证、真实模型冒烟、回归测试、数据库测试、安全测试、代码审查 |
| 执行日期 | 2026-08-26 |
| 测试结论 | **不通过 REAL-AI-01 独立验收**；`DEF-REAL-AI01-001/003/004` 均为部分修复/Open，`DEF-REAL-AI01-002` 保持 Closed |

开发侧已经关闭 003 报告中的固定样例，并完成应用主要运行路径的 UUID Trace ID 迁移；但未进入开发测试的国际完整地址和合法业务负例仍失败，真实意图评测脚本也仍产生不可关联的非 UUID Trace ID。因此，公开 AI 回复、生产翻译、AI 营销和自动回复继续禁止放行。

## 2. 测试依据、目标与边界

### 2.1 测试依据

- 项目根目录、测试工程师、AIAgent 开发工程师、全栈开发工程师、架构师、共享记忆、开发工具和代码目录中的全部适用 `AGENTS.md`。
- `共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md`、`MVP范围与验收标准.md`、管理端接口文档、任务拆解、团队职责和代码编写手册。
- `AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md` 中 `REAL-AI-01`。
- `架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md` 和系统总体架构设计。
- DeepSeek Provider 003 号报告中的 `DEF-REAL-AI01-001/003/004` 复现、放行与回归要求。
- 最新实施记录声明的国际地址、合法业务负例和内部 Trace ID 生产者修复。
- `security-and-hardening`、`independent-verification` 和 `ponytail` Skill。安全 Skill 要求将外部 LLM 视为第三方信任边界并最小化 PII；最小实现原则不得削弱安全门禁。

### 2.2 风险分类与门禁

本轮涉及客户地址向外部模型供应商传输，风险等级为高风险隐私和生产数据出境变更。要求：

1. 先执行静态检查、锁文件审计、开发聚焦测试、全量回归、真实 PostgreSQL、迁移和固定安全评测。
2. 再使用未进入开发测试的独立正例和负例寻找反例。
3. 任何完整地址仍可出境均阻断通过。
4. 本测试 Agent 只提供建议性测试结论；生产发布仍要求架构师和人工责任人审批。

### 2.3 复测目标

1. 验证 003 号报告中的香港、英文拼写门牌、Rural Route 地址已在最终 `StructuredRequest` 边界被阻断。
2. 使用新的欧洲、香港和日本地址形式验证修复是否建立通用安全边界，而非仅补充已知正则。
3. 验证消费券、商品规格、物流中转站等 003 固定负例已恢复，并增加含数字的客服队列、工单和人工复核语句。
4. 验证应用、Webhook、营销和各 Worker 使用规范 UUID，日志字段安全规则不回退。
5. 验证真实模型评测入口的 Trace ID 同样可关联。
6. 验证 Provider 结构化输出、错误分类、有限重试、取消、工具白名单和字段级日志摘要无退化。
7. 使用无客户数据的合成请求重新执行一次真实 DeepSeek 最小调用。

### 2.4 非目标

- 不修改产品代码、开发测试、Prompt、固定评测集、依赖锁或历史报告。
- 不执行真实 TikTok 写操作、公开回复、生产翻译或营销发送。
- 不把一次真实模型冒烟视为 `REAL-AI-05` 正式质量评测。
- 不执行 SSE 50 个授权客户端、首分块/P99 或五日稳定性测试。
- 不验收 REAL-AI-02～05 的完整交付。

## 3. 被测快照与独立性

项目代码目录仍不是 Git 仓库，无法绑定不可变提交。本轮执行前后均按相同顺序核对 14 个 Provider、安全、日志、运行入口、开发测试和锁文件，组合 SHA-256 为：

```text
66248174b15ccac336465608ca2ea1f7d6ba7ce4b13ee107b19a62dd1a37d1fa
```

关键文件摘要：

| 文件 | SHA-256 |
| --- | --- |
| `CRM智能聊天系统/backend/app/agent/security.py` | `83209A530BD0B0EF60CF042AD2DB9069D721198301782F7177DC7A92248C14CD` |
| `CRM智能聊天系统/backend/app/agent/workflow_prompt.py` | `FE256606DA45DE41524B6083E44BC3449F29B61F213DA32E5F795FD8D1DB9AEC` |
| `CRM智能聊天系统/backend/app/agent/providers/base.py` | `EC8C3B9E0E148596300EB021C3BB3EDDCF75F9853BEC99EE597418BF58F25B2E` |
| `CRM智能聊天系统/backend/app/agent/providers/deepseek_provider.py` | `33C3A5BD6FC9EFAC972C2F49E5F00C56D57A0731E35BB5F1FF3F876580816083` |
| `CRM智能聊天系统/backend/app/shared/logging/setup.py` | `7E5B484EDF6A391F185D451BF49557F2DE7005F5DA22B8644ADB4711413F2553` |
| `CRM智能聊天系统/backend/app/main.py` | `BA85B24E507F408CDD041D11DE09D121AB1A6299ECD5EB9FB3A906EBD887ED21` |
| `CRM智能聊天系统/backend/app/integrations/service.py` | `3905B19BA54A15F7AD979AA7287BFE7A311C16D728DF659959A5DDD30796D592` |
| `CRM智能聊天系统/backend/app/integrations/worker.py` | `1AFAC13AD1FA10E64A69B203D2042210A009949EE3484E147B7A215A66431C81` |
| `CRM智能聊天系统/backend/app/jobs/worker.py` | `A75822928E530CCE54E69CA0C19F34CA9B7FC79E8969F10D0BC75EB33B089050` |
| `CRM智能聊天系统/backend/app/chat/worker.py` | `D90EB3EA80CA9C523E796F3F54532C70B41D7F824135CBA5D21673BCC542128B` |
| `CRM智能聊天系统/backend/app/marketing/worker.py` | `35AD7F19783210DEE31A60E5659D39A5C609EE271BD49CF79FE775F40BDE3AF4` |
| `CRM智能聊天系统/backend/uv.lock` | `3AD5B450855EC7684EA0DD2C2361B5A2E663A5A51050C3DCBA96FB79C69B6172` |

独立性说明：本轮重新执行确定性门禁，并使用未写入开发测试和固定评测集的新样例。由于当前目标是可变工作区、无 Git 提交，且测试者仍属于同一 Codex 模型家族，本报告不宣称满足异组织、异模型或签名制品级独立验证。后续产品代码、需求、策略或测试证据发生变化时，本结论立即失效。

## 4. 测试环境

| 项目 | 实际环境 |
| --- | --- |
| 操作系统 | Windows 10.0.19045，Asia/Shanghai |
| PowerShell | 7.6.4 |
| Python | 3.11.15 |
| uv | 0.12.3 |
| Docker Client / Server | 29.7.2 / 29.7.2 |
| Docker Compose | v5.3.1 |
| 隔离 PostgreSQL | `pgvector/pgvector:pg16`，宿主端口 55436，数据目录为 tmpfs |
| 数据库迁移 | `019_tiktok_channel_unique (head)` |
| 真实模型 | DeepSeek 已配置；只执行合成物流查询，不输出 Key、完整 Prompt、原始响应或请求 ID |
| 本地开关观察 | development：LLM 与 live eval 为 true，自动回复和营销为 false，翻译为 true；生产模板仍要求关闭公开能力 |

本地开发翻译开关不是生产放行证据，生产环境必须继续保持公开回复、翻译、营销和自动回复关闭。

## 5. 缺陷状态汇总

| 缺陷编号 | 优先级 | 本轮状态 | 结论 |
| --- | --- | --- | --- |
| `DEF-REAL-AI01-001` | **P1** | 部分修复 / Open | 003 固定地址样例通过；5 种新的国际裸地址仍完整进入 Provider 请求 |
| `DEF-REAL-AI01-002` | P1 | **Closed** | UUID-only 日志字段和 Provider Request ID 摘要均未回退 |
| `DEF-REAL-AI01-003` | P2 | 部分修复 / Open | 003 固定合法文本通过；4 条含数字的合法转交/工单消息仍被整体误脱敏 |
| `DEF-REAL-AI01-004` | P2 | 部分修复 / Open | 应用主要运行路径已迁移 UUID；真实意图评测脚本仍生成 `live-eval-*` 非 UUID Trace ID |

## 6. 确定性验证结果

### 6.1 工程、回归和依赖门禁

| 检查项 | 实际结果 | 判定 |
| --- | --- | --- |
| Provider/安全/工具/配置/健康聚焦 | `148 passed`，1 个既有 warning | 通过 |
| 默认后端全量 | `620 passed, 10 skipped`，2 个既有 warning | 通过 |
| 隔离 PostgreSQL 全量 | `630 passed, 0 skipped`，2 个既有 warning | 通过 |
| Phase 4 固定安全评测 | 234 条；安全准确率和原因码准确率 100%，危险漏放 0 | 通过当前固定集 |
| Ruff | All checks passed | 通过 |
| Ruff format | 210 个文件符合格式 | 通过 |
| mypy | 155 个源文件无错误 | 通过 |
| compileall | 无错误 | 通过 |
| `uv lock --check` | 125 个包解析成功 | 通过 |
| `uv audit --locked` | 124 个包，无已知漏洞或不良状态 | 通过 |
| 空库 Alembic | 001→019 | 通过 |
| 当前迁移可逆性 | 019→018→019，最终为 head | 通过 |

两个既有 warning 为 Starlette TestClient/httpx 弃用提示和 argon2 版本元数据弃用提示，不影响本轮缺陷判定。

### 6.2 真实 DeepSeek 最小冒烟

| 项目 | 结果 |
| --- | --- |
| 输入 | 合成英文物流问题，不含真实客户、地址、订单或平台凭证 |
| 调用结果 | 成功 |
| Schema | 通过 |
| 意图 / 状态 | `logistics_query` / `classified` |
| Provider Request ID | 存在；未记录原值 |
| Token | 输入 539，输出 19 |
| 完整非流式耗时 | 2481 ms |

本数据只证明当前快照的最小非流式成功链路，不代表 SSE 首分块、P95/P99、模型质量或五日稳定性。

## 7. 修复样例和独立用例

### 7.1 003 固定样例回归

| 场景 | 实际结果 | 判定 |
| --- | --- | --- |
| 香港九龙弥敦道地址 | 整体变为 `[ADDRESS]` | 通过 |
| One Microsoft Way | 整体变为 `[ADDRESS]` | 通过 |
| Rural Route 2 Box 152 | 整体变为 `[ADDRESS]` | 通过 |
| 上海市第 1 号消费券 | 保留 | 通过 |
| 公寓模型 1 号/2 号规格 | 保留 | 通过 |
| 北京市中转站 12 号分拨中心 | 保留 | 通过 |
| 应用、Webhook、营销和 Worker 旧式 Trace 字面量 | 已移除并使用 UUID | 通过主要运行路径 |

### 7.2 独立完整地址正例

以下均为虚构或公开格式测试数据，不代表真实客户：

| 独立样例 | 最终 `StructuredRequest.user_prompt` | 判定 |
| --- | --- | --- |
| `Calle de Alcalá 42, 28014 Madrid` | 原样保留 | 失败 |
| `10 Rue de Rivoli, 75001 Paris` | 原样保留 | 失败 |
| `Unter den Linden 77, 10117 Berlin` | 原样保留 | 失败 |
| `Flat A, 12/F, Tower 3, Harbour City, Tsim Sha Tsui, Kowloon` | 原样保留 | 失败 |
| `東京都新宿区西新宿2丁目8-1` | 原样保留 | 失败 |

五条完整地址均没有显式“address/寄到”标签，并使用现有英文街道后缀列表之外的国际格式。客户在改地址场景中可能直接发送地址，因此不能把“没有寄送动词”视为安全证明。

### 7.3 独立合法业务负例

| 独立样例 | 实际结果 | 预期结果 |
| --- | --- | --- |
| `Please send it to Level 2 support for review.` | `[ADDRESS]` | 保留客服转交意图 |
| `Please send it to order 12345 for manual review.` | `[ADDRESS]` | 保留人工复核意图 |
| `请将问题发往2号客服队列处理。` | `[ADDRESS]` | 保留客服队列意图 |
| `请寄到3号售后工单继续处理。` | `[ADDRESS]` | 保留售后工单意图 |

当前寄送语境正则只要在有限距离内看到任意数字便整段失败关闭，因此仍会误伤包含客服层级、订单号、队列号或工单号的合法业务表达。

### 7.4 Trace ID 独立验证

| 路径 | 实际结果 | 判定 |
| --- | --- | --- |
| HTTP 请求、中间件和生命周期 | 使用规范 UUID | 通过 |
| Webhook 事件到 Agent 任务 | 复用事件 UUID | 通过 |
| Marketing 生成、发券和发送 | 复用营销事件 UUID | 通过 |
| Webhook/Jobs/Agent Worker | 进程级 UUID，事件语义单独记录 | 通过 |
| Provider Request ID | 只记录 `sha256:<digest>` | 通过 |
| `scripts/evaluate_intents.py` | 仍使用 `trace_id=f"live-eval-{case.case_id}"` | 失败 |
| 生产 `JsonFormatter` 格式化上述评测 Trace | 输出 `[INVALID_LOG_METADATA]` | 失败 |

结论：生产服务主要路径已恢复关联能力，但计划要求的真实模型评测入口仍无法通过 Trace ID 关联模型调用和评测样本，`DEF-REAL-AI01-004` 只能判定为部分修复。

## 8. 缺陷明细

### DEF-REAL-AI01-001：国际完整地址仍可绕过最终模型出境边界

| 项目 | 内容 |
| --- | --- |
| 优先级 | **P1** |
| 状态 | 部分修复 / Open |
| 类型 | 隐私、安全、数据出境 |
| 影响范围 | 意图识别、FAQ、工具解释、翻译和营销等复用 `StructuredRequest` 的外部模型调用 |
| 是否阻断 | 是；阻断 REAL-AI-01 和所有公开 AI 能力 |
| 建议负责 Agent | AIAgent开发工程师Agent；架构师Agent评审数据最小化方案 |

复现步骤：

1. 使用 7.2 任一虚构完整地址构造 `StructuredRequest`。
2. 读取完成 `__post_init__` 后的 `user_prompt`。
3. 检查地址正文是否仍存在。

实际结果：5 条国际地址全部原样保留。

预期结果：模型任务不需要完整收货位置时，完整地址不得进入外部 Provider；无法可靠识别时应失败关闭或先走受控地址数据最小化层。

根因判断：当前实现继续枚举地址语言、街道后缀和排列形式。地址格式没有封闭集合，新增正则只能关闭已知样例，不能构成稳定的 PII 出境边界。

修复建议：由架构师确认数据边界后，将改地址/收货地址等场景的原始文本在业务层标记为敏感字段，模型默认只接收“客户请求修改地址”等低敏意图标签。自由文本检测只能作为纵深防御，不应继续作为允许完整文本出境的唯一依据。

### DEF-REAL-AI01-003：含数字的合法转交和工单消息仍被误判为地址

| 项目 | 内容 |
| --- | --- |
| 优先级 | P2 |
| 状态 | 部分修复 / Open |
| 类型 | 正确性、可用性、安全规则误报 |
| 影响范围 | 客服队列、支持层级、人工复核、订单和工单语句 |
| 是否阻断 | 阻断 REAL-AI-01 完整验收 |
| 建议负责 Agent | AIAgent开发工程师Agent |

复现步骤：

1. 将 7.3 任一消息传入 `sanitize_prompt_text`。
2. 检查返回值。

实际结果：四条消息均整体变为 `[ADDRESS]`。

预期结果：合法客服路由和工单语义应保留；只有明确的客户地址实体被移除。

根因判断：寄送动词之后的数字被当作地址充分条件，没有验证数字是否属于门牌、邮编或真实地址组成。

修复建议：不要继续为具体业务词追加排除项。将敏感字段来源和业务意图分开处理；若仍保留自由文本检测，应要求地址组成证据，并建立跨语言地址正例与客服/订单/工单负例的成对门禁。

### DEF-REAL-AI01-004：真实意图评测脚本仍生成非 UUID Trace ID

| 项目 | 内容 |
| --- | --- |
| 优先级 | P2 |
| 状态 | 部分修复 / Open |
| 类型 | 可观测性、评测追踪、跨模块兼容性 |
| 影响范围 | `scripts/evaluate_intents.py` 的真实 Provider 评测日志 |
| 是否阻断 | 阻断 REAL-AI-01 完整验收；不影响已修复的在线主要路径 |
| 建议负责 Agent | AIAgent开发工程师Agent |

复现步骤：

1. 查看 `scripts/evaluate_intents.py` 构造 `ClassificationCommand` 的 Trace ID。
2. 使用生产 `JsonFormatter` 格式化 `live-eval-synthetic-001`。
3. 检查 JSON 日志中的 `trace_id`。

实际结果：输出 `[INVALID_LOG_METADATA]`，多个评测样本无法依靠 Trace ID 与 Provider 调用日志关联。

预期结果：每个真实模型评测样本使用规范 UUID Trace ID，同时通过单独的低敏样本摘要或稳定 case 字段完成关联。

修复建议：保留 UUID-only Formatter，不得放宽已关闭的日志安全门禁；评测脚本使用 `uuid.uuid5` 或 `uuid.uuid4` 生成 Trace ID，将 case 语义放入不含原始输入的独立评测结果字段。

## 9. 验收判定

| 验收项 | 判定 | 说明 |
| --- | --- | --- |
| Provider 结构化契约 | 通过 | 聚焦和全量回归无退化 |
| 工具结果白名单 | 通过 | 003 已验证，当前代码摘要未变化 |
| 日志字段级隐私门禁 | 通过 | `DEF-REAL-AI01-002` 保持 Closed |
| 003 固定地址和合法文本 | 通过 | 开发修复样例已关闭 |
| Provider 最终 PII 边界 | **不通过** | 5 条独立国际完整地址原样出境 |
| 脱敏正确性 | 不通过 | 4 条独立合法业务文本被整体误删 |
| Trace ID 端到端一致性 | 不通过 | 真实意图评测入口仍使用非 UUID |
| 全量工程回归 | 通过 | 630 项隔离数据库测试、迁移和审计通过 |
| 真实模型最小成功链路 | 通过 | 单次合成非流式调用成功，不代表质量/性能门禁 |
| REAL-AI-01 独立验收 | **不通过** | 1 个 P1、2 个 P2 仍 Open |

## 10. 放行与下轮回归要求

1. `AI_PUBLIC_REPLY_ENABLED`、`AI_MARKETING_CONTENT_ENABLED`、`AI_AUTO_REPLY_ENABLED` 和生产翻译继续保持 false。
2. `DEF-REAL-AI01-001` 必须从“枚举地址正则”升级为明确的数据来源最小化和失败关闭边界，再由测试工程师使用新的多语言地址独立复测。
3. `DEF-REAL-AI01-003` 必须验证客服路由、工单、订单号、版本号、楼层级别和商品规格等含数字负例，不得只增加四条排除词。
4. `DEF-REAL-AI01-004` 修复后必须执行真实评测脚本入口或等价端到端日志测试，证明 Trace ID 是 UUID 且样本仍可低敏关联。
5. 修复不得回退 `DEF-REAL-AI01-002` 的 UUID-only 和 Provider Request ID 摘要规则。
6. 即使 REAL-AI-01 后续通过，仍需独立完成 REAL-AI-02～05、真实 SSE 50 客户端、P99、五日稳定性和架构师最终放行。

## 11. 清理与证据边界

- 隔离 PostgreSQL 容器已在删除前核对容器 ID、名称、镜像、运行状态和 tmpfs，随后删除；未触碰项目持久化数据库卷。
- pytest 临时目录和固定评测临时 JSON 已删除。
- 未修改任何产品代码、开发测试、Prompt、评测集、依赖锁、数据库迁移或历史测试报告。
- 真实模型测试未记录 API Key、完整 Prompt、原始响应或 Provider Request ID。
- 本轮正式变更只包含本报告和 `共享记忆文档/测试报告索引.md`。
