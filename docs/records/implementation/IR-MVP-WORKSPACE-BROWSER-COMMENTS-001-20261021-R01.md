---
record_id: IR-MVP-WORKSPACE-BROWSER-COMMENTS-001-20261021-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-WORKSPACE-BROWSER-COMMENTS-001
base_sha: 96f84491ecbfda3e0879295b996e4e33b5a090ba
final_sha: 975430475a03d04d91ccc6142eecfb8e0e70aaa7
requirement_ids: [MVP-WORKSPACE-BROWSER-COMMENTS-001]
acceptance_ids: [AC-01, AC-02, AC-03]
test_record: docs/reports/tests/TR-MVP-WORKSPACE-BROWSER-COMMENTS-001-20261021-R01.md
review_record: docs/reports/reviews/RR-MVP-WORKSPACE-BROWSER-COMMENTS-001-20261021-R01.md
created_at: 2026-10-21T07:15:44Z
updated_at: 2026-10-21T07:15:44Z
supersedes: null
---

# 实施目标与范围

修复用户在 staging 工作台标注的十项会话列表、AI 草稿、订单和商品侧栏行为。范围限于授权工作台只读展示及人工编辑，不改变买家发送、退款和发券边界。

# 实际变更及原因

- 会话列表接口新增可访问、未关闭会话的未读消息总数；列表触底自动翻页，失败显示手动重试。搜索框识别逗号、分号和换行分隔的多个词，移除独立批量按钮。主动生成的 AI 建议写入当前可编辑草稿，仍需人工确认发送。
- 订单卡片显示期间等待可见订单详情返回，让付款与物流字段一起呈现；订单号、商品名、SPU、规格、SKU 和货号增加小复制控件。物流状态依次使用已有结构化状态、订单物流阶段及平台原始最新轨迹描述。
- 商品卡片进入可视区且列表无图时读取现有受权详情以取得图片；SKU 表首列改为商品规格，规格和货号可复制。商品列表触底按平台游标自动翻页。

# 关键决定与偏差

官方不同轨迹接口示例的数值动作码含义并不一致，因此没有新增基于动作码的阶段推断。真实订单详情和商品图片受平台请求延迟限制；界面在数据齐备后整卡呈现，失败提供原有重试入口。

# 数据、配置、接口、迁移或 Prompt 影响

工作台会话列表响应增加非破坏性字段 `unread_messages_total`，已同步 API 文档。无数据库迁移、新平台 Scope、Prompt、模型或高风险平台写入。进入可视区的商品卡片可能多一次既有只读详情调用。

# 验证交接

本地测试见 TR R01；源码审查见 RR R01。staging 手动发布与登录态现场核对另行补证，不能把本地合成浏览器结果作为真实店铺验收。

# 限制、风险与回滚

上游无图片、SKU 或轨迹时继续显示空值；不猜测物流阶段。staging 回滚仅切回部署前后端、前端的不可变镜像摘要，保留业务数据与私有恢复点。
