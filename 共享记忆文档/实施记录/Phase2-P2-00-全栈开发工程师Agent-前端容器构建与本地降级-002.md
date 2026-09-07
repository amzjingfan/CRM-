# Phase2 前端容器构建与本地降级实施记录

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

- 缺陷依据：`测试工程师/Phase2-P2-00-全栈开发工程师Agent-M02-平台接入、会话与工作台-综合测试-002.md` 中 ENV-001/ENV-002。
- 产品需求：`共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md` 的客服工作台和 Docker Compose 部署要求。
- 任务依据：`共享记忆文档/开发任务拆解（按人天分配）.md` 中 P1-01、P1-11、P1-12 及 Phase2 阶段汇总映射。
- 验收依据：`共享记忆文档/MVP范围与验收标准.md`。
- 代码规范：`共享记忆文档/代码编写手册.md`。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 解除前端 Dockerfile 对 Docker Hub 固定入口的硬编码依赖。
- 支持企业镜像仓库、审核后的镜像加速、npm 代理和离线导入镜像。
- Docker 外部网络不可用时，提供可重复的本地前端开发启动方式。

### 3.2 实施范围

- `Dockerfile.frontend` 构建参数。
- `docker-compose.yml` 前端构建参数传递。
- `.env.example` 前端镜像和 npm registry 配置。
- 本地前端降级启动脚本和 README 操作说明。

### 3.3 非目标

- 不修改前端页面业务、后端 API、数据库和 AI 能力。
- 不修改 Docker Desktop 的系统代理、DNS 或 registry mirror 配置。
- 不把公开第三方镜像地址硬编码为生产默认值。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单。
- [x] 已读取相关 PRD、接口、任务拆解、团队职责和测试报告。
- [x] 已读取代码编写手册和各级 AGENTS.md。
- [x] 已确认 Phase2、P2-00、M02 和主责 Agent。
- [x] 已确认外部网络阻塞与产品配置问题的边界。

## 5. 实施方案

### 5.1 方案说明

`Dockerfile.frontend` 使用 `NODE_IMAGE` 和 `NPM_REGISTRY` 构建参数，Compose 通过 `FRONTEND_NODE_IMAGE`、`FRONTEND_NPM_REGISTRY` 环境变量传入。默认继续使用官方 Node/npm 源；受限网络由部署环境提供内部仓库、审核后的镜像加速或离线镜像。

新增 `scripts/start-frontend-local.ps1` 作为开发降级入口。脚本检查 Node/npm、依赖目录和端口，支持按需执行 `npm ci`，并只在当前进程中设置 API 地址。该脚本不替代正式 Compose 验收。

### 5.2 依赖关系

- 前置依赖：Node.js 20 LTS；Docker Compose；可用的官方、内部或离线 Node 镜像。
- 后续依赖：测试工程师在可访问镜像仓库或已导入镜像的环境执行 frontend Compose 复测。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 公开镜像加速认证或可用性变化 | 构建仍可能失败 | 不硬编码第三方地址；使用环境变量和内部仓库 |
| 浮动镜像标签供应链风险 | 构建结果变化 | 生产环境要求内部仓库并固定 digest |
| 本地降级被误当正式部署 | 绕过容器验收 | README 和脚本注释明确仅用于开发连续性 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `CRM智能聊天系统/Dockerfile.frontend` | 修改 | 增加基础镜像和 npm registry 构建参数 | 全栈开发工程师Agent |
| `CRM智能聊天系统/docker-compose.yml` | 修改 | 传递前端镜像与 npm registry 参数 | 全栈开发工程师Agent |
| `CRM智能聊天系统/.env.example` | 修改 | 增加前端构建配置和中文说明 | 全栈开发工程师Agent |
| `CRM智能聊天系统/scripts/start-frontend-local.ps1` | 新增 | Docker 外部网络不可用时的本地开发降级入口 | 全栈开发工程师Agent |
| `CRM智能聊天系统/README.md` | 修改 | 增加内部仓库、离线镜像和本地降级说明 | 全栈开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：无变化。
- 数据库：无变化。
- 配置项：新增 `FRONTEND_NODE_IMAGE`、`FRONTEND_NPM_REGISTRY`；默认分别为 `node:20-alpine`、`https://registry.npmjs.org`。
- AI：不适用。

### 6.3 关键实现说明

默认技术基线不变，仍为 Node.js 20 LTS。镜像源覆盖只影响构建来源，不改变容器内运行命令和前端业务行为。本地脚本使用 `try/finally` 清理临时 API 环境变量，避免污染后续终端会话。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| Compose 配置 | `docker-compose config --quiet` | 配置有效 | 退出码 0 | 通过 |
| 前端 lint | `npm run lint` | 无错误 | 通过 | 通过 |
| 前端类型 | `npm run typecheck` | 无错误 | 通过 | 通过 |
| 前端测试 | `npm run test` | 全部成功 | 7 passed，0 failed | 通过 |
| 前端构建 | `npm run build` | 生产构建成功 | 10 个静态页面生成成功 | 通过 |
| 脚本语法 | PowerShell Parser | 无语法错误 | `PowerShell syntax OK` | 通过 |
| 本地降级启动 | `.\scripts\start-frontend-local.ps1 -Port 3010` | Next.js Ready | 1.103 秒 Ready | 通过 |
| 公开镜像构建 | 可配置公开镜像入口 | 能获取基础镜像 | 当前 Docker 网络分别返回 401 或超时 | 阻塞 |

## 8. 实施结果

- 完成项：镜像/npm 源参数化、离线镜像说明、本地开发降级脚本、配置和前端回归。
- 未完成项：当前机器仍无法从外部镜像仓库获取 Node 镜像，frontend 容器尚未在本机完成启动。
- 与原方案差异：无架构变化；新增环境适配和开发降级能力。
- 当前状态：代码实施和开发自测已完成，等待测试工程师在可用镜像环境复测 Compose。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| ENV-001 | 当前 Docker 外部网络无法获取 Node 镜像 | P1 | 环境维护者、测试工程师Agent | Phase2 P2-00 复测 |

## 10. 交接事项

- 交接给：测试工程师Agent、环境维护者。
- 后续任务：准备内部/离线 Node 镜像后执行 `docker compose build frontend`、`docker compose up -d frontend`、页面访问验证。
- 必须注意：本地脚本通过不等于 frontend Compose 通过；正式测试结论仍由测试工程师更新。

## 11. 文档同步

- [x] 已同步新增配置项和启动方式。
- [x] API、数据库和架构决策无变化。
- [x] 已同步实施状态和环境风险。
- [x] 已通知测试工程师需要覆盖的 frontend Compose 复测范围。
- [ ] 测试报告索引由测试工程师在正式复测后更新。
