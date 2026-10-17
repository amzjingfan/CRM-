---
record_id: TR-TEST-CI-FORMAT-001-20261017-R01
record_type: test
revision: R01
status: PASS
task_id: TEST-CI-FORMAT-001
tested_sha: 1cda61d171566aed91976ef02788b6653dc6d7b9
implementation_record: docs/records/implementation/IR-TEST-CI-FORMAT-001-20261017-R01.md
requirement_ids: [TEST-CI-FORMAT-001]
acceptance_ids: [AC-01, AC-02]
environment: local Windows PowerShell; Python 3.11.15; locked Ruff 0.16.3
created_at: 2026-10-17T10:23:22+08:00
updated_at: 2026-10-17T10:40:00+08:00
supersedes: null
---

# 格式修复验证

`TEST_LAYOUT=centralized`。修复前以 Ruff 0.16.3 对三个既有测试运行 `format --check`，确认为 3 files would be reformatted（退出码 1）。对且仅对这三个文件执行 `ruff format` 后：

- `ruff check . ../tests/backend ../tests/integration/postgres`：All checks passed。
- `ruff format --check . ../tests/backend ../tests/integration/postgres`：299 files already formatted，退出码 0。
- 从 `src/backend` 对上述三个测试文件运行 `python -m pytest --rootdir . -c pyproject.toml -q`：43 passed。
- 用 Python `ast.dump(ast.parse(...), include_attributes=False)` 比较 `HEAD` 原文与格式化后文件：`AST_EQUAL=True`。
- `git diff --check`：通过。

本地测试证明排版和这三组测试行为未变；2026-10-17 再次从格式修复分支运行全量 Ruff lint/format 与 43 项受影响测试，通过。PR #283 已 squash 合入 main `2da8e1721590a23ca0fd57b371a06bc83d62ecc4`。GitHub Actions 作业因账户计费在首步前失败，不记为 CI 通过；按用户明确决定，本次使用上述本地等价检查完成合并。
