---
record_id: RR-MVP-WORKSPACE-SEARCH-TRANSLATION-001-20261020-R01
record_type: review
revision: R01
status: APPROVE
task_id: MVP-WORKSPACE-SEARCH-TRANSLATION-001
reviewed_sha: d40e904346d3b378ecabe228f9e4de6fabc813c8
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-SEARCH-TRANSLATION-001-20261020-R01.md
test_record: docs/reports/tests/TR-MVP-WORKSPACE-SEARCH-TRANSLATION-001-20261020-R01.md
review_focus: [correctness, tenant-permission, sensitive-data, translation-boundary, manual-send]
created_at: 2026-10-20T08:19:25Z
updated_at: 2026-10-20T08:19:25Z
supersedes: null
---

# 审查范围、依据与重点风险

自查 `BASE_SHA=692363950192eb67224dc39f6477333fec0799b4` 至 subject 的搜索查询、公共 API、翻译 Prompt/服务、界面发送状态及测试。重点核对跨店关联、搜索词泄漏、模型输入低敏边界、真实发送范围和失败重试收件人。

# 发现、级别、位置和证据

- PostgreSQL 首轮发现最新消息搜索的 `EXISTS` 自动关联错误，已用显式 `correlate(Conversation)` 修复；完整回归 2223/2223 通过。
- 自查发现失败外发草稿可能在切换会话后与当前收件人混淆；重试记录绑定原会话、原消息和幂等键，仅在原会话呈现，浏览器负向用例通过。
- 搜索在数据库分页前执行，并将订单约束到同店、同平台、同买家；跨店订单及 SQL 通配符负向用例通过。搜索词只在 JSON 请求体中传输；用户 URL 不含查询词。
- 译文服务须通过店铺授权、可发送会话和现有翻译开关；DLP 不允许偷偷改写输入或译文。Prompt 把草稿视为数据，结构化输出、目标语言一致且长度受限。预览、审阅和实际发送是三个独立步骤；现有人工发送权限、CSRF、幂等及审计继续适用。

# 已验证与未验证内容

隔离 PostgreSQL 2223 passed/3 skipped、前端契约 47 passed、合成浏览器 38 passed，构建、类型、lint 和格式检查通过。未调用真实 DeepSeek、未向 TikTok 买家发送新消息，尚未验证 staging 的镜像、运行配置或真实会话现场表现。

# 结论和返修条件

`APPROVE` 本地源码与测试证据。staging 发布须单独按手动门禁验证；若观察到跨店结果、译文未经审阅外发或未知发送结果自动重试，应停止发布并返修。production 仍受 G8 No-Go 约束。
