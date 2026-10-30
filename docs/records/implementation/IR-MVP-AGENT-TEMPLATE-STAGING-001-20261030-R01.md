---
record_id: IR-MVP-AGENT-TEMPLATE-STAGING-001-20261030-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-AGENT-TEMPLATE-STAGING-001
created_at: 2026-10-30T16:56:13.795981+00:00
updated_at: 2026-10-30T16:56:13.795981+00:00
supersedes: null
base_sha: fbacb37299c4793ef166b2123e111b24095001b0
final_sha: dcf5621e4c725faead3f6f67d01d6770bca5a88a
requirement_ids: [MVP-AGENT-TEMPLATE-STAGING-001]
acceptance_ids: [AC-CANDIDATE, AC-NO-SEND]
test_record: docs/reports/tests/TR-MVP-AGENT-TEMPLATE-STAGING-001-20261030-R01.md
review_record: docs/reports/reviews/RR-MVP-AGENT-TEMPLATE-STAGING-001-20261030-R01.md
---

# 统一修复候选

用户已批准手动 staging 部署、真实测试、整轮问题统一修复后再部署、结束删除自有测试数据。此修订记录候选代码与首轮现场；最终统一发布及清理尚未完成，任务继续 VERIFYING，不以本记录声明整个目标完成。

首次从 fbacb372 发布，私有 PostgreSQL/MinIO/原配置备份、双预检、共享锁 Deploy、046、12 服务与公开健康通过。首轮真实两店新建、v2 三方差异、本店覆盖保留、处理中离开页面后继续与每项一次执行通过。US 中英文订单/物流/文件检索联合回答及 XBM 独立文件引用通过，无买家外发。

测试期间现场被另一发布切换至主线 d67078db 的富消息修复。已协调部署所有权并整合该主线；当前运行镜像须作为最终切换的新回滚点，不能用旧源码覆盖工作台变更。切换邻近有一次预览通用失败，重试通过，未据此猜改后端。

统一代码仅改两处前端：批次 preview/queued/running 分别显示未确认预览/等待执行/执行中，计数中文化；仍在有效槽映射中的文件不列为移除槽解绑候选，尚未重新预览的本地映射覆盖也优先。权限、店铺索引、旧槽解绑、取消、重试和后台执行路径未改变，无新增依赖/API/迁移/安全开关。

# 恢复边界

最终候选已通过 TR 与独立审查。staging 最终部署复测、数据清理和临时 registry 副本清理待下一修订；production 不在授权内，自动回复/营销/高风险写关闭。
