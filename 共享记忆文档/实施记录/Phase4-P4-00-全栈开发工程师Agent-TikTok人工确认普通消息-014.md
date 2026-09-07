# TikTok 人工确认普通消息实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 REAL-FS-04 |
| 模块编号 | M00 |
| 主责 Agent | 全栈开发工程师Agent |
| 协作 Agent | 架构师Agent、AIAgent开发工程师Agent、测试工程师Agent |
| 实施状态 | 部分完成 |
| 开始日期 | 2026-09-02 |
| 完成日期 | 2026-09-02（确定性工程范围） |
| 代码位置 | `CRM智能聊天系统/` |

## 2. 需求与依据

- 产品需求：`共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md` 的客服工作台与人工发送边界。
- 接口依据：`共享记忆文档/智能客服平台 — 管理端接口文档.md` 的工作台消息接口和 11.17 增量。
- 架构依据：`架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`。
- 任务依据：`全栈开发工程师/PLAN-002-REAL-真实TikTok与DeepSeek运行面实施计划-v1.0.md` 的 REAL-FS-04。
- 验收依据：`共享记忆文档/MVP范围与验收标准.md`、REAL-FS-04 成功/失败/未知/幂等/回滚门禁。
- 代码规范：`共享记忆文档/代码编写手册.md`。
- 平台契约：TikTok Shop Customer Service `Send Message` 202309，Scope `seller.customer_service`。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 让工作台人工普通文本消息统一经过受控工具层，并具备可开关的真实 TikTok 单次发送能力。
- 明确区分 `sent`、`failed` 和不可安全重试的 `unknown`。
- 后端强制店铺、权限、人工确认、幂等、审计和低敏记录；前端提供二次确认与状态提示。

### 3.2 实施范围

- TikTok 202309 普通文本消息客户端、实时签名、加密 Token 解密和平台错误映射。
- `POST /workspace/sessions/{session_id}/messages` 请求/响应增量。
- 管理员 `POST /workspace/messages/{message_id}/reconcile` 人工对账与店铺级未知结果熔断。
- `SqlAlchemyToolExecutor` 人工发送、消息、工具调用和审计统一链路。
- 消息 `unknown` 状态迁移、前端状态、生产受控叠加配置、自动化测试和文档。

### 3.3 非目标

- 不开放 AI 自动回复、AI 营销、发券、地址修改或任何高风险真实写操作。
- 不修改 Prompt、模型、RAG、业务事实判定或 AI Agent 工作流。
- 不在本轮使用真实凭证，不向真实店铺客户发送消息，不宣称真实联调或生产放行通过。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单。
- [x] 已读取相关 PRD、接口、任务拆解和验收标准。
- [x] 已读取代码编写手册、全部适用 `AGENTS.md`、`ponytail` 和 TikTok OpenAPI Skill。
- [x] 已确认 Phase4、REAL-FS-04、M00 和全栈主责边界。
- [x] 已确认迁移前 head 为 `020_knowledge_safety`，现有后端 1157 项、前端 30 项基线测试通过。

## 5. 实施方案

### 5.1 方案说明

```text
工作台人工输入
→ 浏览器二次确认
→ CSRF / workspace.reply / 店铺范围 / Idempotency-Key
→ ToolExecutionContext(user + human_confirmed)
→ SqlAlchemyToolExecutor
→ processing 消息落库
→ TikTok 202309 单次签名请求
→ sent / failed / unknown
→ messages + tool_calls + audit_logs 同步终态
```

TikTok 写接口没有项目可控的远端幂等键，因此平台传输异常、HTTP 5xx、官方内部错误或成功响应缺少消息 ID 时只能记录 `unknown`。系统不自动重试，由人工前往 TikTok 对账。Agent/Job 的 `human_confirmed` 默认为 `false`，不能复用普通消息开关执行真实写操作。

同店铺存在未对账的 `unknown` 消息时，工具执行器阻断后续真实普通消息。管理员在 TikTok 后台确认结果后，使用专用对账接口同步关闭 `messages/tool_calls` 状态并写入审计，才解除该店铺熔断。

### 5.2 依赖关系

- 前置依赖：REAL-FS-01 配置、REAL-FS-02 OAuth 密文、REAL-FS-03 真实只读/Webhook、`seller.customer_service` Scope。
- 后续依赖：测试工程师 REAL-FS-04 独立测试、真实单店铺人工发送灰度、REAL-FS-06 回滚演练。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 平台已接收但本地超时 | 重复发送客户消息 | 记录 `unknown`，停止自动重试，人工对账 |
| Agent/Job 复用写工具 | 绕过人工确认 | 可信执行上下文 `human_confirmed`，真实适配器二次失败关闭 |
| 同一请求重复提交 | 重复消息 | 店铺级 `Idempotency-Key`、请求哈希、在途冲突、终态重放 |
| 配置误开自动能力 | 未授权自动发送 | Settings 启动门禁、生产叠加文件固定 Worker/高风险/自动回复为 false |
| 日志或审计泄露正文 | 客户隐私泄露 | 工具和审计仅保存长度、对象、状态、平台和请求哈希 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `backend/app/integrations/tiktok_write.py` | 新增 | TikTok 202309 单次普通文本发送客户端 | 全栈开发工程师Agent |
| `backend/app/integrations/adapters.py`、`schemas.py` | 修改 | 独立消息适配器门禁、人工确认、`unknown` 结果 | 全栈开发工程师Agent |
| `backend/app/tools/contracts.py`、`executor.py` | 修改 | 可信确认上下文、统一人工发送和未知终态恢复 | 全栈开发工程师Agent |
| `backend/app/workspace/router.py`、`schemas.py`、`service.py` | 修改 | 显式确认、统一工具调用、交付模式响应 | 全栈开发工程师Agent |
| `backend/app/shared/config/settings.py` | 修改 | 放行人工普通消息，继续阻断自动和高风险写入 | 全栈开发工程师Agent |
| `backend/migrations/versions/021_add_unknown_message_status.py` | 新增 | 为消息约束增加 `unknown` 可逆迁移 | 全栈开发工程师Agent |
| `backend/app/marketing/worker.py` | 修改 | 兼容可空平台消息 ID，不改变营销真实写边界 | 全栈开发工程师Agent |
| `backend/tests/test_tiktok_write.py` 等测试 | 新增/修改 | 签名、单次调用、错误、确认、幂等和配置测试 | 全栈开发工程师Agent |
| `frontend/lib/api.ts`、`app/workspace/page.tsx`、`tests/security.test.mjs` | 修改 | 二次确认、真实/Mock/关闭模式及未知对账提示 | 全栈开发工程师Agent |
| `docker-compose.tiktok-manual.yml` | 新增 | 受控生产灰度叠加文件 | 全栈开发工程师Agent |
| `.env.example`、`README.md`、`deploy/production/README.md` | 修改 | 配置、启动、回滚和限制说明 | 全栈开发工程师Agent |
| `共享记忆文档/智能客服平台 — 管理端接口文档.md` | 修改 | 登记 11.17 接口增量 | 全栈开发工程师Agent |
| `全栈开发工程师/PLAN-002-REAL-真实TikTok与DeepSeek运行面实施计划-v1.0.md` | 修改 | 同步 REAL-FS-04 工程进度 | 全栈开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：发送请求增加必填 `confirmed=true`；`MessageView` 增加 `delivery_mode`；会话详情增加 `send_mode` 和 `requires_confirmation`；新增 admin 人工对账接口。
- 数据库：新增 `021_message_unknown`，`messages.status` 允许 `unknown`；降级时转为 `failed` 并保留错误码。
- 配置项：继续复用 `REAL_TIKTOK_MESSAGE_WRITE_ENABLED=false`，新增生产叠加文件，不新增同义开关。
- AI：不适用；仅通过可信上下文保证 Agent/Job 不能触发真实人工消息发送。

### 6.3 关键实现说明

- 官方路径固定，不接受任意 URL；Access Token 只从渠道密文解密后进入 Header。
- 原始紧凑 JSON 字节同时用于签名和请求；正文为 TikTok 要求的双层 JSON 字符串。
- 真实文本上限 2000 字符；前端和后端均在网络调用前约束。
- 写请求始终单次调用。`failed` 只表示确定拒绝；无法确认是否产生副作用时必须为 `unknown`。
- 出站消息先提交 `processing`；外层超时或异常会恢复为 `unknown`，避免永久悬挂。
- 同键同请求只重放已完成终态；同键不同请求或在途重复返回资源冲突。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| 依赖锁 | `uv lock --check` | 锁文件有效 | 125 包解析成功 | 通过 |
| 后端规范 | `uv run ruff check .`、`uv run ruff format --check .` | 无错误 | 通过，222 个文件格式一致 | 通过 |
| 后端类型 | `uv run mypy app scripts` | 无错误 | 161 个源码文件通过 | 通过 |
| 后端默认测试 | `uv run pytest -q` | 无失败 | 1176 通过、10 跳过、2 个既有弃用警告 | 通过 |
| 隔离 PostgreSQL | `scripts/run-postgres-integration-tests.ps1` | 空库迁移和全量测试通过 | 001→021 成功，1186 通过、2 个既有警告 | 通过 |
| 迁移可逆 | 容器内 `upgrade 021 → downgrade 020 → upgrade 021` | 可回滚并恢复 head | 当前 `021_message_unknown` | 通过 |
| 前端检查 | `npm run lint`、`typecheck`、`test`、`build` | 全通过 | 31 项测试通过，14 个静态页面构建成功 | 通过 |
| Compose | 基础+人工叠加、生产+人工叠加 `config --quiet` | 配置合法 | 均通过 | 通过 |
| 健康检查 | `GET http://localhost:8000/v1/health` | HTTP 200 | 返回 `status=ok` | 通过 |
| 依赖审计 | `uv audit --locked` | 无已知漏洞 | `transformers 5.5.4` 命中 GHSA-xrqw-3rrv-vx5w，修复版本 5.10.0 | 失败 |
| 真实店铺发送 | 单店铺人工消息 | 平台真实回执和可对账 | 未执行：OAuth 最终授权/Scope 与正式放行尚未完成 | 未执行 |

## 8. 实施结果

- 完成项：确定性工程代码、数据库迁移、前端交互、配置门禁、自动化测试和文档同步。
- 未完成项：真实 TikTok 单店铺普通消息发送、真实超时/未知人工对账、开关回滚和测试工程师正式报告。
- 与原方案差异：平台远端没有项目可控幂等头，本地幂等只防止 CRM 重复调用；平台未知结果依靠停止重试和人工对账控制。
- 当前状态：确定性工程范围完成；由于真实平台与依赖审计门禁未通过，实施记录为“部分完成”，生产写入未放行。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-REAL-FS04-001 | 真实店铺 OAuth 最终授权、`seller.customer_service` Scope 和人工消息回执尚未验证 | P1 | 全栈开发工程师Agent、架构师Agent、测试工程师Agent | REAL-FS-04 真实灰度 |
| R-REAL-FS04-002 | `transformers 5.5.4` 新增路径穿越漏洞公告，修复版本 5.10.0；本任务不得跨 AI 边界擅自升级 | P1 | AIAgent开发工程师Agent、架构师Agent、测试工程师Agent | REAL-AI / 依赖安全专项 |
| R-REAL-FS04-003 | 真实平台超时后的人工对账与开关回滚尚未演练 | P1 | 全栈开发工程师Agent、测试工程师Agent | REAL-FS-04 / REAL-FS-06 |

## 10. 交接事项

- 交接给：测试工程师Agent、架构师Agent、AIAgent开发工程师Agent。
- 后续任务：测试工程师独立覆盖人工确认、权限/店铺、幂等、失败、未知、审计、日志、迁移和生产叠加配置；架构师批准后执行单店铺单操作人真实灰度；AI Agent 评估依赖升级。
- 必须注意：在正式放行前所有真实开关保持 false。若真实结果为 `unknown`，不得使用相同或新幂等键重复发送，先在 TikTok 后台对账。不得在报告中记录真实消息、Token 或密钥。

## 11. 文档同步

- [x] 已同步接口变化。
- [x] 已同步架构边界的实际实现方式，未修改 ADR 权威决策。
- [x] 已同步任务状态。
- [x] 已明确测试工程师需要覆盖的范围。
- [x] 测试报告索引将在正式测试完成后由测试工程师更新。
