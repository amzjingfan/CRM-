---
record_id: IR-MVP-WORKSPACE-BROWSER-FEEDBACK-001-20261023-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-WORKSPACE-BROWSER-FEEDBACK-001
base_sha: 323bbf73054c6a5719d7a20e87211a51206cb8bb
final_sha: 6dac69e7c205252fcefa7e44720bdd2b9ae9bdec
requirement_ids: [MVP-WORKSPACE-BROWSER-FEEDBACK-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05, AC-06]
test_record: docs/reports/tests/TR-MVP-WORKSPACE-BROWSER-FEEDBACK-001-20261023-R01.md
review_record: docs/reports/reviews/RR-MVP-WORKSPACE-BROWSER-FEEDBACK-001-20261023-R01.md
created_at: 2026-10-23T09:29:46Z
updated_at: 2026-10-23T09:29:46Z
supersedes: null
---

# 实施目标与范围

按 staging 标注修复基础接待的入口结构和工作台的快捷回复、表情、复制、头像、买家阶段与会话卡右键操作。买家阶段以最近订单状态自动判断，可人工覆盖并恢复自动。图片、视频外发另按官方上传接口和现有人工确认工具链实施，本 subject 不启用媒体外发。

# 实际变更及原因

- 智能营销侧栏默认收起，展开后只列营销流程和基础接待；三个接待配置页使用页内标签。根接待路径指向快捷回复。
- 快捷回复浮层可跳转管理页；表情库扩至 36 项并支持点击外部及 Escape 关闭；复制订单与物流编号显示结果。
- 买家头像使用用户名的前三个 Unicode 字符，坐席与机器人头像分别显示；会话卡右键或 Shift+F10 可星标、转交、关闭，后两项仍沿用原选择与确认流程。
- 买家阶段默认从最近订单状态推断；`PATCH /workspace/sessions/{session_id}/buyer-stage` 在会话店铺鉴权后保存客户画像覆盖值，null 恢复自动，变更写低敏审计。复用 `Customer.metadata_json`，无迁移。
- 为使全仓格式门禁通过，顺带格式化基线中 `test_document_schema.py` 的既有导入和排版；未改变其断言。

# 关键决定与偏差

用户明确“主要按订单状态自动显示，也可以手动选择”。未找到订单视为售前；未知订单状态显示待判断，避免错误断定。列表与详情共用客户覆盖值，切换会话后由服务端再次读取。无订单数据、真实媒体发送与生产部署不在本 subject 的浏览器验收中。

# 数据、配置、接口、迁移或 Prompt 影响

新增受 `workspace.reply`、CSRF 和店铺访问权约束的阶段覆盖接口，数据仅存阶段枚举，审计不存订单或聊天内容。无数据库迁移、外部 TikTok 写入、配置或 Prompt 变化。`PRODUCT.md`、`API.md`、`SYSTEM.md` 已同步。

# 验证交接

本地测试、构建、风险审查与未执行项见关联 TR/RR。回滚 subject 可恢复原侧栏和工作台交互；若已保存人工阶段覆盖，回滚后元数据键保留但旧版忽略，重新部署可继续读取。
