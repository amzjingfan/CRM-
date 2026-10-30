---
record_id: IR-MVP-AGENT-TEMPLATE-BATCH-001-20261030-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-AGENT-TEMPLATE-BATCH-001
base_sha: 1eb6dbd1fa44688660fb2809ae3df8ee19108027
final_sha: 831abbcc1510ca71e6ed572408884f789a7ce506
requirement_ids: [MVP-AGENT-TEMPLATE-BATCH-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05, AC-06, AC-07, AC-08, AC-09, AC-10]
test_record: docs/reports/tests/TR-MVP-AGENT-TEMPLATE-BATCH-001-20261030-R01.md
review_record: docs/reports/reviews/RR-MVP-AGENT-TEMPLATE-BATCH-001-20261030-R01.md
created_at: 2026-10-30T12:22:19.880339+00:00
updated_at: 2026-10-30T13:56:53.688132+00:00
supersedes: null
---

# 目标与实际范围

减少多店重复建立 Agent 的操作：系统管理员维护版本化模板，按店铺查看三方差异、映射本店文件，确认后由现有后端持续执行批次。仅本地开发和验证；发布模板、发布 Agent、启用 Agent 和部署仍是不同动作。

# 实现及原因

- `app.agents.management.templates` 管理模板草稿、不可变发布版本、字段基线、知识槽、冻结预览、逐店结果及 SQL 租约处理器。复用现有单体、模型复核、Agent 发布事务及运行器，未新增运行服务或依赖。
- 前端增加模板库、逐店差异与文件映射向导、持久批次页及草稿/运行版本来源。模型作为 provider/name 对比较；七段 Prompt、工具集合和知识槽逐字段处理，名称/编码用于创建，本店 reply_profile 不被模板覆盖。
- 确认只接受冻结 preview_id 和显式 confirmation，使用幂等键；后台重新校验确认人、店铺权限、revision、依赖及租约令牌。模型复核在写事务外，配置、不可变版本、关联、审计和结果在同一短事务提交。取消不撤销成功项，重试不重复发布成功项。
- 来源区分应用版本、审阅版本和本店覆盖；部分更新不会虚报全部跟随新模板。实际文件仅能绑定同店有效文件，归档、撤批或删除会阻断发布；解除模板关联保留 Agent 与已有运行历史。
- 主线整合至 `57c9e7dd`（包含0fc部门功能及后续文案/发布事实）后保留两条045历史，新增 `046_merge_templates_dispatch` 合流。普通 Agent 列表/详情/日志按逐店 agent.view，创建/修改/发布/启停/删除/调试按逐店 agent.manage；部门会话范围不扩展 Agent 配置权限。

# 统一修复与审查

原完整源审发现的锁后身份/权限校验、无变化发布文案、页面卸载尾随请求，以及新增主线引入的普通 Agent 范围交互均在同一功能分支修复。真实锁等待与 JWT/HTTP/PG 回归覆盖实际调用路径；失败与测试编写错误分别保留，不降低门禁。最终定点复审和全量结论以关联 RR/TR 为准。

补充最终视觉修复：390px下新增模板按钮导致保存动作被卡片裁切；配置工具栏改为换行并限制宽度，保留按钮顺序和实际保存行为。浏览器用例验证初始/未保存两状态的完整几何范围与PATCH内容，先等待独立异步模板权限加载。

# 恢复与边界

本轮没有 staging/production 部署、真实买家发送或付费模型调用。将来部署前须独立批准、备份并核对046及安全开关。已有模板/来源/批次数据时降级保护继续拒绝破坏性回退；优先停止新入口/处理器并保留业务历史，结构恢复须另行验证。未知前端 AGENTS 与活动 worktree 保留；五个已确认缓存仅可恢复隔离，未永久删除。
