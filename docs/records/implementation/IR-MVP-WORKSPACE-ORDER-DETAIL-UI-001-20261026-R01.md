---
record_id: IR-MVP-WORKSPACE-ORDER-DETAIL-UI-001-20261026-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-WORKSPACE-ORDER-DETAIL-UI-001
base_sha: b79fe557ef24d930098e534867822f5f8d4dbf33
final_sha: 5ff30c11120344e7b65df568542eff7f32dd5b36
requirement_ids: [MVP-WORKSPACE-ORDER-DETAIL-UI-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
test_record: docs/reports/tests/TR-MVP-WORKSPACE-ORDER-DETAIL-UI-001-20261026-R01.md
review_record: docs/reports/reviews/RR-MVP-WORKSPACE-ORDER-DETAIL-UI-001-20261026-R01.md
created_at: 2026-10-26T06:30:23Z
updated_at: 2026-10-26T06:30:23Z
supersedes: null
---

# 实施目标与范围

根据用户三张 staging 标注，调整工作台订单详情的订单、物流和商品分区；保持只读及现有人工发送边界。

# 实际变更及原因

- 官方订单模型接收 `recipient_address.name/phone_number/full_address`。核验会话、店铺、官方买家和订单 ID 后，详情响应原样投影这三个字段。
- 订单区展示订单号、支付方式、收件电话与地址；物流默认显示最新两条，可展开全部平台节点；商品区展示商品规格和卖家 SKU，不以平台 SKU ID 冒充规格。
- 补充后端身份与字段投影测试、前端合成浏览器交互测试，并同步产品与 API 当前文档。

# 关键决定与偏差

平台对部分订单可能不提供收件信息或只给掩码；页面按实际值显示，缺失显示“—”，不进行解密或推断。订单列表响应不含收件字段；详情请求仍走既有 `workspace.view`、CSRF、店铺和买家核验。

# 数据、配置、接口、迁移或 Prompt 影响

`POST /workspace/sessions/{session_id}/sidebar/orders/detail` 增加可空 `recipient_address` 对象；不落库、不改变权限、配置、迁移或 Prompt。前端能容忍旧后端暂未返回该字段。

# 验证交接

候选源码 `5ff30c11120344e7b65df568542eff7f32dd5b36` 的本地完整结果见 [TR R01](../../reports/tests/TR-MVP-WORKSPACE-ORDER-DETAIL-UI-001-20261026-R01.md)，敏感字段与隔离审查见 [RR R01](../../reports/reviews/RR-MVP-WORKSPACE-ORDER-DETAIL-UI-001-20261026-R01.md)。staging 部署及真实订单核对尚待单独记录。

# 限制、风险与回滚

合成测试无法证明某个真实订单的地址是否由 TikTok 返回。若需回滚，本变更没有迁移；恢复旧前后端镜像并复核原运行模式，保留部署后业务增量。production 仍受 G8 No-Go 约束。
