# 项目状态与恢复入口

本文件是跨 Codex 会话恢复项目所需的精简摘要，不复制 `../tasks/TASKS.md` 的任务状态、`../quality/TEST-STATUS.md` 的测试结论或 `../operations/RELEASE-GATES.md` 的门禁正文。恢复工作时先读本文件，再按链接读取事实源。

## 当前状态

```text
Project phase: ACTIVE
Governance tier: STANDARD
Repository identity: origin=ssh://git@ssh.github.com:443/CP11-gh/CRM.git
Primary branch: main
Working branch at this snapshot: docs/mvp-egress-status-closure
Governance base SHA: 99800c3bfac29df31392a05344e7dcb9a2d34fb1
CANDIDATE_SUBJECT_SHA: 746c10cacf7b2e1e827317e9759e203dc0cc9551
EVIDENCE_HEAD_SHA: READ_AT_GATE
Workspace hygiene: ATTENTION — `CLEANUP-20260921-004` 已删除六个已合并本地 worktree；既有隔离保留期、两份 MVP-001 root-only 恢复副本和其他忽略测试材料不在本批次范围
```

当前工程根为 `src/`，测试资产集中在 `src/tests/`。`MVP-STAGING-001` 已完成双服务器 split-ingress 真实部署：`38.55.145.52` 只承担宝塔 Nginx/TLS 和回环 `18080`，`192.168.110.210` 的 `crmdeploy` Rootless CRM 只发布回环 `18081`；DNS、Let's Encrypt 证书、迁移头、公网健康、隧道恢复和公司负载零变化已验收。最终候选 subject 为 `c0f1e6f0a5c575190b71541be3f67b3163780d61`，与已部署运行配置 `98460796...` 的受审运行资产零差异；终态证据已通过 PR #26 合入 `main`，任务状态为 `DONE`，production 未部署。`EVIDENCE_HEAD_SHA` 必须在门禁或交接时从 Git 现场读取，不在仓库中自指回填。

`MVP-001` 已在真实 staging 完成内部凭据轮换：PostgreSQL、MinIO、JWT、检索令牌和 TikTok 凭据加密主密钥的新配置已注入容器，新 PostgreSQL/MinIO/检索值接受、旧值拒绝，响应/日志扫描通过，三个公网健康端点为 200。TikTok Partner Center 与 DeepSeek 外部凭据仍为空，因此任务状态为 `BLOCKED`、TR 为 `PARTIAL`，production 和真实能力继续关闭。

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
- `REPO-001`、`TEST-001`、`MVP-DOMAIN-001`、`MVP-STAGING-001`、`MVP-EGRESS-001` 与四个维护清理任务已关闭；`MVP-001` 内部轮换通过但因外部凭据缺失而 `BLOCKED`，MVP-002～MVP-009 保持 `BACKLOG`。
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
- MVP-001 当前 revision：[`../records/implementation/IR-MVP-001-20260921-R01.md`](../records/implementation/IR-MVP-001-20260921-R01.md)、[`../reports/tests/TR-MVP-001-20260921-R01.md`](../reports/tests/TR-MVP-001-20260921-R01.md)、[`../reports/reviews/RR-MVP-001-20260921-R01.md`](../reports/reviews/RR-MVP-001-20260921-R01.md)；低敏机器证据见 [`../../release/evidence/staging/crm-staging-credential-rotation-20260921.json`](../../release/evidence/staging/crm-staging-credential-rotation-20260921.json)。
- MVP-EGRESS-001 staging 定稿 R02：[`../records/implementation/IR-MVP-EGRESS-001-20260923-R02.md`](../records/implementation/IR-MVP-EGRESS-001-20260923-R02.md)、[`../reports/tests/TR-MVP-EGRESS-001-20260923-R02.md`](../reports/tests/TR-MVP-EGRESS-001-20260923-R02.md)、[`../reports/reviews/RR-MVP-EGRESS-001-20260923-R02.md`](../reports/reviews/RR-MVP-EGRESS-001-20260923-R02.md)；低敏机器证据见 [`../../release/evidence/staging/crm-staging-tiktok-egress-20260923.json`](../../release/evidence/staging/crm-staging-tiktok-egress-20260923.json)。R01 为历史预部署记录，不再代表 live 结果；派生索引从 `main` 已合并源记录重建为 `CURRENT`。
- 发布基线与低敏机器证据：[`../../release/`](../../release/)。
- 目录卫生：`frontend/` 空缓存树与 `.test-tmp/` 零字节测试残留已移出活动根并进入 `.maintenance/` 持久隔离；`CLEANUP-20260916-001` 状态为 `VERIFIED_UNUSED`，从实际隔离时间起保留满 7 天后，最早永久删除时间为 2026-09-23T14:00:00+08:00。
- `CLEANUP-20260916-002` 已将主 checkout 中唯一的旧 `src/backend/tests/` pytest 缓存隔离到 `.maintenance/`，状态为 `VERIFIED_UNUSED`，最早永久删除时间为 2026-09-23T18:05:00+08:00，恢复方法和摘要见 [`../operations/cleanup/CLEANUP-20260916-002.md`](../operations/cleanup/CLEANUP-20260916-002.md)。
- `CLEANUP-20260921-003` 已把入口服务器 root 家目录中的 staging 备份迁入 `/var/backups/crm-staging`，把两个退役生成物迁入 `/var/lib/crm-staging/quarantine/CLEANUP-20260921-003/root-home/`；状态为 `QUARANTINED`，备份永久保留，隔离物最早复核时间为 2026-09-28T14:37:17+08:00，详见 [`../operations/cleanup/CLEANUP-20260921-003.md`](../operations/cleanup/CLEANUP-20260921-003.md)。
- `CLEANUP-20260921-004` 已通过 PR #32 合入 `main`：截图中的六个已合并本地 worktree 和对应本地短期分支已删除，共移除 2,749,219,080 B；`origin/main`、主 checkout 的本地领先提交与未跟踪 `.superpowers/` 均未改变，详见 [`../operations/cleanup/CLEANUP-20260921-004.md`](../operations/cleanup/CLEANUP-20260921-004.md)。
- TEST-001 验证保留了已忽略的 `src/tests/.artifacts/task6-4cd6664-temp/`，仓库外受控验证工作区也保留 candidate-scoped archive、override 和 temp。它们是已知可重建临时材料，但未建立独立清理任务/批次，未移动或删除，因此目录卫生不标记 `CLEAN`。

## 阻塞、决定与风险

- G0～G6 尚未全部取得真实环境证据，G8 保持阻塞；工程实现、Mock 或历史确定性测试不能替代生产验收。
- `MVP-001` 的内部凭据轮换已通过；解除任务阻塞仍需用户提供 TikTok App Key、Service ID、App Secret、Webhook Secret 和 DeepSeek API Key，并经服务器受限通道注入。固定出口已在 live staging 观测为 `38.55.145.52`；Partner Center 白名单仍需用户按平台流程确认。
- `AUTO_REPLY_ENABLED=false` 与 `REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED=false` 继续作为安全基线。
- staging DNS/TLS、`18080 → 18081` 反向隧道和 Rootless CRM 当前可用；临时 registry 代理已撤除。业务机 GHCR CDN 拉取反复中断，新镜像升级必须另行取得实际下载、摘要和部署验证，不得继承本次 staging 豁免。
- 入口服务器仍有一个失败且非持久的 `crm-external-image-prepare.service` transient unit，引用已不存在的退役脚本；本清理批次未扩大范围修改它，当前不监听端口且不影响 staging。
- TEST-001 独立审查 Critical 0、Important 0；非阻塞 Minor 建议是未来在 `src/tests/README.md` 说明 sibling-path 聚焦 pytest 需要 `-c pyproject.toml`，本候选未因此改变。
- TEST-001 仍保留两个既有前端 lint warning、两个 Python 弃用 warning 与一个 npm high severity audit 项；依赖升级另立任务，ignored temp 清理须遵守独立清理治理。
- 本轮成功恢复点为 `/var/backups/crm-staging/secrets/20260921T080357Z/`；两份失败尝试恢复副本仍为 root-only 0600，清理必须另立 `MAINT-CLEANUP-*`，当前不得删除。
- Git、文件、Codex UI 与 GitHub 不是原子事务；每一步必须查重、执行、复核并保留恢复点。

## 最多三个下一动作

1. 用户确认 TikTok Partner Center 固定出口白名单 `38.55.145.52`，准备并受限注入 TikTok 与 DeepSeek 外部凭据，解除 `MVP-001` 阻塞。
2. 凭据就绪后启动 `MVP-002` 的真实店铺 OAuth、Scope、Token 生命周期和只读验收；真实开关在门禁通过前继续关闭。
3. 业务机 GHCR 下载恢复时重新验证新镜像摘要；在 G0～G8 分项门禁齐备前，production 继续关闭。
