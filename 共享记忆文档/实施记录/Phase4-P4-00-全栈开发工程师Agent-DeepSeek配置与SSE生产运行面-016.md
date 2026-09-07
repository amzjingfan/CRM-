# DeepSeek配置与SSE生产运行面实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 REAL-FS-05 |
| 模块编号 | M02 |
| 主责 Agent | 全栈开发工程师Agent |
| 协作 Agent | 架构师Agent、AIAgent开发工程师Agent、测试工程师Agent |
| 实施状态 | 已完成 |
| 开始日期 | 2026-09-03 |
| 完成日期 | 2026-09-03 |
| 代码位置 | `CRM智能聊天系统/` |

## 2. 需求与依据

- 产品需求：`共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md` 的客服工作台与 AI 建议边界。
- 接口依据：`共享记忆文档/智能客服平台 — 管理端接口文档.md` 的 11.6、11.18。
- 架构依据：`架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`。
- 任务依据：`全栈开发工程师/PLAN-002-REAL-真实TikTok与DeepSeek运行面实施计划-v1.0.md` 的 REAL-FS-05。
- 验收依据：REAL-FS-05 的内部草稿、取消/断线、Provider 错误、50 客户端和五日稳定性要求。
- 代码规范：`共享记忆文档/代码编写手册.md`。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 为现有 DeepSeek Provider 提供可配置、可取消、可超时、可观测的生产 SSE 运行面。
- 保持安全草稿完成后再分块，不让模型原生 Token 绕过 AI 安全门禁。

### 3.2 实施范围

- 后端 SSE 心跳、总超时、任务取消、低敏错误与日志。
- DeepSeek 配置健康状态和受控生产 Compose 叠加。
- 前端显式取消、异常 EOF 与安全错误展示。
- 50 客户端压测终态分类和低敏证据输出。
- 环境、部署、接口与共享实施状态同步。

### 3.3 非目标

- 不修改 DeepSeek Provider、Prompt、RAG、回复策略、业务声明或模型质量算法。
- 不开放公开自动回复、AI 翻译、AI 营销、发券、改地址或自动平台写操作。
- 不使用真实 DeepSeek Key，不执行真实模型质量、50 客户端和五日稳定性正式验收。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单。
- [x] 已读取相关 PRD、接口、任务拆解和验收标准。
- [x] 涉及代码时已读取代码编写手册和适用 Skill。
- [x] 已确认 Phase、任务编号、模块编号和主责 Agent。
- [x] 已确认依赖、风险和验收方式。

## 5. 实施方案

### 5.1 方案说明

复用 `POST /v1/chat/query`。认证、权限、Origin/CSRF 和请求限流继续在建立流之前执行；流接受后创建受控工作流任务，周期检查客户端断线，发送无业务数据的 SSE 注释心跳，并在总预算到期时取消任务。安全草稿完成后才发送 `delta/result/done`。AI 内部错误只转换为公开数字码和固定中文消息，内部错误名仅进入低敏结构化日志。

### 5.2 依赖关系

- 前置依赖：REAL-AI-01 DeepSeek Provider 工程范围有条件通过；现有本地 BGE 服务、Agent 工作流、Cookie/CSRF 与 Redis 限流。
- 后续依赖：测试工程师执行真实模型、50 授权客户端和五日稳定性；架构师根据正式证据决定后续放行。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 浏览器断线后模型继续运行 | 消耗额度并占用并发 | 周期检查断线并取消、等待工作流清理 |
| 超时或限流被误算为成功 | 错误放行性能门禁 | 只有 `done.reason=completed` 计成功 |
| Provider 错误泄露内部信息 | 暴露配置或供应商正文 | 固定错误映射，公开事件不含内部错误名 |
| 配置开关扩散至后台任务 | 触发非预期 AI 生成或发送 | 独立叠加只允许 backend 读取 LLM 开关 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `backend/app/chat/router.py` | 修改 | SSE 心跳、总超时、取消、错误映射和低敏运行日志 | 全栈开发工程师Agent |
| `backend/app/shared/config/settings.py` | 修改 | 新增 SSE 超时与心跳配置及关系校验 | 全栈开发工程师Agent |
| `backend/app/shared/health.py` | 修改 | 新增不调用收费接口的 LLM 配置健康状态 | 全栈开发工程师Agent |
| `backend/scripts/load_test_sse.py` | 修改 | 修正成功判定，增加分类、时间戳和低敏文件输出 | 全栈开发工程师Agent |
| `backend/tests/test_real_fs05_sse_runtime.py` | 新增 | REAL-FS-05 配置、超时、错误和叠加契约测试 | 全栈开发工程师Agent |
| `backend/tests/test_sse_load_test.py` | 修改 | SSE 终态分类回归 | 全栈开发工程师Agent |
| `frontend/lib/api.ts` | 修改 | 终态校验、Reader 清理和意外断线错误 | 全栈开发工程师Agent |
| `frontend/app/workspace/page.tsx` | 修改 | 显式取消、错误保留和无障碍状态 | 全栈开发工程师Agent |
| `frontend/tests/phase4.test.mjs` | 修改 | 取消与终态契约回归 | 全栈开发工程师Agent |
| `.env.example` | 修改 | 新增低敏 SSE 配置模板 | 全栈开发工程师Agent |
| `docker-compose.deepseek-sse.yml` | 新增 | 内部草稿专用生产叠加 | 全栈开发工程师Agent |
| `deploy/nginx/nginx.conf` | 修改 | 关闭 SSE 请求缓冲并补充发送超时 | 全栈开发工程师Agent |
| `README.md`、`deploy/production/README.md` | 修改 | 启用、回滚、压测和边界说明 | 全栈开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：`POST /v1/chat/query` 请求和事件字段保持兼容，增加注释心跳与 `done.reason=timeout`；`/v1/health/ready` 增加 `llm_provider` 组件。
- 数据库：不适用；没有迁移或表结构变化。
- 配置项：新增 `CHAT_STREAM_TIMEOUT_SECONDS=180`、`CHAT_SSE_HEARTBEAT_SECONDS=15`，真实密钥未写入任何文件。
- AI：不修改 Provider、模型、Prompt、RAG、工具和阈值；复用既有 Agent 追踪。

### 6.3 关键实现说明

工作流作为独立异步任务运行。总超时或浏览器断线会取消并等待任务清理，最终释放 Redis 用户并发槽。已完成草稿在结果交付前断线时继续使用既有中断审计。模型、Embedding、Reranker 错误分别映射为 42901/50003/50001，公开响应不包含内部错误名。完成事件记录首个安全输出和总耗时；模型、Prompt、Token 与脱敏摘要继续由 `agent_runs` 记录。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| 锁文件 | `uv lock --check` | 锁文件一致 | 125 个包解析成功 | 通过 |
| Python 语法 | `uv run python -m compileall -q app scripts migrations` | 无语法错误 | 正常退出 | 通过 |
| Ruff | `uv run ruff check app tests scripts migrations` | 无告警 | All checks passed | 通过 |
| 格式 | `uv run ruff format --check app tests scripts migrations` | 无格式漂移 | 226 files already formatted | 通过 |
| mypy | `uv run mypy app scripts` | 严格类型通过 | 162 个源文件通过 | 通过 |
| 后端全量 | `uv run pytest -q --basetemp {项目内临时目录}` | 既有与新增测试通过 | 1230 passed，12 skipped，2 个依赖弃用告警 | 通过 |
| 前端检查 | `npm run lint && npm run typecheck && npm run test` | 全部通过 | 32 项测试通过 | 通过 |
| 前端构建 | `npm run build` | Next.js 生产构建成功 | 14 个静态页面生成，`/workspace` 构建成功 | 通过 |
| Compose | `docker-compose --profile ai ... config --services` | 生产 AI 叠加可解析 | 10 个服务解析成功；本机 Docker config 有访问告警但不影响退出码 | 通过 |
| Python 依赖审计 | `uv audit --locked` | 无已知漏洞 | 124 个包无已知漏洞和不良状态 | 通过 |
| 前端依赖审计 | `npm audit --registry=https://registry.npmjs.org --audit-level=high` | 无高危漏洞 | Next.js 间接依赖 PostCSS/Sharp 共 3 项 High；自动修复要求破坏性升级 Next 16 | 失败 |
| 真实模型 50 客户端 | 仓库外授权凭证池 | P99/首输出与错误率符合门禁 | 未提供真实 DeepSeek/50 组授权凭证 | 未执行 |
| 五日稳定性 | 连续五日低敏证据 | 可用性达到 99.5% | 需要真实环境持续运行 | 未执行 |

## 8. 实施结果

- 完成项：REAL-FS-05 的确定性工程运行面、配置、前端、证据工具、文档和自动化测试。
- 未完成项：真实 DeepSeek 模型调用、50 授权客户端性能、连续五日稳定性和公开回复放行。
- 与原方案差异：沿用项目现有 `DEEPSEEK_BASE_URL`、`LLM_ENABLED` 等配置名，没有创建同义开关；401/403/请求级 429 在流建立前保持正确 HTTP 状态，流接受后的模型限流才使用 SSE `error + done`。
- 当前状态：工程实施已完成；生产验收未完成，所有自动发送能力继续关闭。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-FS05-001 | 未执行真实 DeepSeek 质量和异常评测 | P1 | AIAgent开发工程师Agent、测试工程师Agent | REAL-AI-05 / REAL-FS-05 验收 |
| R-FS05-002 | 未执行 50 授权客户端与五日 99.5% 稳定性 | P1 | 测试工程师Agent | REAL-FS-05 正式性能与稳定性测试 |
| R-FS05-003 | npm 官方审计确认 Next.js 间接依赖 PostCSS/Sharp 共 3 项 High；自动修复要求破坏性升级 Next 16 | P1 | 全栈开发工程师Agent、测试工程师Agent | REAL-FS-01 缺陷关闭与 Next 16 升级专项 |

## 10. 交接事项

- 交接给：测试工程师Agent、架构师Agent、AIAgent开发工程师Agent。
- 后续任务：测试工程师执行 REAL-FS-05 独立综合、50 客户端和五日稳定性；AI 工程师提供已评测模型/Prompt 版本；架构师签署放行或回滚。
- 必须注意：压测凭证与输出必须位于仓库外；只有 `done.reason=completed` 计成功；`llm_provider=ok` 不等于上游实时可用；不得开启自动回复、翻译或营销。

## 11. 文档同步

- [x] 已同步接口变化。
- [x] 已同步架构决策（沿用 ADR，无新增决策）。
- [x] 已同步任务状态。
- [x] 已通知测试工程师需要覆盖的范围。
- [x] 测试报告索引将在正式测试完成后更新。
