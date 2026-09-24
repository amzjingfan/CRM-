# 项目状态与恢复入口

本文件是跨 Codex 会话恢复项目所需的精简摘要，不复制 `../tasks/TASKS.md` 的任务状态、`../quality/TEST-STATUS.md` 的测试结论或 `../operations/RELEASE-GATES.md` 的门禁正文。恢复工作时先读本文件，再按链接读取事实源。

## 当前状态

```text
Project phase: ACTIVE
Governance tier: STANDARD
Repository identity: origin=ssh://git@ssh.github.com:443/CP11-gh/CRM.git
Primary branch: main
Working branch at this snapshot: fix/staging-html-cache-20260924
Governance base SHA: 7890f4acf12e956544c0acbd34033857dce88d81
CANDIDATE_SUBJECT_SHA: 7617647965278198b2712b678007bc3ad6fbbe98
EVIDENCE_HEAD_SHA: READ_AT_GATE
Workspace hygiene: ATTENTION — `CLEANUP-20260921-004` 已删除六个已合并本地 worktree；既有隔离保留期、两份 MVP-001 root-only 恢复副本和其他忽略测试材料不在本批次范围
```

当前工程根为 `src/`，测试资产集中在 `src/tests/`。`MVP-STAGING-001` 已完成双服务器 split-ingress 真实部署：`38.55.145.52` 只承担宝塔 Nginx/TLS 和回环 `18080`，`192.168.110.210` 的 `crmdeploy` Rootless CRM 只发布回环 `18081`；DNS、Let's Encrypt 证书、迁移头、公网健康、隧道恢复和公司负载零变化已验收。最终候选 subject 为 `c0f1e6f0a5c575190b71541be3f67b3163780d61`，与已部署运行配置 `98460796...` 的受审运行资产零差异；终态证据已通过 PR #26 合入 `main`，任务状态为 `DONE`，production 未部署。`EVIDENCE_HEAD_SHA` 必须在门禁或交接时从 Git 现场读取，不在仓库中自指回填。

`MVP-UI-CACHE-001` 针对 staging 精确 `/marketing` 路径仍命中旧 HTML/JS 的问题，候选根布局改为按需生成 HTML；本机生产构建 22/22 浏览器测试、41/41 契约及构建/类型/lint 通过，独立只读复审批准。当前任务为 `VERIFYING`，待 PR CI/合并；合并后只部署 staging，production 不变。此前旧检索摘要例外仅适用 2026-09-23 的部署，不能继承到新发布。

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
- `MVP-UI-CACHE-001` 为 `VERIFYING`；`REPO-001`、`TEST-001`、`MVP-DOMAIN-001`、`MVP-STAGING-001`、`MVP-EGRESS-001`、`MVP-001`、`MVP-UI-001`、`MVP-UI-DEPLOY-001` 与四个维护清理任务已关闭；MVP-002～MVP-009 保持 `BACKLOG`。
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
- MVP-UI-CACHE-001 候选 R01：[`../records/implementation/IR-MVP-UI-CACHE-001-20260924-R01.md`](../records/implementation/IR-MVP-UI-CACHE-001-20260924-R01.md)、[`../reports/tests/TR-MVP-UI-CACHE-001-20260924-R01.md`](../reports/tests/TR-MVP-UI-CACHE-001-20260924-R01.md)、[`../reports/reviews/RR-MVP-UI-CACHE-001-20260924-R01.md`](../reports/reviews/RR-MVP-UI-CACHE-001-20260924-R01.md)；分支派生索引为 `CANDIDATE_VIEW`，合并后从 main 重建。
- 发布基线与低敏机器证据：[`../../release/`](../../release/)。
- 目录卫生：`frontend/` 空缓存树与 `.test-tmp/` 零字节测试残留已移出活动根并进入 `.maintenance/` 持久隔离；`CLEANUP-20260916-001` 状态为 `VERIFIED_UNUSED`，从实际隔离时间起保留满 7 天后，最早永久删除时间为 2026-09-23T14:00:00+08:00。
- `CLEANUP-20260916-002` 已将主 checkout 中唯一的旧 `src/backend/tests/` pytest 缓存隔离到 `.maintenance/`，状态为 `VERIFIED_UNUSED`，最早永久删除时间为 2026-09-23T18:05:00+08:00，恢复方法和摘要见 [`../operations/cleanup/CLEANUP-20260916-002.md`](../operations/cleanup/CLEANUP-20260916-002.md)。
- `CLEANUP-20260921-003` 已把入口服务器 root 家目录中的 staging 备份迁入 `/var/backups/crm-staging`，把两个退役生成物迁入 `/var/lib/crm-staging/quarantine/CLEANUP-20260921-003/root-home/`；状态为 `QUARANTINED`，备份永久保留，隔离物最早复核时间为 2026-09-28T14:37:17+08:00，详见 [`../operations/cleanup/CLEANUP-20260921-003.md`](../operations/cleanup/CLEANUP-20260921-003.md)。
- `CLEANUP-20260921-004` 已通过 PR #32 合入 `main`：截图中的六个已合并本地 worktree 和对应本地短期分支已删除，共移除 2,749,219,080 B；`origin/main`、主 checkout 的本地领先提交与未跟踪 `.superpowers/` 均未改变，详见 [`../operations/cleanup/CLEANUP-20260921-004.md`](../operations/cleanup/CLEANUP-20260921-004.md)。
- TEST-001 验证保留了已忽略的 `src/tests/.artifacts/task6-4cd6664-temp/`，仓库外受控验证工作区也保留 candidate-scoped archive、override 和 temp。它们是已知可重建临时材料，但未建立独立清理任务/批次，未移动或删除，因此目录卫生不标记 `CLEAN`。

## 阻塞、决定与风险

- G0～G6 尚未全部取得真实环境证据，G8 保持阻塞；工程实现、Mock 或历史确定性测试不能替代生产验收。
- `MVP-001` 的内部轮换及外部四项凭据注入已通过；真实 TikTok/DeepSeek 平台是否接受尚未测试。固定出口已在 live staging 观测为 `38.55.145.52`；Partner Center 白名单只有用户截图，仍需真实平台流程确认。Mock 专用 `TIKTOK_WEBHOOK_SECRET` 不是外部待准备凭据。
- `AUTO_REPLY_ENABLED=false` 与 `REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED=false` 继续作为安全基线。
- staging DNS/TLS、`18080 → 18081` 反向隧道和 Rootless CRM 当前可用；临时 registry 代理已撤除。新 backend/frontend 摘要已完成实际下载、部署和健康验证；新检索镜像仍受 GHCR CDN 下载阻断，旧摘要只按本次 UI staging 授权保留。下一次镜像升级不得继承此次或此前固定出口任务的豁免。
- 入口服务器仍有一个失败且非持久的 `crm-external-image-prepare.service` transient unit，引用已不存在的退役脚本；本清理批次未扩大范围修改它，当前不监听端口且不影响 staging。
- TEST-001 独立审查 Critical 0、Important 0；非阻塞 Minor 建议是未来在 `src/tests/README.md` 说明 sibling-path 聚焦 pytest 需要 `-c pyproject.toml`，本候选未因此改变。
- TEST-001 仍保留两个既有前端 lint warning、两个 Python 弃用 warning 与一个 npm high severity audit 项；依赖升级另立任务，ignored temp 清理须遵守独立清理治理。
- MVP-UI-001 的本机隔离浏览器交互和本轮 staging 镜像部署/公开路由冒烟分别有证据；带身份的 staging 逐按钮浏览器与真实 TikTok 授权仍待专门验收。用户根 checkout 的本地 `main` 另有一个未推送提交及未知 `.superpowers/`，本分支没有修改它们。
- 本轮成功恢复点为 `/var/backups/crm-staging/secrets/20260921T080357Z/`；两份失败尝试恢复副本仍为 root-only 0600，清理必须另立 `MAINT-CLEANUP-*`，当前不得删除。
- Git、文件、Codex UI 与 GitHub 不是原子事务；每一步必须查重、执行、复核并保留恢复点。

## 最多三个下一动作

1. 用独立测试账号与隔离数据在已部署 staging 执行带身份的管理端逐按钮浏览器冒烟，并独立启动 `MVP-002` 真实 OAuth/只读验收；真实开关在门禁通过前保持关闭。
2. 安排 `MVP-008` 数据库/对象存储恢复与兼容上一版镜像实际回滚。
3. 业务机 GHCR 下载恢复后补齐新检索镜像的同源部署验证；G0～G8 未齐前 production 继续关闭。
