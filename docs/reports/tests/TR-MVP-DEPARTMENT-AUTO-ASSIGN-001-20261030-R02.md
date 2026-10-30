---
record_id: TR-MVP-DEPARTMENT-AUTO-ASSIGN-001-20261030-R02
record_type: test
revision: R02
status: PASS
task_id: MVP-DEPARTMENT-AUTO-ASSIGN-001
tested_sha: b21f59a76adce8775eb5f9d61993e3b42886d72a
implementation_record: docs/records/implementation/IR-MVP-DEPARTMENT-AUTO-ASSIGN-001-20261030-R02.md
requirement_ids: [REQ-01, REQ-02, REQ-03, REQ-04]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
environment: staging Rootless Docker; PostgreSQL 043 to 044; one admin and three stores; TEST_LAYOUT=centralized
created_at: 2026-10-30T03:29:33+00:00
updated_at: 2026-10-30T03:29:33+00:00
supersedes: docs/reports/tests/TR-MVP-DEPARTMENT-AUTO-ASSIGN-001-20261030-R01.md
---

# 测试范围、环境与 TEST_LAYOUT

本修订覆盖用户批准后的 staging 发布与只读现场验收；R01 的隔离 PostgreSQL、权限/并发和前端合成回归仍为 AC-01～04 的详细事实源。发布源码为合并主线 `b21f59a7`，不以历史测试冒充本次运行。

# 命令和逐项结果

- 本机和远端 Git 均核对干净源码 HEAD `b21f59a7`；Git bundle SHA-256 一致。候选镜像按 `linux/amd64` 子清单、压缩层、OCI revision 和远端 RepoDigest 核对通过。
- 发布前 staging 私有 `0700` 目录保存环境文件、PostgreSQL custom dump 和 MinIO archive，均 `0600`；`pg_restore --list` 与 `tar -tzf` 可读。没有执行整库恢复演练。
- `Test-StagingProductionGates.ps1 -ValidateOnly`：通过，机器证据 SHA-256 `9057264a5caad72cd144109db13cfb69ad52c9dee4bc69b296b4ee19dde55694`。
- 相同摘要、模型/解析、单店人工发送、Webhook、翻译、Agent 调试与人工建议参数执行 `-Deploy`：通过，机器证据 SHA-256 `f493d58bfd496281ec129b793e76fa501cc9a1aa9a325d9590ea2dae7178554d`；迁移头 `044_reception_assignment`、12 个容器、固定出口 `38.55.145.52` 和三健康 200。
- 独立只读复核：运行前后端精确摘要与 revision 一致；公网 `/settings/team/departments`、`/settings/stores` 均 200；数据库仅 1 个指定活跃管理员、3 家指定店铺、派单配置 0 条、清理审计 1 条。
- 已登录页面刷新后，部门名、固定角色标签和店铺咨询分配标签显示新版本；主管/客服权限说明可见，逐店自动派单开关为关闭，待领取队列为 0。浏览器读取较慢，但最终页面状态可见。
- 运行 backend 复核 `AUTO_REPLY_ENABLED=false`、`AI_MARKETING_ENABLED=false`、`REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED=false`；真实人工发送 allowlist 仍只有「TikTok US 测试店铺」，Agent 调试及正式人工建议保持开启。GHCR 临时凭据已在本机和 staging 注销。

# REQ/AC 或门禁与证据映射

AC-01～04 的行为测试与审查见 R01；AC-05 的合并、授权、备份、预检、部署、健康与 UI 均由本修订及[低敏证据](../../../release/evidence/staging/crm-staging-department-assignment-20261030.json)覆盖。

# 缺陷、未执行项与残余风险

没有真实 TikTok 入站自动派单、真人客服多账号分流或真实消息发送测试；唯一剩余账号是管理员，且派单默认关闭。未运行 GitHub Actions 部署。PR #646 与后续合流源码测试已有独立记录；本次没有重跑全部 2730+ 后端用例，最终发布源码的前端生产构建和源镜像验证实际通过。

# 结论和复测条件

AC-05 staging 发布与默认关闭状态通过。开启逐店派单或扩大真实发送范围须按各自任务另行验证；production G8 仍 No-Go。
