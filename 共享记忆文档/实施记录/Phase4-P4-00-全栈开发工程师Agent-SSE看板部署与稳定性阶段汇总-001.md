# SSE、看板、部署与稳定性阶段汇总实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00 阶段汇总；关联 P2-09、P4-01～P4-11 |
| 模块编号 | M02、M04、M05、M06 |
| 主责 Agent | 全栈开发工程师Agent |
| 协作 Agent | 架构师Agent、AIAgent开发工程师Agent、测试工程师Agent |
| 实施状态 | 已完成 |
| 开始日期 | 2026-08-22 |
| 完成日期 | 2026-08-22 |
| 代码位置 | `CRM智能聊天系统/` |

## 2. 需求与依据

- 产品需求：`共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md`。
- 接口依据：`共享记忆文档/智能客服平台 — 管理端接口文档.md`，已增加 11.6 Phase 4 接口增量。
- 架构依据：`架构师/ARCH-001-SYS-系统总体架构设计-v1.1.md`、`架构师/ARCH-003-DATA-数据库与向量库初版设计-v1.0.md` 及后续增量设计。
- 任务依据：`全栈开发工程师/PLAN-001-全栈工程实施计划-v1.0.md` Phase 4 和用户确认的 Phase 4 详细实施计划。
- 验收依据：`共享记忆文档/MVP范围与验收标准.md`。
- 代码规范：`共享记忆文档/代码编写手册.md`。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 交付可信会话 AI 建议、POST SSE 传输、默认关闭的自动化闭环、运营看板、Agent 运营配置、店铺/渠道/团队设置和生产稳定性工具。

### 3.2 实施范围

- 迁移 016～017、Agent 任务、每日指标、最后登录时间。
- `/suggest`、`/chat/query`、看板、`/agents`、`/settings/team` API。
- 工作台建议、看板、Agent 运营、店铺、渠道和团队页面。
- Redis 限流/并发控制、普通 API 超时、JSON 日志、Agent Worker、生产 Compose、非 root 镜像、备份恢复和压测脚本。

### 3.3 非目标

- 不修改 AI Agent 的 Prompt、模型路由、RAG、阈值算法和工作流节点。
- 不宣称 SSE 为模型原生 Token 流。
- 不宣称完成真实 TikTok、Shopee、Amazon 写操作联调。
- 不在本次编码会话伪造真实模型生产 P99、五天连续稳定性或 99.5% 可用性结论。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单。
- [x] 已读取相关 PRD、接口、任务拆解和验收标准。
- [x] 涉及代码时已读取代码编写手册和适用 Skill。
- [x] 已确认 Phase、任务编号、模块编号和主责 Agent。
- [x] 已确认依赖、风险和验收方式。

## 5. 实施方案

### 5.1 方案说明

- Webhook Worker 仍只负责标准化和业务落库；满足显式开关和启用配置时，按 `trigger_message_id` 唯一创建 `agent_tasks`。
- 独立 Agent Worker 通过 `SKIP LOCKED` 认领任务，调用既有 Agent 工作流；Mock 适配器的 `real_writes=false` 在发送前失败关闭。
- 建议接口只接受可信会话 ID，服务端读取当前客户消息、最近 10 条历史和订单上下文。SSE 按固定事件契约传输安全草稿。
- Jobs Worker 每五分钟幂等聚合店铺当天和前一天数据；回填脚本按店铺和日期范围重建。
- Agent 运营 API 只写名称、说明、状态和白名单工具；AI 运行参数只读。日志响应只返回低敏运行字段。

### 5.2 依赖关系

- 前置依赖：迁移 `015_vector_ops`、Phase 2 会话/平台能力、Phase 3 工具与营销、AI Agent Phase 1～3 工作流。
- 后续依赖：测试工程师执行真实模型 SSE 性能、持续稳定性、浏览器无障碍和生产恢复演练；平台工程继续接入真实写适配器。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| Mock 被误认为真实发送 | 产生错误业务结论 | `real_writes=false`，自动发送前阻断并记录 `blocked_mock` |
| SSE 重试产生副作用 | 重复发券/发送 | 建议链路不开放写工具；客户端只填充输入框 |
| Worker 崩溃遗留 processing | 任务永久卡住 | 五分钟后允许重新认领，最多三次；未知写结果不重试 |
| 店铺时区在 Windows 缺失 | 指标日期错误 | 锁定 `tzdata==2026.3`，创建店铺时校验 IANA 时区 |
| 敏感内容进入日志 | 信息泄露 | 单行 JSON 低敏字段；不记录正文、地址、Token、密钥或供应商响应 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `backend/migrations/versions/016_create_agent_configs_and_tasks.py` | 新增 | Agent 配置、可靠任务、Agent Run 关联 | 全栈开发工程师Agent |
| `backend/migrations/versions/017_create_metric_daily_and_user_metadata.py` | 新增 | 每日指标、响应样本、最后登录和查询索引 | 全栈开发工程师Agent |
| `backend/app/agent_management/` | 新增 | Agent 运营 CRUD、只读 AI 参数和脱敏日志 | 全栈开发工程师Agent |
| `backend/app/chat/` | 新增 | 建议、SSE、自动任务 Worker | 全栈开发工程师Agent |
| `backend/app/dashboard/` | 新增 | 聚合、查询和看板指标定义 | 全栈开发工程师Agent |
| `backend/app/users/` | 新增/修改 | 团队列表、创建、角色范围、禁用保护 | 全栈开发工程师Agent |
| `frontend/app/dashboard|agents|settings/` | 新增/修改 | 看板、Agent 运营和系统设置页面 | 全栈开发工程师Agent |
| `frontend/app/workspace/page.tsx`、`frontend/lib/api.ts` | 修改 | POST SSE、UTF-8 解析、取消和建议填充 | 全栈开发工程师Agent |
| `docker-compose.prod.yml`、`Dockerfile.frontend.prod`、`Dockerfile.backend` | 新增/修改 | 生产覆盖、standalone、非 root 镜像 | 全栈开发工程师Agent |
| `scripts/*postgres.ps1`、`scripts/*minio.ps1` | 新增 | 带目标确认的备份恢复脚本 | 全栈开发工程师Agent |
| `backend/scripts/backfill_metrics.py`、`backend/scripts/load_test_sse.py`、`backend/scripts/verify_phase4_runtime.py` | 新增 | 指标回填、50 并发脚本和核心 API 验收 | 全栈开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：新增建议/SSE、五个看板接口、Agent 运营接口和团队管理接口；统一记录权限与店铺隔离描述。
- 数据库：新增 `agent_configs`、`agent_tasks`、`metric_daily`；`agent_runs.agent_config_id`、`users.last_login_at`；迁移 head 为 `017_phase4_metrics`。
- 配置项：新增指标周期、普通请求超时、聊天限流/并发、自动回复开关/轮询/重试；`AUTO_REPLY_ENABLED=false`。
- AI：未修改 Prompt、模型、RAG、阈值和工作流节点；仅通过既有工作流契约调用并补充运营配置关联。

### 6.3 关键实现说明

- `metric_daily` 保存 `response_count`，跨日平均响应时间使用样本数加权，避免“日平均再平均”偏差。
- SSE 断线使用 `AbortController`；后端正常检测断线时产生 `done: disconnected`，取消异常不继续写业务。
- Redis IP 键使用 SHA-256 摘要，不信任未配置代理的转发头。
- 团队角色调整必须指定店铺范围；禁用不物理删除，禁用用户不能继续解析 Access Token 或刷新 Token。
- 生产 Compose 清除源码挂载和 reload，应用镜像以 `crm` 用户运行，前端使用 standalone runner。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| 后端静态检查 | `uv run ruff check .`、`uv run ruff format --check .`、`uv run mypy app scripts` | 全通过 | 全通过，141 个类型检查源文件 | 通过 |
| 后端回归 | `uv run pytest -q` | 无失败 | 116 passed / 4 skipped | 通过 |
| 空库迁移与数据库回归 | `scripts/run-postgres-integration-tests.ps1` | 001→017 和数据库测试通过 | 120 passed，临时库已移除 | 通过 |
| 迁移回滚 | 017→015→016→017 | 逐级可逆 | head 恢复为 017，`response_count` 存在 | 通过 |
| 前端检查 | `npm run lint/typecheck/test/build` | 全通过 | 19 passed，14 路由构建成功 | 通过 |
| 依赖审计 | `uv audit --locked` | 无已知漏洞 | 124 个包未发现已知漏洞 | 通过 |
| Compose 运行 | 重建 backend/frontend/worker/jobs | 服务健康 | 基础七服务健康；Agent Worker 单独启动通过 | 通过 |
| 非 root | 容器 `id` | 应用不以 root 运行 | 后端 UID 999；生产前端 UID 100 | 通过 |
| 核心 API | `python -m scripts.verify_phase4_runtime` | 店铺/Agent/看板/团队/SSE 通过 | 全部 True，临时数据已清理 | 通过 |
| 结构化日志 | 检查 backend/jobs/agent-worker 日志 | 单行 JSON | Uvicorn、应用和 Worker 均为 JSON | 通过 |
| 生产前端镜像 | `docker build -f Dockerfile.frontend.prod ...` | standalone 构建成功 | 使用本地缓存 Node 20 摘要构建成功 | 通过 |
| 固定 Node 标签拉取 | 默认生产 Dockerfile 构建 | 拉取固定标签 | Docker Hub OAuth 网络超时 | 未执行完成 |
| 50 并发真实模型 SSE | `scripts/load_test_sse.py` | 形成真实模型 P99 证据 | 脚本已提供；当前 AI 默认关闭且无授权压测会话 | 未执行 |
| 五天稳定性 | 测试工程师持续运行 | 形成可用性报告 | 一次编码会话无法完成 | 未执行 |

## 8. 实施结果

- 完成项：Phase 4 代码、迁移、页面、配置、运行 Worker、部署覆盖、备份恢复、压测能力、README、接口文档和自动化测试。
- 未完成项：真实平台写联调、真实模型 50 并发 P99、五天稳定性和正式测试报告。
- 与原方案差异：Windows 环境补充锁定 `tzdata`；生产固定 Node 标签因外网认证超时未拉取，改用本地缓存 `node:20-alpine@sha256:fb4c...` 验证 Dockerfile。
- 当前状态：工程实施已完成，等待测试工程师在授权环境完成正式性能与持续稳定性验收。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-P4-001 | 三平台仍为契约级 Mock，`real_writes=false` | P0 | 全栈开发工程师Agent、架构师Agent | 真实平台接入任务 |
| R-P4-002 | 真实模型 50 并发、首分块与 P99 未复测 | P1 | 测试工程师Agent、AIAgent开发工程师Agent | Phase4 正式性能测试 |
| R-P4-003 | 五天连续稳定性和 99.5% 可用性无正式报告 | P1 | 测试工程师Agent | Phase4 稳定性测试 |
| R-P4-004 | Docker Hub 固定 Node 标签在当前网络无法拉取 | P2 | 环境维护者、全栈开发工程师Agent | 发布环境镜像预热 |

## 10. 交接事项

- 交接给：测试工程师Agent、AIAgent开发工程师Agent、架构师Agent。
- 后续任务：执行 SSE/自动化/看板/Agent/团队 E2E，真实模型 50 并发和五天稳定性；真实平台适配器接入后复验自动发送。
- 必须注意：不要把传输层 `delta` 标记为模型 Token 流；不要在 Mock 平台开启真实自动发送；压测凭证只通过环境变量提供。

## 11. 文档同步

- [x] 已同步接口变化。
- [x] 已同步架构/运行边界。
- [x] 已同步任务状态。
- [x] 已明确测试工程师需要覆盖的范围。
- [x] 测试报告索引将在正式测试完成后更新。
