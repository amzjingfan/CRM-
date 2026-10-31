---
record_id: TR-MVP-SUPERVISOR-STORE-AUTH-001-20261031-R02
record_type: test
revision: R02
status: PASS
task_id: MVP-SUPERVISOR-STORE-AUTH-001
tested_sha: 2fe8276b87d4fb26e4093ab000ccc43491453f4f
implementation_record: docs/records/implementation/IR-MVP-SUPERVISOR-STORE-AUTH-001-20261031-R01.md
requirement_ids: [MVP-SUPERVISOR-STORE-AUTH-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
environment: merged-main Linux rootless staging; isolated local PostgreSQL and frontend checks retained from R01
created_at: 2026-10-31T02:38:00Z
updated_at: 2026-10-31T02:38:00Z
supersedes: docs/reports/tests/TR-MVP-SUPERVISOR-STORE-AUTH-001-20261031-R01.md
---

# 范围与来源

[R01](TR-MVP-SUPERVISOR-STORE-AUTH-001-20261031-R01.md) 的权限、OAuth、隔离 PostgreSQL 2984 项和前端 77 项测试绑定实现 subject `2fe8276b87d4fb26e4093ab000ccc43491453f4f`，本轮没有改动实现。PR #686 squash 合并为 `8d2962279d796709279d17b4d8aa6f0a978d87b0`。已核对相对于部署前后端源码仅 6 个本任务文件、前端仅 2 个本任务页面变化。低敏发布原件见[机器证据](../../../release/evidence/staging/crm-staging-supervisor-store-authorization-20261031.json)。

# staging 部署与只读验收

- 从干净的合并主线 Git bundle 建立受审 staging clone，GitHub 当前 main 与镜像 OCI revision 均为 `8d296227...`。本机直接构建和推送 linux/amd64 后端、前端；未使用 GitHub Actions。候选与旧版的五个镜像角色以完整不可变摘要在 Rootless Docker 核对。
- 私有环境、运行快照、自定义 PostgreSQL dump 和 MinIO 数据归档均为 `0600`，目录 `0700`；`pg_restore -l` 与 tar 列表可读。受审源码 `CheckOnly`、`ValidateOnly=validated` 后才运行 `Deploy=passed`。
- 迁移为 `047_supervisor_store_auth (head)`；现场只读 SQL 确认主管角色与新 `settings.store_authorize` 权限关联 1 行。12 个服务运行或健康；后端及前端镜像与候选摘要相符；`/healthz`、`/v1/health`、`/v1/health/ready` 和两个设置页公网请求均为 200。
- 运行模式门禁确认人工真实发送仍仅限原两家店铺，Webhook 读取、工作台翻译、Agent 调试/正式建议、文档解析保持原状；自动回复、AI 营销和 TikTok 高风险写入仍关闭。没有触发真实 OAuth、新店授权、买家消息、退款或 production 操作。

# 异常、边界和结论

业务机从 GHCR 拉取前端镜像耗时过长，停止本轮拉取后通过内网传输受校验的镜像归档；Rootless 导入后完整 RepoDigest、OCI revision 和平台均匹配，后续正式 Deploy 的镜像拉取成功。最初数据库备份目录验证使用了 `pg_restore -l -`，该工具不接受该参数；改用只读临时容器对同一 dump 执行 `pg_restore -l /backup/postgres.dump` 成功。两项恢复点与失败原因保留，不冒充首次通过。

已登录主管页面的 in-app browser 绑定两次超时，记为 `UI_UNAVAILABLE`；公网页面 200 和本地浏览器用例不能替代真实主管点击授权的端到端验收。真实 TikTok 授权将改变外部店铺状态，未在本轮发起。本轮部署与本地 AC-01～05 证据通过，真实主管视觉和真实 OAuth callback 留作首次使用时观察；若出现异常，可按私有备份和旧前后端摘要恢复，并保护部署后的业务增量。
