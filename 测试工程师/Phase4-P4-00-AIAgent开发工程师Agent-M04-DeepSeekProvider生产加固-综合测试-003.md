# Phase 4 REAL-AI-01 M04 DeepSeek Provider 生产加固二次修复后综合复测报告

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
| 关联实施记录 | `共享记忆文档/实施记录/Phase4-P4-00-AIAgent开发工程师Agent-DeepSeekProvider二次测试缺陷修复-003.md` |
| 直接复测基线 | `测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-DeepSeekProvider生产加固-综合测试-002.md` |
| 测试类型 | 综合测试、修复验证、真实模型冒烟、回归测试、数据库测试、安全测试、代码审查 |
| 执行日期 | 2026-08-26 |
| 测试结论 | **不通过 REAL-AI-01 独立验收**；`DEF-REAL-AI01-002` 已关闭，`DEF-REAL-AI01-001` 仍为部分修复/P1/Open，新增 `DEF-REAL-AI01-003/004`（P2/Open） |

本报告只验证当前代码及 `REAL-AI-01` 交付，不改写 001、002 号历史报告。公开 AI 回复、翻译、营销内容、自动回复和真实平台写操作仍不得据此放行。

## 2. 测试依据、目标与边界

### 2.1 测试依据

- 项目根目录、测试工程师、AIAgent 开发工程师、全栈开发工程师、架构师、共享记忆、开发工具和代码目录中的全部适用 `AGENTS.md`。
- `共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md`、`MVP范围与验收标准.md`、管理端接口文档、任务拆解、团队职责和代码编写手册。
- `AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md` 中 `REAL-AI-01`。
- `架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md` 和系统总体架构设计。
- DeepSeek Provider 002 号报告中的 `DEF-REAL-AI01-001/002`、复现样例和回归要求。
- 最新修复实施记录声明的地址最终边界、工具输出白名单和日志标识字段加固。
- `security-and-hardening`、`independent-verification` 和 `ponytail` Skill；最小实现原则不降低安全边界。

### 2.2 复测目标

1. 验证 002 号报告的中英文完整地址样例不能进入外部 Provider 请求。
2. 使用未写入开发测试的独立地址变体验证最终出境边界，而非只重放固定样例。
3. 验证工具结果按工具输出 Schema 白名单重建，契约外地址字段不能进入 Prompt。
4. 验证 Trace ID、Agent Run ID 和 Provider Request ID 的日志字段级处理不泄漏自由文本。
5. 验证 Provider JSON 输出、异常分类、有限重试、取消和 `stream=false` 契约无退化。
6. 验证全量后端、真实 PostgreSQL、迁移、固定安全评测、静态质量和依赖安全无回归。
7. 使用不含客户数据的合成请求执行一次真实 DeepSeek 最小冒烟。

### 2.3 非目标

- 不修改产品代码、开发测试、Prompt、固定评测集或依赖锁。
- 不执行真实 TikTok 写操作、公开回复、翻译或营销发送。
- 不把单次真实模型成功等同于 `REAL-AI-05` 质量评测。
- 不执行真实 SSE 50 个授权客户端并发、首分块/P99 或五日稳定性测试。
- 不测试 REAL-AI-02～05 的正式验收内容。

## 3. 被测快照与独立性

当前产品目录不是 Git 仓库，无法冻结不可变提交。本轮在执行前对 12 个 Provider、安全、Prompt、日志、入口、开发测试和锁文件计算组合 SHA-256：

```text
efba5041723329f1d63eaabc7e6fa6749257d550e94527fa2bd320b6a532b783
```

关键文件摘要：

| 文件 | SHA-256 |
| --- | --- |
| `CRM智能聊天系统/backend/app/agent/security.py` | `7395C0E1AECF08133E4FF439F4CF04E6DDB4E1874EF2497E668FC611AB3260D4` |
| `CRM智能聊天系统/backend/app/agent/providers/base.py` | `EC8C3B9E0E148596300EB021C3BB3EDDCF75F9853BEC99EE597418BF58F25B2E` |
| `CRM智能聊天系统/backend/app/agent/providers/deepseek_provider.py` | `33C3A5BD6FC9EFAC972C2F49E5F00C56D57A0731E35BB5F1FF3F876580816083` |
| `CRM智能聊天系统/backend/app/agent/workflow_prompt.py` | `FE256606DA45DE41524B6083E44BC3449F29B61F213DA32E5F795FD8D1DB9AEC` |
| `CRM智能聊天系统/backend/app/shared/logging/setup.py` | `7E5B484EDF6A391F185D451BF49557F2DE7005F5DA22B8644ADB4711413F2553` |
| `CRM智能聊天系统/backend/app/main.py` | `C9D04AEDC308C03C4510F4121CADA4F71CD28939636876BEC525E219EA02FBC9` |
| `CRM智能聊天系统/backend/uv.lock` | `3AD5B450855EC7684EA0DD2C2361B5A2E663A5A51050C3DCBA96FB79C69B6172` |

独立性说明：本轮由测试工程师重新设计未进入开发测试和固定评测集的样例并实际执行，不直接采信实施记录中的通过结论。受限于工作区可变、无 Git 提交且执行者仍属于同一 Codex 模型家族，本报告属于“独立测试过程和独立样例”，不宣称达到异组织、异模型或签名制品级独立验证。高风险生产放行仍需架构师和人工评审签署。

## 4. 测试环境

| 项目 | 实际环境 |
| --- | --- |
| 操作系统 | Windows 10.0.19045，Asia/Shanghai |
| PowerShell | 7.6.4 |
| Python | 3.11.15 |
| uv | 0.12.3 |
| Docker Engine | 29.7.2 |
| Docker Compose | v5.3.1 |
| 隔离 PostgreSQL | `pgvector/pgvector:pg16`，临时容器，宿主端口 55435，数据目录使用 tmpfs |
| 真实模型 | DeepSeek 已配置；只使用合成客服请求，不打印 Key、完整请求或原始响应 |
| 本地运行开关观察 | `AUTO_REPLY_ENABLED=false`、`AI_MARKETING_ENABLED=false`；本地 development 的 `AI_TRANSLATION_ENABLED=true`，生产模板仍为 false |

本地翻译开关为开发环境观察项，不代表生产配置已放行；生产环境应继续以关闭状态部署。

## 5. 缺陷状态汇总

| 缺陷编号 | 原优先级 | 本轮状态 | 结论 |
| --- | --- | --- | --- |
| `DEF-REAL-AI01-001` | P1 | 部分修复 / Open | 002 固定地址样例已通过，但独立完整地址变体仍可原样进入最终 Provider 请求 |
| `DEF-REAL-AI01-002` | P1 | **Closed** | Provider Request ID 已固定摘要化，Trace/Agent Run ID 只接受规范 UUID；002 固定变体和独立字段级样例通过 |
| `DEF-REAL-AI01-003` | P2 | 新增 / Open | 宽泛中文地址规则把合法优惠券、商品规格和物流中转站消息整体替换为 `[ADDRESS]` |
| `DEF-REAL-AI01-004` | P2 | 新增 / Open | 既有 Webhook、营销、Worker 等非 UUID Trace ID 被统一改为 `[INVALID_LOG_METADATA]`，破坏运行链路关联 |

## 6. 测试执行结果

### 6.1 自动化、质量和依赖门禁

| 检查项 | 结果 | 判定 |
| --- | --- | --- |
| Provider/安全/工具/配置/健康聚焦测试 | `113 passed` | 通过 |
| 默认后端全量 | `579 passed, 10 skipped` | 通过；跳过项为需数据库场景 |
| 隔离 PostgreSQL 全量 | `589 passed, 0 skipped` | 通过 |
| Phase 4 固定评测 | 234 条，安全准确率 1.0，原因准确率 1.0，危险漏放 0 | 通过当前固定集 |
| Ruff 检查 | 通过 | 通过 |
| Ruff 格式检查 | 210 个文件符合格式 | 通过 |
| mypy | 155 个源文件无错误 | 通过 |
| compileall | 无错误 | 通过 |
| `uv lock --check` | 125 个包解析成功 | 通过 |
| `uv audit --locked` | 124 个包，无已知漏洞或不良状态 | 通过 |
| Alembic | 空库升级至 019；019→018→019 成功 | 通过 |

两条既有非阻断警告仍来自 Starlette TestClient/httpx 兼容提示和 argon2 版本元数据读取，不影响本轮结论。

### 6.2 真实 DeepSeek 最小冒烟

| 项目 | 结果 |
| --- | --- |
| 请求数据 | 合成物流查询，不含真实客户、地址、订单或平台凭证 |
| 调用结果 | 成功 |
| Schema 校验 | 通过 |
| 意图 / 状态 | `logistics_query` / `classified` |
| Provider Request ID | 已返回；报告不记录原值 |
| Token | 输入 553，输出 19 |
| 总耗时 | 2484 ms |

该耗时是一次完整非流式结构化响应，不是 SSE 首分块、P95 或 P99 指标，不能作为生产性能放行证据。

### 6.3 修复样例验证

| 场景 | 结果 | 判定 |
| --- | --- | --- |
| 中文天干门牌地址 | 整段变为 `[ADDRESS]` | 通过 |
| 中文小区楼栋房间地址 | 整段变为 `[ADDRESS]` | 通过 |
| 英文 PO Box 地址 | 整段变为 `[ADDRESS]` | 通过 |
| 英文街道号在前地址 | 整段变为 `[ADDRESS]` | 通过 |
| 工具结果附加 `district/street_name/house_number/building/room/postal_code` | 契约外字段全部丢弃，只保留工具 Schema 允许字段 | 通过 |
| Provider Request ID 为客户正文、地址或 `sk-` 样式值 | 日志只含 `sha256:<digest>`，原文不可见 | 通过 |
| 规范 UUID Trace/Agent Run ID | 原值保留 | 通过 |

### 6.4 独立地址边界验证

以下均为虚构测试数据：

| 独立样例 | 实际结果 | 预期结果 |
| --- | --- | --- |
| `请寄到香港九龙旺角弥敦道555号九龙行12楼` | 未变化，完整地址仍在最终请求 | 整体最小化为 `[ADDRESS]` |
| `Please send it to One Microsoft Way, Redmond, WA 98052` | 未变化，完整地址仍在最终请求 | 整体最小化为 `[ADDRESS]` |
| `Please send it to Rural Route 2 Box 152, Springfield, IL 62701` | 未变化，完整地址仍在最终请求 | 整体最小化为 `[ADDRESS]` |

结论：固定正则扩展关闭了已知样例，但尚未建立“默认不向模型发送完整地址”的稳定结构化边界，`DEF-REAL-AI01-001` 不能关闭。

### 6.5 独立负向控制

| 合法客服消息 | 实际结果 | 风险 |
| --- | --- | --- |
| `上海市第1号消费券怎么领取？` | 整句变为 `[ADDRESS]` | 优惠意图丢失 |
| `这款公寓模型有1号和2号规格吗？` | 整句变为 `[ADDRESS]` | 商品规格意图丢失 |
| `订单到达北京市中转站12号分拨中心了吗？` | 整句变为 `[ADDRESS]` | 物流事实查询丢失 |
| `Fifth Avenue系列商品多少钱？` | 保留 | 英文对照通过 |

结论：中文住宅地址正则覆盖过宽，会把合法业务消息全部抹除，形成 `DEF-REAL-AI01-003`。

### 6.6 日志追踪链路验证

生产 Formatter 只保留规范小写连字符 UUID。独立验证结果：

| 输入类型 | 示例类别 | Formatter 结果 |
| --- | --- | --- |
| 规范 UUID | HTTP 请求 Trace ID | 正常保留 |
| Webhook 业务 Trace | `webhook-<event-id>` | `[INVALID_LOG_METADATA]` |
| 营销任务 Trace | `marketing:<event-id>` | `[INVALID_LOG_METADATA]` |
| Agent Worker Trace | `agent-worker` | `[INVALID_LOG_METADATA]` |
| 启动/校验 Trace | `startup`、`validation` | `[INVALID_LOG_METADATA]` |

源码审查确认，`integrations/service.py`、`marketing/worker.py`、`chat/worker.py` 和应用生命周期等现有生产路径仍创建非 UUID Trace ID。字段级安全门禁本身有效，因此 `DEF-REAL-AI01-002` 可以关闭；但生产者未同步迁移，导致同一占位值覆盖多个运行和事件，形成新的可观测性缺陷 `DEF-REAL-AI01-004`。

## 7. 缺陷明细

### DEF-REAL-AI01-001：完整地址仍可绕过 Provider 最终出境边界

| 项目 | 内容 |
| --- | --- |
| 优先级 | **P1** |
| 状态 | 部分修复 / Open |
| 类型 | 隐私、安全、数据出境 |
| 影响范围 | 当前消息、历史消息及任何复用 `sanitize_prompt_text` 的 Provider 请求 |
| 是否阻断 | 是；阻断公开 AI 回复、翻译、营销和自动回复 |
| 建议负责 Agent | AIAgent开发工程师Agent；架构师Agent评审数据出境边界 |

复现步骤：

1. 构造 `StructuredRequest`，分别将 6.4 中三条虚构完整地址放入当前消息。
2. 执行正式 Prompt 构建和 Provider 最终请求序列化。
3. 检查发送给外部 Provider 的消息文本。

实际结果：三条地址未被最小化，仍可完整进入外部模型请求。

预期结果：完整地址默认不进入模型；确需地址语义时只传递经业务层生成的低敏结构化标签或区域级信息。

修复建议：停止继续以枚举地址格式作为唯一安全边界。在进入 Prompt 前按字段来源执行最小化：默认删除原始收货地址和自由文本中的高风险地址段；如业务确需识别，采用专门的高召回实体检测与负向控制集，并由最终 Provider 边界执行失败关闭。新增香港地址、英文拼写数字、Rural Route、国际邮编和多语言地址测试。

### DEF-REAL-AI01-003：地址规则误删合法客服意图

| 项目 | 内容 |
| --- | --- |
| 优先级 | P2 |
| 状态 | Open |
| 类型 | 正确性、可用性、安全规则误报 |
| 影响范围 | 中文优惠券、商品规格、物流中转站等包含“地区 + 数字 + 号”文本 |
| 是否阻断 | 阻断 REAL-AI-01 完整验收；不单独构成隐私泄漏 |
| 建议负责 Agent | AIAgent开发工程师Agent |

复现步骤：

1. 将 6.5 中三条合法消息分别传给 `sanitize_prompt_text`。
2. 检查脱敏后内容。

实际结果：完整消息被替换为 `[ADDRESS]`，核心业务意图全部丢失。

预期结果：仅删除真实地址实体，不删除优惠券编号、商品规格和物流节点等合法业务语义。

修复建议：缩小宽泛中文住宅模式，区分收件/寄送语境和普通业务名词；建立成对的敏感地址正例与合法业务负例，并验证意图识别质量不下降。

### DEF-REAL-AI01-004：严格 UUID 日志门禁使既有内部追踪标识失去关联能力

| 项目 | 内容 |
| --- | --- |
| 优先级 | P2 |
| 状态 | Open |
| 类型 | 可观测性、运行追踪、跨模块兼容性 |
| 影响范围 | Webhook、营销 Worker、Agent Worker、启动和校验日志 |
| 是否阻断 | 阻断 REAL-AI-01 完整验收；不建议放宽日志安全门禁 |
| 建议负责 Agent | AIAgent开发工程师Agent、全栈开发工程师Agent |

复现步骤：

1. 使用当前生产 JSON Formatter 格式化 Webhook、营销、Worker 和启动路径现有 Trace ID。
2. 检查输出的 `trace_id`。

实际结果：不同事件和运行均折叠为 `[INVALID_LOG_METADATA]`，无法从 Provider 日志追踪到相应事件或运行。

预期结果：日志元数据保持安全、低敏且能唯一关联一次请求或运行。

修复建议：保留当前 UUID 门禁，统一把生产者生成的 Trace ID 改为 UUID；将 `webhook`、`marketing`、`startup` 等语义放入受控 `event` 字段，将业务事件关联放入独立低敏 UUID/摘要字段。不得重新允许自由文本 Trace ID。

## 8. 验收判定

| 验收项 | 判定 | 说明 |
| --- | --- | --- |
| DeepSeek Provider 统一契约 | 通过 | 流式/非流式、错误、取消、重试和 Schema 既有测试无退化 |
| 工具输出白名单 | 通过 | 契约外地址字段已在 Prompt 构建前丢弃 |
| 日志自由文本泄漏修复 | 通过 | `DEF-REAL-AI01-002` Closed |
| Provider 最终隐私边界 | **不通过** | 独立完整地址变体仍出境，P1/Open |
| 脱敏正确性 | 不通过 | 合法中文业务消息被整体抹除，P2/Open |
| Trace ID 端到端关联 | 不通过 | 既有生产者尚未迁移 UUID，P2/Open |
| 全量工程回归 | 通过 | 589 项隔离数据库全量、迁移、静态检查和依赖审计通过 |
| 真实模型最小成功链路 | 通过 | 一次合成非流式请求成功，不代表质量或性能门禁 |
| REAL-AI-01 独立验收 | **不通过** | 存在 1 个 P1 和 2 个 P2 Open |

## 9. 放行与回归要求

1. `AI_PUBLIC_REPLY_ENABLED`、`AI_MARKETING_CONTENT_ENABLED`、`AI_AUTO_REPLY_ENABLED` 继续保持 false。
2. 生产翻译开关继续保持 false；本地 development 开关不作为生产放行依据。
3. 修复 `DEF-REAL-AI01-001/003/004` 后，由测试工程师使用新的地址正例、业务负例和跨模块日志链路再次独立复测。
4. 回归必须保留本报告全部失败样例，并扩展多语言和国际地址；不得只针对三条样例追加特例。
5. 修复日志链路时不得降低 `DEF-REAL-AI01-002` 已建立的字段级安全门禁。
6. REAL-AI-01 通过后，仍需分别完成 REAL-AI-02～05、真实 SSE 50 客户端、P99、五日稳定性及架构师最终放行。

## 10. 清理与证据边界

- 隔离 PostgreSQL 临时容器已按名称和镜像核对后删除，使用 tmpfs，未触碰项目持久化数据库卷。
- 本轮生成的 pytest 临时目录和固定评测临时 JSON 已删除。
- 未修改任何产品代码、开发测试、Prompt、评测集、依赖锁、迁移或历史报告。
- 真实模型执行过程未在报告、终端摘要或测试文件中写入 API Key、完整请求、原始响应或供应商请求 ID。
- 本报告和 `共享记忆文档/测试报告索引.md` 是本轮唯一正式交付变更。
