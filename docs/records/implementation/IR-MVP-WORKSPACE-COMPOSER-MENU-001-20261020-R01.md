---
record_id: IR-MVP-WORKSPACE-COMPOSER-MENU-001-20261020-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-WORKSPACE-COMPOSER-MENU-001
base_sha: d13872c92a3d0d1ba40a9dc5e5b46e29be52e3c5
final_sha: fdb08729d7decd74f473c9f6dfc25d2a5e919415
requirement_ids: [MVP-WORKSPACE-COMPOSER-MENU-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
test_record: docs/reports/tests/TR-MVP-WORKSPACE-COMPOSER-MENU-001-20261020-R01.md
review_record: docs/reports/reviews/RR-MVP-WORKSPACE-COMPOSER-MENU-001-20261020-R01.md
created_at: 2026-10-20T12:06:01Z
updated_at: 2026-10-20T13:07:03Z
supersedes: null
---

# 实施目标与范围

按用户三张发送栏参考图，在现有 TikTok 人工辅助工作台内提供目标语言菜单、译文预览、直接发送/翻译后发送分流和 2000 字计数。保持原有确认发送、单店许可、CSRF、幂等与审计边界；本任务不向买家发送测试消息，不发布 production。

# 实际变更及原因

- 工作台输入区改为 2000 字上限；Enter 打开人工审阅，Shift+Enter 换行，并处理中文输入法组合态。底部并排显示计数、目标语言、翻译和分割发送按钮。
- 英语作为初始目标语言，通过“更多”选择印尼语、菲律宾语、马来语、泰语、缅甸语、越南语、葡萄牙语、西班牙语、波兰语、法语、繁体中文和简体中文。切换草稿、语言或会话会使旧预览失效；异步译文若与当前草稿不符，不进入审阅。
- “直接发送”审阅原文；“翻译后发送”复用当前译文或先调用现有受控翻译端点，然后审阅准确待发送文字。实际平台发送仍须点击原有独立确认，失败关闭及请求幂等键沿用既有逻辑。
- 后端翻译目标语言契约与前端一致；翻译 Prompt 从 `workspace-draft-translation-v1.0.0` 更新至 `v1.1.0`，注册的 SHA-256 为 `2609e877099f69ab0b4d91f8e70876baeef756eee52d9cc2a374066c57b66bd2`。同步 API/AI 文档与回归测试。

# 关键决定与偏差

参考图中的“发送”动作在本产品中保持人工审阅与二次确认，以免误向真实 TikTok 买家外发。翻译仍由现有 `WORKSPACE_MESSAGE_TRANSLATION_ENABLED` 和已授权 DeepSeek 通路控制；未增加自动发送、营销或其他平台真实接入。

# 数据、配置、接口、迁移或 Prompt 影响

`DraftTargetLanguage`、工作台翻译请求 schema 与前端 API 类型扩展到上述 13 种语言。无新数据库迁移，无新增持久化配置；翻译结果仅按当前草稿临时预览。Prompt 版本和注册摘要已更新。

# 验证交接

源码 PR [#475](https://github.com/CP11-gh/CRM/pull/475) 已 squash 合入 `main=fdb08729d7decd74f473c9f6dfc25d2a5e919415`，合并树与已测候选构建输入相同。该源码构建的前后端不可变镜像已通过 staging 手动 validate/deploy，已登录工作台的菜单、译文预览和人工审阅已现场核对。结果见关联 TR、RR 和[低敏部署证据](../../../release/evidence/staging/crm-staging-composer-menu-deploy-20261020.json)。

# 限制、风险与回滚

没有逐语言真实买家发送或译文质量评估。本次 staging 候选后端与前端以不可变摘要部署，保留前版镜像和受限 PostgreSQL 备份；恢复前须保护部署后新增会话消息，不能直接用旧备份覆盖。Production G8 No-Go 不变。
