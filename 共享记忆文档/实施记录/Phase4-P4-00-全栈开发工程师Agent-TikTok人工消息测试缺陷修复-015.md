# TikTok 人工消息测试缺陷修复实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 REAL-FS-04 |
| 模块编号 | M00 |
| 主责 Agent | 全栈开发工程师Agent |
| 协作 Agent | 架构师Agent、AIAgent开发工程师Agent、测试工程师Agent |
| 实施状态 | 已完成 |
| 开始日期 | 2026-09-02 |
| 完成日期 | 2026-09-02（开发修复与自测范围） |
| 代码位置 | `CRM智能聊天系统/` |

## 2. 需求与依据

- 产品需求：`共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md` 的客服工作台与人工发送边界。
- 接口依据：`共享记忆文档/智能客服平台 — 管理端接口文档.md` 的工作台消息接口和 11.17 增量。
- 架构依据：`架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`。
- 任务依据：`全栈开发工程师/PLAN-002-REAL-真实TikTok与DeepSeek运行面实施计划-v1.0.md` 的 REAL-FS-04。
- 缺陷依据：`测试工程师/Phase4-P4-00-全栈开发工程师Agent-M00-TikTok人工确认普通消息-综合测试-001.md` 的 `DEF-REAL-FS04-001～004`。
- 验收依据：REAL-FS-04 的可信人工主体、单次写入、未知结果、严格确认、幂等和 OpenAPI 安全契约。
- 代码规范：`共享记忆文档/代码编写手册.md`。
- 平台契约：TikTok Shop Customer Service `Send Message` 202309，Scope `seller.customer_service`。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 修复测试报告确认的四项 REAL-FS-04 阻断缺陷。
- 保证 Agent、Job 或缺失人工身份的调用不能复用人工普通消息开关触发真实写入。
- 保证平台内部错误、二次确认输入和 OpenAPI 契约与正式接口边界一致。

### 3.2 实施范围

- 真实平台消息工具执行边界。
- TikTok 客服消息写接口错误终态分类。
- 人工发送请求 Schema 的严格输入校验。
- Bearer/Cookie OpenAPI 安全方案、必填幂等头和接口说明。
- 对应单元、契约、全量、迁移、前端和 Compose 回归。

### 3.3 非目标

- 不执行真实店铺发送，不注入或读取真实平台凭证。
- 不开启真实普通消息、高风险写入、营销或自动回复开关。
- 不修改 AI Agent、Prompt、模型、RAG 或业务事实判定。
- 不在本任务升级 `transformers` 或 Next.js 依赖；继承的生产依赖风险由对应主责任务处理。
- 不替测试工程师修改正式缺陷状态或测试报告结论。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单。
- [x] 已读取相关 PRD、接口、任务拆解和验收标准。
- [x] 已读取代码编写手册、全部适用 `AGENTS.md`、TikTok OpenAPI Skill 和最小化实现 Skill。
- [x] 已确认 Phase4、REAL-FS-04、M00 和全栈主责边界。
- [x] 已先用独立回归测试复现四项缺陷，再实施最小修复。
- [x] 已确认真实写入开关保持关闭，测试不触达真实 TikTok。

## 5. 实施方案

### 5.1 方案说明

```text
人工发送请求
→ OpenAPI 可识别的 Cookie/Bearer 认证
→ 必填 Idempotency-Key + confirmed 严格 true
→ Service 构造 user + actor_id + human_confirmed 上下文
→ Tool Executor 对真实适配器二次失败关闭
→ 单次 TikTok 写请求
→ sent / failed / unknown
→ 消息、工具调用和审计统一终态
```

真实适配器调用前必须同时满足 `actor_type=user`、`actor_id` 有效和 `human_confirmed=true`。TikTok 官方客服写接口内部错误 `45101001` 与 `36009003` 都不能证明平台没有产生副作用，因此独立归类为 `unknown`，不自动重试。

### 5.2 依赖关系

- 前置依赖：REAL-FS-01 配置门禁、REAL-FS-02 OAuth 密文、REAL-FS-03 平台适配、迁移 head `021_message_unknown`。
- 后续依赖：测试工程师 REAL-FS-04 独立复测；架构师批准后的真实单店铺人工发送灰度和回滚演练。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 非人工调用伪造确认 | 未授权真实客户消息 | 工具执行器在真实适配器边界强制主体、身份和确认三项校验 |
| 平台内部错误被判失败 | 操作员重复发送 | 写接口独立未知错误集合，单次请求后进入人工对账 |
| JSON 类型强制转换 | 绕过二次确认契约 | 输入前使用身份比较，只接受原始布尔 `true` |
| OpenAPI 与运行时不一致 | 客户端漏传幂等或误判鉴权 | 必填依赖与安全方案直接进入 OpenAPI，并由契约测试锁定 |
| 继承依赖漏洞 | 生产放行风险 | 不扩大本任务边界，维持生产关闭并交由对应主责 Agent 处理 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `CRM智能聊天系统/backend/app/tools/executor.py` | 修改 | 真实消息调用前强制可信人工主体、身份和当次确认 | 全栈开发工程师Agent |
| `CRM智能聊天系统/backend/app/tools/contracts.py` | 修改 | 登记人工确认失败公开错误码 | 全栈开发工程师Agent |
| `CRM智能聊天系统/backend/app/integrations/tiktok_write.py` | 修改 | 增加客服写接口独立未知错误集合 | 全栈开发工程师Agent |
| `CRM智能聊天系统/backend/app/workspace/schemas.py` | 修改 | `confirmed` 输入前严格校验原始 JSON 布尔值 | 全栈开发工程师Agent |
| `CRM智能聊天系统/backend/app/workspace/router.py` | 修改 | 幂等头改为必填依赖并补齐发送、对账接口说明 | 全栈开发工程师Agent |
| `CRM智能聊天系统/backend/app/auth/dependencies.py` | 修改 | 声明 Bearer 与 Cookie 两种 OpenAPI 安全方案 | 全栈开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_tiktok_write.py` | 修改 | 覆盖 `45101001` 未知终态和不重试 | 全栈开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_tool_executor.py` | 修改 | 覆盖 user/agent/job、缺失身份和未确认的失败关闭矩阵 | 全栈开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_phase3_domain.py` | 修改 | 覆盖确认严格类型及 OpenAPI 幂等/鉴权契约 | 全栈开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_auth_cookies.py` | 修改 | 覆盖非法 Authorization 头不得静默降级到 Cookie | 全栈开发工程师Agent |
| `全栈开发工程师/PLAN-002-REAL-真实TikTok与DeepSeek运行面实施计划-v1.0.md` | 修改 | 同步首次测试缺陷开发修复状态 | 全栈开发工程师Agent |
| `共享记忆文档/实施记录索引.md` | 修改 | 登记本实施记录 | 全栈开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：运行时语义未扩展；`confirmed` 现在严格只接受 JSON `true`，`Idempotency-Key` 在 OpenAPI 中与运行时一致为必填。
- OpenAPI：新增 `BearerAuth` 和 `CookieAuth` 安全方案；人工发送与管理员对账接口声明二选一认证，并补齐权限、店铺隔离、CSRF 和未知结果说明。
- 数据库：无迁移和表结构变化；既有 `021_message_unknown` 迁移完成回归。
- 配置项：无新增或默认值变化；所有真实写入与自动能力开关保持关闭。
- AI：不适用；未修改 AI Agent 代码，仅验证其不能复用人工真实写工具。

### 6.3 关键实现说明

- 主体校验放在工具执行器解析到真实写适配器之后、消息创建和平台调用之前，Mock 业务与既有工具契约不被无关收紧。
- `actor_type=user` 仍不足以单独放行，必须同时存在 `actor_id` 和当次人工确认；任一条件缺失均返回 `TOOL_HUMAN_CONFIRMATION_REQUIRED`。
- 写接口错误集合不复用只读重试语义。`45101001/36009003` 均以可能已产生副作用处理，返回 `TIKTOK_MESSAGE_RESULT_UNKNOWN` 且尝试次数固定为一次。
- `confirmed` 的输入前校验使用 `value is True`，避免 Python/Pydantic 将 `1` 转成 `True`。
- OpenAPI 安全方案只描述既有认证方式，不改变 Bearer 优先、Cookie 回退的运行时行为。
- 显式但格式非法的 `Authorization` 头会返回 `TOKEN_INVALID`，不得静默回退到 Cookie，避免安全方案显式化引入认证降级。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| 修复前红测 | 聚焦运行新增缺陷用例 | 四类问题均可稳定复现 | 5 失败、46 通过 | 通过 |
| 修复后聚焦回归 | `pytest tests/test_auth_cookies.py tests/test_tiktok_write.py tests/test_tool_executor.py tests/test_phase3_domain.py tests/test_real_runtime_config.py` | 无失败 | 121 通过、1 条既有弃用告警 | 通过 |
| 后端默认全量 | `pytest`，工作区临时基目录 | 保留全部既有回归 | 1183 通过、10 跳过、2 条既有弃用告警 | 通过 |
| 隔离 PostgreSQL 全量 | `scripts/run-postgres-integration-tests.ps1 -KeepDatabase` | 空库迁移并运行全量 | 001→021 成功，1193 通过、2 条既有弃用告警 | 通过 |
| 迁移可逆 | 隔离库 `current → downgrade 020 → upgrade 021 → current` | 可回滚并恢复 head | 最终恢复 `021_message_unknown` | 通过 |
| Ruff 检查 | `ruff check .` | 无代码问题 | 通过；扫描非源码临时目录时存在两条访问警告 | 通过 |
| Ruff 格式 | `ruff format --check app tests scripts migrations` | 产品源码格式一致 | 220 个文件格式一致 | 通过 |
| mypy | `mypy app scripts` | 无类型错误 | 161 个源码文件通过 | 通过 |
| 锁文件 | `uv --no-cache lock --check --offline` | 锁文件有效 | 125 个包解析成功 | 通过 |
| 前端检查 | `npm run lint`、`typecheck`、`test`、`build` | 全通过 | 31 项测试通过，14 个静态页面构建成功 | 通过 |
| Compose | 基础、生产+人工叠加配置校验 | 配置合法且无真实凭证输出 | 均通过；只使用占位配置值 | 通过 |
| 真实 TikTok 写入 | 单店铺人工消息 | 真实回执和人工对账 | 未执行：本任务只修复确定性缺陷，生产门禁未放行 | 未执行 |

说明：`ruff format --check .` 在扫描工作区中其他 Agent 遗留且访问受限的临时目录时触发 Ruff Windows panic；限定正式源码目录后 220 个文件全部通过。本任务创建的 `.test-artifacts` 和 `.test-artifacts-real-fs04-final` 已在确认绝对路径位于项目后删除，不触碰其他 Agent 的临时证据目录。隔离 `postgres-test` 容器也已停止并删除，其 tmpfs 测试数据不可恢复且不涉及开发或真实数据库。

## 8. 实施结果

- 完成项：四项缺陷均完成代码修复、针对性回归、默认全量、隔离 PostgreSQL、迁移、前端、Compose 和文档同步。
- 未完成项：测试工程师独立复测、真实单店铺人工发送、真实未知结果对账和开关回滚演练。
- 与原方案差异：无接口能力扩张；仅将运行时和 OpenAPI 收敛到原定失败关闭边界。
- 当前状态：开发缺陷修复任务已完成并有验证证据；`DEF-REAL-FS04-001～004` 在测试工程师复测前仍保持 Open，REAL-FS-04 生产写入未放行。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-REAL-FS04-FIX-001 | 四项正式缺陷尚未由测试工程师独立复测关闭 | P1 | 测试工程师Agent | REAL-FS-04 第二次综合测试 |
| R-REAL-FS04-FIX-002 | 真实店铺授权 Scope、发送回执、未知对账和回滚尚未演练 | P1 | 全栈开发工程师Agent、架构师Agent、测试工程师Agent | REAL-FS-04 真实灰度 / REAL-FS-06 |
| R-REAL-FS04-FIX-003 | Python 与前端继承的生产依赖安全阻断仍未关闭 | P1 | AIAgent开发工程师Agent、全栈开发工程师Agent、架构师Agent | REAL-AI / REAL-FS-01 依赖安全专项 |
| R-REAL-FS04-FIX-004 | Ruff 在扫描其他 Agent 遗留的访问受限临时目录时发生工具崩溃 | P3 | 全栈开发工程师Agent、开发工具Agent | 工程环境清理专项；不删除未经确认的他人证据 |

## 10. 交接事项

- 交接给：测试工程师Agent、架构师Agent、AIAgent开发工程师Agent。
- 后续任务：测试工程师针对四项缺陷执行独立复测；架构师确认 REAL-FS-01 依赖安全门禁后，才可安排真实单店铺人工发送灰度。
- 必须注意：重点验证真实适配器前置失败关闭、无半成品消息/平台调用、`45101001` 单次未知终态、确认输入矩阵及 OpenAPI 安全契约。所有真实写入开关继续保持 false，不得把开发自测视为生产放行。

## 11. 文档同步

- [x] 已同步接口契约实现状态；接口业务语义无新增。
- [x] 已遵守架构边界，未修改 ADR 权威决策。
- [x] 已同步 REAL-FS-04 任务状态。
- [x] 已通知测试工程师需要覆盖的四项复测范围。
- [x] 测试报告索引和正式缺陷状态由测试工程师在独立复测后更新。
