---
record_id: IR-MVP-TIKTOK-ALL-STORE-MANUAL-SEND-001-20261030-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-TIKTOK-ALL-STORE-MANUAL-SEND-001
base_sha: 18a0d7bb0b0ca6b2bb601de32af7128d1a41a9ec
final_sha: 18a0d7bb0b0ca6b2bb601de32af7128d1a41a9ec
requirement_ids: [REQ-01]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
test_record: docs/reports/tests/TR-MVP-TIKTOK-ALL-STORE-MANUAL-SEND-001-20261030-R01.md
review_record: docs/reports/reviews/RR-MVP-TIKTOK-ALL-STORE-MANUAL-SEND-001-20261030-R01.md
created_at: 2026-10-30T04:10:46+00:00
updated_at: 2026-10-30T04:10:46+00:00
supersedes: null
---

# 实施目标与范围

在 staging 对所有现存且已授权接入 TikTok 客服渠道的店铺开放坐席人工确认发送。自动回复、营销和高风险平台写入继续关闭；不向真实买家发送测试消息，不发布 production。

# 实际变更及原因

- 部署时三家保留店铺中，「TikTok US 测试店铺」和「XBM」均有 connected 渠道、`seller.customer_service` Scope、shop cipher 和可解密且可用的 Token；两店的只读 TikTok 会话查询成功。「测试店铺」没有 TikTok 渠道，也没有会话，因此不进入 allowlist。
- 使用当前 staging 已运行、且与干净 `origin/main` 一致的 `18a0d7bb` 前后端不可变镜像；仅将 backend 的 `TIKTOK_MESSAGE_WRITE_ALLOWED_STORE_IDS` 从一店扩大到上述两店。现有 Worker、Jobs、Agent Worker、Webhook、翻译、Agent 调试与人工建议模式原样保留。
- 使用同一源码的 staging 门禁完成 ValidateOnly 与 Deploy。迁移仍是 `044_reception_assignment`，未改数据库结构或私有默认环境文件。
- 按用户要求，在没有 TikTok 渠道的「测试店铺」暂建两个合成坐席、配置及咨询，开启派单验证并发容量与幂等；随后精确删除测试行，派单配置回到 0。

# 关键决定与偏差

“所有店铺”按当前已授权且已接入 TikTok 客服渠道解释；未接入店铺不能预先放行，避免以后接入时无审查地获得真实发送能力。此次派单测试通过 staging 数据库服务链路，因「测试店铺」未连接 TikTok，不声称验证了真实平台入站。

# 数据、配置、接口、迁移或 Prompt 影响

只有 backend 的人工发送店铺名单变化。现有服务层仍检查店铺归属、渠道状态、Scope、Token 时效、会话状态和坐席权限；接口、迁移与 Prompt 均未改。私有备份包含环境、PostgreSQL custom dump 和 MinIO archive。

# 验证交接

逐店只读发送模式、全部运行开关、私有备份、门禁摘要、三健康及合成派单清理见 [TR R01](../../reports/tests/TR-MVP-TIKTOK-ALL-STORE-MANUAL-SEND-001-20261030-R01.md) 和[低敏机器证据](../../../release/evidence/staging/crm-staging-all-store-manual-send-20261030.json)。

# 限制、风险与回滚

没有向真实买家外发以验证平台实际接收，也没有演练真实 TikTok 入站派单。若要回退人工发送范围，使用相同四个镜像摘要与安全开关，经 ValidateOnly/Deploy 将 allowlist 恢复为原单店；不得用旧数据库备份覆盖部署后新业务数据。
