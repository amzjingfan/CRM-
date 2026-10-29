---
record_id: RR-MVP-TIKTOK-MULTISHOP-AUTH-001-20261028-R01
record_type: review
revision: R01
status: APPROVE
task_id: MVP-TIKTOK-MULTISHOP-AUTH-001
reviewed_sha: bfb470e5e76d1ddc52facee21708ffead73c16d3
implementation_record: docs/records/implementation/IR-MVP-TIKTOK-MULTISHOP-AUTH-001-20261028-R01.md
test_record: docs/reports/tests/TR-MVP-TIKTOK-MULTISHOP-AUTH-001-20261028-R01.md
review_focus: [authorization, store_isolation, token_lifecycle, migration, regression]
created_at: 2026-10-28T09:09:46Z
updated_at: 2026-10-28T09:09:46Z
supersedes: null
---

# 审查范围、依据与重点风险

只读独立审查与主任务复核覆盖 `48c079fb36475f429cd86e4b6365cebd9e1abb43..bfb470e5e76d1ddc52facee21708ffead73c16d3` 的 OAuth、共享 Token、店铺删除、Webhook、迁移、前端选择及测试。重点核查跨店权限、既有单店兼容、并发刷新/撤销、凭证不泄露与失败关闭。

# 发现、级别、位置和证据

- P1 跨店重授权：初稿仅校验目标店权限，可能连带更新兄弟店。已在共享凭证轮换前逐店核验在线渠道管理权；新增 A 店管理员无权改变 B 店及卖家凭证的测试。
- P1 单店刷新：初稿仍要求平台清单恰好一家，会在卖家新增第二店后误过期旧店。已改为核对目标店 ID 且拒绝重复 ID；新增兼容回归。
- P2 选择与撤销竞态：选中既有渠道读取改为 `FOR UPDATE`，并在冲突测试断言请求锁。真实双会话交错尚未单独实演。
- P2 暂存选择恢复：保留 job URL，页内提供“继续选择店铺”入口；生产浏览器回归覆盖关闭和重开。平台清单上限由旧 20 调整为 200，21 家契约测试通过。

# 已验证与未验证内容

独立审查复核上述四项修复后给出 APPROVE。最终 subject 上完整后端 2459 passed/3 skipped、前端生产浏览器 114/114、契约 49/49、静态与迁移往返结果见 [TR](../tests/TR-MVP-TIKTOK-MULTISHOP-AUTH-001-20261028-R01.md)。未核对真实 TikTok 平台或 staging 运行，未做真实双会话撤销竞态现场测试。

# 结论和返修条件

本地分支可合并，未发现当前范围阻断项。若正式环境出现不同授权清单、迁移冲突或跨店状态变动，保持失败关闭并在部署前修复、重跑受影响验证和审查；本记录不构成 staging/production 放行。
