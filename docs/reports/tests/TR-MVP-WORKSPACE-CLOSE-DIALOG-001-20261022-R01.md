---
record_id: TR-MVP-WORKSPACE-CLOSE-DIALOG-001-20261022-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-WORKSPACE-CLOSE-DIALOG-001
tested_sha: 3afb15f8f5465a3e8c25fb7cfe801e147bd0b2e9
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-CLOSE-DIALOG-001-20261022-R01.md
requirement_ids: [MVP-WORKSPACE-CLOSE-DIALOG-001]
acceptance_ids: [AC-01, AC-02, AC-03]
environment: Windows local frontend checks; merged-main Linux rootless staging; deployed-page synthetic Chrome
created_at: 2026-10-22T01:23:04Z
updated_at: 2026-10-22T01:23:04Z
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

测试源码位于固定 `src/tests/`；临时 OCI、源码包和辅助脚本在已忽略的 `src/tests/.artifacts/`。正式门禁证据原件与数据库备份留在 staging 私有目录，仓库仅保存[低敏摘要](../../../release/evidence/staging/crm-staging-workspace-close-dialog-20261022.json)。

# 命令和逐项结果

- 修复前定向浏览器用例因找不到站内 dialog 失败；修改后定向用例通过。subject 上 `npm test` 47/47、`npm run typecheck`、`npm run build`、`npm run lint`（0 error、4 条既有 warning）、开发浏览器文件 24/24、生产构建浏览器 55/55、`git diff --check` 均通过。
- GitHub Actions 的 PR 检查和前端发布运行 `39703711134` 都在执行步骤前失败，不计作 CI 通过。改由本机按合入 SHA 构建 OCI，传输时核对归档 SHA-256；staging Rootless Docker 导入后核对不可变 RepoDigest 与 `org.opencontainers.image.revision`，通过主机既有 GHCR 凭据推送该摘要。
- 现场从干净的完整 Git bundle checkout 核对 `HEAD=56ea8d4e5d95951c9052220b26b3b54d051992b4`，远端 main 同 SHA。部署前私有运行模式快照与 `pg_dump -Fc` 备份模式均为 `0600`，备份 `pg_restore -l` 可读。六镜像角色不可变摘要预取、`Test-StagingProductionGates.ps1 -ValidateOnly` 与 `-Deploy` 均通过；迁移头 `025_workspace_actions`。后端、检索摘要不变，前端运行新摘要，11 个容器正常，四个公网路径均 HTTP 200。
- 在已部署 `https://staging.overselfx.com` 页面运行 `UI_BASE_URL=https://staging.overselfx.com node --test --test-name-pattern='closing a conversation uses an in-app dialog' src/tests/frontend/browser/workspace-experience.test.mjs`：1/1 通过。测试拦截所有 `/v1/` 请求，仅用合成会话，覆盖取消、Escape、切换会话、失败重试、确认关闭及没有原生弹窗。

# 验收与限制

AC-01～AC-03 的确定性浏览器和部署门禁通过。用户刷新真实会话并按要求检查关闭弹窗与取消路径后回复“修复好了”；这是用户现场反馈，Codex 未直接读取该登录态页面，也未在真实会话执行关闭写入。GitHub Actions 零步骤故障仍需独立修复，production G8 No-Go。
