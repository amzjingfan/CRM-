---
record_id: TR-MVP-AUTH-SUPERVISOR-KNOWLEDGE-001-20261103-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-AUTH-SUPERVISOR-KNOWLEDGE-001
tested_sha: b558a4a8c9c137e56777a64006e51b7bec4ef196
implementation_record: docs/records/implementation/IR-MVP-AUTH-SUPERVISOR-KNOWLEDGE-001-20261103-R01.md
requirement_ids: [SUPERVISOR_KNOWLEDGE_MANAGE]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: Windows PowerShell; Python 3.11.15; uv 0.12.3; isolated Docker PostgreSQL/pgvector test profile
created_at: 2026-11-03T04:45:59Z
updated_at: 2026-11-03T06:15:03Z
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT: centralized`。在当前隔离 worktree 和仓库规定的 `src/tests/` 测试根执行。无真实 TikTok、买家消息或 production 操作。

# 命令和逐项结果

- 先运行新增权限与知识写入测试：分别观测到 3 项和 2 项预期失败；实现后 `5 passed`。
- `uv run pytest -c pyproject.toml ../tests/backend/knowledge_base ../tests/backend/auth_security -q`：`126 passed`。
- `uv run pytest -c pyproject.toml ../tests/backend -q`：修正受影响测试替身后 `3300 passed, 4 skipped`。
- `uv run ruff check . ../tests/backend ../tests/integration/postgres`：通过；`uv run ruff format --check . ../tests/backend ../tests/integration/postgres`：通过；`uv run mypy app scripts`：`321 source files` 通过。
- 仓库 `run-postgres-integration-tests.ps1` 首次运行：迁移至 `051` 成功，`3657 passed, 5 skipped`；新增 PostgreSQL 权限用例单独复跑：`1 passed`。
- 合并前候选 `5e7ac8e46241e0424bfde6f0c2f70e2c38c21324`：仓库 `run-postgres-integration-tests.ps1` 执行 `051` 在线迁移及完整后端/隔离 PostgreSQL 回归，`3658 passed, 5 skipped, 2 warnings`，退出码 0；临时容器停止并删除。
- 合入 `origin/main` 最新三个提交（至 `3a37611d`）并解决任务/证据索引冲突后复测：知识库、认证和受影响 TikTok 用例 `224 passed`；Ruff 与 mypy 通过；仓库 `run-postgres-integration-tests.ps1` 再次执行 `051` 在线迁移和完整隔离回归，`3684 passed, 5 skipped, 2 warnings`，退出码 0；临时 PostgreSQL 容器已删除。

# REQ/AC 或门禁与证据映射

- AC-01/02：主管、部门成员撤销与多角色混合的权限单测及 PostgreSQL 实库用例。
- AC-03：知识分类创建/更新越权用例，知识库及认证回归。
- AC-04：Alembic 迁移至最新 head、格式/类型与全量后端测试。

# 缺陷、未执行项与残余风险

第一次直接调用 `uv run python -m pytest ../tests/backend` 因没有显式加载仓库 pytest 配置导致 31 项导入错误；改用 `-c pyproject.toml` 后完整执行。`alembic upgrade head --sql` 遇旧版 `010` 迁移要求在线查询而失败；实际隔离 PostgreSQL 在线升级成功。新增实库测试首次遗漏必填登录标识，修正合成数据后通过。未进行真实账号 UI 或 staging 部署验收。

# 结论和复测条件

本地验证通过。5 项跳过包含 POSIX bash 环境用例及缺少独立模型迁移条件的用例；真实 staging UI 与部署仍未执行。
