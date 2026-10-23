---
record_id: IR-MVP-KNOWLEDGE-SIDEBAR-DIALOG-001-20261023-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-KNOWLEDGE-SIDEBAR-DIALOG-001
base_sha: bc542e7b34d7eac3ac97db0bb97b43ef74772cdb
final_sha: f7950619487a853fa2c6afb27ff6a0ca1bd76fdc
requirement_ids: [MVP-KNOWLEDGE-SIDEBAR-DIALOG-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
test_record: docs/reports/tests/TR-MVP-KNOWLEDGE-SIDEBAR-DIALOG-001-20261023-R01.md
review_record: null
created_at: 2026-10-23T02:00:18Z
updated_at: 2026-10-23T02:00:18Z
supersedes: null
---

# 实施目标与范围

修复用户在 staging 知识库页面标注的两个问题：移除侧栏“按知识层级查看”整块入口；把自定义分类删除的原生浏览器确认框换成与知识库现有样式一致的站内弹窗。用户明确选择整块移除层级区块。

# 实际变更及原因

- 删除知识库页 A/B/C/D 层级侧栏及其页面状态、查询和 URL 参数；旧 `layer` 链接进入页面后回到“全部知识”，避免隐形筛选。
- 删除分类按钮先展示包含分类名称、空分类限制与不可恢复提示的站内确认弹窗。取消、Escape 和遮罩关闭不发请求；确认后才调用原有删除接口。提交中不能重复或关闭；失败保留分类并显示服务端错误，成功关闭弹窗并刷新侧栏、选中状态及 URL。
- 更新原有浏览器与前端合同测试。未修改 Agent 管理、后端、检索、公共 API、数据库或运行配置。

# 关键决定与偏差

继续使用原服务端的店铺授权、空分类和子分类校验；前端只负责明确提示与防止误触。预置分类仍不显示删除按钮。没有添加依赖。

# 数据、配置、接口、迁移或 Prompt 影响

无。`layer` 仍可由后端接口处理，但知识库页面不再生成、恢复或提交该筛选参数。

# 验证交接

见 [TR R01](../../reports/tests/TR-MVP-KNOWLEDGE-SIDEBAR-DIALOG-001-20261023-R01.md)。本地生产构建、前端合同和浏览器回归通过；staging 发布与现场复核待续记录。

# 限制、风险与回滚

本轮不操作真实分类或外发消息。需要回滚时，将 staging 前端恢复到先前不可变摘要并核对页面和原有运行模式。production 仍为 No-Go。
