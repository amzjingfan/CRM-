# `src/` 工程根迁移设计

**日期：** 2026-09-16

**治理档位：** `STANDARD`

**变更类型：** 仓库结构、构建、测试和启动路径迁移

**状态：** 已由用户书面确认，进入实施

## 背景与目标

当前仓库把应用、测试、脚本、部署资产、Dockerfile、Compose 和环境示例分散在仓库根目录。用户要求把全部工程代码和运行资产收拢到 `src/`，并允许改变启动命令，但要求迁移后项目能够真实启动。

本次迁移建立一个单层工程根：应用、测试、运维脚本、部署资产、构建文件、Compose 和本地环境模板全部位于 `src/`。仓库根只保留 Git/GitHub/Codex 元数据、治理与项目文档、发布基线和证据入口。

迁移不改变产品范围、公共 API、数据结构、数据库迁移顺序、权限、安全开关、模型协议或生产门禁结论。

## 已确认决定

1. 采用“单层工程根”，不增加 `apps/`、`ops/` 等额外嵌套。
2. 允许改变启动命令，不保留根目录 Compose 或 Dockerfile 兼容副本。
3. Compose 显式保留项目名 `crm`，避免目录迁移导致网络和命名卷从 `crm_*` 漂移到 `compose_*`。
4. 标准本地启动通过 `src/scripts/start-local.ps1` 执行；脚本兼容 `docker compose` 和 `docker-compose` 两种可用入口。
5. `deploy/cloudflared/config.example.yml` 的现有未提交删除是用户确认要保留的删除。迁移后不得在 `src/deploy/cloudflared/config.example.yml` 恢复该文件。
6. 历史设计、计划、冻结发布清单和机器证据保留形成时的路径，不批量改写历史事实。
7. 迁移前发现的五个 worktree 路径缺陷纳入本任务修复，不作为阻止迁移的既有失败。

## 目标目录

```text
src/
├─ backend/
├─ frontend/
├─ tests/
├─ scripts/
├─ deploy/
├─ docker/
│  ├─ Dockerfile.backend
│  ├─ Dockerfile.frontend
│  ├─ Dockerfile.frontend.prod
│  └─ Dockerfile.model-service
├─ compose/
│  ├─ docker-compose.yml
│  ├─ docker-compose.ai.yml
│  ├─ docker-compose.deepseek-sse.yml
│  ├─ docker-compose.gpu.yml
│  ├─ docker-compose.prod.yml
│  ├─ docker-compose.rootless-staging.yml
│  ├─ docker-compose.sse-load-test.yml
│  └─ docker-compose.tiktok-manual.yml
└─ config/
   └─ .env.example
```

仓库根保留：

```text
.git/
.github/
.worktrees/
.gitattributes
.gitignore
.mcp.json
AGENTS.md
README.md
design-qa.md
docs/
release/
```

`design-qa.md` 是项目文档，不是运行代码；`.github/` 必须留在 GitHub 识别的固定根路径；`.mcp.json`、`AGENTS.md` 和 Git 元数据同样属于平台入口。`release/` 保存冻结基线与低敏证据，不属于工程源目录。

## 路径映射

| 当前路径 | 目标路径 |
| --- | --- |
| `backend/` | `src/backend/` |
| `frontend/` | `src/frontend/` |
| `tests/` | `src/tests/` |
| `scripts/` | `src/scripts/` |
| `deploy/` | `src/deploy/` |
| `Dockerfile.backend` | `src/docker/Dockerfile.backend` |
| `Dockerfile.frontend` | `src/docker/Dockerfile.frontend` |
| `Dockerfile.frontend.prod` | `src/docker/Dockerfile.frontend.prod` |
| `Dockerfile.model-service` | `src/docker/Dockerfile.model-service` |
| `docker-compose.yml` | `src/compose/docker-compose.yml` |
| `docker-compose.ai.yml` | `src/compose/docker-compose.ai.yml` |
| `docker-compose.deepseek-sse.yml` | `src/compose/docker-compose.deepseek-sse.yml` |
| `docker-compose.gpu.yml` | `src/compose/docker-compose.gpu.yml` |
| `docker-compose.prod.yml` | `src/compose/docker-compose.prod.yml` |
| `docker-compose.rootless-staging.yml` | `src/compose/docker-compose.rootless-staging.yml` |
| `docker-compose.sse-load-test.yml` | `src/compose/docker-compose.sse-load-test.yml` |
| `docker-compose.tiktok-manual.yml` | `src/compose/docker-compose.tiktok-manual.yml` |
| `.env.example` | `src/config/.env.example` |

`deploy/cloudflared/config.example.yml` 是映射中的精确例外：源路径删除，目标路径不创建。

## 根路径模型

迁移后代码和测试必须区分两个稳定边界：

- `SOURCE_ROOT`：`<repository>/src`，包含所有工程和运行资产；
- `REPOSITORY_ROOT`：Git `--show-toplevel` 返回的仓库根，包含 `.github/`、`docs/` 和 `release/`。

禁止继续使用固定数量的 `parents[n]` 假设仓库外层没有 `.worktrees/`。需要仓库身份时优先使用 Git；不应依赖 Git 的运行时路径从已知文件位置定位 `src/`，并对目标存在性失败关闭。

Python 配置将本地环境文件固定为 `src/config/.env`。容器中仍由 Compose `env_file` 和显式 `environment` 注入配置，不依赖镜像内存在环境文件。

## Compose 与 Docker 契约

### Compose

基础 `src/compose/docker-compose.yml` 设置：

```yaml
name: crm
```

Compose 相对路径以 `src/compose/` 为基准：

- 后端构建上下文和开发挂载：`../backend`；
- 前端构建上下文和开发挂载：`../frontend`；
- Dockerfile 相对各构建上下文定位到 `../docker/Dockerfile.*`；
- 模型与 Nginx 资产：`../deploy/...`；
- 本地环境文件：`../config/.env`，保持 `required: false`。

全部覆盖文件继续按现有顺序与基础文件合并，不改变服务名、网络协议、端口、健康检查、安全开关或生产镜像契约。

### Dockerfile

Dockerfile 移入 `src/docker/`，但构建上下文仍分别是 `src/backend/` 和 `src/frontend/`。Dockerfile 的 `COPY` 语义保持不变，不扩大构建上下文，也不把 `docs/`、`release/`、密钥或其他根文件复制进镜像。

### Compose 项目身份

显式项目名 `crm` 保留当前解析结果：网络 `crm_default`，命名卷 `crm_postgres_data`、`crm_redis_data`、`crm_minio_data`、`crm_frontend_node_modules` 和 `crm_frontend_next_cache`。目录迁移不得静默创建一套 `compose_*` 数据卷。

## 启动入口

标准本地流程为：

```powershell
Copy-Item src/config/.env.example src/config/.env
.\src\scripts\start-local.ps1
```

`start-local.ps1`：

1. 从 `$PSScriptRoot` 解析 `SOURCE_ROOT`、环境文件和基础 Compose 文件；
2. 优先探测 Docker CLI 的 Compose 插件，失败时探测独立 `docker-compose`；
3. 缺少 Compose、环境模板或 Compose 文件时在执行容器操作前失败；
4. 使用项目名 `crm`、`src/config/.env` 和 `src/compose/docker-compose.yml`；
5. 默认执行等价于 `up -d --build` 的启动；
6. 返回底层 Compose 的非零退出码，不吞掉构建或健康失败。

直接命令仍允许：

```powershell
docker-compose --project-name crm --env-file src/config/.env -f src/compose/docker-compose.yml up -d --build
```

使用 Compose 插件的环境可把 `docker-compose` 替换为 `docker compose`。

## 测试与 CI 路径

- 后端工作目录改为 `src/backend/`，其模块测试仍位于 `src/backend/tests/`。
- 跨模块集成测试改为 `src/tests/integration/`；相对 `src/backend/` 仍是 `../tests/integration`，pytest 发现规则可保持该值。
- 前端工作目录改为 `src/frontend/`，测试仍位于 `src/frontend/tests/`。
- CI 的工作目录、npm 缓存、Docker build context 和 Dockerfile 路径全部同步。
- `.github/CODEOWNERS` 同步 `src/docker/`、`src/compose/`、`src/deploy/` 和 `src/backend/migrations/`。
- PowerShell 脚本从 `src/scripts/` 推导 `SOURCE_ROOT`，需要 `.github/` 或 `release/` 时通过 Git 解析 `REPOSITORY_ROOT`。

## 迁移前基线例外

在基线 `6b726a32502a364040ccf0a0b251a320d379ee7d` 的隔离 worktree 中，本次真实运行得到：

- 后端 Ruff、格式、mypy 通过；
- 后端 pytest：`1525 passed, 14 skipped, 2 failed`；
- 前端 lint、typecheck、生产 build 通过；
- 前端测试：`37 passed, 3 failed`。

五个失败均来自固定 `parents[n]` 路径推导：前端测试错误读取 `.worktrees/.github` 和 `.worktrees/release`；后端安全测试把 `.worktrees/` 误判为应拒绝的嵌套 checkout 路径。用户已明确批准在本任务中修复。

迁移后的验收不允许保留这些失败；所有五个用例必须在普通 checkout 和链接 worktree 路径模型下通过。

## 实施顺序

1. 在 `docs/tasks/TASKS.md` 登记任务、分支和 `BASE_SHA`。
2. 用 Git 可识别的移动建立目标目录；精确删除已批准的 cloudflared 示例文件。
3. 先更新路径契约测试，使旧路径或固定层级推导失败。
4. 更新运行配置、Compose、Dockerfile、Python 环境加载、PowerShell 和 CI。
5. 更新 README 与当前架构、开发、部署、测试、任务和恢复文档。
6. 执行完整验证并修复所有迁移回归。
7. 为最终候选 SHA 定稿 IR、TR 和生产基础设施路径 RR，再关闭任务。

## 验证策略

### 静态和路径

- 目标目录存在，旧工程路径不存在；
- 根目录只保留批准的元数据、文档与证据入口；
- 排除历史 `docs/superpowers/**` 与冻结 `release/**` 后，活动引用不再使用旧路径；
- Markdown 本地链接解析通过；
- `git diff --check`、敏感信息和差异范围检查通过；
- Windows PowerShell 5.1 与 PowerShell 7 可用时均执行脚本解析检查。

### 后端

从 `src/backend/` 运行：

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy app scripts
uv run pytest
```

### 前端

从 `src/frontend/` 运行：

```powershell
npm run lint
npm run typecheck
npm run test
npm run build
```

### Compose、镜像和实际启动

1. 解析基础 Compose 及所有当前受支持的覆盖组合；
2. 从新上下文构建后端、前端开发、前端生产和模型服务镜像；
3. 使用独立验证项目名实际执行本地 `up -d --build`，避免覆盖可能存在的 `crm` 运行栈；
4. 等待并检查后端 `/v1/health`、后端 `/v1/health/ready` 和前端 `/login`；
5. 只清理该独立验证项目的容器、网络和测试卷；不触碰用户已有 `crm_*` 数据卷。

如果 Docker daemon、外部镜像仓库或依赖网络不可用，不能把静态配置解析冒充实际启动成功。必须记录真实阻塞并在可用环境完成启动门禁后才能把任务标为 `DONE`。

## 记录与审查

本任务改变源码位置、测试路径、配置、CI、镜像构建和生产基础设施引用，因此最终候选 SHA 必须具备：

- 实施记录 IR；
- 测试记录 TR；
- 以构建上下文、路径逃逸、密钥边界、Compose 合并和启动恢复为重点的 RR。

记录不得使用 `WORKTREE` 作为最终 SHA。任务只有在文档同步、记录定稿、全部适用验证通过后进入 `DONE`。

## 失败处理与回滚

- 任一路径、测试、构建或启动门禁失败，任务保持 `DOING` 或 `VERIFYING`，不降低阈值或删除测试。
- 移动全部使用可审阅 Git diff；迁移分支失败不会改变 `main` 或已有本地数据。
- 合并后需要回滚时使用 `git revert` 回滚迁移提交，不使用 `git reset --hard`。
- 对已共享迁移执行回滚前，先停止使用新路径的进程和 CI，并验证旧 Compose 路径与环境文件位置恢复。
- `deploy/cloudflared/config.example.yml` 的删除已得到精确授权；回滚整个迁移时该删除也随提交回滚。若只恢复该文件，需要新的明确指令。

## 非目标

- 不拆分现有模块化单体，不新增微服务、包管理工作区或共享平台。
- 不更改业务逻辑、API、数据库迁移、权限、安全开关、Prompt、模型或生产门禁结论。
- 不迁移 `.github/`、`docs/`、`release/`、Git/Codex 元数据或项目入口文档到 `src/`。
- 不改写历史规格、计划、冻结发布清单或机器证据中的旧路径。
- 不推送远端、不创建或合并 Pull Request、不发布镜像、不部署 staging 或 production。

## 验收标准

1. 所有工程代码和运行资产位于已确认的 `src/` 目录结构中，根目录没有旧工程副本。
2. cloudflared 示例文件按用户决定保持删除，不在目标路径恢复。
3. Compose 项目名仍为 `crm`，现有命名卷契约不漂移。
4. 标准启动脚本和直接 Compose 命令均解析新路径。
5. 后端、前端、CI、脚本和当前文档不依赖旧路径或固定 worktree 层级。
6. 五个已知路径基线失败全部修复，完整后端和前端门禁通过。
7. 全部受支持 Compose 配置解析、四类镜像构建和独立项目实际启动健康检查通过。
8. IR、TR、RR、任务状态和当前文档绑定真实最终候选 SHA。
9. 不包含未经授权的产品、数据、安全、远端或发布变化。
