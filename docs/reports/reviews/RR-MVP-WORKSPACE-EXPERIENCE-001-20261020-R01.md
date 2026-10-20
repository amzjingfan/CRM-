---
record_id: RR-MVP-WORKSPACE-EXPERIENCE-001-20261020-R01
record_type: review
revision: R01
status: APPROVE
task_id: MVP-WORKSPACE-EXPERIENCE-001
reviewed_sha: 1aff6dfd4302c64c9e1c7394f1ebd9898b3652c4
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-EXPERIENCE-001-20261020-R01.md
test_record: docs/reports/tests/TR-MVP-WORKSPACE-EXPERIENCE-001-20261020-R01.md
review_focus: [correctness, tenant-permission, send-boundary, idempotency-audit, migration-rollback]
created_at: 2026-10-20T05:03:00Z
updated_at: 2026-10-20T05:19:29Z
supersedes: null
---

# 审查范围、依据与重点风险

审查 `BASE_SHA=d0ba04575407abdeddb66525467aaf9bf6f14621` 至候选 SHA 的工作台前后端、会话同步、迁移及测试。重点核对每会话未读、历史阅读位置、AI 草稿不会自动发送、同店坐席转交、CRM 内部关闭、真实平台消息发送边界，以及迁移回退的数据影响。

# 发现、级别、位置和证据

- 审查发现只读同步缺少增量未读补记，已在候选内按上次成功同步时间修复并增加测试；首次历史回填不产生旧消息未读。
- 审查发现 `filter=closed` 可被冲突的 `status` 参数覆盖，已在候选内使已关闭筛选始终限定关闭会话，并增加 PostgreSQL 负向用例。
- `workspace.transfer`、CSRF 和店铺授权共同守护新写接口；指定坐席限同店在职且有 `workspace.reply`，转交前后重新校验。消息发送服务与工具层均拒绝已关闭会话；关闭前拒绝有 `processing`/`unknown` 的出站消息。星标与关闭重复设置不新增审计。
- 迁移 `025_workspace_actions` 增加非空默认星标与可空 UTC 关闭时间，提供 downgrade；实际回退会丢弃这两列的数据，部署后须先备份和审查，不自动执行。

# 已验证与未验证内容

合并 SHA 上完整后端 2216 passed、3 skipped；前端契约 47 passed、合成浏览器 34 passed，静态检查、类型检查和构建通过。首次 DeepSeek canary 曾有一次未复现的合成请求失败，已在 TR 保留；后续单项和两轮完整回归通过。尚无 staging 迁移或真实买家现场验证。本次没有扩大 TikTok 真实发送白名单，没有自动回复、外部消息、生产发布或新付费资源。

# 结论和返修条件

`APPROVE` 本地会话体验与操作改造的源码及证据。真实店铺部署前必须另行执行迁移、健康、权限和恢复门禁；本 RR 不代表任何运行环境已部署或生产放行。
