---
record_id: RR-MVP-WORKSPACE-MEDIA-SEND-001-20261023-R01
record_type: review
revision: R01
status: APPROVE
task_id: MVP-WORKSPACE-MEDIA-SEND-001
reviewed_sha: b457da5f6e72f6a63aeced994beaf4ab40da8712
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-MEDIA-SEND-001-20261023-R01.md
test_record: docs/reports/tests/TR-MVP-WORKSPACE-MEDIA-SEND-001-20261023-R01.md
review_focus: [human-confirmation, store-isolation, csrf, idempotency, fixed-egress, upload-url, unknown-reconciliation, staging-boundary]
created_at: 2026-10-23T10:38:40Z
updated_at: 2026-10-23T10:38:40Z
supersedes: null
---

# 审查范围、依据与重点风险

审查新增媒体上传、签名凭据、工具层发送、前端二次确认及 Nginx 精确路径。官方客服 Send Message 与图片上传文档、官方大文件分片文档是协议依据；用户只批准图片及 10–100 MiB 视频范围。源提交为 `b457da5f6e72f6a63aeced994beaf4ab40da8712`。

# 发现、级别、位置和证据

- 上传在服务端通过当前用户允许的店铺查找会话，并再次检查 TikTok 渠道、Scope、令牌有效期和真实发送白名单。发送时工具层重新锁定会话及店铺，不信任客户端提供的 URL 或 `vid`。
- 原草稿凭据只绑定坐席/店铺/会话，允许改用另一幂等键重复发送。已修为上传和发送共用同一幂等键，工具层验签时校验，定向测试覆盖换键拒绝。
- 视频上传 URL 是平台返回的外部输入；现在只允许 HTTPS 官方 `open-api.tiktokglobalshop.com/file/`，禁止用户信息、显式端口和重定向。所有请求复用固定出口。
- 前端在审阅前不发上传或发送请求，取消零请求；后端仍要求 `confirmed:true`、CSRF、权限和幂等键。上传审计只记录类型与字节数，不记录文件内容或上传凭据。
- 平台消息写入沿用一次发送和 `unknown` 人工对账。上传失败不会创建发给买家的消息；确认后若结果未知，不得重新以新键发送。

# 已验证与未验证内容

已审阅上述边界及 TR 的合成测试结果。未执行真实 TikTok 买家发送、staging 两层代理运行配置验收或 production 发布；本审查批准候选代码，不构成部署放行。

# 结论和返修条件

当前提交未发现未关闭的高优先级代码缺陷。若官方媒体契约、凭据绑定、发送状态机或代理配置发生变化，需要重新审查。父分支依赖和 GitHub CI 仍须独立通过。
