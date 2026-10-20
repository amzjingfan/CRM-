---
record_id: TR-MVP-WORKSPACE-EXPERIENCE-001-20261020-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-WORKSPACE-EXPERIENCE-001
tested_sha: 1aff6dfd4302c64c9e1c7394f1ebd9898b3652c4
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-EXPERIENCE-001-20261020-R01.md
requirement_ids: [MVP-WORKSPACE-EXPERIENCE-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
environment: Windows 11, Python 3.11.15, Node 24.19.0, isolated PostgreSQL Compose test profile, local production Next.js and headless Chrome with synthetic API
created_at: 2026-10-20T05:03:00Z
updated_at: 2026-10-20T05:19:29Z
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

集中式测试位于 `src/tests/backend/`、`src/tests/integration/postgres/` 和 `src/tests/frontend/`。浏览器测试拦截 `/v1/` 并只用合成数据；后端完整回归使用 Compose `test` profile 的隔离 PostgreSQL，迁移到 `025_workspace_actions` 后测试并清理。没有调用真实 TikTok 写接口。

# 命令和逐项结果

- 源码候选 `eaef1e59b437ed2bfbc62ac8da2d072d2ee45165` 与 PR #463 squash 合入 `1aff6dfd4302c64c9e1c7394f1ebd9898b3652c4` 的文件树 diff 为空。以下完整验证已在最终合并 SHA 上重跑。
- `uv lock --check`、`uv run ruff check . ../tests/backend ../tests/integration/postgres`、`uv run ruff format --check . ../tests/backend ../tests/integration/postgres`、`uv run mypy app scripts` 均通过；源码候选的 `git diff --check BASE_SHA..HEAD` 通过。增量文件及新增行的私钥/Token 模式扫描未命中。
- 前端 `npm run test`：47/47；`npm run typecheck`：通过；`npm run lint`：0 错误、2 条既有内部跳转警告；`npm run build`：通过。启动本地生产 Next.js 后 `/workspace` 返回 200，以 `UI_CACHE_EXPECT_PRODUCTION=1` 执行 `npm run test:ui`：34/34，通过。
- 定向 `uv run pytest -c pyproject.toml ../tests/backend/domain/test_workspace_conversation_actions.py -q`：9/9，通过。
- 合并 SHA 上 `run-postgres-integration-tests.ps1`：迁移到 `025_workspace_actions`、2216 passed、3 skipped、2 warnings，隔离 PostgreSQL 服务已清理；源码候选无并发构建的同命令复测也为 2216 passed、3 skipped、2 warnings。更早一轮源码候选为 2215 passed、1 failed、3 skipped，唯一失败为既有 `test_canary_observes_response_headers_through_the_real_sdk_without_network` 的 MockTransport 未收到请求；该测试单独复测 1/1 通过。失败成因未证实，不能把首轮描述成通过。

# REQ/AC 或门禁与证据映射

AC-01：后端未读/只读同步行为测试与浏览器滚动、未读、历史位置测试。AC-02：浏览器 AI 建议进入可编辑草稿且真实发送计数保持零。AC-03：隔离 PostgreSQL 持久化过滤、同店权限行为测试与浏览器星标/转交/关闭/重开测试。AC-04：后端越权、CSRF、重复设置审计、关闭会话拒绝发送和转交及未结清消息拒绝关闭测试。AC-05：上述本地验证；不计 GitHub Actions、staging 或真实买家现场验证。

# 缺陷、未执行项与残余风险

Windows 缺少 POSIX bash，3 项进程等待器测试按既有规则跳过；现有 Starlette/httpx 和 argon2 各 1 条弃用警告。首次 canary 失败原因未证实，单项及后续两轮完整复测均通过，保留为间歇性风险。PR #463 的两项 GitHub Actions 在零步骤时失败，未计为 CI 验证。没有执行生产/现网数据操作、实际 TikTok 外发、staging 部署或迁移 downgrade。

# 结论和复测条件

`PASS`：AC-01～AC-05 的本地实现验收通过。部署前仍需按环境门禁验证迁移、备份/回退和真实授权店铺的只读页面；本 TR 不构成 staging 或 production 放行。
