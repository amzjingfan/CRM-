---
record_id: IR-MVP-WORKSPACE-TIKTOK-RICH-MESSAGES-001-20261031-R02
record_type: implementation
revision: R02
status: FINAL
task_id: MVP-WORKSPACE-TIKTOK-RICH-MESSAGES-001
base_sha: 5564a491548c0174478c575568a06b533b5c4885
final_sha: 60265d6566fca45ef1196ac777ea281be0662016
requirement_ids: [MVP-WORKSPACE-TIKTOK-RICH-MESSAGES-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
test_record: docs/reports/tests/TR-MVP-WORKSPACE-TIKTOK-RICH-MESSAGES-001-20261031-R02.md
review_record: docs/reports/reviews/RR-MVP-WORKSPACE-TIKTOK-RICH-MESSAGES-001-20261031-R02.md
created_at: 2026-10-30T16:53:52Z
updated_at: 2026-10-30T17:43:07Z
supersedes: docs/records/implementation/IR-MVP-WORKSPACE-TIKTOK-RICH-MESSAGES-001-20261030-R01.md
---

# 实施目标与范围

将已合并的 TikTok 富消息修复发布到 staging，按平台消息 ID 补齐两家授权店铺的旧占位消息。只读 TikTok 历史接口和本地消息更新，不向买家发送消息。

# 实际变更及原因

产品实现沿用 R01 的共同解析器、Webhook/历史同步、工作台 API 和前端渲染。源码 PR #678 squash 合入主线 `d67078db7445b1ef71a35af095075b1280f0d70c`。发布前现场发现 staging 实际运行 `fbacb37299c4793ef166b2123e111b24095001b0`、迁移 `046_merge_templates_dispatch`，而非旧记录中的 045。对比已部署源码与当前主线后，产品代码差异只有本富消息修复，因此从干净合并主线构建并直接部署精确前后端镜像，保留既有 Agent 模板运行状态及 046 数据库。

# 关键决定与偏差

未使用此前基于 045 的选择性 hotfix 候选，避免降级现有 staging。GitHub Actions 未用于部署；镜像由本地从 d670 构建并以摘要传至 staging。GHCR 远端拉取卡住后，核对同一镜像摘要和传输包校验值，再经现有 SSH 导入，随后重新执行 ValidateOnly。旧消息逐会话调用官方只读接口，按平台 ID 幂等更新；无实时发送或自动回复开关变化。

# 数据、配置、接口、迁移或 Prompt 影响

无新增迁移或配置。staging 原 046 保持为 head。既有两店人工真实发送允许列表、Webhook 读取、Agent 调试/建议及文档导入保持；自动回复、营销和高风险 TikTok 写入继续关闭。历史富消息在现有 `message_type`/`raw_payload` 列补齐可信展示字段，绝不写入完整第三方载荷。

# 验证交接

产品 subject `60265d6566fca45ef1196ac777ea281be0662016`，部署源码 `d67078db7445b1ef71a35af095075b1280f0d70c`。精确镜像、私有备份、两次 ValidateOnly、Deploy、运行健康、历史补录和只读 UI 核验见 TR R02 与 `release/evidence/staging/crm-staging-tiktok-rich-messages-20261031.json`；发布审查见 RR R02。官方最近会话列表没有覆盖 31 个旧会话，因此通过官方单会话只读接口定向补录，最终两店类型占位清零。

# 限制、风险与回滚

TikTok 未返回可播放视频 URL 或签名 URL 过期时只显示封面和提示，不能凭视频 ID 推造地址；平台卡片缺失字段也不补造。回滚优先切回发布前精确前后端摘要，保留 046 和发布后业务增量；不能用旧备份直接覆盖新增消息。
