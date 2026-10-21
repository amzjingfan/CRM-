---
record_id: TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-DEPLOY-001-20261021-R02
record_type: test
revision: R02
status: PARTIAL
task_id: MVP-WORKSPACE-CUSTOMER-SIDEBAR-DEPLOY-001
tested_sha: 15ceabf8eac90f2fe8c7843e24af26381c3e0499
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-DEPLOY-001-20261021-R02.md
requirement_ids: [MVP-WORKSPACE-CUSTOMER-SIDEBAR-DEPLOY-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: staging Rootless Docker; public HTTPS; customer sidebar UI pending authenticated refresh
created_at: 2026-10-21T02:42:00Z
updated_at: 2026-10-21T02:42:00Z
supersedes: docs/reports/tests/TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-DEPLOY-001-20261021-R01.md
---

# 本次验证

- 用户发布前的三张真实 staging 截图显示订单各状态字段、商品状态和优惠券原始枚举/金额结构与原型不符；对应源码行为、类型和合成浏览器验证见[字段修复 TR](TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-FIELDS-001-20261021-R01.md)。
- 手动构建并发布合并 main 的 backend `sha256:317081db…2a7cd0`、frontend `sha256:c6a38d5f…5a6c8b`；二者 OCI revision 均为 `15ceabf8eac90f2fe8c7843e24af26381c3e0499`。检索镜像不变。
- 源码 `CheckOnly` 通过；staging 私有 `pg_dump` 为 382089 字节，权限 `0600`；六角色不可变摘要预取通过；手动 `ValidateOnly=validated`、`Deploy=passed`。私有原件 SHA 与摘要见[低敏部署证据](../../../../release/evidence/staging/crm-staging-customer-sidebar-real-fields-deploy-20261021.json)。
- 运行 11 服务、backend/frontend 健康，迁移头已应用、固定 TikTok 出口通过；`/healthz`、`/v1/health`、`/v1/health/ready` 现场均为 200。原单店人工发送及翻译模式保持，自动回复与高风险写入关闭。
- Codex 应用内浏览器新标签仍连续超时，记 `UI_UNAVAILABLE`；发布后的真实订单、SKU 与优惠券卡片仍需用户刷新截图确认。未向买家外发、退款或发券。

# 结论与复测条件

AC-01、AC-02、AC-04 已取得现场证据。AC-03 的发布后已登录 UI 验收未完成，因此本记录 `PARTIAL`，部署任务保持 `VERIFYING`。取得三张发布后页面截图并逐项核对后更新记录；若仍不匹配，应继续修复。
