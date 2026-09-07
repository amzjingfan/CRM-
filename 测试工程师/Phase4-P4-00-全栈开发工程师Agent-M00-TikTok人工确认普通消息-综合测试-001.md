# Phase 4 REAL-FS-04 TikTok 人工确认普通消息综合测试报告

## 1. 报告信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase 4 |
| 任务编号 | P4-00；专项任务 REAL-FS-04 |
| 模块编号 | M00 |
| 模块名称 | TikTok 人工确认普通消息 |
| 被测主责 Agent | 全栈开发工程师Agent |
| 测试执行 Agent | 测试工程师Agent |
| 测试类型 | 综合测试、契约测试、接口测试、数据库测试、安全测试、回归测试、部署配置测试 |
| 测试日期 | 2026-09-02 |
| 报告序号 | 001 |
| 最终结论 | **不通过** |

## 2. 测试结论

REAL-FS-04 当前工程范围不通过，不能开启真实 TikTok 普通消息写入。

本轮确认工程主路径、数据库迁移、幂等、消息终态、人工对账、前端提示、部署开关和既有回归整体稳定，但独立负向测试发现：

- `DEF-REAL-FS04-001`（P1/Open）：`agent` 或 `job` 上下文可通过设置 `human_confirmed=true` 复用真实人工消息通道，未在受信任工具边界强制限制为人工用户。
- `DEF-REAL-FS04-002`（P1/Open）：TikTok 官方 `45101001 Internal error` 被归类为确定失败，而不是结果未知，存在操作员换新幂等键再次发送造成重复消息的风险。
- `DEF-REAL-FS04-003`（P2/Open）：接口声明的严格布尔 `confirmed=true` 在运行时接受 JSON 数字 `1`。
- `DEF-REAL-FS04-004`（P2/Open）：OpenAPI 把运行时必填的 `Idempotency-Key` 标记为可选，且未声明接口鉴权要求。

既有自动化测试全部通过不能覆盖上述边界。两个 P1 直接涉及真实客户消息的未授权发送和不确定结果重复发送，因此在缺陷独立复测关闭前：

```text
REAL_TIKTOK_MESSAGE_WRITE_ENABLED=false
REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED=false
AI_AUTO_REPLY_ENABLED=false
```

必须保持关闭，不执行真实店铺消息发送灰度。

## 3. 测试依据与边界

### 3.1 已读取的项目约束

- 项目级、测试工程师、全栈开发工程师、AI Agent、架构师、共享记忆及代码目录下全部 `AGENTS.md`。
- `共享记忆文档/代码编写手册.md`。
- 最新 PRD、MVP 范围、管理端接口文档、任务拆解、团队职责、测试命名规范。
- `全栈开发工程师/PLAN-002-REAL-真实TikTok与DeepSeek运行面实施计划-v1.0.md`。
- `架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`。
- REAL-FS-04 实施记录及 REAL-FS-01～03 最新测试报告。

### 3.2 官方契约基线

本轮以当前适用的 TikTok Shop 客服消息接口为基线：

- `POST /customer_service/202309/conversations/{conversation_id}/messages`
- Scope：`seller.customer_service`
- 文本消息类型：`TEXT`
- 请求体 `content` 为序列化后的 JSON 字符串。
- 官方发送消息文档仍列出 `45101001 Internal error`。

参考：

- [TikTok Shop Send Message](https://partner.tiktokshop.com/docv2/page/send-message-202309)
- [TikTok Shop Customer Service API Overview](https://partner.tiktokshop.com/docv2/page/customer-service-api-overview)

本轮同时使用本地 `tts-openapi-guide` OAS 资料核对 endpoint、Scope、请求体和响应错误，不以历史记忆替代官方契约。

### 3.3 本轮范围

覆盖：

- 人工消息二次确认、权限和店铺隔离。
- 工具执行、幂等、`tool_calls`、`audit_logs` 和消息状态。
- TikTok 真实写适配器签名、单次请求、错误分类和结果未知处理。
- 同店铺 `unknown` 熔断和管理员人工对账。
- 前端真实/模拟/失败/未知状态。
- 迁移 `021_message_unknown` 的升级、回滚和恢复。
- 生产人工消息 Compose 叠加配置和默认关闭状态。
- 全量后端、前端和数据库回归。

不覆盖：

- 真实店铺实际消息发送。
- TikTok 目标环境权限、频控、审核和人工后台对账实操。
- 高风险写操作、主动营销、AI 自动回复。
- DeepSeek 真实模型质量、公开 SSE 和五日稳定性。

## 4. 测试环境

| 组件 | 版本或状态 |
| --- | --- |
| 操作系统 | Windows，PowerShell |
| Python | 3.11.15 |
| uv | 0.12.3 |
| Node.js | v24.19.0 |
| npm | 11.17.0 |
| Docker | 29.7.2 |
| Docker Compose | v5.3.1（`docker-compose`） |
| 数据库迁移 | `021_message_unknown (head)` |
| 运行态 | backend、frontend、postgres、redis、minio 健康；worker、jobs 运行 |

测试期间未读取、输出或写入真实 TikTok Token、App Secret、客户完整消息或地址。

## 5. 测试结果汇总

| 测试项 | 结果 | 证据摘要 |
| --- | --- | --- |
| REAL-FS-04 聚焦回归 | 通过 | 112 项通过，1 条既有告警 |
| 默认后端全量回归 | 通过 | 1176 项通过，10 项按条件跳过，2 条既有告警 |
| 隔离 PostgreSQL 全量回归 | 通过 | 1186 项通过，2 条既有告警 |
| Ruff 检查与格式 | 通过 | 无静态检查问题，226 个文件格式通过 |
| mypy | 通过 | 161 个源文件无类型错误 |
| uv 锁文件 | 通过 | 离线锁定检查通过 |
| 前端测试 | 通过 | 31 项通过 |
| 前端 lint/typecheck/build | 通过 | ESLint、TypeScript、Next.js 生产构建通过，14 个静态页面生成 |
| 迁移升级/回滚 | 通过 | 空库升级到 021；021→020→021 通过 |
| Compose 默认关闭 | 通过 | backend/worker 普通消息、高风险写入和自动回复均关闭 |
| 人工消息叠加配置 | 通过 | 仅 backend 可开启普通消息写入；worker、高风险和自动回复保持关闭 |
| 健康检查 | 通过 | `/v1/health` 与 `/v1/health/ready` 返回 200 |
| 真实写入 actor 边界 | **失败** | `actor_type=agent` 且 `human_confirmed=true` 可触发适配器调用 |
| 官方内部错误分类 | **失败** | `45101001` 返回 `failed/TIKTOK_MESSAGE_REJECTED`，预期 `unknown` |
| 确认字段严格类型 | **失败** | JSON 数字 `1` 被 Pydantic 转换并接受为布尔 `true` |
| OpenAPI 契约 | **失败** | `Idempotency-Key.required=false`，接口 `security` 未声明 |
| Python 生产依赖审计 | **失败（继承阻断）** | `transformers 5.5.4` 命中 1 个已知漏洞，修复版本为 5.10.0 |
| 前端生产依赖审计 | **失败（继承阻断）** | 官方 npm registry 报告 3 个 High，涉及 `next/postcss/sharp` 依赖链 |

## 6. 已验证通过的能力

### 6.1 平台请求契约

- 使用 202309 客服消息路径和 `seller.customer_service` Scope。
- 文本请求体结构和签名正文一致。
- 真实写适配器只发送一次，不自动重试。
- 网络异常、HTTP 5xx、非法响应和成功响应缺少消息 ID 会进入 `unknown`。
- Token、权限和稳定拒绝可映射为确定失败。

### 6.2 消息与审计链路

- 平台调用前先保存 `processing` 消息。
- 发送结果可落为 `sent | failed | unknown`。
- 工具调用、消息和审计通过幂等键关联。
- 同键同请求可以重放终态；同键不同请求返回冲突。
- 同店铺存在未对账的真实 `unknown` 时阻止后续发送。
- 管理员可依据平台事实对账为 `sent` 或 `failed`，并记录审计。

### 6.3 前端与部署

- 发送前要求二次确认并显示真实平台提示。
- 显示模拟、真实、失败和未知结果，不将未知伪装为成功。
- 真实 TikTok 文本长度限制为 2000 字符。
- AI 建议仍只填充输入框，不自动发送。
- 人工消息生产叠加文件不向 worker 开放写入开关。

## 7. 缺陷详情

### DEF-REAL-FS04-001：Agent/Job 可复用人工消息开关触发真实写入

| 项目 | 内容 |
| --- | --- |
| 优先级 | P1 |
| 状态 | Open |
| 类型 | 权限边界、真实平台写入安全 |
| 影响范围 | `send_platform_message`、AI/Job 工具调用、真实客户消息 |
| 是否阻断 | 是 |
| 建议负责 Agent | 全栈开发工程师Agent；AIAgent开发工程师Agent协作回归 |

依据：管理端接口文档 11.17 和实施计划明确要求 Agent/Job 不能复用普通消息开关执行真实写操作。

复现：

1. 构造 `ToolExecutionContext(actor_type="agent", human_confirmed=true)`。
2. 赋予 `workspace.reply` 并调用 `send_platform_message`。
3. 使用真实写适配器替身记录平台调用次数。

实际结果：

```text
blocked = false
platform_calls = 1
```

代码审查确认：工具上下文只保存可赋值布尔 `human_confirmed`；执行器向适配器传递该值，但真实写入口没有强制 `actor_type == "user"`。

预期结果：

- 真实普通消息必须同时满足可信人工用户、当次明确确认、权限、店铺和幂等要求。
- `actor_type=agent|job` 无论是否携带 `human_confirmed=true` 都应在创建消息和调用平台前失败关闭。

修复建议：

- 在受信任工具执行边界对真实发送强制校验 `actor_type == "user"`。
- 不把调用方可自行设置的普通布尔值视为可信批准证明；由人工 Service 构造不可伪造或不可跨入口复用的批准上下文。
- 增加 user/agent/job 对称负向测试，并断言平台调用数为 0、无半成品消息。

### DEF-REAL-FS04-002：TikTok 官方内部错误 45101001 被误判为确定失败

| 项目 | 内容 |
| --- | --- |
| 优先级 | P1 |
| 状态 | Open |
| 类型 | 第三方错误分类、幂等与重复发送风险 |
| 影响范围 | TikTok 客服消息真实发送 |
| 是否阻断 | 是 |
| 建议负责 Agent | 全栈开发工程师Agent |

复现：

1. 让 TikTok 发送接口返回 HTTP 200。
2. 响应 JSON 中设置 `code=45101001`，即官方 Send Message 文档列出的 `Internal error`。
3. 调用真实写适配器一次。

实际结果：

```json
{
  "status": "failed",
  "error_code": "TIKTOK_MESSAGE_REJECTED",
  "attempts": 1
}
```

预期结果：

```json
{
  "status": "unknown",
  "error_code": "TIKTOK_MESSAGE_RESULT_UNKNOWN",
  "attempts": 1
}
```

风险：内部错误不能证明平台未执行写入。若系统记录为 `failed`，操作员可用新幂等键再次发送，造成真实客户收到重复消息。

修复建议：为写接口维护基于官方文档的独立错误分类，至少将 `45101001` 和 `36009003` 归入结果未知；保持单次请求并进入人工对账，不复用只读 API 的不完整瞬时错误集合。

### DEF-REAL-FS04-003：`confirmed` 接受 JSON 数字 1

| 项目 | 内容 |
| --- | --- |
| 优先级 | P2 |
| 状态 | Open |
| 类型 | API 契约、输入校验 |
| 影响范围 | 人工发送接口二次确认 |
| 是否阻断 | 是 |
| 建议负责 Agent | 全栈开发工程师Agent |

独立输入矩阵结果：

| 输入 | 实际结果 | 预期结果 |
| --- | --- | --- |
| `true` | 接受 | 接受 |
| `false` | 拒绝 | 拒绝 |
| `1` | **接受并转换为 `true`** | 拒绝 |
| `0` | 拒绝 | 拒绝 |
| `"true"` | 拒绝 | 拒绝 |

接口文档要求 `confirmed` 必须逐字为 JSON 布尔 `true`。当前 `Literal[True]` 仍受 Pydantic 非严格布尔转换影响。

修复建议：使用严格布尔类型并在校验器中要求值为 `true`，增加数值、字符串、空值、缺失和容器类型测试。

### DEF-REAL-FS04-004：OpenAPI 未表达必填幂等头和鉴权要求

| 项目 | 内容 |
| --- | --- |
| 优先级 | P2 |
| 状态 | Open |
| 类型 | OpenAPI、客户端契约、安全文档 |
| 影响范围 | 人工发送和管理员对账接口、前端类型生成、第三方客户端 |
| 是否阻断 | 是 |
| 建议负责 Agent | 全栈开发工程师Agent |

独立 OpenAPI 检查：

```text
POST /v1/workspace/sessions/{session_id}/messages
Idempotency-Key.required = false
security = null
```

实际运行时代码会拒绝缺失 `Idempotency-Key`，与 OpenAPI 声明不一致；发送接口和对账接口也没有通过 OpenAPI security scheme 表达认证要求。

预期结果：

- `Idempotency-Key` 在 OpenAPI 中为必填，包含长度和用途说明。
- 文档明确 Cookie/JWT 认证、CSRF、权限、店铺隔离、管理员对账角色及统一错误码。

修复建议：将 header 参数声明为真正必填；为认证依赖建立可被 OpenAPI 识别的安全方案，或至少在 operation 描述中完整声明，增加契约快照测试。

## 8. 继承阻断与环境观察

### 8.1 生产依赖安全

本轮复核发现以下项目级生产阻断仍存在，不重复创建 REAL-FS-04 缺陷编号：

- `uv audit --locked`：`transformers 5.5.4` 命中 `GHSA-xrqw-3rrv-vx5w / CVE-2026-9856`，报告修复版本为 5.10.0。
- 使用 npm 官方 registry 执行生产依赖审计，报告 3 个 High，涉及 `next` 依赖链中的 `postcss`、`sharp/libvips`；自动建议涉及 Next 16，需由主责 Agent 评估兼容升级，不能直接强制修复。
- 共享测试索引已记录 `DEF-REAL-FS01-005/006` 仍为 Open，REAL-FS-01 当前不通过。

因此，即使 REAL-FS-04 四个缺陷关闭，生产放行仍需先满足 REAL-FS-01 和架构师门禁。

### 8.2 Docker 环境

- 测试期间 Docker 服务、隔离 PostgreSQL 迁移和运行态健康检查均已完成。
- 测试收尾时 Docker CLI 对用户配置文件和 named pipe 出现访问受限；隔离测试容器已在迁移测试完成后显式停止并删除，该权限现象不改变已取得的测试结果。
- 测试产生的 `backend/.test-artifacts` 临时目录已在确认位于工作区后删除，可恢复性不适用。

## 9. 主要执行命令与证据

```text
后端聚焦：
python -m pytest tests/test_tiktok_write.py tests/test_tool_executor.py tests/test_phase3_domain.py tests/test_real_runtime_config.py -q
结果：112 passed

后端默认全量：
python -m pytest -q -rs --basetemp=<workspace>/backend/.test-artifacts/real-fs04-pytest-002
结果：1176 passed, 10 skipped

隔离 PostgreSQL：
scripts/run-postgres-integration-tests.ps1 -KeepDatabase
结果：1186 passed；空库 001→021；021→020→021 通过

静态质量：
uv lock --check --offline
uv run ruff check .
uv run ruff format --check .
uv run mypy app scripts
结果：通过

前端：
npm run test
node_modules/.bin/eslint.cmd .
node_modules/.bin/tsc --noEmit
npm run build
结果：31 passed；lint/typecheck/build 通过

基础设施：
docker-compose config --quiet
docker-compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.tiktok-manual.yml config --quiet
curl /v1/health
curl /v1/health/ready
结果：通过
```

独立负向探针只在进程内使用模拟 HTTP 响应和适配器替身，不创建新的产品测试文件，不调用真实 TikTok 接口。

## 10. 验收建议

REAL-FS-04 进入下一轮独立复测前，至少完成：

1. 在真实工具边界阻断 `agent/job` actor，并证明平台调用数为 0。
2. 将官方 `45101001` 及其他内部不确定错误归为 `unknown`，保持不重试和人工对账。
3. 严格拒绝 `confirmed=1` 等非 JSON 布尔值。
4. 修复 OpenAPI 必填幂等头与认证/权限说明。
5. 运行全部既有后端、隔离 PostgreSQL、前端和迁移回归。
6. 由测试工程师独立复测并关闭四个缺陷。
7. 在架构师签署 REAL-FS-01、OAuth、只读、Webhook、凭证、日志和回滚门禁后，才可申请单店铺、单账号、单操作者真实灰度。

修复后真实灰度仍应按以下顺序执行：

```text
保持默认关闭
→ 单店铺只读和 Webhook 已验收
→ 开启 backend 人工普通消息开关
→ 发送一条无敏感信息的人工测试消息
→ 在 TikTok 后台核对消息 ID 和内容
→ 执行一次 unknown 人工对账演练
→ 关闭开关并验证回滚
```

在该流程完成前，不得标记“真实 TikTok 人工消息生产接入完成”。

