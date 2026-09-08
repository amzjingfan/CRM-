# MVP 生产门禁收口实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | PhaseX |
| 任务编号 | PX-00；关联 REAL-FS-01/G0 |
| 模块编号 | 跨模块工程与发布治理 |
| 主责 Agent | 全栈开发工程师Agent |
| 协作 Agent | 架构师Agent、测试工程师Agent |
| 实施状态 | 部分完成；工程实现完成，真实 staging 与独立复测待执行 |
| 开始日期 | 2026-09-07 |
| 完成日期 | 未完成 |
| 分支 | `fix/mvp-production-gates`；最终证据 `docs/final-image-digests` |

## 2. 目标与边界

- 使用上游支持版本关闭前端 3 个 High，不用跨主版本依赖覆盖规避审计。
- 发布 backend、frontend、retrieval model service 镜像到 GHCR，固定全部生产基础镜像 RepoDigest。
- 提供只允许 staging 的预检、部署和回滚演练脚本及 GitHub Actions 入口。
- 不开启真实 TikTok、DeepSeek、翻译、营销或自动回复，不把 dry-run 视为真实门禁证据。

依据：`docs/superpowers/specs/2026-09-07-mvp-production-gates-design.md`、
`docs/superpowers/plans/2026-09-07-mvp-production-gates.md`、生产放行检查表 v1.1 和代码编写手册。

## 3. 实际变更

### 3.1 前端安全升级

- `next`、`eslint-config-next` 固定为 `16.3.4`。
- Next.js 内置传递依赖更新为 PostCSS `8.5.23`、Sharp `0.35.4`。
- ESLint 改用 Next.js 16 原生 flat config；保留现有异步加载行为，暂不在安全修复中重构页面 effect。
- Node.js 生产基础镜像固定为 `node:20.19.4-alpine3.22@sha256:df025...2799`，满足 Next.js 16 的 Node 20.9+ 要求。
- 检索模型构建基础镜像固定为 `ghcr.io/astral-sh/uv:python3.11-bookworm-slim@sha256:4f5d...bb36`。

### 3.2 镜像与生产 Compose

- `publish-images.yml` 使用最小 `contents: read`、`packages: write` 权限和固定 SHA 的官方 Actions。
- workflow run `34112919503` 已成功发布分支候选：
  - backend：`ghcr.io/cp11-gh/crm-backend@sha256:b7c4e0679613049323d57e1b0e5ad741d6785e0dd0eb92cfd46fb7ac84c5aff5`；
  - frontend：`ghcr.io/cp11-gh/crm-frontend@sha256:c616b24b77d06faf48753986e9a17e504bdb8a511417d44b4a75ba2ba3170712`。
- 最终 `main@f7c0f9f9dd9a8c7b36a07145c053db7df23a15b8` 已由 workflow run `34178017173` 发布三类应用镜像：
  - backend：`ghcr.io/cp11-gh/crm-backend@sha256:30f3a6816f718a92cd241330458124ea8b7b5407aafb1f533bcd0044e56914a9`；
  - frontend：`ghcr.io/cp11-gh/crm-frontend@sha256:c24b385250d61729667f372da1f63397a1b564019969d5bf424fff0682a910a0`；
  - retrieval model service：`ghcr.io/cp11-gh/crm-retrieval-model-service@sha256:e13818dfad09cfa565a6764024628a262e48a9089a37b6f8b517fb81997a1fcf`。
- 最终低敏 JSON 制品 id 为 `10037989028`；三类 build 和 evidence job 均为 `success`。
- PostgreSQL、Redis、MinIO、Nginx 已固定 Docker Hub 官方多架构清单摘要。
- 生产 Compose 的后端进程、前端和检索模型服务全部重置本机构建配置，只消费显式应用 RepoDigest。
- 发布 job 使用 main-only `image-publishing` Environment、`github.ref` 校验和 job 级 `packages: write`。
- 机器可读证据：`release/images/mvp-production-gates.json`。

### 3.3 staging 与回滚

- `Test-StagingProductionGates.ps1` 校验 staging 双确认、严格仓库白名单、仓库外环境文件、全部镜像摘要、安全关闭开关和合并后的 Compose image/build 结构，并支持候选部署和低敏健康证据。
- `Invoke-StagingRollbackDrill.ps1` 同样校验外部镜像与 Compose 契约，固定执行顺序为“关闭全部真实能力→切换三类历史应用摘要→健康复核”。
- 两个脚本在 `WhatIf` 或操作人拒绝 `ShouldProcess` 时只报告 `not_executed`，不会执行健康检查或写 `passed`。
- `staging-gates.yml` 只在带 `crm-staging` 标签的自托管 Linux runner 上运行，并使用 GitHub `staging` Environment。
- GitHub `staging` Environment 已创建，部署分支策略只允许 `main`。

## 4. 验证结果

| 验证项 | 结果 | 状态 |
| --- | --- | --- |
| npm 官方安全审计 | 0 High、0 Critical、0 total | 通过 |
| 前端 ESLint/TypeScript | 0 error；2 个既有导航 warning；typecheck 通过 | 通过 |
| 前端 Node 测试 | 40 passed | 通过 |
| Next.js 16 生产构建 | 12 条应用路由及 `_not-found` 构建完成 | 通过 |
| 后端 Ruff/格式/mypy | 236 files formatted；166 source files 无类型错误 | 通过 |
| 后端完整测试 | 1332 passed、12 skipped、2 warnings | 通过 |
| 脚本行为测试 | 11 passed；拒绝 production/浮动摘要/凭据型引用，WhatIf 不伪造通过，候选部署包含检索模型服务 | 通过 |
| PowerShell 兼容性 | Windows PowerShell 5.1 与 PowerShell 7 解析通过；UTF-8 BOM | 通过 |
| Compose 结构 | 合并配置 `config --services` 成功，应用 build 已重置 | 通过 |
| GHCR 最终 main 发布 | backend、frontend、retrieval model、evidence 四个 job 均 success | 通过 |
| staging 真实部署/回滚 | runner、环境文件路径、staging URL 和历史摘要未提供 | 未执行 |

## 5. 遗留风险与交接

1. 测试工程师需独立复测 `DEF-REAL-FS01-005`，当前不能自行标记 Closed。
2. 运维需连接 `crm-staging` 自托管 runner，在 GitHub Environment 配置 `CRM_STAGING_ENV_FILE` 和 `CRM_STAGING_BASE_URL`，并把三条最终摘要同步到仓库外环境文件；环境文件正文不得进入 GitHub 或仓库。
3. 真实回滚还需要上一版本 backend、frontend、retrieval model service RepoDigest。未提供上述资源前只能完成 `-ValidateOnly`，不得勾选真实演练通过。
4. `DEF-REAL-FS01-006` 日志事件语义折叠、真实店铺、真实模型、五日稳定性及 G7/G8 仍阻断生产放行。

## 6. 文档同步

- [x] 已更新生产运行说明。
- [x] 已更新生产放行检查表 v1.1。
- [x] 已新增机器可读镜像证据。
- [x] 已更新实施记录索引。
- [ ] 待测试工程师形成独立复测报告并更新测试报告索引。
