---
record_id: TR-MVP-STAGING-PREFETCH-002-20261013-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-STAGING-PREFETCH-002
tested_sha: f78350e12b85840e8f5ddc1036c2792caf702339
implementation_record: docs/records/implementation/IR-MVP-STAGING-PREFETCH-002-20261013-R01.md
requirement_ids: [MVP-STAGING-PREFETCH-002, G4]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: Windows PowerShell; uv Python 3.12; staging not mutated
created_at: 2026-10-13T16:21:00+08:00
updated_at: 2026-10-13T17:02:00+08:00
supersedes: null
---

# 本次验证

测试根遵守 `TEST_LAYOUT: centralized`。先扩展三仓库、严格镜像引用、Token scope 与六角色 OCI 路径测试；变更前定向运行 `8 failed, 19 passed`，修复后定向 `30 passed`。在 `src/backend` 以 `uv run pytest -c pyproject.toml -q` 完整回归为 `1758 passed, 19 skipped, 2 warnings`。项目规定 `uv run mypy app scripts` 为 172 个文件无问题；Ruff 检查和格式检查通过，独立传输脚本及两份受影响测试文件的 Ruff/格式也通过。PowerShell Parser 解析 `Prepare-StagingRollbackImages.ps1` 零错误，`git diff --check` 通过。

额外把 Linux 专用传输脚本加入 Windows mypy 时有两项类型错误：既有 `json.loads` 返回 Any、Windows 类型存根不提供 `os.geteuid`。此额外命令并非项目规定的类型门禁，未改运行脚本以适配 Windows 存根；运行环境为 Linux UID 1004，现场仍需验证。

# 尚缺与结论

原生拉取挂起的 #38363713490 已受控取消。修复后的正式预取 #38369618427 绑定 main `9765189e…ddd629`，六项摘要精确匹配，状态 `passed`、`service_mutation=false`、`production_release=false`。日志证实第 1 项后端由 OCI 分块导入并核对 RepoDigest，剩余五项从本地精确缓存通过；原始 JSON SHA-256 `a8a823ff0f7875255840b9e86b3ff0d64fd5274270b27872c58397d756a2801a`。后续 validate #38371623054 为 `validated`、未执行迁移；deploy #38372083732 为 `passed`、迁移头已应用、健康三项 200、固定出口 `38.55.145.52`、Webhook 只读。它们的原始 JSON SHA-256 依次为 `bbc2cc358ac42aa9cb345ce7306b358a1591d7bb8d5e51572783d897262bcd01` 和 `8bc096e2632e41716fee7e7a5e63aaf922a295b9a67095b51738033bf42ac102`。四份低敏镜像/现场证据见 `release/evidence/staging/crm-staging-g4-dlp-*.json`。`AC-04` 现场通过；G4 质量和 production 仍独立判断。
