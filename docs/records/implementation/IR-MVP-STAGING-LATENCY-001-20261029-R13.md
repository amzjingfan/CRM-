---
record_id: IR-MVP-STAGING-LATENCY-001-20261029-R13
record_type: implementation
revision: R13
status: FINAL
task_id: MVP-STAGING-LATENCY-001
base_sha: 85572de4f2534513605849be83c15fa2a0dfcaf5
final_sha: 86e5c4e48862da445932ad50529c3a85bd3801f5
requirement_ids: [MVP-STAGING-LATENCY-001]
acceptance_ids: [AC-05, AC-06]
test_record: docs/reports/tests/TR-MVP-STAGING-LATENCY-001-20261029-R16.md
review_record: docs/reports/reviews/RR-MVP-STAGING-LATENCY-001-20261029-R13.md
created_at: 2026-10-29T06:05:00+08:00
updated_at: 2026-10-29T06:05:00+08:00
supersedes: docs/records/implementation/IR-MVP-STAGING-LATENCY-001-20261029-R12.md
---

# 实施目标与范围

基础接待的快捷回复、超时自动回复、进店欢迎语在 `/v1/auth/me` 已返回授权店铺编号后，仍等待 `/v1/settings/stores` 店铺名称请求结束，才开始读取配置。弱网下这增加一段无必要的等待。

# 实际变更及原因

两个前端管理组件现在先用服务端给出的 `user.store_ids` 建立已授权店铺选择，校验 URL 中的 `store_id`，立即启动只读配置加载；店铺名称到达后仅补齐显示。名称请求失败时保留编号和配置回显，并显示名称读取提示。新增合成浏览器用例故意延迟店铺名称响应，验证快捷回复和超时策略在该响应完成前可见。产品文档同步说明。源码提交为 `86e5c4e48862da445932ad50529c3a85bd3801f5`。

# 关键决定与偏差

授权仍只取自 `/v1/auth/me`，不从店铺名称列表推断。未增加缓存或后台服务；没有后端、接口、迁移、配置、平台写入及自动发送行为变化。此变更只消除页面初始化的一次串行等待，不能消除入口网络抖动。

# 验证交接

先观察新增用例失败，再实施并复测；完整结果与未完成的现场验收见 [TR R16](../../reports/tests/TR-MVP-STAGING-LATENCY-001-20261029-R16.md)。租户边界和失败状态审查见 [RR R13](../../reports/reviews/RR-MVP-STAGING-LATENCY-001-20261029-R13.md)。

# 限制、风险与回滚

完整公网、跨店和真实平台异常验收未完成，任务保持 `VERIFYING`。若发布后发生回归，仅把前端镜像切回发布前精确摘要，保留数据库和其他业务增量。
