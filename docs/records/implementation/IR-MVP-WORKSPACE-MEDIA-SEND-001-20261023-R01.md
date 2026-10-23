---
record_id: IR-MVP-WORKSPACE-MEDIA-SEND-001-20261023-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-WORKSPACE-MEDIA-SEND-001
base_sha: d6926c08d08365b91c2315338893187e23c90996
final_sha: b457da5f6e72f6a63aeced994beaf4ab40da8712
requirement_ids: [MVP-WORKSPACE-MEDIA-SEND-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
test_record: docs/reports/tests/TR-MVP-WORKSPACE-MEDIA-SEND-001-20261023-R01.md
review_record: docs/reports/reviews/RR-MVP-WORKSPACE-MEDIA-SEND-001-20261023-R01.md
created_at: 2026-10-23T10:38:40Z
updated_at: 2026-10-23T10:38:40Z
supersedes: null
---

# 实施目标与范围

在工作台已核准的真实 TikTok 人工发送会话中开放图片和视频。图片限 JPG/PNG/GIF/WebP 且不超过 10 MiB；视频限 MP4/MOV/WebM 且为 10–100 MiB。用户选择文件后先看到收件人与预览，只有再次确认才上传并调用一次平台消息接口。小于 10 MiB 的视频明确提示不支持。

# 实际变更及原因

- 工作台添加文件选择、媒体审阅、取消零请求、错误反馈和消息展示。上传与发送分别调用两个受 CSRF 和 `workspace.reply` 保护的接口。
- 后端校验授权店铺、会话、真实发送白名单、有效 TikTok 客服 Scope、MIME、文件头及大小。图片用官方客服图片上传接口；视频经固定出口初始化并顺序分片，上传 URL 限定官方域名和路径。
- 上传只返回以服务端密钥签发的 20 分钟凭据，绑定坐席、店铺、会话和发送幂等键。人工二次确认后，工具层重新核对凭据及目标，复用既有消息状态机、同店未结清熔断、幂等、审计和未知结果人工对账。
- 三份 Nginx 配置仅为精确媒体上传路径设置 105 MiB 请求体和 720 秒上游读取超时；其他路由维持原上限。

# 关键决定与偏差

用户选择“先支持已核实范围”。目前没有核实 10 MiB 以下客服视频直传接口，因此不开放该范围。媒体文件不存入 CRM 数据库；上传完成但未发送的 TikTok 资源可能自然过期。视频只保存平台 `vid`，不合成播放地址。本分支从工作台浏览器反馈分支建立，须在父分支合入后再合流。

# 数据、配置、接口、迁移或 Prompt 影响

新增 `POST /workspace/sessions/{id}/messages/media/upload` 和 `POST /workspace/sessions/{id}/messages/media`；两者共用 `Idempotency-Key`。不新增迁移、密钥或自动发送开关。更新 API、系统、产品和部署当前文档。staging 和 production 均未部署；没有真实买家外发。

# 验证交接与回滚

测试与未执行项见 TR；风险审查见 RR。回滚先禁用界面入口并恢复原前后端及三份 Nginx 配置；已发送消息不可撤销，`unknown` 必须先核对平台事实。
