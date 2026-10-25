---
record_id: RR-MVP-STORE-VIEW-CONSISTENCY-001-20261025-R02
record_type: review
revision: R02
status: APPROVE
task_id: MVP-STORE-VIEW-CONSISTENCY-001
reviewed_sha: aadf5087969ceb8ccb2b533ce8a42c191c3f96d9
implementation_record: docs/records/implementation/IR-MVP-STORE-VIEW-CONSISTENCY-001-20261025-R02.md
test_record: docs/reports/tests/TR-MVP-STORE-VIEW-CONSISTENCY-001-20261025-R02.md
review_focus: [deployment, migration, store_isolation, rollback]
created_at: 2026-10-25T03:49:00Z
updated_at: 2026-10-25T03:49:00Z
supersedes: docs/reports/reviews/RR-MVP-STORE-VIEW-CONSISTENCY-001-20261025-R01.md
---

# 审查范围、依据与重点风险

R01 对权限、CSRF、幂等、审计、店铺隔离和迁移的源码审查继续有效；合并主线与候选构建输入相同。本修订审查 staging 镜像来源、私有备份、模式保持、迁移及回滚边界。

# 发现、级别、位置和证据

未发现本次 CRM 发布门禁阻断项。私有数据库备份已验证可列目录；`ValidateOnly` 和 `Deploy` 的低敏证据显示相同精确摘要、单店人工发送范围、固定出口及迁移头。`032` 在已有归档后不能无损降级；回退优先仅切应用镜像并保留新列与增量。公网 UI 只核对了路由、缓存与静态资源；已登录交互工具不可用，未虚报现场点击。无关系统 Docker Redis 长期重启循环为单独运维风险，本次未处理。

# 已验证与未验证内容

已验证主线 SHA、OCI revision、Rootless 12 容器、读写模式、迁移和公网页面。未验证真实店铺的切换、文件归档/删除写入及网关主机 Nginx 配置；后者因自动审批拒绝临时复制私钥，且部署未触及网关配置。未运行 GitHub Actions 测试步骤，用户仅对本次直接 staging 作出替代决定。

# 结论和返修条件

对本次 staging 部署范围 **APPROVE**；production 仍 No-Go。若实际店铺交互与本地验收不符、运行摘要漂移、健康失败或数据迁移出现异常，应暂停后续写入，按私有快照和业务增量对账，必要时回滚应用摘要。