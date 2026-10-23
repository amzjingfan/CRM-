---
record_id: TR-MVP-MARKETING-BASIC-RECEPTION-POLICY-003-20261023-R02
record_type: test
revision: R02
status: PASS
task_id: MVP-MARKETING-BASIC-RECEPTION-POLICY-003
tested_sha: db16111df252c4d941cfd1b6c1223a83e2c58cac
implementation_record: docs/records/implementation/IR-MVP-MARKETING-BASIC-RECEPTION-POLICY-003-20261023-R02.md
requirement_ids: [MVP-MARKETING-BASIC-RECEPTION-POLICY-003]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
environment: Windows clean merged-main worktree; isolated PostgreSQL; staging Rootless Docker and authenticated browser
created_at: 2026-10-23T12:21:06Z
updated_at: 2026-10-23T12:21:06Z
supersedes: docs/reports/tests/TR-MVP-MARKETING-BASIC-RECEPTION-POLICY-003-20261023-R01.md
---

# 合并后验证与现场结果

最终主线 `db16111df252c4d941cfd1b6c1223a83e2c58cac`：后端完整测试 2351 passed / 42 skipped，Ruff、格式和 mypy 通过；前端契约 48 passed、typecheck、lint 0 error / 7 warning、生产 build 通过；生产浏览器 101 passed / 1 skipped。跳过项及既有 warning 不记为通过项。较早候选的定向回归见前版 TR。

部署前后实际完成：源码树与两镜像 OCI revision 一致、私有 PostgreSQL/MinIO 备份可读取、手动 ValidateOnly=`validated`、Deploy=`passed`、Alembic 单头 `031_reception_policy_schedule`、12 个 CRM 容器运行、三健康和四个产品 URL 均为 HTTP 200；系统 Docker 其他容器快照一致。已登录 staging 页面看到一条现有超时策略；欢迎语列表为空，但新增表单显示店铺多选和三种有效期。两类策略的保存、重载与权限隔离由本地 PostgreSQL 和生产浏览器行为测试覆盖；本次未向真实店铺新建欢迎语。

[低敏现场证据](../../../release/evidence/staging/crm-staging-direct-reception-workspace-20261023.json)保存摘要、备份哈希、健康与运行模式。未运行 GitHub Actions：用户明确要求直接部署，原 PR 作业因账户付款/额度问题零步骤结束；不将其写为 CI 通过。未做真实买家消息发送、媒体传输或 production 发布。

# 结论

本任务的已授权源码与 staging 配置/页面范围通过。真实店铺的欢迎语新建、真实买家媒体接收与生产放行仍不在本次现场测试范围。
