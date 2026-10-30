---
record_id: IR-MVP-DEPARTMENT-AUTO-ASSIGN-001-20261030-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-DEPARTMENT-AUTO-ASSIGN-001
base_sha: c7ba0f4c2ce725b9e7672ce24db73f60b235f4af
final_sha: dcc2ada1eb3290c64857b4b5e5e0328402f4281d
requirement_ids: [REQ-01, REQ-02, REQ-03, REQ-04]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
test_record: docs/reports/tests/TR-MVP-DEPARTMENT-AUTO-ASSIGN-001-20261030-R01.md
review_record: docs/reports/reviews/RR-MVP-DEPARTMENT-AUTO-ASSIGN-001-20261030-R01.md
created_at: 2026-10-30T01:47:04+08:00
updated_at: 2026-10-30T01:47:04+08:00
supersedes: null
---

# 实施目标与范围

在单客服部内提供固定角色、逐店人工接待资格及默认关闭的自动派单。普通客服可转交本人负责的会话给同店合格客服；派单只更改 CRM 内部归属，不自动回复买家。

# 实际变更及原因

- 新增逐店派单配置、接单名册、工作台短期在线心跳、待处理容量、失败原因、队列重试及低敏分配记录。Webhook 与增量同步的新买家消息进入同一幂等派单逻辑。
- 有效候选须在职、属于客服部、具备该店人工回复权限、参与该店派单、在线且未达上限；先找 72 小时内同店近期人工服务者，再按待处理量、最久未分配和稳定账号 ID 排序。
- 手工归属优先且不会被自动重派覆盖；自动归属离线且有新买家消息时经过宽限可回到队列。无候选保留未分配并记具体原因。
- 工作台与工具执行在服务端再次校验店铺操作权限和会话归属；主管看到同店队列、接管提醒及分配历史，普通客服只能处理本人会话或领取未分配会话。
- 部门管理展示固定角色能力、逐店接待配置和队列状态；告警以已保存店铺配置为准。

# 关键决定与偏差

不新增任意权限编辑器。部门成员关系不自动授予店铺权限。自动派单逐店显式开启；主管默认不参与派单。保留现有人工发送、安全开关与单个主接待人模型。

# 数据、配置、接口、迁移或 Prompt 影响

迁移 `044_reception_assignment` 新增接待配置、在线状态、归属来源和分配记录，未重写历史归属。新增接待配置与心跳 API，会话响应附带可操作能力和待接管状态；接口与架构文档已同步。无 Prompt、模型或外部发送接口变化。

# 验证交接

本地全量结果见关联 TR；审查见关联 RR。AC-05 的 staging 部署尚需用户单独批准及发布门禁，PR 合并不代表发布。

# 限制、风险与回滚

未以真实 TikTok 入站或真实坐席在 staging 验收。发布前需备份和 ValidateOnly，确认默认关闭配置；回滚先关闭逐店派单，再恢复应用与数据库备份，并保留已产生审计。production 不在范围内。
