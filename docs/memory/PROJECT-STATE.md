# 项目状态与恢复入口

本文件是跨 Codex 会话恢复项目所需的精简摘要，不复制 `../tasks/TASKS.md` 的任务状态、`../quality/TEST-STATUS.md` 的测试结论或 `../operations/RELEASE-GATES.md` 的门禁正文。恢复工作时先读本文件，再按链接读取事实源。

2026-09-28 目录卫生补记：`MAINT-CLEANUP-20260928-001` 已移除 PR #53 合并后的 OAuth 代码本地工作树与分支，清理记录由 PR #57 合入 `main`；`MAINT-CLEANUP-20260928-002` 已按用户精确授权移除 PR #52 合并后的 HTML 缓存工作树、两份重复 SSH 私钥副本与本地诊断资料，原始密钥不变，清理记录由 PR #59 合入 `main`。另三个截图工作树因开放 PR 或未完成现场验收而保留。批次见 [`../operations/cleanup/CLEANUP-20260928-001.md`](../operations/cleanup/CLEANUP-20260928-001.md)、[`../operations/cleanup/CLEANUP-20260928-002.md`](../operations/cleanup/CLEANUP-20260928-002.md)。下方历史部署快照不是当日运行状态，以当前任务表与发布证据为准。

## 当前状态

```text
Project phase: ACTIVE
Governance tier: STANDARD
Repository identity: origin=ssh://git@ssh.github.com:443/CP11-gh/CRM.git
Primary branch: main
Working branch at this snapshot: docs/mvp002-oauth-reauth-evidence-20260928
Governance base SHA: fd750c15b6c2970b250de4f7218a4d456a3257aa
CANDIDATE_SUBJECT_SHA: fd750c15b6c2970b250de4f7218a4d456a3257aa
EVIDENCE_HEAD_SHA: READ_AT_GATE
Workspace hygiene: ATTENTION — `CLEANUP-20260921-004` 已删除六个已合并本地 worktree；既有隔离保留期、两份 MVP-001 root-only 恢复副本和其他忽略测试材料不在本批次范围
```

当前工程根为 `src/`，测试资产集中在 `src/tests/`。`MVP-STAGING-001` 已完成双服务器 split-ingress 真实部署：`38.55.145.52` 只承担宝塔 Nginx/TLS 和回环 `18080`，`192.168.110.210` 的 `crmdeploy` Rootless CRM 只发布回环 `18081`；DNS、Let's Encrypt 证书、迁移头、公网健康、隧道恢复和公司负载零变化已验收。最终候选 subject 为 `c0f1e6f0a5c575190b71541be3f67b3163780d61`，与已部署运行配置 `98460796...` 的受审运行资产零差异；终态证据已通过 PR #26 合入 `main`，任务状态为 `DONE`，production 未部署。`EVIDENCE_HEAD_SHA` 必须在门禁或交接时从 Git 现场读取，不在仓库中自指回填。

`MVP-OAUTH-REDIRECT-001` 已由 PR #53 合入 `main`。用户重新选择 North America seller 与 US 后完成 TikTok 授权，成功页自动返回 CRM；此前卖家类型拒绝系操作选择错误，不再作为当前阻塞。现场只读预检中旧版物流 `202309` 成功，增强物流 `202604` 返回业务码 `11007009`，含义未确认，不能将两者混同；Token 生命周期、店铺隔离和重复回调现场证据仍未关闭 G1。production 未变。

`MVP-READONLY-LOG-001` 源码已由 PR #54 合入 main；staging 部署和增强物流失败的独立记录仍在 PR #56 草稿中。2026-09-28 本轮非物流预检在现有 staging 后端执行六项真实只读查询成功，未提交合成用户跨店读/OAuth 发起均 404，当前 connected 渠道的 Scope、密文和未到期刷新调度核对通过；后端本机 1650 passed/18 skipped。08:00:03Z 盘点时 OAuth job 为零，后续复核已见新 job；授权审计与该初次零值均不能证明新任务终态，成功刷新和 `202604` 增强物流仍未过。证据见下文 `MVP-G1-NONLOG-001`，G1 保持部分通过，production 不变。

`MVP-OAUTH-REAUTH-001` 本次 staging 事实：用户确认美国测试店铺授权后自动返回 CRM 并显示已连接；08:00Z 后唯一新 OAuth job 已完成为 connected、code/state 清空，同一发起用户/店铺/渠道的成功审计一条；原用户可重复读取状态，同店异人 404，合成用户已回滚。运行库迁移头 `024_tiktok_oauth_jobs`，backend/jobs 与公网 ready 健康；OAuth 聚焦 36 passed。首次权限探针在回滚后因 detached ORM 对象退出 1，修正复测通过。真实 callback 重放和 Token 成功刷新仍未验，G1/production 不放行；低敏证据见下文记录入口。

`MVP-UI-CACHE-001` 针对 staging 精确 `/marketing` 路径仍命中旧 HTML/JS 的问题，根布局改为按需生成 HTML；本机生产构建 22/22 浏览器测试、41/41 契约及构建/类型/lint 通过，独立只读复审批准。PR #47 前后端 CI 均通过并 squash 合入远端 `main=118ba775e291b88998bd033b7bca3410e29f8b88`，任务为 `DONE`，production 不变。

独立 `MVP-UI-CACHE-DEPLOY-001` 的首次三新摘要尝试因新检索镜像拉取停滞，在容器切换前取消，失败事实保留。用户随后明确批准**仅本次 staging**复用有依赖锁偏差的旧检索摘要；混合预检 `35953530870`、部署 `35953792293` 通过，新 backend/frontend 已运行。PR #49 合并并仅在 staging vhost 关闭继承的代理缓存；PR #50 合并并修正首页 307 入口验证器；证据 PR #51 前后端 CI 通过并合入 main `8038ad99c3ceb47787bb29b489611a28d012c575`。现场精确无 query 的四个 HTML 路径 200/no-store、指纹 JS immutable、三个健康 200，双机最终验证器通过，其他 vhost/公司负载未变。终态低敏证据见 `../../release/evidence/staging/crm-staging-html-cache-rollout-20260924.json`。任务标为 `DONE`；带身份 staging 全按钮、真实 TikTok、恢复演练和 production 不在此次完成范围。

`MVP-001` 已在真实 staging 完成内部凭据轮换和 TikTok App Key、Service ID、App Secret、DeepSeek API Key 四项外部凭据的安全注入；R02 现场职责矩阵、失败关闭、响应/日志无泄漏、固定出口和三个公网健康端点均通过。一次性工具首次因 cwd 权限在变更前失败，独立复核原配置与健康后修正重试成功。Mock 专用 `TIKTOK_WEBHOOK_SECRET` 不需向平台获取并保持空。R02 TR 为 `PASS`，证据已由 PR #40 合入 main；任务状态收尾为 `DONE`。真实平台接受、G0 恢复/回滚及 production 仍未通过。

`MVP-UI-001` 已修复知识/营销无店铺加载、过期 URL 店铺范围、店铺/渠道/Agent/团队表单反馈、会话筛选与 Agent 日志旧请求竞态。本机合成数据浏览器 20/20（开发服务与生产构建）、前端契约 41/41、lint/typecheck/build 及生产依赖 audit 通过；独立只读复审的问题均已返修。PR #43 前后端 CI 通过并 squash 合入 main `c9e49b88f54807f37b72c4c93ad1d66e554acc7d`，任务为 `DONE`。独立 staging 部署见 `MVP-UI-DEPLOY-001`；production 和真实 TikTok 授权仍未验收。

`MVP-UI-DEPLOY-001` 已从合并 `main=58263b1...` 发布三个镜像，业务机新 backend/frontend 摘要已实际切换且健康。约 8 GB 新检索镜像下载停滞，全量运行在切换前取消；用户明确授权**仅本次 staging**保留有依赖锁偏差的旧检索摘要。限定组合预检 `35849293069`、部署 `35849490309` 通过；固定出口、迁移头、公网三个健康端点、公司 GitLab/system Docker 前后摘要和入口隧道均复核。数据库、MinIO、环境文件受限恢复点已建且可读，未执行真正恢复/兼容回滚或带身份的 staging 逐按钮浏览器验收。证据 PR #45 已通过前后端 CI 并合入 main `ef62b4371736b144ef447352667d6854fb5dcaa8`，本次状态与索引收尾将任务标为 `DONE`；production 未部署。

`MVP-EGRESS-001` 的应用级 SOCKS5H 失败关闭、独立 Rootless helper、最小权限 `crm-egress` 安装器、出口验证器和 staging/回滚门禁已合入 `main`。staging 实际部署运行 `35806983990` 通过，固定出口配置和观测均为 `38.55.145.52`，故障关闭、TikTok 无凭据 TLS、双服务器保护基线和公网健康已验收；最终镜像摘要预检 `35808949842` 通过。业务机 GHCR 下载不稳定，用户明确批准仅本次 staging 保留构建输入等价的旧 backend/frontend 镜像及有依赖差异的旧检索镜像；差异和残余风险见 R02 记录及机器证据。R02 证据已通过 PR #38 合入 `main`；状态收尾分支将任务标为 `DONE`，production 未部署或放行。

入口服务器 root 家目录清理候选为 `85602c3c2702c33cbf00cf554afdfdc8c5ab0aa7`：3.1 GB staging 备份已原子迁入 `/var/backups/crm-staging`，退役 Python 缓存和误生成探针文件已进入 root-only 隔离目录；`/root` 顶层 CRM 项目匹配项为 0。迁移未删除数据，staging vhost、回环隧道与公网健康保持不变。

`MVP-DOMAIN-001` 的 `staging.overselfx.com` / `www.overselfx.com` 契约已合入远端 `main`；staging DNS/TLS 已由 `MVP-STAGING-001` 落地，production 与 Partner Center 仍未放行或变更。

## 权威入口

- 产品范围与验收：[`../product/PRODUCT.md`](../product/PRODUCT.md)
- 系统架构：[`../architecture/SYSTEM.md`](../architecture/SYSTEM.md)
- API 契约：[`../architecture/API.md`](../architecture/API.md)
- AI、RAG 与工具安全：[`../architecture/AI.md`](../architecture/AI.md)
- 唯一任务状态：[`../tasks/TASKS.md`](../tasks/TASKS.md)
- 开发与协作规范：[`../engineering/DEVELOPMENT.md`](../engineering/DEVELOPMENT.md)
- STANDARD 治理：[`../governance/GOVERNANCE.md`](../governance/GOVERNANCE.md)
- 测试策略：[`../quality/TEST-STRATEGY.md`](../quality/TEST-STRATEGY.md)
- 最新测试状态：[`../quality/TEST-STATUS.md`](../quality/TEST-STATUS.md)
- 部署边界：[`../operations/DEPLOYMENT.md`](../operations/DEPLOYMENT.md)
- 生产门禁：[`../operations/RELEASE-GATES.md`](../operations/RELEASE-GATES.md)

## 里程碑与活动任务

- 当前里程碑：关闭 TikTok 人工辅助 v0.1 的 G0～G6 真实环境门禁。
- `MVP-OAUTH-REDIRECT-001`、`MVP-UI-CACHE-DEPLOY-001`、`MVP-UI-CACHE-001`、`REPO-001`、`TEST-001`、`MVP-DOMAIN-001`、`MVP-STAGING-001`、`MVP-EGRESS-001`、`MVP-001`、`MVP-UI-001`、`MVP-UI-DEPLOY-001` 与四个维护清理任务已关闭；MVP-002～MVP-009 保持 `BACKLOG`。
- `MVP-G1-NONLOG-001` 的非物流预检已由 PR #61 合入 main；`MVP-OAUTH-REAUTH-001` 正在整理重新授权现场证据；`MVP-002` 的真实刷新、真实 callback 重放与增强物流仍未关闭。
- v0.1 之后的 Shopee/Amazon、生产翻译、公开自动回复、主动营销和高风险写入保持 `BACKLOG`，不得提前描述为已放行。

## 记录、索引与证据

- REPO-001 实施记录：[`../records/implementation/IR-REPO-001-20260916-R01.md`](../records/implementation/IR-REPO-001-20260916-R01.md)。
- REPO-001 测试记录：[`../reports/tests/TR-REPO-001-20260916-R01.md`](../reports/tests/TR-REPO-001-20260916-R01.md)。
- REPO-001 审查记录：[`../reports/reviews/RR-REPO-001-20260916-R01.md`](../reports/reviews/RR-REPO-001-20260916-R01.md)。三个派生索引状态为 `CURRENT`。
- TEST-001 实施记录：[`../records/implementation/IR-TEST-001-20260916-R01.md`](../records/implementation/IR-TEST-001-20260916-R01.md)。
- TEST-001 测试记录：[`../reports/tests/TR-TEST-001-20260916-R01.md`](../reports/tests/TR-TEST-001-20260916-R01.md)。
- TEST-001 审查记录：[`../reports/reviews/RR-TEST-001-20260916-R01.md`](../reports/reviews/RR-TEST-001-20260916-R01.md)。三个派生索引已从全部源记录重建为 `CURRENT`。
- MVP-DOMAIN-001 实施、测试与审查记录：[`../records/implementation/IR-MVP-DOMAIN-001-20260917-R01.md`](../records/implementation/IR-MVP-DOMAIN-001-20260917-R01.md)、[`../reports/tests/TR-MVP-DOMAIN-001-20260917-R01.md`](../reports/tests/TR-MVP-DOMAIN-001-20260917-R01.md)、[`../reports/reviews/RR-MVP-DOMAIN-001-20260917-R01.md`](../reports/reviews/RR-MVP-DOMAIN-001-20260917-R01.md)。三个派生索引从本地 `main` 读取时为 `CURRENT`。
- MVP-STAGING-001 定稿实施、测试与审查记录：[`../records/implementation/IR-MVP-STAGING-001-20260919-R01.md`](../records/implementation/IR-MVP-STAGING-001-20260919-R01.md)、[`../reports/tests/TR-MVP-STAGING-001-20260919-R01.md`](../reports/tests/TR-MVP-STAGING-001-20260919-R01.md)、[`../reports/reviews/RR-MVP-STAGING-001-20260919-R01.md`](../reports/reviews/RR-MVP-STAGING-001-20260919-R01.md)；工作流与绑定最终 subject 的终态低敏证据见 [`../../release/evidence/staging/crm-staging-deploy-35561109568.json`](../../release/evidence/staging/crm-staging-deploy-35561109568.json) 和 [`../../release/evidence/staging/crm-staging-final-state-20260921.json`](../../release/evidence/staging/crm-staging-final-state-20260921.json)。
- MVP-001 当前 R02：[`../records/implementation/IR-MVP-001-20260923-R02.md`](../records/implementation/IR-MVP-001-20260923-R02.md)、[`../reports/tests/TR-MVP-001-20260923-R02.md`](../reports/tests/TR-MVP-001-20260923-R02.md)、[`../reports/reviews/RR-MVP-001-20260923-R02.md`](../reports/reviews/RR-MVP-001-20260923-R02.md)；外部凭据低敏机器证据见 [`../../release/evidence/staging/crm-staging-external-credentials-20260923.json`](../../release/evidence/staging/crm-staging-external-credentials-20260923.json)。R01 仅代表此前内部轮换；三个派生索引已从 main 合并源记录重建为 `CURRENT`。
- MVP-EGRESS-001 staging 定稿 R02：[`../records/implementation/IR-MVP-EGRESS-001-20260923-R02.md`](../records/implementation/IR-MVP-EGRESS-001-20260923-R02.md)、[`../reports/tests/TR-MVP-EGRESS-001-20260923-R02.md`](../reports/tests/TR-MVP-EGRESS-001-20260923-R02.md)、[`../reports/reviews/RR-MVP-EGRESS-001-20260923-R02.md`](../reports/reviews/RR-MVP-EGRESS-001-20260923-R02.md)；低敏机器证据见 [`../../release/evidence/staging/crm-staging-tiktok-egress-20260923.json`](../../release/evidence/staging/crm-staging-tiktok-egress-20260923.json)。R01 为历史预部署记录，不再代表 live 结果；派生索引从 `main` 已合并源记录重建为 `CURRENT`。
- MVP-UI-001 定稿记录：[`../records/implementation/IR-MVP-UI-001-20260923-R01.md`](../records/implementation/IR-MVP-UI-001-20260923-R01.md)、[`../reports/tests/TR-MVP-UI-001-20260923-R01.md`](../reports/tests/TR-MVP-UI-001-20260923-R01.md)、[`../reports/reviews/RR-MVP-UI-001-20260923-R01.md`](../reports/reviews/RR-MVP-UI-001-20260923-R01.md)。三个派生索引已从 main 的全部合并源记录重建为 `CURRENT`。
- MVP-UI-DEPLOY-001 staging R01：[`../records/implementation/IR-MVP-UI-DEPLOY-001-20260923-R01.md`](../records/implementation/IR-MVP-UI-DEPLOY-001-20260923-R01.md)、[`../reports/tests/TR-MVP-UI-DEPLOY-001-20260923-R01.md`](../reports/tests/TR-MVP-UI-DEPLOY-001-20260923-R01.md)、[`../reports/reviews/RR-MVP-UI-DEPLOY-001-20260923-R01.md`](../reports/reviews/RR-MVP-UI-DEPLOY-001-20260923-R01.md)；低敏现场证据为 [`../../release/evidence/staging/crm-staging-ui-rollout-20260923.json`](../../release/evidence/staging/crm-staging-ui-rollout-20260923.json)。三个派生索引从 main 已合并源记录重建为 `CURRENT`。
- MVP-UI-CACHE-001 定稿 R01：[`../records/implementation/IR-MVP-UI-CACHE-001-20260924-R01.md`](../records/implementation/IR-MVP-UI-CACHE-001-20260924-R01.md)、[`../reports/tests/TR-MVP-UI-CACHE-001-20260924-R01.md`](../reports/tests/TR-MVP-UI-CACHE-001-20260924-R01.md)、[`../reports/reviews/RR-MVP-UI-CACHE-001-20260924-R01.md`](../reports/reviews/RR-MVP-UI-CACHE-001-20260924-R01.md)。
- MVP-UI-CACHE-DEPLOY-001 staging 定稿 R01：[`../records/implementation/IR-MVP-UI-CACHE-DEPLOY-001-20260924-R01.md`](../records/implementation/IR-MVP-UI-CACHE-DEPLOY-001-20260924-R01.md)、[`../reports/tests/TR-MVP-UI-CACHE-DEPLOY-001-20260924-R01.md`](../reports/tests/TR-MVP-UI-CACHE-DEPLOY-001-20260924-R01.md)、[`../reports/reviews/RR-MVP-UI-CACHE-DEPLOY-001-20260924-R01.md`](../reports/reviews/RR-MVP-UI-CACHE-DEPLOY-001-20260924-R01.md)；现场终态证据为 [`../../release/evidence/staging/crm-staging-html-cache-rollout-20260924.json`](../../release/evidence/staging/crm-staging-html-cache-rollout-20260924.json)。三个派生索引从已合并的 main 源记录重建为 `CURRENT`。
- MVP-OAUTH-REDIRECT-001 已合入 R01：[`../records/implementation/IR-MVP-OAUTH-REDIRECT-001-20260924-R01.md`](../records/implementation/IR-MVP-OAUTH-REDIRECT-001-20260924-R01.md)、[`../reports/tests/TR-MVP-OAUTH-REDIRECT-001-20260924-R01.md`](../reports/tests/TR-MVP-OAUTH-REDIRECT-001-20260924-R01.md)、[`../reports/reviews/RR-MVP-OAUTH-REDIRECT-001-20260924-R01.md`](../reports/reviews/RR-MVP-OAUTH-REDIRECT-001-20260924-R01.md)。
- MVP-READONLY-LOG-001 定稿 R01：[`../records/implementation/IR-MVP-READONLY-LOG-001-20260928-R01.md`](../records/implementation/IR-MVP-READONLY-LOG-001-20260928-R01.md)、[`../reports/tests/TR-MVP-READONLY-LOG-001-20260928-R01.md`](../reports/tests/TR-MVP-READONLY-LOG-001-20260928-R01.md)、[`../reports/reviews/RR-MVP-READONLY-LOG-001-20260928-R01.md`](../reports/reviews/RR-MVP-READONLY-LOG-001-20260928-R01.md)。三个派生索引从已合并 main 的源记录重建为 `CURRENT`。
- MVP-G1-NONLOG-001 非物流预检 R01 已由 PR #61 合入 main：[`../records/implementation/IR-MVP-G1-NONLOG-001-20260928-R01.md`](../records/implementation/IR-MVP-G1-NONLOG-001-20260928-R01.md)、[`../reports/tests/TR-MVP-G1-NONLOG-001-20260928-R01.md`](../reports/tests/TR-MVP-G1-NONLOG-001-20260928-R01.md)、[`../reports/reviews/RR-MVP-G1-NONLOG-001-20260928-R01.md`](../reports/reviews/RR-MVP-G1-NONLOG-001-20260928-R01.md)；低敏机器证据为 [`../../release/evidence/staging/crm-staging-g1-nonlog-20260928.json`](../../release/evidence/staging/crm-staging-g1-nonlog-20260928.json)。三个派生索引从已合并 main 的源记录重建为 `CURRENT`。
- MVP-OAUTH-REAUTH-001 staging R01：[`../records/implementation/IR-MVP-OAUTH-REAUTH-001-20260928-R01.md`](../records/implementation/IR-MVP-OAUTH-REAUTH-001-20260928-R01.md)、[`../reports/tests/TR-MVP-OAUTH-REAUTH-001-20260928-R01.md`](../reports/tests/TR-MVP-OAUTH-REAUTH-001-20260928-R01.md)、[`../reports/reviews/RR-MVP-OAUTH-REAUTH-001-20260928-R01.md`](../reports/reviews/RR-MVP-OAUTH-REAUTH-001-20260928-R01.md)；低敏证据为 [`../../release/evidence/staging/crm-staging-oauth-reauth-20260928.json`](../../release/evidence/staging/crm-staging-oauth-reauth-20260928.json)。分支索引为 `CANDIDATE_VIEW`。
- 发布基线与低敏机器证据：[`../../release/`](../../release/)。
- 目录卫生：`frontend/` 空缓存树与 `.test-tmp/` 零字节测试残留已移出活动根并进入 `.maintenance/` 持久隔离；`CLEANUP-20260916-001` 状态为 `VERIFIED_UNUSED`，从实际隔离时间起保留满 7 天后，最早永久删除时间为 2026-09-23T14:00:00+08:00。
- `CLEANUP-20260916-002` 已将主 checkout 中唯一的旧 `src/backend/tests/` pytest 缓存隔离到 `.maintenance/`，状态为 `VERIFIED_UNUSED`，最早永久删除时间为 2026-09-23T18:05:00+08:00，恢复方法和摘要见 [`../operations/cleanup/CLEANUP-20260916-002.md`](../operations/cleanup/CLEANUP-20260916-002.md)。
- `CLEANUP-20260921-003` 已把入口服务器 root 家目录中的 staging 备份迁入 `/var/backups/crm-staging`，把两个退役生成物迁入 `/var/lib/crm-staging/quarantine/CLEANUP-20260921-003/root-home/`；状态为 `QUARANTINED`，备份永久保留，隔离物最早复核时间为 2026-09-28T14:37:17+08:00，详见 [`../operations/cleanup/CLEANUP-20260921-003.md`](../operations/cleanup/CLEANUP-20260921-003.md)。
- `CLEANUP-20260921-004` 已通过 PR #32 合入 `main`：截图中的六个已合并本地 worktree 和对应本地短期分支已删除，共移除 2,749,219,080 B；`origin/main`、主 checkout 的本地领先提交与未跟踪 `.superpowers/` 均未改变，详见 [`../operations/cleanup/CLEANUP-20260921-004.md`](../operations/cleanup/CLEANUP-20260921-004.md)。
- TEST-001 验证保留了已忽略的 `src/tests/.artifacts/task6-4cd6664-temp/`，仓库外受控验证工作区也保留 candidate-scoped archive、override 和 temp。它们是已知可重建临时材料，但未建立独立清理任务/批次，未移动或删除，因此目录卫生不标记 `CLEAN`。

## 阻塞、决定与风险

- G0～G6 尚未全部取得真实环境证据，G8 保持阻塞；工程实现、Mock 或历史确定性测试不能替代生产验收。
- 用户已重新选择 North America seller/US 完成授权并自动返回 CRM；job 终态和任务读取权限已有本次低敏核对，仍需真实 callback 重放、Token 生命周期与增强物流，不得将前端回跳或本次窄范围验收视为 G1 全通过。
- `MVP-001` 的内部轮换及外部四项凭据注入已通过；TikTok OAuth 已获用户确认，DeepSeek 平台接受仍未测试。固定出口已在 live staging 观测为 `38.55.145.52`；Partner Center 白名单只有用户截图，仍需真实平台出口证据确认。Mock 专用 `TIKTOK_WEBHOOK_SECRET` 不是外部待准备凭据。
- `AUTO_REPLY_ENABLED=false` 与 `REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED=false` 继续作为安全基线。
- staging DNS/TLS、`18080 → 18081` 反向隧道和 Rootless CRM 当前可用；临时 registry 代理已撤除。2026-09-24 新 backend/frontend 摘要已运行且健康；旧检索摘要仅按本次 staging 的重新授权保留，依赖锁有差异。下一次镜像升级不得继承此次豁免。
- 入口服务器仍有一个失败且非持久的 `crm-external-image-prepare.service` transient unit，引用已不存在的退役脚本；本清理批次未扩大范围修改它，当前不监听端口且不影响 staging。
- TEST-001 独立审查 Critical 0、Important 0；非阻塞 Minor 建议是未来在 `src/tests/README.md` 说明 sibling-path 聚焦 pytest 需要 `-c pyproject.toml`，本候选未因此改变。
- TEST-001 仍保留两个既有前端 lint warning、两个 Python 弃用 warning 与一个 npm high severity audit 项；依赖升级另立任务，ignored temp 清理须遵守独立清理治理。
- MVP-UI-001 的本机隔离浏览器交互和本轮 staging 镜像部署/公开路由冒烟分别有证据；带身份的 staging 逐按钮浏览器与真实 TikTok 授权仍待专门验收。用户根 checkout 的本地 `main` 另有一个未推送提交及未知 `.superpowers/`，本分支没有修改它们。
- 本轮成功恢复点为 `/var/backups/crm-staging/secrets/20260921T080357Z/`；两份失败尝试恢复副本仍为 root-only 0600，清理必须另立 `MAINT-CLEANUP-*`，当前不得删除。
- Git、文件、Codex UI 与 GitHub 不是原子事务；每一步必须查重、执行、复核并保留恢复点。

## 最多三个下一动作

1. 单独设计安全的真实 callback 重放验收；不得读取、保存或传播回调 `code/state`，也不能把重复 job 轮询冒充重放。
2. 在自然刷新窗口验证 Token 成功刷新，并单独核对增强物流 `202604` 业务码 `11007009`；不要把六项只读成功外推为 G1 全过。
3. 安排 `MVP-008` 数据库/对象存储恢复与兼容上一版镜像实际回滚；G0～G8 未齐前 production 继续关闭。
