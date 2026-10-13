---
record_id: IR-MVP-STAGING-PREFETCH-002-20261013-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-STAGING-PREFETCH-002
base_sha: 85035505b620731fafe11e154d3104d2dbfc211d
final_sha: f78350e12b85840e8f5ddc1036c2792caf702339
requirement_ids: [MVP-STAGING-PREFETCH-002, G4]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
test_record: docs/reports/tests/TR-MVP-STAGING-PREFETCH-002-20261013-R01.md
review_record: docs/reports/reviews/RR-MVP-STAGING-PREFETCH-002-20261013-R01.md
created_at: 2026-10-13T16:21:00+08:00
updated_at: 2026-10-13T17:02:00+08:00
supersedes: null
---

# 目标与变更

G4 诊断后端候选 `sha256:bb38fa09…e7d80` 的预取 #38363713490 在第 1/6 项后端原生 `docker pull` 中停滞约 28 分钟，30 分钟后受控取消。作业没有进入 validate、deploy，也没有生成六摘要通过证据。底层连接为何没有返回仍未知，但脚本只让第 2/5 项检索镜像使用有超时、有限重试和逐层校验的 OCI 分块传输，是确定的流程缺口。

本次把该分块传输用于六角色中所有本地缺失的镜像。Python 入口仅接受 `cp11-gh` 的 backend、frontend、retrieval 三个固定 GHCR 仓库及小写不可变 SHA-256；GHCR Token scope、manifest 与导入 base-name 随经检查的仓库确定。保留缓存命中跳过、1 MiB 范围续传、描述符长度及 SHA-256、Rootless containerd 导入和最终 Docker RepoDigest 精确匹配。OCI 路径失败时不回退原生 `docker pull`，PowerShell 抛错且工作流的成功条件不会上传通过证据。无脚本参数的本地旧路径仍可单独测试，不是正式工作流入口。

# 边界与恢复

PR #146 已通过前后端 CI 并 squash 合入 main `9765189e554eef5c632301e674673c2976ddd629`。从该 main 新派发的预取 #38369618427 对第 1/6 项后端走 OCI 分块传输、完整 SHA-256 校验和 Rootless 导入，其余五项命中本地精确摘要；六角色 `RepoDigest` 全部匹配，`service_mutation=false`。随后 validate #38371623054、staging deploy #38372083732 通过，运行候选后端 `sha256:bb38fa09…e7d80`，迁移头 `024`、三个公网健康 200、固定出口匹配；前端/检索摘要和 Webhook 只读模式不变。低敏原始机器证据及 SHA-256 见 TR 和 `release/evidence/staging/crm-staging-g4-dlp-*.json`。旧后端 `sha256:22fb55db…211102` 为恢复目标。G4 质量另验，production 不在范围。
