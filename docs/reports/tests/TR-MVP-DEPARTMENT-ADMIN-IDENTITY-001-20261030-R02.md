---
record_id: TR-MVP-DEPARTMENT-ADMIN-IDENTITY-001-20261030-R02
record_type: test
revision: R02
status: PASS
task_id: MVP-DEPARTMENT-ADMIN-IDENTITY-001
tested_sha: 476cc8d5cf95e6304f53eec27a41d6bdaa01b056
implementation_record: docs/records/implementation/IR-MVP-DEPARTMENT-ADMIN-IDENTITY-001-20261030-R02.md
requirement_ids: [MVP-DEPARTMENT-ADMIN-IDENTITY-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: staging crmdeploy Rootless Docker, HTTPS staging.overselfx.com
created_at: 2026-10-30T14:27:29Z
updated_at: 2026-10-30T14:27:29Z
supersedes: TR-MVP-DEPARTMENT-ADMIN-IDENTITY-001-20261030-R01
---

# 现场验证

TEST_LAYOUT: centralized。代码候选本地后端 2730 passed/3 skipped、前端契约 55/55、生产构建浏览器 166/166 及静态检查见 R01，本次没有冒充重跑。

- 从干净合并 main `476cc8d5` 构建并核对前后端远端摘要、linux/amd64 和 OCI revision，Git bundle SHA 一致。
- 私有 PostgreSQL dump 可列目录、MinIO 压缩包可读、环境备份权限 0700/0600；旧版与候选 ValidateOnly、Deploy 均通过，迁移仍为 045，12 服务运行，固定出口一致，三健康与两个设置页均 HTTP 200。
- 在运行后端用只读事务调用本版 `list_team` 和 `get_department_reception`：主管目录 2 个账号；旧管理员登录标识有值且独立联系方式隐藏；管理员在部门 2 店均有回复资格，派单勾选仍为 false。无账号、派单配置或买家会话写入。
- 运行态原两店人工发送、Webhook 只读、Agent 模式和安全开关不变。临时 GHCR 登录已注销；零真实买家测试外发，production 未部署。

已登录 in-app browser 的绑定连续两次超时，记 `UI_UNAVAILABLE`；所以本次没有声称真实登录页面视觉回显。真实入站自动派单未执行；管理员参与仍须显式开启，不能把“有资格”当作“已经接单”。机器证据见[低敏 JSON](../../../release/evidence/staging/crm-staging-department-admin-identity-20261030.json)。
