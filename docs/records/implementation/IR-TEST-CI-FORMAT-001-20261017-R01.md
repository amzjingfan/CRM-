---
record_id: IR-TEST-CI-FORMAT-001-20261017-R01
record_type: implementation
revision: R01
status: FINAL
task_id: TEST-CI-FORMAT-001
base_sha: 1abc9d30bdcdb5284c54085c75802f8cb2ecc6b2
final_sha: 1cda61d171566aed91976ef02788b6653dc6d7b9
requirement_ids: [TEST-CI-FORMAT-001]
acceptance_ids: [AC-01, AC-02]
test_record: docs/reports/tests/TR-TEST-CI-FORMAT-001-20261017-R01.md
review_record: null
created_at: 2026-10-17T10:23:22+08:00
updated_at: 2026-10-17T10:23:22+08:00
supersedes: null
---

# 恢复既有测试文件的格式门禁

用户确认在独立 `fix/*` 分支从 main `1abc9d3` 修复全量 Ruff 格式检查。用仓库 `uv.lock` 锁定的 Ruff 0.16.3 仅格式化 `test_manual_staging_gate.py`、`test_manual_staging_source_policy.py`、`test_sse_staging_vectorization.py` 三个既有测试文件。未修改断言、应用代码、部署配置或 GitHub 工作流；改动前后 Python AST 完全一致。源码回滚为撤销本次纯排版提交。

PR 的 GitHub 作业因账户付款/支出上限问题在首个步骤前被平台拒绝，属于仓库外计费状态；本次不修改用户账户或费用设置。待账户状态恢复后才能取得真实自动 CI 结果，再决定合并。本修复不部署 staging、不调用模型。
