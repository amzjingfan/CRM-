---
record_id: IR-MVP-WORKSPACE-TIKTOK-RICH-MESSAGES-001-20261030-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-WORKSPACE-TIKTOK-RICH-MESSAGES-001
base_sha: 5564a491548c0174478c575568a06b533b5c4885
final_sha: 60265d6566fca45ef1196ac777ea281be0662016
requirement_ids: [MVP-WORKSPACE-TIKTOK-RICH-MESSAGES-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
test_record: docs/reports/tests/TR-MVP-WORKSPACE-TIKTOK-RICH-MESSAGES-001-20261030-R01.md
review_record: docs/reports/reviews/RR-MVP-WORKSPACE-TIKTOK-RICH-MESSAGES-001-20261030-R01.md
created_at: 2026-10-30T15:58:12Z
updated_at: 2026-10-30T15:58:12Z
supersedes: null
---

# 实施目标与范围

修复工作台把 TikTok 买家图片和商品卡片显示为 `[TikTok 类型]` 的问题，并核对同一消息链路的视频、表情和其余官方卡片类型。只改变消息读取、持久化和展示，不发送或修改平台消息。

# 实际变更及原因

原 Webhook 适配器对非文本只生成类型占位，持久化又固定为 text；历史同步也只保留 content，未请求平台结构化 data/plaintext。现用共同解析器提取媒体 HTTPS URL、封面、视频 ID 与商品/订单/物流/优惠券/售后卡片所需字段。Webhook 与历史同步均保存平台类型及最小展示快照，工作台分别呈现图片、可播放的平台视频、表情和原生卡片；多包裹物流卡片保留各包裹。旧占位由 staging 专用只读 `--refresh-rich` 按平台消息 ID 修复；普通增量同步节奏不变。

# 关键决定与偏差

只保存业务展示必需字段，不持久化完整第三方响应。视频只使用 TikTok 返回的播放 URL，不从 vid 构造。链接不可信时不渲染；平台签名视频 URL 过期或加载失败时展示封面及提示。图片/卡片使用平台实际字段，缺失不补造。历史回填不会产生新的未读或外发。

# 数据、配置、接口、迁移或 Prompt 影响

现有消息表 `message_type` 与 `raw_payload` 承载新增结构，无迁移、无新服务、无配置开关。工作台 `MessageView` 增加 `rich_card`，`media` 补充封面、时长与过期时间；TikTok 消息只读请求增加 `need_data=true` 和 `need_plaintext=true`。仅对已连接授权店铺执行既有只读 Scope 请求。

# 验证交接

最终代码 subject 为 `60265d6566fca45ef1196ac777ea281be0662016`；测试与限制见对应 TR，公共展示契约、安全和隔离审查见 RR。当前 main 还含未批准部署的 Agent 模板批次，发布时必须使用不带入该功能的受审 staging 候选。

# 限制、风险与回滚

本记录只确认源码实施；staging 部署和旧消息现场补录尚未执行。平台返回的短期视频链接到期后可能无法播放；不能因此猜测长期地址。回滚代码可恢复旧镜像摘要，已有富消息展示快照可保留；不得用旧备份覆盖发布后的业务增量。
