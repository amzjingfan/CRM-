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
updated_at: 2026-10-13T16:21:00+08:00
supersedes: null
---

# 目标与变更

G4 诊断后端候选 `sha256:bb38fa09…e7d80` 的预取 #38363713490 在第 1/6 项后端原生 `docker pull` 中停滞约 28 分钟，30 分钟后受控取消。作业没有进入 validate、deploy，也没有生成六摘要通过证据。底层连接为何没有返回仍未知，但脚本只让第 2/5 项检索镜像使用有超时、有限重试和逐层校验的 OCI 分块传输，是确定的流程缺口。

本次把该分块传输用于六角色中所有本地缺失的镜像。Python 入口仅接受 `cp11-gh` 的 backend、frontend、retrieval 三个固定 GHCR 仓库及小写不可变 SHA-256；GHCR Token scope、manifest 与导入 base-name 随经检查的仓库确定。保留缓存命中跳过、1 MiB 范围续传、描述符长度及 SHA-256、Rootless containerd 导入和最终 Docker RepoDigest 精确匹配。OCI 路径失败时不回退原生 `docker pull`，PowerShell 抛错且工作流的成功条件不会上传通过证据。无脚本参数的本地旧路径仍可单独测试，不是正式工作流入口。

# 边界与恢复

源码与本地验证只证明预取逻辑；此记录定稿时新的 main 现场六摘要预取仍待执行，`AC-04` 未关闭。staging 仍运行旧后端 `sha256:22fb55db…211102`；前端/检索、Webhook 只读与 TikTok 写开关未变。已发布的新后端镜像不等于已部署。下一步从合入后的精确 main 新派发预取，通过后才可继续 validate、deploy、G4 prepare/live。production 不在范围。
