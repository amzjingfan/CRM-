---
record_id: TR-MVP-WORKSPACE-TRACKING-TIMELINE-001-20261022-R01
record_type: test
revision: R01
status: PARTIAL
task_id: MVP-WORKSPACE-TRACKING-TIMELINE-001
tested_sha: 475f585c10fa543b0d3550a4426f97f935cf6786
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-TRACKING-TIMELINE-001-20261022-R01.md
requirement_ids: [MVP-WORKSPACE-TRACKING-TIMELINE-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: Windows local worktree; CPython 3.11; Node 22; merged-main Linux rootless staging; deployed-page synthetic browser
created_at: 2026-10-22T02:20:11Z
updated_at: 2026-10-22T02:40:47Z
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT=centralized`。后端测试位于 `src/tests/backend/`，前端契约与合成浏览器测试位于 `src/tests/frontend/`。浏览器拦截全部 `/v1/` 请求，不使用真实店铺或 TikTok 数据。

# 命令与结果

- `uv run ruff check` 受影响后端文件：通过；`uv run ruff format --check`：通过；`uv run mypy app/workspace/sidebar.py app/workspace/router.py app/workspace/service.py`：通过。
- `uv run python -m pytest ../tests/backend/domain/test_workspace_sidebar_live_orders.py ../tests/backend/domain/test_workspace_translation.py`：23 passed；另含平台适配器的相关回归：70 passed。最终 subject 上全量 `uv run python -m pytest -q`：2227 passed、29 skipped、2 条既有依赖弃用 warning。
- `npm run lint`：0 errors、4 条既有 warning；`npm run typecheck`、`npm run build`：通过；`npm run test`：47 passed。
- 开发浏览器 `node --test ../tests/frontend/browser/workspace-experience.test.mjs`：26 passed；生产构建浏览器同文件：26 passed；最终 subject 再跑物流两项：2 passed。验证全部节点、复制文本、PNG 头、跨境包裹切换、节点翻译切回原文及零外发。
- `git diff --check`：通过。未修改迁移、依赖锁或真实平台写入范围。
- 源码 PR #506 合并后，`main=1f74077a56136cbd705d35251a3afd76849f82b6`，与 subject 的前后端和 Dockerfile 构建输入相同。本机按 main SHA 构建前后端 `linux/amd64` 镜像；源码 bundle `2177e0cf…ddacdc27de`、双镜像 OCI 归档 `e82edf0d…3291ab` 在 staging 逐字节哈希相同，干净 Git checkout 的 HEAD 与远端 main 精确一致。两个镜像经主机现有 GHCR 凭据发布并核对不可变摘要与 OCI revision。
- 私有恢复点：原前后端/检索三摘要只读核对、单店人工发送与翻译仍启用、`0600` PostgreSQL `pg_dump -Fc` 备份 `pg_restore -l` 可读。六摘要预取 `passed`、`Test-StagingProductionGates.ps1 -ValidateOnly` 为 `validated`、`-Deploy` 为 `passed`；原件仅留 staging 私有目录，[低敏摘要](../../../release/evidence/staging/crm-staging-workspace-tracking-timeline-20261022.json)记录 SHA-256。迁移头已应用，固定出口 configured/observed 一致，11 个 CRM 容器运行，新后端/前端 RepoDigest 与候选精确相同，检索摘要不变；`/healthz`、`/v1/health`、`/v1/health/ready`、`/workspace` 均 200。
- 已部署页面 `UI_BASE_URL=https://staging.overselfx.com node --test --test-name-pattern='tracking popover|cross border tracking' ../tests/frontend/browser/workspace-experience.test.mjs`：2 passed，全部 `/v1/` 请求被合成拦截，发送调用 0。Codex 两次读取已登录应用内标签与 Chrome 新标签均超时，标记 `UI_UNAVAILABLE`，不冒称用户真实页面已验收。

# AC 映射与剩余项

AC-01：通用全部节点降序与最新描述一致，后端及浏览器通过。AC-02：跨买家 404、非跨境 404、成功缓存和并发占位行为通过；真实跨境首程无现场样本。AC-03：合成浏览器复制、PNG、翻译及原文切换通过。AC-04：本地授权/隔离、构建及合并后 staging 只读运行核对通过；真实登录态视觉点击仍待核。GitHub Actions 本次 PR 两作业均零步骤失败，不计 CI。生产 G8 No-Go。

# 结论与复测条件

`PARTIAL`：本地实现、staging 部署门禁与已部署页面合成验收通过；真实登录态视觉点击待用户核对，真实 CBT 多包裹样本尚不可用。不能据此宣称真实跨境轨迹已验证。
