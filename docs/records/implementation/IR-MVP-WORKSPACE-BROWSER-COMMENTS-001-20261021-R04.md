---
record_id: IR-MVP-WORKSPACE-BROWSER-COMMENTS-001-20261021-R04
record_type: implementation
revision: R04
status: FINAL
task_id: MVP-WORKSPACE-BROWSER-COMMENTS-001
base_sha: 770ec69a60418c177dff0a6b2dd1658756902ed6
final_sha: ef0ec3aa4948c22c5823646abf5a0019e8c9ede0
requirement_ids: [MVP-WORKSPACE-BROWSER-COMMENTS-001]
acceptance_ids: [AC-02, AC-03]
test_record: docs/reports/tests/TR-MVP-WORKSPACE-BROWSER-COMMENTS-001-20261021-R04.md
review_record: docs/reports/reviews/RR-MVP-WORKSPACE-BROWSER-COMMENTS-001-20261021-R04.md
created_at: 2026-10-21T10:27:16Z
updated_at: 2026-10-21T10:27:16Z
supersedes: docs/records/implementation/IR-MVP-WORKSPACE-BROWSER-COMMENTS-001-20261021-R03.md
---

# 实施目标与范围

用户现场确认 staging 物流状态为中文且按需翻译成功，进一步明确要求译文替换英文原文显示，不在下方另起一行。此轮沿原任务返修物流描述的前端呈现。

# 实际变更及原因

- 翻译成功后在描述原位置显示中文，按钮改为“查看原文”；切回英文后显示“查看译文”，切换不重复请求模型。
- 详情刷新清除旧译文；失败时保留英文原文与重试入口。更新产品事实及合成浏览器用例，断言同一位置只显示当前语言并可切回。
- 源码 PR #495 squash 合入 `main=f98dca4ed81110d6bb1d2084a084b8c5789f1e97`；本地对比确认业务代码和测试树与 subject 一致。

# 关键决定与偏差

保留可查看原文的小按钮，便于坐席核对承运商原话。未改变后端翻译接口、模型、审计、店铺/买家核对或人工发送范围。

# 数据、配置、接口、迁移或 Prompt 影响

无数据结构、配置、公共接口、迁移或 Prompt 变化。前后端镜像使用同一合入 SHA 的 OCI revision；后端代码内容与上轮相同，仅为手动部署门禁生成新 revision 镜像。

# 验证交接、限制、风险与回滚

本地与 staging 验证见 TR R04；镜像、私有备份、预取和部署摘要见 `release/evidence/staging/crm-staging-workspace-tracking-display-20261021.json`。旧镜像均保留可回滚。真实已登录页面由用户确认译文原位替换与原文切换；内置浏览器读取超时，故不声称工具直接观察了真实订单。Production G8 No-Go。
