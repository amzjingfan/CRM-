---
record_id: TR-MVP-STAGING-PREFETCH-002-20261013-R01
record_type: test
revision: R01
status: PARTIAL
task_id: MVP-STAGING-PREFETCH-002
tested_sha: f78350e12b85840e8f5ddc1036c2792caf702339
implementation_record: docs/records/implementation/IR-MVP-STAGING-PREFETCH-002-20261013-R01.md
requirement_ids: [MVP-STAGING-PREFETCH-002, G4]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: Windows PowerShell; uv Python 3.12; staging not mutated
created_at: 2026-10-13T16:21:00+08:00
updated_at: 2026-10-13T16:21:00+08:00
supersedes: null
---

# 本次验证

测试根遵守 `TEST_LAYOUT: centralized`。先扩展三仓库、严格镜像引用、Token scope 与六角色 OCI 路径测试；变更前定向运行 `8 failed, 19 passed`，修复后定向 `30 passed`。在 `src/backend` 以 `uv run pytest -c pyproject.toml -q` 完整回归为 `1758 passed, 19 skipped, 2 warnings`。项目规定 `uv run mypy app scripts` 为 172 个文件无问题；Ruff 检查和格式检查通过，独立传输脚本及两份受影响测试文件的 Ruff/格式也通过。PowerShell Parser 解析 `Prepare-StagingRollbackImages.ps1` 零错误，`git diff --check` 通过。

额外把 Linux 专用传输脚本加入 Windows mypy 时有两项类型错误：既有 `json.loads` 返回 Any、Windows 类型存根不提供 `os.geteuid`。此额外命令并非项目规定的类型门禁，未改运行脚本以适配 Windows 存根；运行环境为 Linux UID 1004，现场仍需验证。

# 尚缺与结论

原生拉取挂起的 #38363713490 已受控取消，没有六摘要通过 artifact，也没有服务变更。本地结果支持代码候选进入 PR；`AC-04` 仍须从合入后的 main 重新派发正式六摘要预取并核对精确摘要。此 TR 不宣称 staging 预取或 G4 通过。
