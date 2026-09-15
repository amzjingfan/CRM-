# 项目状态与恢复入口

本文件是跨 Codex 会话恢复项目所需的精简摘要，不复制 `../tasks/TASKS.md` 的任务状态、`../test-status.md` 的测试结论或 `../release-gates.md` 的门禁正文。恢复工作时先读本文件，再按链接读取事实源。

## 当前状态

```text
Project phase: ACTIVE
Governance tier: STANDARD
Repository identity: origin=ssh://git@ssh.github.com:443/CP11-gh/CRM.git
Primary branch: main
Working branch at this snapshot: docs/codex-standard-governance
Governance base SHA: e0592c29c2e9d4153ffbbbf43da9a7aa05c29207
CANDIDATE_SUBJECT_SHA: e0592c29c2e9d4153ffbbbf43da9a7aa05c29207
EVIDENCE_HEAD_SHA: READ_AT_GATE
Workspace hygiene: CLEAN
```

`CANDIDATE_SUBJECT_SHA` 是当前最后一个影响产品交付内容的已确认提交；本次治理分支只修改文档和协作规则。`EVIDENCE_HEAD_SHA` 必须在门禁或交接时从 Git 现场读取，不在仓库中自指回填。

## 权威入口

- 产品范围与验收：[`../product.md`](../product.md)
- 系统架构：[`../architecture.md`](../architecture.md)
- API 契约：[`../api.md`](../api.md)
- AI、RAG 与工具安全：[`../ai.md`](../ai.md)
- 唯一任务状态：[`../tasks/TASKS.md`](../tasks/TASKS.md)
- 开发与协作规范：[`../development.md`](../development.md)
- STANDARD 治理：[`../governance.md`](../governance.md)
- 测试策略：[`../quality/TEST-STRATEGY.md`](../quality/TEST-STRATEGY.md)
- 最新测试状态：[`../test-status.md`](../test-status.md)
- 部署边界：[`../deployment.md`](../deployment.md)
- 生产门禁：[`../release-gates.md`](../release-gates.md)

## 里程碑与活动任务

- 当前里程碑：关闭 TikTok 人工辅助 v0.1 的 G0～G6 真实环境门禁。
- `TASKS.md` 当前没有 `READY`、`DOING` 或 `VERIFYING` 业务任务；MVP-001～MVP-009 均为 `BACKLOG`。
- v0.1 之后的 Shopee/Amazon、生产翻译、公开自动回复、主动营销和高风险写入保持 `BACKLOG`，不得提前描述为已放行。

## 记录、索引与证据

- 当前格式的 IR/TR/RR：`NOT_YET_CREATED`。历史实施与测试事实仍由 Git 历史、`test-status.md` 和 `release/evidence/` 保留，不伪造迁移记录。
- `IMPLEMENTATION-INDEX`、`TEST-INDEX`、`REVIEW-INDEX`：`NOT_YET_CREATED`；首次产生对应真实源记录时创建。
- 发布基线与低敏机器证据：[`../../release/`](../../release/)。
- 目录卫生：在治理基线启动盘点中未发现未跟踪/忽略对象或重解析点，状态为 `CLEAN`；当前没有活动清理任务或批次。

## 阻塞、决定与风险

- G0～G6 尚未全部取得真实环境证据，G8 保持阻塞；工程实现、Mock 或历史确定性测试不能替代生产验收。
- `AUTO_REPLY_ENABLED=false` 与 `REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED=false` 继续作为安全基线。
- 本地 `main` 在治理启动时相对 `origin/main` 领先 132 个提交。任何远端修改或推送前必须重新读取远端状态、确认目标与历史关系，不得从旧快照推断。
- Git、文件、Codex UI 与 GitHub 不是原子事务；每一步必须查重、执行、复核并保留恢复点。

## 最多三个下一动作

1. 复核治理分支差异和静态验证结果，再由用户决定是否推送并创建 Pull Request。
2. 为 MVP-001 补齐精确环境、资源、授权和验收步骤，满足后将其从 `BACKLOG` 转为 `READY`。
3. MVP-001 完成后按依赖关系准备 MVP-002、MVP-005 与 MVP-008，避免并行触碰同一凭证或环境状态。

