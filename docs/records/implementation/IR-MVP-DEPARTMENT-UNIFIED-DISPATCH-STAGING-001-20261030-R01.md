---
record_id: IR-MVP-DEPARTMENT-UNIFIED-DISPATCH-STAGING-001-20261030-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-DEPARTMENT-UNIFIED-DISPATCH-STAGING-001
base_sha: 0fc2b50b993d2f53e63d1b555fd60a26add268d4
final_sha: 0fc2b50b993d2f53e63d1b555fd60a26add268d4
requirement_ids: [MVP-DEPARTMENT-UNIFIED-DISPATCH-STAGING-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
test_record: docs/reports/tests/TR-MVP-DEPARTMENT-UNIFIED-DISPATCH-STAGING-001-20261030-R01.md
review_record: docs/reports/reviews/RR-MVP-DEPARTMENT-UNIFIED-DISPATCH-STAGING-001-20261030-R01.md
created_at: 2026-10-30T12:01:25Z
updated_at: 2026-10-30T12:01:25Z
supersedes: null
---

# 目标与实施

从已合并的 `main=0fc2b50b` 直接发布部门统一派单和账号目录修复到 staging，不使用 GitHub Actions 部署。与上一运行源码 `4483ec9b` 相比，只有 PR #668 的产品实现及证据收尾；后端和前端镜像同源、同次切换。使用用户指定的 `192.168.1.173` 私钥接入业务机，远端完整 Git bundle 与本地 SHA-256 一致，干净 checkout 的 HEAD 为发布提交。

构建并推送 `linux/amd64` 前后端，OCI revision 与发布提交一致，远端加载传输哈希相同的镜像并复核 RepoDigest。旧运行环境、PostgreSQL 自定义格式转储和 MinIO 数据备份留在私有目录，可列出与解包，目录及文件权限为 0700/0600。原版和候选 `ValidateOnly` 后执行 `Deploy`，迁移到 `045_dept_dispatch_login`，12 服务、固定 TikTok 出口、公网健康及运行开关通过。精确摘要与证据见[低敏 JSON](../../../release/evidence/staging/crm-staging-department-unified-dispatch-20261030.json)。

# 边界与恢复

人工真实发送只保留原两家已授权店铺；Webhook 只读、Agent 调试与人工建议保持，自动回复、营销及高风险写入关闭。工作台翻译在本次切换前实际为关闭，部署后仍关闭。没有触发真实买家消息或退款，没有操作 production。迁移 045 有数据后禁止直接降级；恢复先评估业务增量，优先切回旧镜像并保持新库，必要的数据恢复须单独审查。旧镜像摘要和私有备份路径见低敏 JSON。

部门旧逐店配置迁移为一个部门开启；现场当前没有参与派单的客服，因此开启开关不代表已有自动接待者。旧无 `sid` 的登录令牌需首次刷新或重新登录才产生在线记录。
