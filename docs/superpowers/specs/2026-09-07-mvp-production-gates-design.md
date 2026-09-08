# MVP/生产门禁收口设计

日期：2026-09-07  
状态：用户已批准  
分支：`fix/mvp-production-gates`

## 目标

在不改变真实能力默认关闭策略的前提下，完成三类工作：关闭前端 3 个 High 依赖风险；把应用镜像发布到 GHCR 并把生产外部镜像固定到不可变 RepoDigest；提供只能在 staging 显式执行的真实环境预检、健康检查和回滚演练入口。

本任务不会因为脚本或镜像已经就绪而把 `production_release` 改为 `true`。真实店铺、真实 DeepSeek、五日稳定性及最终签署仍必须由对应责任人使用真实证据关闭。

## 已批准方案

### 1. 前端依赖

将 `next` 与 `eslint-config-next` 升级到 `16.3.4`。这是 npm 审计给出的上游正式修复路径；Next.js 16 要求 Node.js 20.9+，项目生产基础镜像使用 Node.js 20.19.4，满足要求。升级后必须通过 ESLint、TypeScript、Node 测试、生产构建和 `npm audit --audit-level=high`。

不采用在 Next.js 15 下强制覆盖其内置 PostCSS/Sharp 的方案，因为这会形成上游没有声明兼容性的依赖组合。

### 2. 镜像供应链

- 后端发布到 `ghcr.io/cp11-gh/crm-backend`。
- 前端发布到 `ghcr.io/cp11-gh/crm-frontend`。
- 检索模型服务发布到 `ghcr.io/cp11-gh/crm-retrieval-model-service`。
- GitHub Actions 的三个发布 job 绑定 main-only `image-publishing` Environment，只在 job 级使用仓库自动生成的 `GITHUB_TOKEN` 和最小 `packages: write` 权限构建、推送，并把完整 `repository@sha256:...` 写入构建摘要和 JSON 证据制品。
- 正式工作流只允许手工触发，输入必须是完整 Git commit SHA；发布标签包含该 SHA，不使用 `latest`。
- 首次建立工作流时允许 `fix/mvp-production-gates` 分支的一次性 push 触发候选镜像。取得真实 RepoDigest 后删除该临时触发器，再进入最终审阅。
- `Dockerfile.frontend.prod` 的 Node 基础镜像固定到 Docker Hub 多架构清单摘要。
- `Dockerfile.model-service` 的 uv 基础镜像固定到 GHCR 多架构清单摘要。
- 生产 Compose 默认引用以下已从 Docker Hub 官方标签 API 解析的不可变摘要：
  - `pgvector/pgvector:0.8.0-pg16@sha256:a132765ec351c65111b5b675928a3a0515a466a40f97277329db8b8209ad8bc9`
  - `redis:7.4.2-alpine@sha256:02419de7eddf55aa5bcf49efb74e88fa8d931b4d77c07eff8a6b2144472b6952`
  - `minio/minio:RELEASE.2025-04-22T22-12-26Z@sha256:a1ea29fa28355559ef137d71fc570e508a214ec84ff8083e39bc5428980b015e`
  - `nginx:1.27.5-alpine@sha256:65645c7bb6a0661892a8b03b89d0743208a18dd2f3f17a54ef4b76fb8e2f2a10`

生产部署必须通过仓库外环境变量显式提供后端、前端和检索模型服务 GHCR RepoDigest。Compose 合并后的应用服务不得保留本机构建配置，防止目标主机临时重建未审阅镜像。

### 3. staging 与回滚

新增 PowerShell 门禁脚本，要求调用者同时提供：`-Environment staging`、仓库外环境文件、完整带摘要的后端/前端/检索模型镜像，以及显式确认字符串。镜像引用使用严格仓库白名单；脚本只输出变量名、服务名、校验后的镜像摘要和低敏健康结果，不输出任何环境变量值。

执行顺序：

1. 校验所有生产镜像均为 `@sha256:<64 hex>`。
2. 校验环境文件存在、权限由运维负责、必需变量名齐全且真实能力默认关闭。
3. 运行 Compose 结构校验，但不打印展开后的完整配置。
4. 部署指定候选摘要并检查 HTTPS、API health 和 ready。
5. 回滚演练先关闭全部真实能力，再把三类应用镜像切换到调用者显式提供的上一版本摘要；`WhatIf` 或拒绝确认不得生成 `passed` 证据。
6. 回滚后再次检查健康接口，并生成不含秘密的 JSON 证据。

GitHub Actions 的 staging 工作流使用 `environment: staging` 与带标签的自托管 runner（`self-hosted, linux, x64, crm-staging`），避免把生产环境文件或 SSH 私钥复制到通用 GitHub runner。若尚未配置 runner 和 Environment secrets，工作流保持不可执行状态，文档明确记录这一外部阻塞。

## 安全边界

- 所有 `REAL_TIKTOK_*`、LLM、翻译、营销和自动回复开关在候选部署和回滚后均保持 `false`。
- 脚本拒绝 `production`，本任务只允许 staging。
- 不自动重试 `unknown` 消息，不删除数据库数据，不执行降级迁移。
- 回滚目标必须是调用者提供的历史不可变镜像摘要，不能使用浮动标签。
- 未取得真实执行证据的检查项继续标记“未执行/阻塞”。

## 验收标准

- `npm audit --audit-level=high` 为 0 High/0 Critical。
- 前端 lint、typecheck、测试和 build 全部通过。
- Docker/Compose 契约测试能拒绝浮动生产镜像和 production 环境调用。
- 分支 bootstrap 的后端、前端 GHCR 候选镜像取得真实 RepoDigest；检索模型镜像由最终 main 工作流发布并固定。
- 4 个外部生产镜像均固定完整 RepoDigest。
- staging 工具通过无秘密的静态与 dry-run 测试；真实执行只有在 runner、环境文件和真实授权资源齐备后才能形成正式证据。
