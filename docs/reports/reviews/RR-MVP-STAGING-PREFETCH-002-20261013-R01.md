---
record_id: RR-MVP-STAGING-PREFETCH-002-20261013-R01
record_type: review
revision: R01
status: APPROVE
task_id: MVP-STAGING-PREFETCH-002
reviewed_sha: f78350e12b85840e8f5ddc1036c2792caf702339
implementation_record: docs/records/implementation/IR-MVP-STAGING-PREFETCH-002-20261013-R01.md
test_record: docs/reports/tests/TR-MVP-STAGING-PREFETCH-002-20261013-R01.md
review_focus: [repository-allowlist, digest-integrity, rootless-import, failure-closed, deployment-boundary]
created_at: 2026-10-13T16:21:00+08:00
updated_at: 2026-10-13T17:02:00+08:00
supersedes: null
---

# 审查与结论

检查 subject 的 PowerShell 路由、Python 仓库选择与受影响测试。正式工作流以 Git blob SHA 校验精确提交的三个脚本，始终传入 OCI 脚本；本次六项缺失摘要因此都走同一受限 OCI 路径。镜像引用须匹配固定三仓库和 64 位小写 SHA-256；Token scope 与请求路径取自同一经检查的仓库。原有分块 Content-Range/长度、清单/层 SHA-256 和最终 RepoDigest 约束保留。传输失败抛错，成功证据只在工作流成功时上传；没有修改部署操作、容器、外部消息或生产开关。

未发现阻断问题。Linux 现场 #38369618427 已验证第 1 项后端 OCI 分块传输、Rootless 导入及六摘要通过，validate/deploy 后运行后端摘要与健康证据一致；因此批准关闭本预取任务。传输耗时约 15 分钟，说明 GHCR 链路仍慢，但不再发生原生拉取无界挂起。G4 的 live 质量报告另属 MVP-005；本审查不将预取成功视为 G4 或 production 通过。
