---
record_id: IR-MVP-WORKSPACE-SEARCH-TRANSLATION-001-20261020-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-WORKSPACE-SEARCH-TRANSLATION-001
base_sha: 692363950192eb67224dc39f6477333fec0799b4
final_sha: d40e904346d3b378ecabe228f9e4de6fabc813c8
requirement_ids: [MVP-WORKSPACE-SEARCH-TRANSLATION-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
test_record: docs/reports/tests/TR-MVP-WORKSPACE-SEARCH-TRANSLATION-001-20261020-R01.md
review_record: docs/reports/reviews/RR-MVP-WORKSPACE-SEARCH-TRANSLATION-001-20261020-R01.md
created_at: 2026-10-20T08:19:25Z
updated_at: 2026-10-20T08:19:25Z
supersedes: null
---

# 实施目标与范围

按已确认原型实施工作台第 3 项统一会话搜索与第 5 项多语言人工回复。保留现有 TikTok 单店真实发送边界，不启用自动回复、其他店铺真实发送或 production。

# 实际变更及原因

- 服务端先按授权店铺、状态和平台筛选，再对买家昵称、订单号、物流号、商品名/ID/SKU 或最新消息预览进行大小写无关匹配；多词使用 OR，过滤后统计总数并稳定分页。订单关联同时约束店铺、平台和买家，通配符按普通字符处理。
- 搜索词改用 `POST /workspace/sessions/search` 的 JSON 请求体，工作台提供单项范围和最多 20 项的批量搜索；刷新及加载更多沿用同一条件，搜索词不写入 URL。
- 坐席可选英语、印尼语、西班牙语、葡萄牙语、法语、泰语，按需调用已配置 DeepSeek 生成低敏译文预览。改动草稿、语言或会话会使预览失效；审阅弹窗显示准确外发文字，只有再次点击确认才调用现有幂等发送接口。失败重试绑定原会话和原幂等键。
- 翻译路由使用 `workspace.reply`、CSRF、频率限制、发送范围和 DLP 检查；记录不含正文的审计元数据。新增受版本和哈希约束的翻译 Prompt。

# 关键决定与偏差

翻译是人工触发的预览，服务端不调用 TikTok 发送接口。用户已批准使用项目现有 DeepSeek 翻译能力；本地测试全部使用合成 Provider/API，不产生真实买家消息或付费模型调用。工作台仍允许“原文”发送，且继续使用原有真实发送授权范围。

# 数据、配置、接口、迁移或 Prompt 影响

新增两个工作台 POST API 和详情响应中的 `draft_translation_enabled`；更新 `docs/architecture/API.md`、`SYSTEM.md`、`AI.md`、`PRODUCT.md` 及部署说明。新增 `workspace-draft-translation-v1.0.0`，Prompt SHA-256 为 `8fd9e9ef5c735cfc0e60ebec3c5a5ffe599cd1600721a2d16e12364754947f4e`。无数据库迁移、依赖或新的运行环境变量。

# 验证交接

精确 subject SHA 为 `d40e904346d3b378ecabe228f9e4de6fabc813c8`；测试命令、全量数量和已修复的首轮失败见关联 TR。店铺隔离、人工发送边界与风险审查见关联 RR。IR/TR/RR 后续仅作为证据与任务控制提交，不更改交付源码。

# 限制、风险与回滚

本记录只证明本地实现，不代表 staging 或 production 已部署。真实 DeepSeek 可用性、译文质量与真实买家接收需在受控环境分别验收；模型译文必须人工核对。代码回滚可恢复先前搜索与输入界面；既有发送消息不可撤销，不能通过重试未知结果来回滚。
