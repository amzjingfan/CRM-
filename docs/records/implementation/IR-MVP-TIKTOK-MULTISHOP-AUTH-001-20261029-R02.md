---
record_id: IR-MVP-TIKTOK-MULTISHOP-AUTH-001-20261029-R02
record_type: implementation
revision: R02
status: FINAL
task_id: MVP-TIKTOK-MULTISHOP-AUTH-001
base_sha: 7cee8b4cf5703b1f4bd3213a7219e3162f4272e0
final_sha: c289a9a07e9a71b244b6a07b93a56f9f57e3f699
requirement_ids: [MVP-TIKTOK-MULTISHOP-AUTH-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
test_record: docs/reports/tests/TR-MVP-TIKTOK-MULTISHOP-AUTH-001-20261029-R02.md
review_record: docs/reports/reviews/RR-MVP-TIKTOK-MULTISHOP-AUTH-001-20261029-R02.md
created_at: 2026-10-29T01:23:33Z
updated_at: 2026-10-29T01:23:33Z
supersedes: docs/records/implementation/IR-MVP-TIKTOK-MULTISHOP-AUTH-001-20261028-R01.md
---

# 实施目标与范围

将 R01 已在本地验证的 `tkw api` Custom 应用多店授权功能集成至权威 `origin/main`，供统一 staging 发布。此次不操作 staging/production、不调用真实 TikTok，也不执行平台发送；现场部署由独立 `MVP-AGENT-STAGING-DEPLOY-001` 单点执行。

# 实际变更及原因

- 从 `origin/main=7cee8b4c` 建立隔离分支，移植 R01 的卖家级共享凭证、OAuth 多店选择、逐店授权隔离、兼容单店路径、前端交互和行为测试。
- 主线 Agent 迁移已从 `034` 延伸到 `040_agent_collaboration`。新增 `041_merge_agent_multishop_collab` 汇合该链与独立 TikTok `035_tiktok_seller_multishop`，保持唯一 Alembic 头。
- 店铺页沿用主线的 `/settings/store-authorizations` 聚合读取，增入多店选择流程；浏览器回归同时保留主线的即时回显、刷新失败与权限撤销测试。
- 同步产品、API、系统架构与迁移说明，不改变现有真实发送白名单、Agent 正式执行或生产门禁。

# 关键决定与偏差

保留旧单店凭证与既有 `Store` ID；共享卖家 Token 只在已选择店铺完成逐店绑定，刷新与撤销仍按原有店铺权限失败关闭。R01 的旧基线测试不作为本次联合版本证据，全部适用验证在集成树重跑。

# 数据、配置、接口与迁移影响

`035_tiktok_seller_multishop` 新增共享授权表、渠道关联和 OAuth 待选择字段；`041` 只合流历史，不另写表。多店选择 API 与低敏任务状态见 `docs/architecture/API.md`。本功能无新环境变量；部署需先备份，并由统一发布门禁检查 staging 的实际迁移路径。

# 验证交接

最终功能 subject 为 `c289a9a07e9a71b244b6a07b93a56f9f57e3f699`。联合回归见 [TR](../../reports/tests/TR-MVP-TIKTOK-MULTISHOP-AUTH-001-20261029-R02.md)，合流与授权安全审查见 [RR](../../reports/reviews/RR-MVP-TIKTOK-MULTISHOP-AUTH-001-20261029-R02.md)。

# 限制、风险与回滚

真实卖家多店授权、Webhook、逐店读取及人工发送仍须 staging 现场验证，不由合成测试推定通过。已有共享授权或待选择任务时 TikTok `035` 拒绝直接降级；不得删除店铺历史或凭证来制造回滚通过。production G8 仍为 No-Go。
