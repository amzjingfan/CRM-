# Phase 4 REAL-FS-04 TikTok 人工确认普通消息第二次综合测试报告

## 1. 测试基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 REAL-FS-04 |
| 模块编号 | M00 |
| 模块名称 | TikTok 人工确认普通消息 |
| 被测主责 Agent | 全栈开发工程师Agent |
| 被测协作 Agent | 架构师Agent、AIAgent开发工程师Agent |
| 测试执行 Agent | 测试工程师Agent |
| 关联实施记录 | `共享记忆文档/实施记录/Phase4-P4-00-全栈开发工程师Agent-TikTok人工消息测试缺陷修复-015.md` |
| 前序报告 | `测试工程师/Phase4-P4-00-全栈开发工程师Agent-M00-TikTok人工确认普通消息-综合测试-001.md` |
| 测试类型 | 综合测试、修复验证、契约测试、接口测试、数据库测试、安全测试、回归测试、部署配置测试 |
| 执行日期 | 2026-09-02 |
| 报告序号 | 002 |
| 测试结论 | **有条件通过当前确定性工程范围** |

## 2. 测试结论

REAL-FS-04 首次报告中的四项缺陷已经完成独立复测并关闭：

- `DEF-REAL-FS04-001`（P1）：Closed。`agent`、`job`、缺少人工用户 ID 或未确认的上下文均在创建消息和调用真实适配器前失败关闭。
- `DEF-REAL-FS04-002`（P1）：Closed。TikTok 官方内部错误 `45101001` 和 `36009003` 均返回 `unknown`，请求次数固定为一次。
- `DEF-REAL-FS04-003`（P2）：Closed。`confirmed` 只接受 JSON 布尔值 `true`，数字、字符串、空值和容器类型全部拒绝。
- `DEF-REAL-FS04-004`（P2）：Closed。OpenAPI 已将 `Idempotency-Key` 声明为必填，并公开 Bearer/Cookie 二选一认证方案和接口安全边界。

本轮未发现新的 REAL-FS-04 P0/P1/P2/P3 缺陷。121 项聚焦测试、1183 项默认后端、1193 项隔离 PostgreSQL、31 项前端测试、静态质量、迁移、生产构建、Compose 配置和运行态健康检查均通过。

本结论只覆盖不触达真实 TikTok 的确定性工程范围，不等于真实消息生产接入验收通过。以下门禁仍未满足：

- 未使用真实店铺执行普通消息发送、平台回执核对、`unknown` 人工对账和开关回滚演练。
- `uv audit --locked` 仍报告 `transformers 5.5.4` 的 1 个已知漏洞。
- npm 官方 registry 仍报告 3 个 High 生产依赖漏洞。
- `DEF-REAL-FS01-005/006` 和 REAL-FS-01 生产基础设施门禁尚未关闭。

因此当前必须继续保持：

```text
REAL_TIKTOK_MESSAGE_WRITE_ENABLED=false
REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED=false
AUTO_REPLY_ENABLED=false
```

只有架构师关闭生产依赖、安全、真实权限和回滚门禁后，才能进入单店铺、单账号、单操作员真实灰度。

## 3. 测试依据与边界

### 3.1 已读取的项目约束

- 项目级、测试工程师、全栈开发工程师、AI Agent、架构师、共享记忆、开发工具及产品代码目录下全部 `AGENTS.md`。
- `共享记忆文档/代码编写手册.md`。
- 最新 PRD、MVP 范围、管理端接口文档、任务拆解、团队职责和测试报告命名规范。
- `全栈开发工程师/PLAN-002-REAL-真实TikTok与DeepSeek运行面实施计划-v1.0.md`。
- `架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`。
- REAL-FS-04 001 号权威测试报告及 015 号全栈修复实施记录。

### 3.2 TikTok 官方契约复核

当前适用的人工客服消息能力仍为：

```text
POST /customer_service/202309/conversations/{conversation_id}/messages
Scope: seller.customer_service
```

本地 OAS 和 TikTok Shop Partner Center 当前文档一致；当前官方错误表同时列出 `45101001` 和 `36009003` 为内部错误。对于不支持远端业务幂等键的写请求，内部错误不能证明平台未产生副作用，因此项目将其记录为 `unknown`、禁止自动重试并要求人工对账，符合安全边界。

官方资料：

- [TikTok Shop Send Message](https://partner.tiktokshop.com/docv2/page/send-message-202309)
- [TikTok Shop Customer Service API Overview](https://partner.tiktokshop.com/docv2/page/customer-service-api-overview)
- [Upgrade Customer Service API to 202309](https://partner.tiktokshop.com/docv2/page/upgrade-customer-service-api-to-202309)

### 3.3 本轮覆盖范围

- 四项原缺陷的独立关闭验证。
- 人工消息权限、店铺范围、二次确认和真实适配器前置失败关闭。
- TikTok 写请求签名、单次调用、确定失败和未知结果分类。
- 幂等重放、内容冲突、`tool_calls`、`messages`、`audit_logs` 和同店铺未知结果熔断。
- 管理员人工对账及迁移 `021_message_unknown` 的升级、回滚和恢复。
- OpenAPI 幂等头、Cookie/JWT 认证、CSRF、权限和店铺边界。
- 前端真实/Mock/失败/未知展示及 AI 建议不自动发送。
- 生产人工消息 Compose 叠加、默认关闭和运行态健康检查。
- 锁定依赖安全审计和既有全量回归。

### 3.4 不覆盖范围

- 真实店铺实际消息发送和 TikTok 后台人工对账实操。
- 目标环境 `seller.customer_service` Scope、平台频控、审核和撤销。
- 发券、修改地址、主动营销和 AI 自动回复。
- DeepSeek 真实模型质量、公开 SSE、50 客户端并发和五日稳定性。

## 4. 测试环境

| 组件 | 版本或状态 |
| --- | --- |
| 操作系统 | Windows，PowerShell |
| Python | 3.11.15 |
| uv | 0.12.3 |
| Node.js | v24.19.0 |
| npm | 11.17.0 |
| Docker | 29.7.2 |
| Docker Compose | v5.3.1 |
| 数据库迁移 | `021_message_unknown (head)` |
| 隔离数据库 | `postgres-test`，PostgreSQL + pgvector，tmpfs |
| 运行态 | `/v1/health=ok`，`/v1/health/ready=ready` |

测试期间未读取、输出或写入真实 TikTok Token、App Secret、客户完整消息或地址，未向真实客户发送消息。

## 5. 缺陷复测结果

| 缺陷 | 原优先级 | 独立复测方法 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| `DEF-REAL-FS04-001` | P1 | 分别构造 `agent/job/user缺ID/user未确认` 四类真实写上下文，记录消息和平台调用 | 四类均返回 `TOOL_HUMAN_CONFIRMATION_REQUIRED`；`session.add` 为 0，平台调用为 0 | **Closed** |
| `DEF-REAL-FS04-002` | P1 | 模拟 HTTP 200 且平台 `code=45101001/36009003` | 两类均为 `unknown/TIKTOK_MESSAGE_RESULT_UNKNOWN`，每类只调用一次 | **Closed** |
| `DEF-REAL-FS04-003` | P2 | 输入 `1/0/"true"/"false"/null/[]/{}` 及合法 `true` | 7 个非法值全部拒绝，合法布尔 `true` 接受 | **Closed** |
| `DEF-REAL-FS04-004` | P2 | 直接解析运行时 `/openapi.json` | 幂等头 `required=true`；发送和对账均为 `BearerAuth OR CookieAuth`；安全方案存在 | **Closed** |

补充认证负向验证：显式但非法的 `Authorization` 头不能静默回退到 Cookie，返回 `TOKEN_INVALID`，未发现认证降级。

## 6. 测试结果汇总

| 测试项 | 结果 | 证据摘要 |
| --- | --- | --- |
| 独立缺陷探针 | 通过 | actor 4 类、非法确认值 7 类、OpenAPI 和未知错误集合全部通过 |
| REAL-FS-04 聚焦回归 | 通过 | 121 项通过，1 条既有弃用告警 |
| 默认后端全量回归 | 通过 | 1183 项通过，10 项按条件跳过，2 条既有弃用告警 |
| 隔离 PostgreSQL 全量回归 | 通过 | 空库 001→021，1193 项通过，2 条既有弃用告警 |
| 迁移可逆性 | 通过 | `021→020→021` 成功，最终恢复 `021_message_unknown (head)` |
| Ruff | 通过 | 正式源码目录 220 个文件通过检查和格式校验 |
| mypy | 通过 | 161 个源文件无类型错误 |
| uv 锁文件 | 通过 | 离线解析 125 个包 |
| 前端测试 | 通过 | 31 项通过 |
| 前端 lint/typecheck/build | 通过 | ESLint、TypeScript 和 Next.js 15.5.23 构建通过，14 个静态页面生成 |
| Compose 基础配置 | 通过 | 配置解析成功 |
| 人工消息生产叠加 | 通过 | 模拟开关为 true 时只有 backend=true；worker/jobs、高风险写入和自动回复均为 false |
| 健康检查 | 通过 | `/v1/health=ok`，`/v1/health/ready=ready` |
| Python 生产依赖审计 | **失败（继承阻断）** | `transformers 5.5.4` 命中 `GHSA-xrqw-3rrv-vx5w/CVE-2026-9856`，修复版本 5.10.0 |
| 前端生产依赖审计 | **失败（继承阻断）** | npm 官方 registry 报告 3 个 High，涉及 `next/postcss/sharp`；自动修复要求 Next 16 破坏性升级 |
| 真实店铺发送 | 未执行 | 生产门禁未放行，本轮禁止触达真实客户 |

## 7. 代码与安全审查结论

### 7.1 真实写入主体边界

`SqlAlchemyToolExecutor._send_platform_message` 在解析到真实写适配器后、查询未对账消息和创建 `processing` 消息前，强制要求：

```text
actor_type == user
actor_id != null
human_confirmed == true
```

四类失败路径均未创建半成品消息、未提交事务、未调用平台适配器。AI Agent 和后台 Job 无法通过设置普通布尔值复用人工消息开关。

### 7.2 平台未知结果

写接口维护独立的 `WRITE_UNKNOWN_PLATFORM_CODES`，包含当前官方两个内部错误。网络异常、HTTP 5xx、非法响应、成功响应缺少数字消息 ID 和内部错误均为 `unknown`；写客户端没有重试循环，符合“可能产生副作用时停止重试”的规则。

### 7.3 输入与 OpenAPI

`confirmed` 在 Pydantic 类型转换前使用原始值身份比较，只允许真正的 JSON 布尔 `true`。幂等头通过必填依赖直接进入 OpenAPI；认证依赖声明 Bearer 与 HttpOnly Cookie 两种方案，接口说明包含权限、店铺、CSRF、幂等和未知结果。

### 7.4 前端与配置

前端仍要求发送前二次确认，AI 建议只填入编辑框，不自动发送。生产人工消息叠加只允许 backend 接收普通消息开关，worker、jobs、高风险写入和自动回复保持 false。

## 8. 继承阻断与环境观察

### 8.1 生产依赖安全

本轮确认 001 号报告中的依赖阻断仍存在，不重复创建 REAL-FS-04 缺陷：

- Python：`transformers 5.5.4` 存在路径穿越漏洞公告，锁定版本尚未升级。
- 前端：npm 官方 registry 仍报告 3 个 High；建议修复会升级至 Next 16，必须由全栈开发工程师评估兼容性并经架构师确认。
- `DEF-REAL-FS01-005/006` 保持 Open，REAL-FS-01 仍不通过。

即使 REAL-FS-04 四项缺陷已关闭，仍不得据此开启真实平台消息写入。

### 8.2 测试环境观察

- 默认后端首次执行时指定的 `--basetemp` 父目录不存在，产生 2 个临时目录创建错误；在工作区创建专用父目录后同一套测试 1183 项全部通过，因此不登记产品缺陷。
- 前端首次构建与前一构建进程重叠，`.next` 产物出现一次 JSON 解析错误；确认后清理精确派生目录并串行构建，14 个页面全部成功，因此不登记产品缺陷。
- Ruff 扫描其他 Agent 遗留且访问受限的临时目录时可能出现 Windows 访问警告；限定正式源码目录后检查与格式全部通过。
- 本轮 `postgres-test` 容器和测试临时目录已在确认精确路径后删除，未触碰开发或真实数据库。

## 9. 主要执行命令与证据

```text
聚焦回归：
.venv/Scripts/pytest tests/test_auth_cookies.py tests/test_tiktok_write.py tests/test_tool_executor.py tests/test_phase3_domain.py tests/test_real_runtime_config.py -q
结果：121 passed

默认后端：
.venv/Scripts/pytest -q -rs --basetemp=.test-artifacts/real-fs04-retest-002
结果：1183 passed, 10 skipped

隔离 PostgreSQL：
scripts/run-postgres-integration-tests.ps1 -KeepDatabase
结果：001→021；1193 passed；021→020→021；最终 head=021_message_unknown

静态质量：
ruff check app tests scripts migrations
ruff format --check app tests scripts migrations
mypy app scripts
uv --no-cache lock --check --offline
结果：通过；220 个格式文件；161 个类型文件；125 个锁定包

前端：
npm run lint
npm run typecheck
npm run test
npm run build
结果：31 passed；lint/typecheck/build 通过；14 个静态页面

配置和运行态：
docker compose config
docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.tiktok-manual.yml config
GET /v1/health
GET /v1/health/ready
结果：配置通过；backend 人工写开关可独立灰度；健康状态 ok/ready

依赖审计：
uv --no-cache audit --locked
npm audit --registry=https://registry.npmjs.org --omit=dev --audit-level=high
结果：Python 1 个已知漏洞；前端 3 个 High
```

独立缺陷探针只使用进程内模拟对象、Mock HTTP 响应和运行时 OpenAPI，不创建持久产品测试文件，不连接真实 TikTok。

## 10. 验收与放行建议

### 10.1 当前工程验收

建议接受 REAL-FS-04 当前确定性工程范围，关闭 `DEF-REAL-FS04-001～004`。当前代码已具备进入后续真实灰度前评审的功能基础。

### 10.2 生产放行结论

**不建议开启真实 TikTok 普通消息写入。** 在以下条件全部满足前，保持所有真实写入开关关闭：

1. REAL-FS-01 的生产依赖和日志缺陷完成修复并由测试工程师复测关闭。
2. 架构师确认目标环境 HTTPS、固定出口 IP、密钥轮换、备份恢复和回滚门禁。
3. 真实店铺 OAuth、`seller.customer_service` Scope、会话可发送状态和账号权限验证通过。
4. 单店铺、单账号、单操作员发送一条无敏感信息的测试消息，并在 TikTok 后台核对消息 ID 和内容。
5. 完成一次真实 `unknown` 人工对账和开关关闭演练。
6. 测试工程师生成真实灰度专项报告，架构师签署放行记录。

推荐顺序：

```text
关闭依赖与基础设施阻断
→ 核对真实 OAuth 和 Scope
→ 开启单一 backend 人工消息开关
→ 发送一条人工测试消息
→ 平台后台核对
→ unknown 对账演练
→ 关闭开关并验证回滚
→ 架构师决定是否扩大灰度
```

本报告不覆盖也不授权高风险写入、主动营销或 AI 自动回复。
