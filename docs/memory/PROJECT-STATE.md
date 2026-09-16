# 项目状态与恢复入口

本文件是跨 Codex 会话恢复项目所需的精简摘要，不复制 `../tasks/TASKS.md` 的任务状态、`../quality/TEST-STATUS.md` 的测试结论或 `../operations/RELEASE-GATES.md` 的门禁正文。恢复工作时先读本文件，再按链接读取事实源。

## 当前状态

```text
Project phase: ACTIVE
Governance tier: STANDARD
Repository identity: origin=ssh://git@ssh.github.com:443/CP11-gh/CRM.git
Primary branch: main
Working branch at this snapshot: codex/src-layout-migration
Governance base SHA: 6b726a32502a364040ccf0a0b251a320d379ee7d
CANDIDATE_SUBJECT_SHA: PENDING_VERIFICATION
EVIDENCE_HEAD_SHA: READ_AT_GATE
Workspace hygiene: CLEAN
```

当前工程根已迁移到 `src/`，`CANDIDATE_SUBJECT_SHA` 在完整质量、镜像构建和实际启动验证结束后确定。`EVIDENCE_HEAD_SHA` 必须在门禁或交接时从 Git 现场读取，不在仓库中自指回填。

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
- `REPO-001` 正在 `VERIFYING`，负责 `src/` 工程根迁移与启动证明；MVP-001～MVP-009 均为 `BACKLOG`。
- v0.1 之后的 Shopee/Amazon、生产翻译、公开自动回复、主动营销和高风险写入保持 `BACKLOG`，不得提前描述为已放行。

## 记录、索引与证据

- REPO-001 的 IR/TR/RR 与三个首次索引将在本次验证完成后写入，当前不得提前标记通过。
- 发布基线与低敏机器证据：[`../../release/`](../../release/)。
- 目录卫生：在治理基线启动盘点中未发现未跟踪/忽略对象或重解析点，状态为 `CLEAN`；当前没有活动清理任务或批次。

## 阻塞、决定与风险

- G0～G6 尚未全部取得真实环境证据，G8 保持阻塞；工程实现、Mock 或历史确定性测试不能替代生产验收。
- `AUTO_REPLY_ENABLED=false` 与 `REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED=false` 继续作为安全基线。
- 本地 `main` 在治理启动时相对 `origin/main` 领先 132 个提交。任何远端修改或推送前必须重新读取远端状态、确认目标与历史关系，不得从旧快照推断。
- Git、文件、Codex UI 与 GitHub 不是原子事务；每一步必须查重、执行、复核并保留恢复点。

## 最多三个下一动作

1. 完成 REPO-001 的全量质量、四镜像构建与隔离启动验证并写入 IR/TR/RR。
2. 将已验证分支按用户授权合并到本地 `main`，不修改远端。
3. 合并后复核新路径与启动冒烟，再准备 MVP-001 的精确环境、资源、授权和验收步骤。
