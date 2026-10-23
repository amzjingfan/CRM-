---
record_id: IR-MVP-KNOWLEDGE-CATEGORY-DELETE-DEPLOY-001-20261023-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-KNOWLEDGE-CATEGORY-DELETE-DEPLOY-001
base_sha: 2ccc93b2939781ae68e35abe6c3ef4470f69ab69
final_sha: 2ccc93b2939781ae68e35abe6c3ef4470f69ab69
requirement_ids: [MVP-KNOWLEDGE-CATEGORY-DELETE-DEPLOY-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
test_record: docs/reports/tests/TR-MVP-KNOWLEDGE-CATEGORY-DELETE-DEPLOY-001-20261023-R01.md
review_record: null
created_at: 2026-10-23T01:23:48Z
updated_at: 2026-10-23T01:23:48Z
supersedes: null
---

# 实施目标与范围

将已合并的知识库自定义分类删除 UI 发布到现有 staging。用户只授权 staging；本次不改源码、公共接口、数据结构、运行配置或 production。源功能见 [PR #532](https://github.com/CP11-gh/CRM/pull/532) 及原任务记录。

# 实际变更及原因

- 以当时权威 `main=2ccc93b2939781ae68e35abe6c3ef4470f69ab69` 的干净 Git bundle 构建 `linux/amd64` 前端镜像，OCI revision 与该 SHA 一致。相比现场原版本，后端、检索、部署配置和 Docker 构建输入均未变，因此只替换前端。新前端不可变摘要为 `sha256:4290e793e40ebf250e622a8733f9420bf0f64f143f5740959e4acf2962c99a30`；旧前端摘要为 `sha256:b0bc4ff9f2eab8a0192e938189a252016457de067070f71e9b62e35d8cebc9de`。
- 官方前端镜像发布 [Actions 运行](https://github.com/CP11-gh/CRM/actions/runs/39881715896) 在零步骤失败，未提供构建或测试结果。本次改用手动 Docker 构建、推送并记录推送摘要；远端 manifest 二次查询遇 TLS 超时，不将其记为通过。staging 导入的镜像标签、摘要和 OCI revision 已核对。
- 在冻结原三镜像摘要及单店人工发送、Webhook 读取、工作台翻译模式后，完成六角色不可变镜像预取、`ValidateOnly`、私有 PostgreSQL 备份及 `pg_restore -l` 可读检查，再执行 staging `Deploy`。部署门禁原件留在 staging 私有目录；低敏摘要见 [部署证据](../../../release/evidence/staging/crm-staging-knowledge-category-delete-20261023.json)。

# 关键决定与偏差

沿用原后端 `sha256:b3598ebf39c1982937528d1b834008764add6886c4f7347733b849f7aabeebf0` 和检索服务 `sha256:feeee5a3327bc7d18e49bf534dad431adcb12a3089b025bb068a687662523059`。镜像发布走人工替代路径，但 staging 部署仍经过既有 Rootless 门禁。未扩大店铺、发送或自动化权限。

# 数据、配置、接口、迁移或 Prompt 影响

无新增迁移或接口。数据库迁移头保持 `027_tiktok_direct_store_oauth`；现有单店人工发送、Webhook 读取、工作台翻译模式保持，SSE、高风险写入和自动回复未启用。

# 验证交接

同任务 [TR R01](../../reports/tests/TR-MVP-KNOWLEDGE-CATEGORY-DELETE-DEPLOY-001-20261023-R01.md) 记录本次构建、门禁、运行健康及已部署资源的合成浏览器交互。无真实店铺数据修改或外部消息发送；真实登录态页面未直接验收。

# 限制、风险与回滚

上一版三个不可变摘要及私有备份、模式快照已冻结。需要回滚时用现有 staging 回滚门禁恢复旧前端摘要并重查模式、健康与页面；数据库备份用于既有恢复流程。本次不需要逆向迁移。production G8 仍为 No-Go。
