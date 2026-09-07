# 前端 Next 构建缓存隔离实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase2 |
| 任务编号 | P2-00 阶段汇总 |
| 模块编号 | M02 |
| 主责 Agent | 全栈开发工程师Agent |
| 协作 Agent | 测试工程师Agent |
| 实施状态 | 已完成 |
| 开始日期 | 2026-08-20 |
| 完成日期 | 2026-08-20 |
| 代码位置 | `CRM智能聊天系统/` |

## 2. 需求与依据

- 产品需求：`共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md` 中管理端登录与客服工作台要求。
- 接口依据：`共享记忆文档/智能客服平台 — 管理端接口文档.md` 中认证与工作台接口。
- 架构依据：`架构师/ARCH-001-SYS-系统总体架构设计-v1.1.md` 中 Next.js 管理端和 Docker Compose MVP 部署方案。
- 任务依据：`共享记忆文档/开发任务拆解（按人天分配）.md` 中 Phase 2 平台接入、会话与客服工作台任务。
- 验收依据：`共享记忆文档/MVP范围与验收标准.md`，以及 `测试工程师/Phase2-P2-00-全栈开发工程师Agent-M02-平台接入、会话与工作台-综合测试-004.md` 的 DEF-P2-002。
- 代码规范：`共享记忆文档/代码编写手册.md`。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 消除宿主机 `frontend/.next` 与 Compose 前端开发容器 `/app/.next` 共用目录导致的构建产物竞争。
- 保证前端容器运行期间执行宿主机 `npm run build` 后，`/login` 仍返回 200 且容器保持健康。
- 增加自动化回归门禁，防止 Compose 挂载策略回退。

### 3.2 实施范围

- frontend 服务的 Compose 卷挂载。
- 前端 Node 测试中的 Compose 静态回归检查。
- README 开发运行说明。
- 前端容器、登录页和受保护路由运行回归。

### 3.3 非目标

- 不修改认证、工作台或平台接入业务逻辑。
- 不修改 API、数据库结构、AI Agent、Prompt 或 RAG。
- 不替代测试工程师生成正式复测报告和验收结论。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单。
- [x] 已读取相关 PRD、接口、任务拆解和验收标准。
- [x] 涉及代码时已读取代码编写手册和浏览器验证 Skill。
- [x] 已确认 Phase、任务编号、模块编号和主责 Agent。
- [x] 已确认依赖、风险和验收方式。

## 5. 实施方案

### 5.1 方案说明

Compose 原配置将宿主机整个 `frontend/` 绑定到容器 `/app`，导致宿主机与容器共用 `.next`。当宿主机执行生产构建时，运行中的 `next dev` 所依赖的服务端 chunk 会被替换，进而产生 `Cannot find module './833.js'` 和 `/login` 500。

本次在 `/app/.next` 增加嵌套命名卷 `frontend_next_cache`。嵌套挂载会遮蔽宿主机绑定目录中的 `.next`，使容器开发缓存与宿主机生产构建产物分别保存；`node_modules` 继续使用原有独立命名卷。新增 Node 测试固定检查挂载声明和卷定义均存在。

### 5.2 依赖关系

- 前置依赖：Docker Compose、现有 frontend 镜像、backend 健康检查和 Next.js 15 工程。
- 后续依赖：测试工程师针对 DEF-P2-002 生成 005 号正式复测报告。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 后续修改 Compose 时删除嵌套卷 | 缺失 chunk 和 `/login` 500 复发 | 增加 `compose.test.mjs` 自动化门禁 |
| 仅验证启动、不验证并发构建 | 无法覆盖 004 报告的真实触发条件 | 容器健康后在宿主机执行完整 `npm run build`，再检查 HTTP、健康和日志 |
| 只检查 HTTP、不检查真实页面 | 可能遗漏客户端渲染或路由问题 | 使用浏览器检查 DOM、控制台、响应式宽度和受保护路由重定向 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `CRM智能聊天系统/docker-compose.yml` | 修改 | 为 frontend 新增 `frontend_next_cache:/app/.next` 嵌套命名卷 | 全栈开发工程师Agent |
| `CRM智能聊天系统/frontend/tests/compose.test.mjs` | 新增 | 校验 `.next` 独立挂载及命名卷声明 | 全栈开发工程师Agent |
| `CRM智能聊天系统/README.md` | 修改 | 说明宿主机与容器构建目录隔离规则 | 全栈开发工程师Agent |
| `共享记忆文档/实施记录索引.md` | 修改 | 登记本次实施记录 | 全栈开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：不适用；无接口变化。
- 数据库：不适用；无迁移、表、字段或索引变化。
- 配置项：新增 Docker 命名卷 `frontend_next_cache`，不涉及环境变量或密钥。
- AI：不适用；无 Prompt、模型、RAG、工具或阈值变化。

### 6.3 关键实现说明

- `/app` 继续绑定宿主机源码，以保留 Next.js 开发热更新。
- `/app/node_modules` 和 `/app/.next` 分别使用独立命名卷，避免宿主机依赖和构建输出污染容器运行态。
- 修复后强制重建 frontend 容器，确认实际 Mounts 中 `/app/.next` 类型为 volume、卷名为 `crm_frontend_next_cache`。
- 回归测试不读取密钥，不输出环境变量，不修改业务数据。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| 前端 lint | `npm run lint` | 无 lint 错误 | 通过 | 通过 |
| 前端类型检查 | `npm run typecheck` | 无 TypeScript 错误 | 通过 | 通过 |
| 前端自动化测试 | `npm run test` | 全部通过并覆盖 Compose 挂载 | 8 passed、0 failed | 通过 |
| Compose 解析 | `docker-compose config --services` | 服务配置可解析 | 正常列出 postgres、redis、worker、minio、backend、frontend、jobs | 通过 |
| 前端容器重建 | `docker-compose up -d --force-recreate frontend` | 创建独立卷并正常启动 | 创建 `crm_frontend_next_cache`，frontend 启动成功 | 通过 |
| 实际挂载 | `docker inspect crm-frontend-1` | `/app/.next` 为独立 volume | `crm_frontend_next_cache -> /app/.next` | 通过 |
| 初始运行态 | 容器健康检查 + `GET /login` | healthy 且 HTTP 200 | healthy，HTTP 200 | 通过 |
| 并发构建回归 | frontend 容器运行期间在宿主机执行 `npm run build` | 构建成功且不破坏容器 | Next.js 生产构建成功 | 通过 |
| 并发构建后运行态 | 再次检查健康、`GET /login` 和近 5 分钟日志 | healthy、HTTP 200、无缺失 chunk | healthy、HTTP 200、缺失 chunk 错误 0 条 | 通过 |
| 浏览器登录页 | 打开 `/login` 并检查 DOM 和控制台 | 登录表单正常、控制台无错误 | 标题、邮箱、密码、登录按钮正常，0 条 console error | 通过 |
| 响应式 | 浏览器验证 375/768/1024/1440 宽度 | 无横向溢出且登录按钮可见 | 四档全部通过 | 通过 |
| 受保护路由 | 未认证打开 `/workspace` | 重定向 `/login` | 已重定向且登录标题正常 | 通过 |
| 后端全量回归 | `.\\scripts\\run-postgres-integration-tests.ps1` | 隔离测试库迁移成功、pytest 全部通过 | 66 passed、0 failed、0 skipped；2 条第三方弃用警告 | 通过 |

## 8. 实施结果

- 完成项：DEF-P2-002 根因修复、Compose 缓存隔离、自动化门禁、运行时并发回归、浏览器回归和文档同步。
- 未完成项：测试工程师 005 号正式复测报告尚未生成。
- 与原方案差异：无。
- 当前状态：开发修复已完成且开发侧验证全部通过，等待测试工程师独立复测后更新正式测试结论。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-001 | 004 号测试报告是历史失败证据，不能由开发 Agent 改写为通过 | P1 | 测试工程师Agent | Phase2/P2-00 005 号复测 |
| R-002 | Starlette TestClient 与 argon2-cffi 各有一条第三方弃用警告，不影响本缺陷修复 | P3 | 全栈开发工程师Agent | 后续依赖维护任务 |

## 10. 交接事项

- 交接给：测试工程师Agent。
- 后续任务：Phase2/P2-00，复测 DEF-P2-002 并生成 `...综合测试-005.md`。
- 必须注意：复测时应保持 frontend 容器运行，执行一次宿主机 `npm run build`，随后再次验证容器健康、`/login` 200、浏览器控制台和容器日志；不要只验证首次启动。

## 11. 文档同步

- [x] 已同步接口变化（本次无接口变化）。
- [x] 已同步架构决策（本次未新增架构决策，仅落实 Compose 运行隔离）。
- [x] 已同步任务状态。
- [x] 已通知测试工程师需要覆盖的范围。
- [x] 测试报告索引将在正式测试完成后更新。
