# 项目状态与恢复入口

本文件是跨 Codex 会话恢复项目所需的精简摘要，不复制 `../tasks/TASKS.md` 的任务状态、`../quality/TEST-STATUS.md` 的测试结论或 `../operations/RELEASE-GATES.md` 的门禁正文。恢复工作时先读本文件，再按链接读取事实源。

## 当前状态

```text
Project phase: ACTIVE
Governance tier: STANDARD
Repository identity: origin=ssh://git@ssh.github.com:443/CP11-gh/CRM.git
Primary branch: main
Working branch at this snapshot: feature/split-ingress-staging-20260919
Governance base SHA: 98414c2b51bfd403365aa6c72e0585f045d4a26a
CANDIDATE_SUBJECT_SHA: WORKTREE
EVIDENCE_HEAD_SHA: READ_AT_GATE
Workspace hygiene: ATTENTION — CLEANUP-20260916-001/002 quarantines and other TEST-001 temporary material remain under retention or require a separate cleanup batch
```

当前工程根为 `src/`，测试资产集中在 `src/tests/`。`MVP-STAGING-001` 正在隔离 worktree 实现双服务器 split-ingress：新服务器 `38.55.145.52` 只承担宝塔 Nginx/TLS 和回环 `18080`，旧服务器 `192.168.110.210` 的 `crmdeploy` Rootless CRM 只发布回环 `18081`。仓库 runtime、受限隧道、宝塔 vhost、失败关闭门禁和测试已实现，任务处于 `VERIFYING`；远端 main、镜像和两台服务器尚未按本候选变更。`EVIDENCE_HEAD_SHA` 必须在门禁或交接时从 Git 现场读取，不在仓库中自指回填。

`MVP-DOMAIN-001` 已在候选 `10428b4501fd470a5a671676edcdc00e75180844` 将 staging/production 的仓库内固定域名统一为 `staging.overselfx.com` / `www.overselfx.com`，通过完整后端回归与安全契约审查，并已快进合并到本地 `main`；任务为 `DONE`，尚未推送远端或执行真实 DNS/TLS/Partner Center 变更。

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
- `REPO-001`、`TEST-001`、`MVP-DOMAIN-001` 与两个维护清理任务为 `DONE`；`MVP-STAGING-001` 为 `VERIFYING`，MVP-001～MVP-009 仍为 `BACKLOG`。
- v0.1 之后的 Shopee/Amazon、生产翻译、公开自动回复、主动营销和高风险写入保持 `BACKLOG`，不得提前描述为已放行。

## 记录、索引与证据

- REPO-001 实施记录：[`../records/implementation/IR-REPO-001-20260916-R01.md`](../records/implementation/IR-REPO-001-20260916-R01.md)。
- REPO-001 测试记录：[`../reports/tests/TR-REPO-001-20260916-R01.md`](../reports/tests/TR-REPO-001-20260916-R01.md)。
- REPO-001 审查记录：[`../reports/reviews/RR-REPO-001-20260916-R01.md`](../reports/reviews/RR-REPO-001-20260916-R01.md)。三个派生索引状态为 `CANDIDATE_VIEW`；从本地主分支读取时重建为 `CURRENT`。
- TEST-001 实施记录：[`../records/implementation/IR-TEST-001-20260916-R01.md`](../records/implementation/IR-TEST-001-20260916-R01.md)。
- TEST-001 测试记录：[`../reports/tests/TR-TEST-001-20260916-R01.md`](../reports/tests/TR-TEST-001-20260916-R01.md)。
- TEST-001 审查记录：[`../reports/reviews/RR-TEST-001-20260916-R01.md`](../reports/reviews/RR-TEST-001-20260916-R01.md)。三个派生索引已从全部源记录重建为 `CANDIDATE_VIEW`；从本地主分支读取时重建为 `CURRENT`。
- MVP-DOMAIN-001 实施、测试与审查记录：[`../records/implementation/IR-MVP-DOMAIN-001-20260917-R01.md`](../records/implementation/IR-MVP-DOMAIN-001-20260917-R01.md)、[`../reports/tests/TR-MVP-DOMAIN-001-20260917-R01.md`](../reports/tests/TR-MVP-DOMAIN-001-20260917-R01.md)、[`../reports/reviews/RR-MVP-DOMAIN-001-20260917-R01.md`](../reports/reviews/RR-MVP-DOMAIN-001-20260917-R01.md)。三个派生索引从本地 `main` 读取时为 `CURRENT`。
- 发布基线与低敏机器证据：[`../../release/`](../../release/)。
- 目录卫生：`frontend/` 空缓存树与 `.test-tmp/` 零字节测试残留已移出活动根并进入 `.maintenance/` 持久隔离；`CLEANUP-20260916-001` 状态为 `VERIFIED_UNUSED`，从实际隔离时间起保留满 7 天后，最早永久删除时间为 2026-09-23T14:00:00+08:00。
- `CLEANUP-20260916-002` 已将主 checkout 中唯一的旧 `src/backend/tests/` pytest 缓存隔离到 `.maintenance/`，状态为 `VERIFIED_UNUSED`，最早永久删除时间为 2026-09-23T18:05:00+08:00，恢复方法和摘要见 [`../operations/cleanup/CLEANUP-20260916-002.md`](../operations/cleanup/CLEANUP-20260916-002.md)。
- TEST-001 验证保留了已忽略的 `src/tests/.artifacts/task6-4cd6664-temp/`，仓库外受控验证工作区也保留 candidate-scoped archive、override 和 temp。它们是已知可重建临时材料，但未建立独立清理任务/批次，未移动或删除，因此目录卫生不标记 `CLEAN`。

## 阻塞、决定与风险

- G0～G6 尚未全部取得真实环境证据，G8 保持阻塞；工程实现、Mock 或历史确定性测试不能替代生产验收。
- `AUTO_REPLY_ENABLED=false` 与 `REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED=false` 继续作为安全基线。
- staging DNS A 已指向 `38.55.145.52`，但当前证书 SAN 不匹配，CRM 尚未部署，已有反向隧道仍错误指向 GitLab `10080`；在现场切换、公开健康和公司负载复核完成前不得宣称 staging 可用。
- TEST-001 独立审查 Critical 0、Important 0；非阻塞 Minor 建议是未来在 `src/tests/README.md` 说明 sibling-path 聚焦 pytest 需要 `-c pyproject.toml`，本候选未因此改变。
- TEST-001 仍保留两个既有前端 lint warning、两个 Python 弃用 warning 与一个 npm high severity audit 项；依赖升级另立任务，ignored temp 清理须遵守独立清理治理。
- 本地 `main` 已完成 TEST-001 快进合并且显著领先 `origin/main`；本任务未修改远端。任何远端修改或推送前必须重新读取远端状态、确认目标与历史关系，不得从旧快照推断。
- Git、文件、Codex UI 与 GitHub 不是原子事务；每一步必须查重、执行、复核并保留恢复点。

## 最多三个下一动作

1. 完成 `MVP-STAGING-001` 本地全量验证与审查，通过 PR 合入远端 main，并发布与 main SHA 绑定的三个不可变镜像。
2. 在保护公司负载和其他 vhost 的前提下，把公网入口置为 `503`，切换隧道到 `18081`，部署 Rootless CRM并通过宝塔签发正确证书。
3. 完成公网健康、隧道恢复和前后基线复核，定稿 IR/TR/RR；TikTok G1～G6 与 production 继续保持关闭。
