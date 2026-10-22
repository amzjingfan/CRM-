---
record_id: RR-MVP-SETTINGS-TIKTOK-STORES-001-20261022-R01
record_type: review
revision: R01
status: APPROVE
task_id: MVP-SETTINGS-TIKTOK-STORES-001
reviewed_sha: 76767ed78682614e78ef66fedcd1284a43f2256f
implementation_record: docs/records/implementation/IR-MVP-SETTINGS-TIKTOK-STORES-001-20261022-R01.md
test_record: docs/reports/tests/TR-MVP-SETTINGS-TIKTOK-STORES-001-20261022-R01.md
review_focus: [oauth-state, tenant-isolation, credential-revocation, webhook, migration, staging-boundary]
created_at: 2026-10-22T10:20:07Z
updated_at: 2026-10-22T10:20:07Z
supersedes: null
---

# 审查范围与依据

对受审提交的店铺列表、新店及原店 OAuth、渠道删除、Webhook、目标店铺权限和迁移做独立只读安全审查，并根据审查结果修正实现；复核定向与完整回归结论。

# 发现与修正

发现原实现只按 Refresh Token 期限显示状态、把无 TikTok 渠道的内部店铺放进授权列表、隐藏平台侧解除授权的异常店铺。现取更早的真实授权期限，筛掉无 TikTok 渠道的店铺，仅隐藏使用者本地删除的记录，保留平台失效行供重新添加。

发现本地删除后 TikTok 仍可能投递消息/订单 Webhook，甚至已有通知排队。本提交在入站拒绝断开渠道的非生命周期新通知，在 worker 持渠道行锁再次核验并清除被忽略的载荷；晚到生命周期通知保留本地删除标记。另修复全局合并角色导致的跨店铺别名修改、删除和重新授权借权，要求目标店铺的管理员或渠道管理权限。

# 已验证、未验证与结论

后端 2260 passed/30 skipped、前端契约 48/48、生产浏览器 62/62、Ruff、mypy、typecheck、lint 和 build 通过。未执行真实卖家授权、staging 迁移/发布、真实店铺删除或 production 回滚。受审源码可进入 PR 与受限 staging 部署，任务继续 `VERIFYING`；staging 证据和真实页面确认需后续 TR 修订，不得把本地 Mock 当作现场验收。
