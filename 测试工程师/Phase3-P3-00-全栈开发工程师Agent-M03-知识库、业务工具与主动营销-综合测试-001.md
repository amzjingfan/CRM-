# Phase 3 知识库、业务工具与主动营销综合测试报告

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| 报告编号 | Phase3-P3-00-M03-001 |
| Phase | Phase3 |
| 任务编号 | P3-00（阶段汇总） |
| 模块编号 | M03 |
| 模块名称 | 知识库、业务工具与主动营销 |
| 被测主责 Agent | 全栈开发工程师Agent |
| 测试执行 Agent | 测试工程师Agent |
| 测试类型 | 综合测试、回归测试、数据库测试、接口测试、安全测试、浏览器兼容性测试 |
| 测试日期 | 2026-08-20 |
| 权威实施记录 | `共享记忆文档/实施记录/Phase3-P3-00-全栈开发工程师Agent-知识库业务工具与主动营销阶段汇总-001.md` |
| 最终结论 | **不通过，不建议进入 Phase 3 验收** |

## 2. 测试结论

Phase 3 的工程主链路已具备可运行基础：迁移可逆、pgvector 与核心表/索引可用、知识库 CSV/XLSX 解析和异步导入冒烟通过、受控工具基本幂等和跨店铺隔离通过、前端可构建并可在四个目标宽度正常展示。

但本轮独立测试发现 5 个 P1 和 3 个 P2 未关闭缺陷，其中以下问题直接阻断验收：

1. 平台发送结果为 `unknown` 后，第二轮会把营销事件误标为 `succeeded`。
2. 同一客户同一活动的 24 小时冷却可在同一扫描周期被绕过，实测产生两次优惠券发放。
3. 7 个知识库/营销前端写操作未携带 `Idempotency-Key`，现有前端测试产生假阳性。
4. Phase 3 约定的知识库编辑/分类树和营销编辑/删除页面能力未交付。
5. 宿主机生产构建和 Compose 开发容器共享 `.next`，正常验收命令序列可使前端持续 500。

因此本报告结论为：**不通过；修复全部 P1 后必须由测试工程师执行独立复测。**

## 3. 测试依据与边界

### 3.1 测试依据

- `全栈开发工程师/PLAN-001-全栈工程实施计划-v1.0.md` 的 Phase 3。
- 用户确认的“Phase 3：知识库、业务工具与主动营销实施计划（基于当前代码重制）”。
- `共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md`。
- `共享记忆文档/智能客服平台 — 管理端接口文档.md` 的 Phase 3 已实现接口增量。
- `共享记忆文档/MVP范围与验收标准.md`。
- `架构师/ARCH-001-SYS-系统总体架构设计-v1.1.md`。
- `架构师/ARCH-003-DATA-数据库与向量库初版设计-v1.0.md`。
- 项目及各目录 `AGENTS.md`、`共享记忆文档/代码编写手册.md`。

### 3.2 本轮覆盖

- 010～013 迁移升级、回滚、恢复及数据库约束。
- FAQ 分类、条目、发布门禁、CSV/XLSX 解析、MinIO 和 Jobs 异步导入。
- 订单物流、Mock 地址、Mock 发券、工具调用幂等和审计边界。
- 店铺级资源隔离及越权统一 404。
- 弃单营销、AI 等待态、重试、结果未知、冷却和频控。
- 前端知识库、营销、Agent 状态页面、构建、主题、语言和响应式。
- OpenAPI 对权限、隔离、幂等、Mock、异步状态和统一错误的描述。
- Phase 1、Phase 2 和现有 AI Agent 自动化回归。

### 3.3 非目标

- 真实 TikTok Shop、Shopee、Amazon 写操作联调。
- 真实 Embedding/RAG、AI 自动回复、AI 营销文案和 Agent 工具选择。
- 生产部署、正式性能压测和真实模型质量门禁。

上述非目标不作为本轮全栈缺陷，但 Mock 标识、等待态和接口边界纳入测试。

## 4. 测试环境

| 项目 | 实际环境 |
| --- | --- |
| 操作系统 | Windows，PowerShell |
| Python | 项目当前 3.11 基线，`uv` 管理 |
| Node.js / Next.js | Node.js 本地环境；Next.js 15.5.23 |
| 数据库 | PostgreSQL 16 + pgvector |
| 缓存/对象存储 | Redis 7、MinIO |
| 容器 | Docker Compose：backend、frontend、postgres、redis、minio、worker、jobs |
| Alembic 最终版本 | `013_marketing (head)` |
| 浏览器 | Codex In-app Browser，本地实际页面 |

环境说明：迁移回滚测试后，旧 Jobs 镜像因缺少新增的 `tiktoken` 依赖启动失败；按当前 `uv.lock` 重建 Jobs 镜像后，容器常驻且同一运行时脚本通过。该问题归为部署制品同步风险，未计入未关闭产品缺陷。

## 5. 执行结果总览

| 测试项 | 方法或命令 | 结果 | 状态 |
| --- | --- | --- | --- |
| 锁文件 | `uv lock --check` | 解析成功 | 通过 |
| Python 规则检查 | `uv run ruff check .` | All checks passed | 通过 |
| Python 格式 | `uv run ruff format --check .` | 146 files already formatted | 通过 |
| Python 类型 | `uv run mypy app scripts` | 110 个源文件无问题 | 通过 |
| 后端回归 | `uv run pytest -q -rs` | 64 通过，2 跳过，2 个弃用警告 | 通过（有环境说明） |
| 依赖安全 | `uv audit` | 85 个包未发现已知漏洞或不良状态 | 通过 |
| 前端 lint | `npm run lint` | 通过 | 通过 |
| 前端类型 | `npm run typecheck` | 通过 | 通过 |
| 前端测试 | `npm run test` | 7/7 通过 | 通过，但发现覆盖假阳性 |
| 前端构建 | 停止开发容器后执行 `npm run build` | 8 个路由构建成功 | 通过 |
| Compose 配置 | `docker-compose config -q` | 配置合法 | 通过 |
| Compose 服务 | `docker-compose ps` | 7 个服务运行，声明健康检查的服务健康 | 通过 |
| 健康接口 | `GET /v1/health` | HTTP 200，`code=0` | 通过 |
| 迁移可逆性 | `013 → 009 → 013` | 表和权限随迁移正确删除/恢复 | 通过 |
| 数据库结构 | SQL 元数据查询 | pgvector、9 张 Phase 3 表、关键索引和 12 个状态约束存在 | 通过 |
| Phase 3 主链路 | `scripts/verify_phase3_runtime.py` | 知识、导入、工具、营销管理通过并清理夹具 | 通过 |
| 跨店铺隔离 | 临时主管账号 + 两店铺 API 专项 | 5 个越权场景全部 404 | 通过 |
| XLSX/行数边界 | 内存 XLSX 与 5001 行 CSV 专项 | XLSX 解析成功；5001 行返回 `TOO_MANY_ROWS` | 通过 |
| 营销 unknown | 真实 PostgreSQL + Mock 超时专项 | 第二轮误标成功 | **失败** |
| 营销冷却/频控 | 同客户两笔弃单专项 | 2 个事件均成功并发券 | **失败** |
| 前端写请求幂等 | API 客户端逐函数矩阵 | 7 个知识/营销写操作无幂等头 | **失败** |
| Phase 3 页面范围 | 实际 DOM 与代码/API 对照 | 编辑、删除、分类树等能力缺失 | **失败** |
| 前端构建/运行隔离 | `npm run build` 后恢复 Compose 前端 | 开发容器持续 500，清理 `.next` 后才恢复 | **失败** |
| 浏览器响应式 | 375/768/1024/1440 | 无横向溢出，按钮最小高度 44px | 通过 |
| 主题与控制台 | 浏览器交互和日志 | 明暗主题有效，无控制台错误 | 通过 |
| 中英文 | 浏览器语言切换 | 仅导航/页头翻译，正文及 `html lang` 未切换 | **失败** |
| URL 状态 | 知识库筛选后读取 URL | 仅保留 `store_id` | **失败** |
| OpenAPI 描述 | `/openapi.json` 抽查 | 权限、隔离、统一错误等说明不完整 | **失败** |

后端 2 项跳过用例均为 AI RAG PostgreSQL 集成测试，原因是未提供独立测试数据库；本轮已经在当前 Compose 数据库单独验证 Phase 3 pgvector、迁移和店铺隔离，不将这两项计为全栈 Phase 3 阻断缺陷。

## 6. 关键通过证据

### 6.1 迁移和数据完整性

- 初始版本：`013_marketing (head)`。
- 回滚到 `009_agent_runs` 后，9 张 Phase 3 表计数为 0，5 个 Phase 3 权限计数为 0。
- 再次升级后恢复到 `013_marketing (head)`。
- `vector` 扩展存在。
- `idx_knowledge_chunks_embedding`、`uq_tool_call_store_idempotency`、`uq_marketing_event_source` 存在。
- 分类层级、文档状态、向量状态、导入状态、工具状态、评分、营销活动和营销事件状态约束均存在。

### 6.2 店铺隔离

主管账号只授权店铺 A，测试资源全部位于店铺 B，结果如下：

```json
{
  "knowledge_direct": 404,
  "knowledge_filtered": 404,
  "order_direct": 404,
  "marketing_direct": 404,
  "marketing_filtered": 404
}
```

直接资源 ID 和 `store_id` 筛选均未泄露资源存在性。

### 6.3 浏览器与响应式

知识库页面实测结果：

| 宽度 | 横向溢出 | 最小可见按钮高度 | 页面加载 |
| --- | --- | --- | --- |
| 375 | 无 | 44px | 成功 |
| 768 | 无 | 44px | 成功 |
| 1024 | 无 | 44px | 成功 |
| 1440 | 无 | 44px | 成功 |

知识库和营销页面均能显示加载后数据、AI `waiting_ai` 提示和 Mock 边界文案，浏览器警告/错误日志为空。

## 7. 未关闭缺陷

### DEF-P3-001：unknown 工具结果被营销事件误标为成功

| 项目 | 内容 |
| --- | --- |
| 优先级 | P1 |
| 模块 | `marketing` / `tools` |
| 状态 | 未修复 |
| 影响 | 平台发送结果未知时，营销统计和运营界面可能显示成功，无法确认客户是否真正收到消息 |

复现步骤：

1. 创建模板消息活动、客户、会话和已连接渠道。
2. 让平台适配器首次发送抛出超时异常。
3. 执行一次到期事件，确认工具状态为 `unknown`、事件为 `failed`。
4. 将 `next_attempt_at` 推进到当前时间并再次执行同一事件。

实际结果：

```json
{
  "first_event_status": "failed",
  "second_event_status": "succeeded",
  "attempt_count": 2,
  "adapter_send_calls": 1,
  "tool_status": "unknown"
}
```

预期结果：`unknown` 必须失败关闭，不再调用平台，也不能把营销事件置为成功。

代码证据：`app/tools/repository.py` 把 `unknown` 视为可重放终态；`app/marketing/worker.py` 在重放时直接返回调用 ID，随后无条件设置事件为 `succeeded`。

修复建议：工具重放结果必须携带原终态；营销执行器只接受明确的 `succeeded`，`unknown` 应直接关闭事件并保留未知结果审计。

### DEF-P3-002：同一扫描周期绕过 24 小时营销冷却

| 项目 | 内容 |
| --- | --- |
| 优先级 | P1 |
| 模块 | `marketing` |
| 状态 | 未修复 |
| 影响 | 同一客户可能在短时间内收到多次优惠券或消息，违反触达频控并造成骚扰和成本风险 |

复现步骤：

1. 为同一客户创建两笔超过触发时长的未支付订单。
2. 创建 `send_coupon` 弃单活动，配置 24 小时冷却。
3. 执行一次事件发现，再连续执行两个到期事件。

实际结果：

```json
{
  "events_discovered_same_cycle": 2,
  "events_succeeded": 2,
  "coupon_issuances": 2,
  "configured_cooldown_hours": 24
}
```

预期结果：同一客户和活动在冷却窗口内最多创建并执行一个触达事件。

根因：发现阶段只统计已成功事件，不包含本轮新建的 `pending/processing` 事件；执行阶段也没有再次校验冷却与 30 天频次。

修复建议：增加客户/活动维度的数据库防重或窗口锁；发现和执行两处均检查 `pending/processing/succeeded`，并加入并发回归测试。

### DEF-P3-003：知识库和营销写请求未携带幂等键

| 项目 | 内容 |
| --- | --- |
| 优先级 | P1 |
| 模块 | 前端 API 客户端、知识库、营销 |
| 状态 | 未修复 |
| 影响 | 网络重试或重复点击可能重复创建 FAQ、导入任务或营销活动 |

逐函数检查结果：

```json
{
  "createKnowledgeCategory": false,
  "createKnowledgeEntry": false,
  "publishKnowledgeEntry": false,
  "archiveKnowledgeEntry": false,
  "importKnowledge": false,
  "createCampaign": false,
  "setCampaignEnabled": false,
  "updateShippingAddress": true,
  "issueCoupon": true,
  "transferSession": true
}
```

现有 `frontend/tests/phase3.test.mjs` 只确认整个 `api.ts` 中出现过 `Idempotency-Key`，没有逐个写函数断言，因此测试虽然通过但没有覆盖需求。

修复建议：统一为所有非安全方法生成幂等键，并由后端对可能产生重复副作用的接口强制校验；前端测试必须逐函数断言请求头。

### DEF-P3-004：Phase 3 管理页面功能范围不完整

| 项目 | 内容 |
| --- | --- |
| 优先级 | P1 |
| 模块 | 知识库页面、营销页面 |
| 状态 | 未修复 |
| 影响 | 运营人员无法通过管理端完成计划约定的完整管理流程 |

实际页面和 API 客户端只提供：

- 知识库：新增分类、创建 FAQ、发布、归档、导入；分类以平铺标签显示。
- 营销：创建、启用、停用和查看事件。

缺失：

- 分类树展示及分类编辑/删除入口。
- FAQ 编辑入口。
- 营销活动编辑和删除入口。

后端已经存在相应 PATCH/DELETE 接口，因此属于前端交付缺口。

### DEF-P3-005：宿主机生产构建会破坏 Compose 前端开发运行态

| 项目 | 内容 |
| --- | --- |
| 优先级 | P1 |
| 模块 | Docker Compose / Next.js 前端 |
| 状态 | 未修复 |
| 影响 | 按测试计划执行生产构建并恢复 Compose 后，前端健康检查失败且 `/login` 持续返回 500 |

复现步骤：

1. 启动 Compose 前端开发容器，其配置将整个 `./frontend` 挂载到 `/app`。
2. 停止前端容器，在宿主机执行 `npm run build`。
3. 再次启动 Compose 前端容器并访问 `/login`。

实际结果：

```text
Cannot find module './833.js'
Require stack:
- /app/.next/server/webpack-runtime.js
- /app/.next/server/pages/_document.js
GET /login 500
```

容器状态变为 `unhealthy`。停止容器、删除已校验的可再生目录 `frontend/.next` 并重启后，HTTP 200 和 healthy 恢复。

预期结果：宿主机构建产物与容器开发构建相互隔离，执行项目规定的构建/Compose 验收顺序不会破坏运行态。

修复建议：为 `/app/.next` 使用独立命名卷，或为宿主机和容器配置不同的构建目录；CI 中禁止共享同一 `.next`。

### DEF-P3-006：中英文切换只覆盖导航，页面语义语言未更新

| 项目 | 内容 |
| --- | --- |
| 优先级 | P2 |
| 模块 | 前端国际化、可访问性 |
| 状态 | 未修复 |

浏览器切换语言后，导航和页头显示英文，但知识库/营销正文、表单、状态和按钮仍为中文；`document.documentElement.lang` 仍为 `zh-CN`。

预期结果：Phase 3 页面文案完整切换，且 `html lang` 与当前语言一致。

### DEF-P3-007：筛选和分页状态未完整保存到 URL

| 项目 | 内容 |
| --- | --- |
| 优先级 | P2 |
| 模块 | 知识库页面、营销页面 |
| 状态 | 未修复 |

知识库输入 `search=退货` 并选择 `status=published` 后，URL 仍只有：

```text
/knowledge?store_id={store_id}
```

营销页面也只保存 `store_id`，页面固定请求第一页和 100 条，没有 URL 分页状态。

### DEF-P3-008：OpenAPI 未完整记录 Phase 3 契约要求

| 项目 | 内容 |
| --- | --- |
| 优先级 | P2 |
| 模块 | OpenAPI / 接口文档 |
| 状态 | 未修复 |

抽查知识分类创建、导入和营销活动创建接口，只看到 CSRF/认证参数和 200/202/422 响应；接口描述未明确所需权限、店铺隔离、统一错误码及全部幂等规则。地址修改接口能够展示 `Idempotency-Key` 和 Mock 描述，但仍未列出权限及完整统一错误响应。

## 8. 环境与测试风险

| 编号 | 风险 | 影响 | 处理结果 |
| --- | --- | --- | --- |
| ENV-P3-001 | Jobs 使用旧镜像，缺少 `tiktoken` | 首次异步导入冒烟无人消费 | 按当前锁文件重建后通过；建议 CI 强制重建或校验镜像摘要 |
| ENV-P3-003 | 2 项 AI RAG 测试缺少独立 PostgreSQL 测试库 | 自动化显示 skipped | 不属于本轮全栈 Phase 3 阻断项，后续 AI 集成复测处理 |
| ENV-P3-004 | pytest 有 Starlette/httpx、argon2 弃用警告 | 后续升级可能破坏兼容 | P3 依赖治理项 |

## 9. 回归结论与验收建议

- Phase 1/2 既有认证、平台适配和工作台自动化未出现阻断性回归。
- Phase 3 数据库迁移、知识导入主链路、店铺隔离、Mock 标识、基础工具幂等、构建和响应式通过。
- 主动营销的失败关闭和冷却频控未达到验收标准。
- 前端写请求幂等和约定管理功能未达到验收标准。
- 前端生产构建与 Compose 开发运行态未实现构建目录隔离。

**验收建议：不通过，不建议合并为 Phase 3 已验收状态，也不建议启用主动营销 Jobs 对真实客户执行。**

## 10. 复测门禁

复测前必须满足：

1. 修复 DEF-P3-001～DEF-P3-005，并提供针对每个缺陷的自动化回归用例。
2. `unknown` 结果不得在任何重放路径变成成功。
3. 同客户/活动在并发、多来源和多 Worker 条件下均满足冷却及 30 天频控。
4. 所有前端写请求逐函数验证幂等头，后端对副作用接口定义明确策略。
5. 补齐知识库编辑/分类树和营销编辑/删除页面能力。
6. P2 缺陷至少给出修复版本和复测计划。
7. 重新执行 009→013→009→013、完整后端/前端回归、Compose 主链路和四断点浏览器测试。

## 11. 测试数据与环境恢复

- 所有临时用户、店铺、客户、订单、知识、营销事件、工具调用和优惠券记录均已清理。
- Alembic 已恢复为 `013_marketing (head)`。
- backend、frontend、postgres、redis、minio、worker、jobs 均已恢复运行。
- 为恢复前端，仅删除了可再生的 `frontend/.next` 构建产物；源码和依赖未删除。
- `/v1/health` 最终返回 HTTP 200、`code=0`。
- 测试工程师未修改任何产品代码。
