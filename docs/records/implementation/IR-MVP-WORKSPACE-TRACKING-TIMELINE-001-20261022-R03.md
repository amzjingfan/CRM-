---
record_id: IR-MVP-WORKSPACE-TRACKING-TIMELINE-001-20261022-R03
record_type: implementation
revision: R03
status: FINAL
task_id: MVP-WORKSPACE-TRACKING-TIMELINE-001
base_sha: 43f7a3c84b825effd127d0267a25187649a99bf1
final_sha: 39244eb15b6c11db9b7463656304de1a92153c9d
requirement_ids: [MVP-WORKSPACE-TRACKING-TIMELINE-001]
acceptance_ids: [AC-03, AC-04, AC-05]
test_record: docs/reports/tests/TR-MVP-WORKSPACE-TRACKING-TIMELINE-001-20261022-R03.md
review_record: docs/reports/reviews/RR-MVP-WORKSPACE-TRACKING-TIMELINE-001-20261022-R03.md
created_at: 2026-10-22T03:25:07Z
updated_at: 2026-10-22T03:25:07Z
supersedes: docs/records/implementation/IR-MVP-WORKSPACE-TRACKING-TIMELINE-001-20261022-R02.md
---

# 实施目标与实际变更

R02 源码通过 [PR #508](https://github.com/CP11-gh/CRM/pull/508) squash 合入 `main=218befe0113291d14fd3bde98a4f95a1e9ac8718`。受影响前后端与 Docker 构建输入同 subject `39244eb15b6c11db9b7463656304de1a92153c9d` 无差异。功能仍为全部包裹节点一键翻译、切回原文/重新翻译、单号复制和物流卡片仅预填草稿；不自动外发。

# staging 发布与恢复点

从合入 SHA 的干净 checkout 构建 `linux/amd64` 前后端镜像，带精确 OCI revision；源码 bundle 与双镜像归档经本机/staging SHA-256 逐字节核对后导入 staging Rootless Docker，并使用主机现有 GHCR 授权发布不可变摘要。保留原后端/前端/检索三摘要及私有可读数据库备份。六镜像角色预取、`ValidateOnly` 与 `Deploy` 门禁均通过；运行摘要与候选相同，11 个 CRM 容器和四个公网路径健康。详情见 [低敏部署证据](../../../release/evidence/staging/crm-staging-workspace-tracking-bulk-20261022.json)及 R03 TR。

# 限制、风险与回滚

用户在已登录 staging 会话中确认全部节点一键译成中文、原文切换、重新翻译以及物流卡片只填入草稿且没有直接发送；此反馈不等于独立读取模型审计。已部署页面合成浏览器 3/3 通过。超过 40 个节点时整批翻译失败并保留原文；原 CBT 首程样本仍未确认。若现场失败，停止后续操作并用已记录的旧不可变摘要和受审门禁回滚；本次未发布 production。
