---
record_id: TR-MVP-WORKSPACE-EXPERIENCE-DEPLOY-001-20261020-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-WORKSPACE-EXPERIENCE-DEPLOY-001
tested_sha: 4cd019c26f15bcbff2fb83f5175021e6a672a5cb
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-EXPERIENCE-DEPLOY-001-20261020-R01.md
requirement_ids: [MVP-WORKSPACE-EXPERIENCE-DEPLOY-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: Windows checkout, staging Linux Rootless Docker, signed-in in-app browser; production unchanged
created_at: 2026-10-20T14:28:00+08:00
updated_at: 2026-10-20T14:37:25+08:00
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT: centralized`。构建与传输的本地临时脚本/日志仅在忽略的 `src/tests/.artifacts/`，数据库备份和原始门禁留在 staging 主机，仓库只保留[低敏汇总](../../../release/evidence/staging/crm-staging-workspace-experience-deploy-20261020.json)。本轮是已有源功能的 staging 部署验收，不把 `MVP-WORKSPACE-EXPERIENCE-001` 的历史 2216/47/34 条测试冒充本轮重跑。

# 命令和逐项结果

- `git ls-remote origin refs/heads/main` 和 staging 干净 clone 的 `git rev-parse HEAD` 均为 `4cd019c...5cb`；源码 bundle SHA-256 与候选镜像 OCI revision 一致。后端和前端 `linux/amd64` 单子清单 OCI index 导入后 RepoDigest 与目标摘要精确匹配；六角色预取门禁通过，服务尚未切换。
- 部署前自定义格式 PostgreSQL 备份模式 `0600`、SHA-256 `cf68823a...47ec`，`pg_restore -l` 可列目录；旧三个镜像可用。当前迁移头 `024_tiktok_oauth_jobs`、11 容器运行，切换前私有快照限制为原有一个店铺。
- `Test-StagingProductionGates.ps1 -ValidateOnly` 通过；`-Deploy '-Confirm:$false'` 通过，私有证据 `status=passed`、`runtime_mode_verified=true`、`database_migration=heads_applied`、固定 TikTok 出口核对通过；三健康分别为 200，`production_release=false`。
- 独立 `docker inspect` 核对后端和四个工作/出口进程、前端、检索镜像摘要和健康；`docker exec crm-staging-backend-1 alembic current --check-heads` 为 `025_workspace_actions (head)`。单店人工发送、Webhook 读取、工作台翻译开启；通用 LLM、自动回复、高风险写入关闭；临时 GHCR 认证目录已清除。
- 本机对 `/healthz`、`/v1/health`、`/v1/health/ready` 的独立 HTTPS GET 均返回 200。已登录浏览器刷新后显示真实会话的星标/转交/关闭入口、列表未读/星标/已关闭筛选及紧凑 AI 草稿；选中会话 `.message-scroll` 距底部为 `0px`。
- 证据 PR #466 的 GitHub Actions 自动出现两项失败检查；GitHub Job API 均显示 `steps=0` 且无 runner 名称，故未执行任何前后端测试。这两项不计入本轮验证；本任务按用户决定只采用上述手动门禁、现场检查和文档一致性检查。

# REQ/AC 或门禁与证据映射

AC-01 对应构建元数据与六摘要预取；AC-02 对应受限备份、validate/deploy、迁移、运行摘要和健康；AC-03 对应运行配置与只读浏览器；AC-04 对应低敏汇总、IR/RR、部署状态与恢复边界。原始私有 validate/prefetch/deploy/snapshot 文件的 SHA-256 已写入低敏汇总供主机复核。

# 缺陷、未执行项与残余风险

未在真实买家会话上写入星标、转交或关闭，未制造新买家消息验证实时未读数字；新功能的写操作与权限回归以源任务的本地隔离测试为依据。未向 TikTok 外发新消息，未执行模型调用、生产部署或迁移 `025` 的实际降级。公网既有间歇故障风险和 G8 No-Go 不因三个健康 200 消失。

# 结论和复测条件

本次 **staging 部署与只读现场验收 PASS**。结论仅覆盖已观察的运行摘要、健康、配置和 UI 入口；真实会话业务写操作、回滚实演与 production 放行各需独立授权和证据。运行镜像、DB 或公网状态变化时重跑对应门禁。
