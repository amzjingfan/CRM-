---
record_id: TR-MVP-DEPARTMENT-UNIFIED-DISPATCH-STAGING-001-20261030-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-DEPARTMENT-UNIFIED-DISPATCH-STAGING-001
tested_sha: 0fc2b50b993d2f53e63d1b555fd60a26add268d4
implementation_record: docs/records/implementation/IR-MVP-DEPARTMENT-UNIFIED-DISPATCH-STAGING-001-20261030-R01.md
requirement_ids: [MVP-DEPARTMENT-UNIFIED-DISPATCH-STAGING-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: Windows Docker linux/amd64; staging crmdeploy Rootless Docker; authenticated in-app browser; HTTPS staging.overselfx.com
created_at: 2026-10-30T12:01:25Z
updated_at: 2026-10-30T12:01:25Z
supersedes: null
---

# 现场结果

TEST_LAYOUT: centralized。原 subject 的 2730/3 后端、55 前端契约、165/1 浏览器及单独生产缓存 1 项、静态检查、生产构建和隔离旧数据 044→045 迁移结果见[功能 TR](TR-MVP-DEPARTMENT-UNIFIED-DISPATCH-001-20261030-R01.md)，这些是原代码候选的验证，不冒充本轮重跑。

- AC-01：主线 `0fc2b50b` 干净 checkout、Git bundle、前后端 `linux/amd64` OCI revision、远端相同 RepoDigest 核对通过；上一运行版到该提交只含 PR #668 实现与证据收尾。
- AC-02：私有环境、PostgreSQL、MinIO 备份可读且有 SHA-256/权限证据；原版与候选 `ValidateOnly`、候选 `Deploy` 均通过。业务库为 `045_dept_dispatch_login (head)`。
- AC-03：12 服务运行或健康，固定出口为 `38.55.145.52`；公网三个健康路径与账号、部门页面均为 HTTP 200。已登录浏览器刷新部门页，显示新版“账号目录 (2)”以及管理员、主管两行；只读数据库统计为 1 个部门开启、0 位参与派单客服、1 条当前有效登录会话。
- AC-04：运行后端原两家店铺人工发送白名单与 Webhook 读取、Agent 调试/人工建议保持，自动回复、营销、高风险写入关闭。临时 GHCR 登录已注销，本轮未触发真实买家消息或退款，production 未部署。

精确镜像、备份及原版/候选门禁原件哈希见[低敏 JSON](../../../release/evidence/staging/crm-staging-department-unified-dispatch-20261030.json)。

# 限制

浏览器进一步读取派单配置页超时，记录为 `UI_UNAVAILABLE`；未使用 `admin-test` 的独立登录态做 staging 账号目录现场检查，且没有真实 TikTok 入站派单演练。这些行为由原 subject 的生产构建浏览器及 PostgreSQL 权限/派单测试覆盖，本轮 PASS 仅指限定的 staging 部署与安全边界。旧令牌刷新前没有在线记录，待坐席刷新或重新登录生效。
