---
record_id: TR-MVP-DEPARTMENT-AUTO-ASSIGN-001-20261030-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-DEPARTMENT-AUTO-ASSIGN-001
tested_sha: dcc2ada1eb3290c64857b4b5e5e0328402f4281d
implementation_record: docs/records/implementation/IR-MVP-DEPARTMENT-AUTO-ASSIGN-001-20261030-R01.md
requirement_ids: [REQ-01, REQ-02, REQ-03, REQ-04]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: Windows local; isolated PostgreSQL Docker on 127.0.0.1:5434; synthetic data; TEST_LAYOUT=centralized
created_at: 2026-10-30T01:47:04+08:00
updated_at: 2026-10-30T01:47:04+08:00
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

测试集中于 `src/tests/`，使用专属合成 PostgreSQL；没有真实买家发送、退款或生产操作。最终 subject SHA 的末次提交只改前端告警和浏览器用例，后端树与后端全量运行时相同。

# 命令和逐项结果

- `uv run alembic upgrade head`、降到 `043_logistics_updates`、再升级到 `044_reception_assignment`：通过。
- `uv run pytest -q --tb=short`：2730 passed、3 skipped、0 failed；2 项既有警告，约 248 秒。
- `uv run ruff check app ../tests/backend ../tests/integration/postgres`、`uv run ruff format --check app ../tests/backend ../tests/integration/postgres`、`uv run mypy app`：通过；450 个文件格式通过，mypy 检查 250 个文件。
- `npm test`：55/55；`npm run typecheck`：通过；`npm run lint`：0 error、8 项既有 warning；`npm run build -- --webpack`：通过。
- 前端完整浏览器回归：162 项中 161 passed、1 skipped、0 failed。最终前端告警用例也单独通过。
- `git diff origin/main --check`：通过；主线为分支祖先，最终候选 PR diff 限于本任务相关 47 个文件。

# REQ/AC 或门禁与证据映射

- AC-01：逐店授权、普通客服本人会话转交、跨店/他人归属拒绝，由 store-scoped 权限及 PostgreSQL 归属测试覆盖。
- AC-02：默认关闭、名单、在线心跳、容量与队列，由规则、集成和前端浏览器回归覆盖。
- AC-03：重复/并发入站、人工归属优先、近期人工服务与负载选择、无候选失败原因、Webhook/同步同路径，由派单 PostgreSQL/领域测试覆盖；零自动外发。
- AC-04：后端全量、前端契约/浏览器、静态/类型/构建、迁移均通过；IR/TR/RR 已齐备。

# 缺陷、未执行项与残余风险

AC-05 是合并后的 staging 发布验收，不在本地 PASS 结论内。未执行真实入站派单和真实客服登录验收。GitHub PR CI 在创建 PR 后单独核验；本记录不预称 CI 结果。

# 结论和复测条件

本地候选 AC-01 至 AC-04 通过。若目标主线变化影响接待模块或最终候选源码再改，重跑受影响验证；部署需另行批准。
