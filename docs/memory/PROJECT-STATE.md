# 项目状态与恢复入口

本文件是跨 Codex 会话恢复项目所需的精简摘要，不复制 `../tasks/TASKS.md` 的任务状态、`../quality/TEST-STATUS.md` 的测试结论或 `../operations/RELEASE-GATES.md` 的门禁正文。恢复工作时先读本文件，再按链接读取事实源。

2026-09-28 目录卫生补记：`MAINT-CLEANUP-20260928-001` 已移除 PR #53 合并后的 OAuth 代码本地工作树与分支，清理记录由 PR #57 合入 `main`；`MAINT-CLEANUP-20260928-002` 已按用户精确授权移除 PR #52 合并后的 HTML 缓存工作树、两份重复 SSH 私钥副本与本地诊断资料，原始密钥不变，清理记录由 PR #59 合入 `main`。另三个截图工作树因开放 PR 或未完成现场验收而保留。批次见 [`../operations/cleanup/CLEANUP-20260928-001.md`](../operations/cleanup/CLEANUP-20260928-001.md)、[`../operations/cleanup/CLEANUP-20260928-002.md`](../operations/cleanup/CLEANUP-20260928-002.md)。下方历史部署快照不是当日运行状态，以当前任务表与发布证据为准。

## 当前状态

```text
Project phase: ACTIVE
Governance tier: STANDARD
Repository identity: origin=ssh://git@ssh.github.com:443/CP11-gh/CRM.git
Primary branch: main
Working branch at this snapshot: docs/staging-proxy-persist-done-20261008
Governance base SHA: 8fae4fb85c4ed9c8cdf862f99d839c3de60e55ab
CANDIDATE_SUBJECT_SHA: dcddb26cbb6ecc92db30a11a2f504d034e6ec048
EVIDENCE_HEAD_SHA: READ_AT_GATE
Workspace hygiene: ATTENTION — `CLEANUP-20260921-004` 已删除六个已合并本地 worktree；既有隔离保留期、两份 MVP-001 root-only 恢复副本和其他忽略测试材料不在本批次范围
```

当前工程根为 `src/`，测试资产集中在 `src/tests/`。`MVP-STAGING-001` 已完成双服务器 split-ingress 真实部署：`38.55.145.52` 只承担宝塔 Nginx/TLS 和回环 `18080`，`192.168.110.210` 的 `crmdeploy` Rootless CRM 只发布回环 `18081`；DNS、Let's Encrypt 证书、迁移头、公网健康、隧道恢复和公司负载零变化已验收。最终候选 subject 为 `c0f1e6f0a5c575190b71541be3f67b3163780d61`，与已部署运行配置 `98460796...` 的受审运行资产零差异；终态证据已通过 PR #26 合入 `main`，任务状态为 `DONE`，production 未部署。`EVIDENCE_HEAD_SHA` 必须在门禁或交接时从 Git 现场读取，不在仓库中自指回填。

`MVP-OAUTH-REDIRECT-001` 已由 PR #53 合入 `main`。用户重新选择 North America seller 与 US 后完成 TikTok 授权，成功页自动返回 CRM；此前卖家类型拒绝系操作选择错误，不再作为当前阻塞。现场只读预检中旧版物流 `202309` 成功，增强物流 `202604` 返回业务码 `11007009`，含义未确认，不能将两者混同；Token 生命周期、店铺隔离和重复回调现场证据仍未关闭 G1。production 未变。

`MVP-READONLY-LOG-001` 源码已由 PR #54 合入 main；staging 部署和增强物流失败的独立记录仍在 PR #56 草稿中。2026-09-28 本轮非物流预检在现有 staging 后端执行六项真实只读查询成功，未提交合成用户跨店读/OAuth 发起均 404，当前 connected 渠道的 Scope、密文和未到期刷新调度核对通过；后端本机 1650 passed/18 skipped。08:00:03Z 盘点时 OAuth job 为零，后续复核已见新 job；授权审计与该初次零值均不能证明新任务终态，成功刷新和 `202604` 增强物流仍未过。证据见下文 `MVP-G1-NONLOG-001`，G1 保持部分通过，production 不变。

`MVP-OAUTH-REAUTH-001` 本次 staging 事实：用户确认美国测试店铺授权后自动返回 CRM 并显示已连接；08:00Z 后唯一新 OAuth job 已完成为 connected、code/state 清空，同一发起用户/店铺/渠道的成功审计一条；原用户可重复读取状态，同店异人 404，合成用户已回滚。运行库迁移头 `024_tiktok_oauth_jobs`，backend/jobs 与公网 ready 健康；OAuth 聚焦 36 passed。首次权限探针在回滚后因 detached ORM 对象退出 1，修正复测通过。真实 callback 重放和 Token 成功刷新仍未验，G1/production 不放行；低敏证据见下文记录入口。

`MVP-008-RESTORE-001` 的 2026-09-29 staging 隔离恢复已现场执行：PostgreSQL 备份恢复后 `024`、29 表/85 行逐表计数一致；MinIO 原桶为空，隔离实例中用合成对象验证第二次备份恢复后字节/SHA 一致。临时数据库/容器/卷/网络已移除，受限备份保留；公司系统 Docker 基线及三个公网健康未变。用户人工审阅、独立只读复审与前后端 CI 通过后，证据由 PR #65 合入 main `ad86ce141c1a467b535378665c0e71179036f3a6`；仅隔离恢复子项可标记 DONE，兼容上一版镜像实际回滚和 G0/production 仍未通过。

`MVP-008` 早期预取连续受 GHCR/CDN TCP 重置和 Runner 自动更新超时阻断；PR #79～#83 形成分层检索镜像、Runner 2.337.0 恢复及可校验 OCI 续传。历史失败运行与原因见 `../operations/DEPLOYMENT.md`，不得将其当作当前门禁状态。

2026-09-30 已完成六摘要预取 `36699523917`、候选预检 `36700668599`、候选部署 `36701049769`、上一版三镜像实际切回 `36701815122`、候选切返 `36702556391`。切返后独立核对候选三摘要、11 个容器、数据库迁移头 `024`、三个公网健康 200 及固定出口；Docker 配置原始 SHA 恢复，环境文件 `0600` 恢复副本保留。原始 artifact 摘要见 `../../release/evidence/staging/crm-staging-mvp008-g0-20260930.json`。G0 的 staging 恢复/回滚证据已齐；G1～G6、G8 和 production 未放行。

2026-10-02 恢复点：G1 真实 callback 重放的低敏验收流程已由 PR #86 合入 `main=c707731c0d09b610938585088653875a0a377063`，见 [`../operations/RELEASE-GATES.md`](../operations/RELEASE-GATES.md)。同日 staging 11 个 CRM 容器运行，过去 24 小时新增 OAuth job 与授权/刷新审计均为零；现有访问 Token 到期时间为 2026-10-05T10:05:17Z，按当前提前一天的配置，自然刷新窗口约从 2026-10-04T10:05:17Z 开始。真实重放、成功刷新和增强物流 `202604` 仍未取得通过证据；G1 维持部分通过。

2026-10-08 恢复点：自然 Token 刷新已由后台 job 于 10-04T10:05Z 真实成功完成，渠道保持 connected，低敏证据见 [`../../release/evidence/staging/crm-staging-g1-natural-token-refresh-20261008.json`](../../release/evidence/staging/crm-staging-g1-natural-token-refresh-20261008.json)。同日发现固定出口 helper 自 10-06T18:01Z 退出，Docker 最后错误为 systemd cgroup scope 创建超时；仅重启该既有容器后健康，应用 SOCKS5H 实测仍从 `38.55.145.52` 出站，见 [`../../release/evidence/staging/crm-staging-tiktok-egress-recovery-20261008.json`](../../release/evidence/staging/crm-staging-tiktok-egress-recovery-20261008.json)。历史 Network 303 被排除为本次重放证据；新的 OAuth 发起未收到 callback，用户报告 TikTok 账号无法登录。G1 继续部分通过，G6 的五日稳定性不得包含本次出口中断。

同日 staging 全容器重启暴露 proxy 配置 bind 来源在已清理的 Runner 临时目录：proxy 首次重启失败且公网 ready 返回 502。用哈希一致的持久受审源码恢复原挂载文件后，PR #89 改为从持久目录部署；`main=dcddb26cbb6ecc92db30a11a2f504d034e6ec048` 的预检/部署 `37716193186`/`37716402745` 通过，作业结束后再次重启 proxy 健康，公网登录和三个健康接口 200，固定出口仍为 `38.55.145.52`，同机系统 Docker 容器 ID 不变。低敏证据见 [`../../release/evidence/staging/crm-staging-proxy-persistent-source-20261008.json`](../../release/evidence/staging/crm-staging-proxy-persistent-source-20261008.json)。用户新截图显示已进入 TikTok 商家中心，但授权页提示“连接失败”；CRM 起始链接仅含 `service_id`/`state`，尚无证据说明平台页失败原因或收到新的 callback，不复用截图中的状态参数。

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
- `MVP-008` 的 staging 现场预取、候选部署、旧版回滚和切返证据已由 PR #84 合入 main `8fae4fb85c4ed9c8cdf862f99d839c3de60e55ab`；任务状态以 `../tasks/TASKS.md` 为准。
- `MVP-G1-NONLOG-001` 与 `MVP-OAUTH-REAUTH-001` 已合入 main；`MVP-002` 的真实 Token 刷新、callback 重放与增强物流 `202604` 仍未关闭。
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
- MVP-OAUTH-REAUTH-001 staging R01 已由 PR #63 合入 main：[`../records/implementation/IR-MVP-OAUTH-REAUTH-001-20260928-R01.md`](../records/implementation/IR-MVP-OAUTH-REAUTH-001-20260928-R01.md)、[`../reports/tests/TR-MVP-OAUTH-REAUTH-001-20260928-R01.md`](../reports/tests/TR-MVP-OAUTH-REAUTH-001-20260928-R01.md)、[`../reports/reviews/RR-MVP-OAUTH-REAUTH-001-20260928-R01.md`](../reports/reviews/RR-MVP-OAUTH-REAUTH-001-20260928-R01.md)；低敏证据为 [`../../release/evidence/staging/crm-staging-oauth-reauth-20260928.json`](../../release/evidence/staging/crm-staging-oauth-reauth-20260928.json)。三个派生索引从已合并 main 源记录重建为 `CURRENT`。
- MVP-008-RESTORE-001 staging R01 已由 PR #65 合入 main：[`../records/implementation/IR-MVP-008-RESTORE-001-20260929-R01.md`](../records/implementation/IR-MVP-008-RESTORE-001-20260929-R01.md)、[`../reports/tests/TR-MVP-008-RESTORE-001-20260929-R01.md`](../reports/tests/TR-MVP-008-RESTORE-001-20260929-R01.md)、[`../reports/reviews/RR-MVP-008-RESTORE-001-20260929-R01.md`](../reports/reviews/RR-MVP-008-RESTORE-001-20260929-R01.md)；低敏证据为 [`../../release/evidence/staging/crm-staging-isolated-restore-20260929.json`](../../release/evidence/staging/crm-staging-isolated-restore-20260929.json)。三个派生索引从已合并 main 的源记录重建为 `CURRENT`；本任务不代表 G0 签署。
- MVP-008 staging G0 R01 已由 PR #84 合入 main：[`../records/implementation/IR-MVP-008-20260930-R01.md`](../records/implementation/IR-MVP-008-20260930-R01.md)、[`../reports/tests/TR-MVP-008-20260930-R01.md`](../reports/tests/TR-MVP-008-20260930-R01.md)、[`../reports/reviews/RR-MVP-008-20260930-R01.md`](../reports/reviews/RR-MVP-008-20260930-R01.md)；[低敏 G0 现场证据](../../release/evidence/staging/crm-staging-mvp008-g0-20260930.json)。三个派生索引已从 main 的源记录重建为 `CURRENT`。
- MVP-STAGING-PROXY-PERSIST-001 staging R01 已由证据 PR #90 合入 main：[`../records/implementation/IR-MVP-STAGING-PROXY-PERSIST-001-20261008-R01.md`](../records/implementation/IR-MVP-STAGING-PROXY-PERSIST-001-20261008-R01.md)、[`../reports/tests/TR-MVP-STAGING-PROXY-PERSIST-001-20261008-R01.md`](../reports/tests/TR-MVP-STAGING-PROXY-PERSIST-001-20261008-R01.md)、[`../reports/reviews/RR-MVP-STAGING-PROXY-PERSIST-001-20261008-R01.md`](../reports/reviews/RR-MVP-STAGING-PROXY-PERSIST-001-20261008-R01.md)；[低敏持久挂载证据](../../release/evidence/staging/crm-staging-proxy-persistent-source-20261008.json)。三份索引已从合并 main 的源记录核对为 `CURRENT`，任务为 `DONE`，G1/G6 和 production 不因此放行。
- 发布基线与低敏机器证据：[`../../release/`](../../release/)。
- 目录卫生：`frontend/` 空缓存树与 `.test-tmp/` 零字节测试残留已移出活动根并进入 `.maintenance/` 持久隔离；`CLEANUP-20260916-001` 状态为 `VERIFIED_UNUSED`，从实际隔离时间起保留满 7 天后，最早永久删除时间为 2026-09-23T14:00:00+08:00。
- `CLEANUP-20260916-002` 已将主 checkout 中唯一的旧 `src/backend/tests/` pytest 缓存隔离到 `.maintenance/`，状态为 `VERIFIED_UNUSED`，最早永久删除时间为 2026-09-23T18:05:00+08:00，恢复方法和摘要见 [`../operations/cleanup/CLEANUP-20260916-002.md`](../operations/cleanup/CLEANUP-20260916-002.md)。
- `CLEANUP-20260921-003` 已把入口服务器 root 家目录中的 staging 备份迁入 `/var/backups/crm-staging`，把两个退役生成物迁入 `/var/lib/crm-staging/quarantine/CLEANUP-20260921-003/root-home/`；状态为 `QUARANTINED`，备份永久保留，隔离物最早复核时间为 2026-09-28T14:37:17+08:00，详见 [`../operations/cleanup/CLEANUP-20260921-003.md`](../operations/cleanup/CLEANUP-20260921-003.md)。
- `CLEANUP-20260921-004` 已通过 PR #32 合入 `main`：截图中的六个已合并本地 worktree 和对应本地短期分支已删除，共移除 2,749,219,080 B；`origin/main`、主 checkout 的本地领先提交与未跟踪 `.superpowers/` 均未改变，详见 [`../operations/cleanup/CLEANUP-20260921-004.md`](../operations/cleanup/CLEANUP-20260921-004.md)。
- TEST-001 验证保留了已忽略的 `src/tests/.artifacts/task6-4cd6664-temp/`，仓库外受控验证工作区也保留 candidate-scoped archive、override 和 temp。它们是已知可重建临时材料，但未建立独立清理任务/批次，未移动或删除，因此目录卫生不标记 `CLEAN`。

## 阻塞、决定与风险

- G0 staging 恢复/回滚现场通过；G1～G6 尚未全部取得真实环境证据，G8 保持阻塞，production 未部署。
- 用户此前选择 North America seller/US 完成授权并自动返回 CRM；job 终态和任务读取权限已有低敏核对，2026-10-04 自然 Token 刷新也已通过。当前仍需同一真实 callback 重放与增强物流 `202604`；2026-10-08 TikTok 账号登录问题阻断新的浏览器授权，不得把历史 Network 303 当成本次重放。
- `MVP-001` 的内部轮换及外部四项凭据注入已通过；TikTok OAuth 已获用户确认，DeepSeek 平台接受仍未测试。固定出口已在 live staging 观测为 `38.55.145.52`；Partner Center 白名单只有用户截图，仍需真实平台出口证据确认。Mock 专用 `TIKTOK_WEBHOOK_SECRET` 不是外部待准备凭据。
- `AUTO_REPLY_ENABLED=false` 与 `REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED=false` 继续作为安全基线。
- staging DNS/TLS、`18080 → 18081` 隧道和 Rootless CRM 可用；切返后运行候选后端、前端及分层检索三个不可变摘要。固定出口 helper 曾异常退出，2026-10-08 已恢复健康并复测 `38.55.145.52`；后续须核对是否再发以及告警覆盖。
- 入口服务器仍有一个失败且非持久的 `crm-external-image-prepare.service` transient unit，引用已不存在的退役脚本；本清理批次未扩大范围修改它，当前不监听端口且不影响 staging。
- TEST-001 独立审查 Critical 0、Important 0；非阻塞 Minor 建议是未来在 `src/tests/README.md` 说明 sibling-path 聚焦 pytest 需要 `-c pyproject.toml`，本候选未因此改变。
- TEST-001 仍保留两个既有前端 lint warning、两个 Python 弃用 warning 与一个 npm high severity audit 项；依赖升级另立任务，ignored temp 清理须遵守独立清理治理。
- MVP-UI-001 的本机隔离浏览器交互和本轮 staging 镜像部署/公开路由冒烟分别有证据；带身份的 staging 逐按钮浏览器与真实 TikTok 授权仍待专门验收。用户根 checkout 的本地 `main` 另有一个未推送提交及未知 `.superpowers/`，本分支没有修改它们。
- 本轮成功恢复点为 `/var/backups/crm-staging/secrets/20260921T080357Z/`；两份失败尝试恢复副本仍为 root-only 0600，清理必须另立 `MAINT-CLEANUP-*`，当前不得删除。
- Git、文件、Codex UI 与 GitHub 不是原子事务；每一步必须查重、执行、复核并保留恢复点。

## 最多三个下一动作

1. 另行定位 TikTok 商家中心授权页“连接失败”，从 CRM **重新发起**授权后按 `../operations/RELEASE-GATES.md` 验证同一真实 callback 重放；不得读取、保存或传播 `code/state`，历史 303 不算证据。
2. 单独核对增强物流 `202604` 的平台适用条件和固定出口告警；保持活动 proxy 的持久源码目录。
3. 继续 G1～G6 的真实门禁；G8 与 production 仍为 No-Go。
