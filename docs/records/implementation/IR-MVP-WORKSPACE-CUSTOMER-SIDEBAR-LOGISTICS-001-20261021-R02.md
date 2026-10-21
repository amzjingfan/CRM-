---
record_id: IR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-LOGISTICS-001-20261021-R02
record_type: implementation
revision: R02
status: FINAL
task_id: MVP-WORKSPACE-CUSTOMER-SIDEBAR-LOGISTICS-001
base_sha: 4f32c04e2cc2f92170f30c91b8a2ca4d1bf75266
final_sha: 6e1f2489007b085b5a02d0aff2df6f4d2f86c44e
requirement_ids: [MVP-WORKSPACE-CUSTOMER-SIDEBAR-LOGISTICS-001]
acceptance_ids: [AC-04]
test_record: docs/reports/tests/TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-LOGISTICS-001-20261021-R02.md
review_record: null
created_at: 2026-10-21T03:39:47Z
updated_at: 2026-10-21T03:39:47Z
supersedes: docs/records/implementation/IR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-LOGISTICS-001-20261021-R01.md
---

# 实施目标与范围

将 R01 的订单卡片只读展示修复从已合并主线手动发布到 staging，保持 production No-Go。

# 实际变更及原因

- 核对源码提交与合并主线的前端构建输入一致，从 `main=4f32c04e2cc2f92170f30c91b8a2ca4d1bf75266` 构建并推送不可变前端镜像 `sha256:7dbdd3ac…d543934`。
- 使用现有 staging 受限部署账号核对旧运行摘要、单店人工发送范围，保存模式 `0600` 的数据库快照；预取六个候选/回滚镜像角色，再顺序运行手动 validate 与 deploy。
- 仅切换前端镜像。后端、检索镜像及现有 Webhook 读取、人工发送、翻译模式均未扩大；没有向买家发送消息、退款或发券。

# 关键决定与偏差

现有断点预取工具只接受 OCI image index，新构建镜像为单平台 manifest，故改用同一预取门禁内的 Docker 直接拉取路径。全部六个角色最终按不可变摘要核对通过，失败的首次预取未切换服务。

# 数据、配置、接口、迁移或 Prompt 影响

无新数据库迁移、接口、配置、Prompt 或模型变化。部署门禁确认既有迁移头已应用、固定出口匹配、三个公网健康接口为 200。

# 验证交接

本次 R02 TR 与[低敏现场清单](../../../release/evidence/staging/crm-staging-customer-sidebar-logistics-20261021.json)记录镜像、备份 SHA、门禁原件 SHA 和用户在真实订单卡片上的截图确认。截图含订单标识，仅留在对话中，不纳入仓库。

# 限制、风险与回滚

内置浏览器读取旧标签与新标签均超时，记 `UI_UNAVAILABLE`；用户提供已登录页面截图补足可见字段验收。上游缺失结构化物流状态时仍显示明确的订单运输阶段或空值，不推断“待派送”。需回滚时使用已保留的旧前端摘要重新跑 staging 门禁，不用旧数据库备份覆盖新消息。
