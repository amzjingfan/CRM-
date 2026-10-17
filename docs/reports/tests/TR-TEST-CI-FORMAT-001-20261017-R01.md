---
record_id: TR-TEST-CI-FORMAT-001-20261017-R01
record_type: test
revision: R01
status: PARTIAL
task_id: TEST-CI-FORMAT-001
tested_sha: 1cda61d171566aed91976ef02788b6653dc6d7b9
implementation_record: docs/records/implementation/IR-TEST-CI-FORMAT-001-20261017-R01.md
requirement_ids: [TEST-CI-FORMAT-001]
acceptance_ids: [AC-01, AC-02]
environment: local Windows PowerShell; Python 3.11.15; locked Ruff 0.16.3
created_at: 2026-10-17T10:23:22+08:00
updated_at: 2026-10-17T10:23:22+08:00
supersedes: null
---

# 格式修复验证

`TEST_LAYOUT=centralized`。修复前以 Ruff 0.16.3 对三个既有测试运行 `format --check`，确认为 3 files would be reformatted（退出码 1）。对且仅对这三个文件执行 `ruff format` 后：

- `ruff check . ../tests/backend ../tests/integration/postgres`：All checks passed。
- `ruff format --check . ../tests/backend ../tests/integration/postgres`：299 files already formatted，退出码 0。
- 从 `src/backend` 对上述三个测试文件运行 `python -m pytest --rootdir . -c pyproject.toml -q`：43 passed。
- 用 Python `ast.dump(ast.parse(...), include_attributes=False)` 比较 `HEAD` 原文与格式化后文件：`AST_EQUAL=True`。
- `git diff --check`：通过。

本地测试证明排版和这三组测试行为未变。PR 的自动 CI 尚未实际执行：GitHub 检查注解为近期账户付款失败或 Actions 支出上限不足，作业 `steps=[]`。账户恢复后的真实 CI 及合并仍待完成；不将本地结果冒充 CI 通过。
