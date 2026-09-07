# Phase2 平台接入、会话与客服工作台再次复测报告

## 1. 测试基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase2 |
| 任务编号 | P2-00 阶段汇总 |
| 模块编号 | M02 |
| 模块名称 | 平台接入、会话与工作台 |
| 被测主责 Agent | 全栈开发工程师 Agent |
| 被测协作 Agent | 架构师 Agent、测试工程师 Agent |
| 测试执行 Agent | 测试工程师 Agent |
| 关联上一份报告 | `测试工程师/Phase2-P2-00-全栈开发工程师Agent-M02-平台接入、会话与工作台-综合测试-003.md` |
| 关联实施记录 | `共享记忆文档/实施记录/Phase2-P2-00-全栈开发工程师Agent-前端容器构建与本地降级-002.md` |
| 测试类型 | 回归测试、综合测试、页面交互测试、集成测试、兼容性测试 |
| 执行日期 | 2026-08-20 |
| 测试结论 | 不通过；frontend Compose 页面运行时阻断，需全栈工程师修复后复测 |

## 2. 复测目标与范围

本次针对 003 号报告及其后当前工作区状态进行独立复测，验证：

- 后端、前端质量门禁是否回归。
- Compose 全套服务是否真实可用，而不仅是容器进程处于运行状态。
- frontend 容器内 `/login` 是否返回正常页面。
- 浏览器页面、认证、Webhook、迁移和工作台基础链路是否受到影响。

## 3. 执行环境

| 项目 | 实际环境 |
| --- | --- |
| 后端 | Python 3.11 虚拟环境 |
| 数据库 | Docker `pgvector/pgvector:pg16` |
| Redis | Docker `redis:7-alpine` |
| MinIO | Docker `minio/minio:latest` |
| 前端容器 | `crm-frontend-1`，Next.js 15.5.23，Node.js 20 LTS |
| 浏览器 | Codex In-app Browser |
| 前端地址 | `http://127.0.0.1:3000` |
| 后端地址 | `http://localhost:8000` |

## 4. 全量质量门禁

| 验证项 | 实际结果 | 状态 |
| --- | --- | --- |
| Ruff | All checks passed | 通过 |
| mypy | 110 source files，无错误 | 通过 |
| 后端 pytest | 64 passed，2 skipped，2 warnings | 通过 |
| compileall | 无编译错误 | 通过 |
| 前端 lint | 成功 | 通过 |
| 前端 typecheck | 成功 | 通过 |
| 前端测试 | 7 passed，0 failed | 通过 |
| 前端 build | Next.js 15.5.23 构建成功 | 通过 |
| Compose config | `docker-compose config --quiet` 成功 | 通过 |
| 后端健康检查 | `/v1/health` 返回 HTTP 200、`code=0` | 通过 |

说明：2 项跳过为 Phase 3 Agent RAG PostgreSQL 集成测试，原因是未提供隔离测试数据库，不计入本次 Phase 2 M02 结论。

## 5. Compose 运行态测试

| 用例 | 预期 | 实际 | 状态 |
| --- | --- | --- | --- |
| ENV-004-001 服务启动 | frontend 容器启动 | `crm-frontend-1` 进程启动并暴露 3000 端口 | 部分通过 |
| ENV-004-002 健康检查 | 页面可访问时为 healthy | 初始短时间显示运行，随后 Docker inspect 显示 `unhealthy`，FailingStreak=14 | 失败 |
| ENV-004-003 HTTP 登录页 | `/login` 返回 200 | HTTP 500 | 失败 |
| ENV-004-004 容器日志 | 无运行时错误 | 多次出现 `Cannot find module './833.js'` | 失败 |
| ENV-004-005 浏览器登录页 | 页面显示登录表单 | 浏览器显示 Next.js Runtime Error，无法显示登录页 | 失败 |

### 5.1 缺陷 DEF-P2-002

**标题：frontend Compose 启动后 `/login` 缺少 Next.js server chunk，返回 500**

- 优先级：P1
- 影响：Phase 2 前端容器虽能创建，但用户无法访问登录页和客服工作台；Compose 全链路不可验收。
- 复现步骤：

```text
cd CRM智能聊天系统
docker-compose up -d frontend
docker-compose ps frontend
Invoke-WebRequest -UseBasicParsing http://localhost:3000/login
docker-compose logs --tail=80 frontend
```

- 实际结果：
  - `/login` 返回 HTTP 500。
  - 浏览器控制台/页面错误：`Cannot find module './833.js'`。
  - 容器日志堆栈包含 `/app/.next/server/webpack-runtime.js` 和 `/app/.next/server/app/login/page.js`。
  - `docker inspect crm-frontend-1` 显示健康检查状态 `unhealthy`。
- 预期结果：`/login` 返回 HTTP 200，显示登录表单，frontend 健康检查为 healthy。
- 初步定位方向：Compose 将宿主机 `frontend` 目录挂载到 `/app`，当前 `.next` 开发构建产物与容器运行时引用的 chunk 不一致或缺失；需由全栈工程师确认构建产物清理、挂载策略和容器启动命令。
- 当前状态：待全栈工程师修复。

## 6. 后端与 Phase 2 API 回归

后端独立回归未发现新失败：

| 用例 | 实际结果 | 状态 |
| --- | --- | --- |
| `/v1/health` | HTTP 200，`status=ok` | 通过 |
| 浏览器 Cookie 登录 API | `code=0`，权限加载正常 | 通过 |
| `/auth/me` | 返回角色及 17 项权限 | 通过 |
| 店铺与会话列表 | 演示店铺 1 个、会话 2 个 | 通过 |
| Webhook 首次投递 | `duplicate=false`、accepted=true | 通过 |
| Webhook 重复投递 | `duplicate=true` | 通过 |
| Worker 事件处理 | `succeeded`、`retry_count=0` | 通过 |
| 非法签名 | HTTP 401 | 通过 |
| 缺少 CSRF | HTTP 403 | 通过 |

后端通过不能抵消 frontend Compose 页面 500 对 Phase 2 端到端验收的阻断。

## 7. 数据库迁移回归

在一次性临时数据库执行：

```text
alembic upgrade head
alembic downgrade base
alembic upgrade head
```

三次退出码均为 0，001～013 迁移成功，测试数据库已清理。

## 8. 003 号报告问题回归状态

| 项目 | 003 号状态 | 本次状态 |
| --- | --- | --- |
| 前端基础镜像获取 | 已关闭 | 构建/容器创建成功，但页面运行失败，不能视为完整关闭 |
| 浏览器响应式 | 通过 | 当前无法进入正常登录页，需 frontend 修复后重新验证 |
| 后端与 API | 通过 | 本次仍通过 |
| Compose 页面可用性 | 通过 | 回归失败，新增 DEF-P2-002 |

## 9. 验收结论

本轮不建议将 Phase 2 M02 标记为最终通过。后端、数据库、Webhook、认证和静态质量门禁均通过，但 frontend Compose 的核心登录页面返回 500，直接阻断客服工作台使用。

必须完成以下修复后重新生成递增序号测试报告：

1. frontend 容器启动后 `/login` 稳定返回 HTTP 200。
2. 容器健康检查保持 healthy。
3. 浏览器重新验证登录页、保护路由和响应式布局。
4. 检查宿主机 `.next` 挂载、容器构建产物和 `node_modules` 卷的一致性。

## 10. 交接事项

- 交接给：全栈开发工程师 Agent、架构师 Agent。
- 缺陷：`DEF-P2-002`，优先级 P1。
- 测试工程师不修改产品代码；修复完成后执行 Phase2 M02 005 号复测。
- 真实第三方平台联调和 AI Agent 能力仍不属于本阶段范围。
