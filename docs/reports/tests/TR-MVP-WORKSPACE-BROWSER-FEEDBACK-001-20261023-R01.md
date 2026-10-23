---
record_id: TR-MVP-WORKSPACE-BROWSER-FEEDBACK-001-20261023-R01
record_type: test
revision: R01
status: PARTIAL
task_id: MVP-WORKSPACE-BROWSER-FEEDBACK-001
tested_sha: 6dac69e7c205252fcefa7e44720bdd2b9ae9bdec
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-BROWSER-FEEDBACK-001-20261023-R01.md
requirement_ids: [MVP-WORKSPACE-BROWSER-FEEDBACK-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05, AC-06]
environment: Windows 11, Python 3.11.15, Node.js Next.js 16.4.2, isolated worktree, synthetic browser API fixtures, PYTHONUTF8=1
created_at: 2026-10-23T09:29:46Z
updated_at: 2026-10-23T09:29:46Z
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT: centralized`。后端行为测试位于 `src/tests/backend/`，前端契约与浏览器测试位于 `src/tests/frontend/`。浏览器使用本地生产 Next 服务与合成 API fixture；未向真实 TikTok 买家发送消息。

# 命令和逐项结果

- `PYTHONUTF8=1 uv run pytest -q`：2342 passed、41 skipped、2 个第三方弃用警告，0 failed。首次未设置 UTF-8 时 2 个 Windows 环境相关失败；同项与全量均重跑通过。
- `uv run ruff check . ../tests/backend ../tests/integration/postgres`、`uv run ruff format --check . ../tests/backend ../tests/integration/postgres`：通过，371 文件格式通过。
- `uv run mypy app scripts`：通过，208 文件。
- `npm run lint`：0 error、5 条既有 warning；`npm run typecheck`：通过；`npm run build`：通过。
- 提交后 `npm test`：48/48 通过；提交后 `PYTHONUTF8=1 uv run pytest -c pyproject.toml ../tests/backend/domain/test_workspace_conversation_actions.py -q`：10/10 通过。
- 提交后 `node --test ../tests/frontend/browser/reception-management.test.mjs ../tests/frontend/browser/workspace-experience.test.mjs`：47/47 通过。首次未启动 3101 测试服务时连接拒绝；服务启动后复测通过。
- `git diff --check`：无空白错误。

# REQ/AC 与证据映射

AC-01 由接待管理浏览器导航测试覆盖；AC-02/03/04/05 由工作台浏览器测试覆盖；AC-05 服务鉴权、持久化与审计由后端行为测试覆盖；AC-06 由本报告逐项命令和源码审查覆盖。

# 缺陷、未执行项与残余风险

未做 staging 已登录态验收，未部署；GitHub Actions 门禁和 PR 合并状态需在 PR 创建后读取，不能把本地结果当作 CI。媒体发送另立受控任务。外部平台发送与真实店铺数据修改均未执行。

# 结论和复测条件

本地受影响行为和全仓后端、前端静态门禁通过；TR 为 `PARTIAL`，待 PR 门禁和 staging 验收后更新新修订。任何 subject 内容变更需重跑受影响验证。
