---
record_id: IR-MVP-WORKSPACE-TRACKING-TIMELINE-001-20261022-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-WORKSPACE-TRACKING-TIMELINE-001
base_sha: b58e4d99427c09fb89b9938c93d063550865183b
final_sha: 475f585c10fa543b0d3550a4426f97f935cf6786
requirement_ids: [MVP-WORKSPACE-TRACKING-TIMELINE-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
test_record: docs/reports/tests/TR-MVP-WORKSPACE-TRACKING-TIMELINE-001-20261022-R01.md
review_record: docs/reports/reviews/RR-MVP-WORKSPACE-TRACKING-TIMELINE-001-20261022-R01.md
created_at: 2026-10-22T02:20:11Z
updated_at: 2026-10-22T02:40:47Z
supersedes: null
---

# 实施目标与范围

在已授权买家的订单卡物流状态旁按需打开轨迹弹层，展示 TikTok 已返回的完整节点；复制全部包裹文本、下载当前包裹 PNG，并对单个节点按需翻译且可切回原文。没有新增物流写入或买家消息发送。

# 实际变更及原因

- 订单详情继续使用已现场验证的通用 `202309` 接口，保留其全部节点而非仅取最新一条。由于该接口没有可靠包裹归属，只投影一个订单轨迹组；多个商品行单号不会被用来虚构包裹。
- 新增受保护的跨境增强轨迹 POST：先核对会话店铺、官方买家 IM ID、订单域买家 ID 和数字订单 ID，再限定 `seller_type=CROSS_BORDER` 调用现有 `202604` 只读适配器。Redis 按店铺 cipher 摘要及订单原子占位；成功或失败冷却均为八小时。增强轨迹失败时浏览器保留通用轨迹。
- 前端使用固定定位弹层避免窄侧栏裁切，按官方包裹切换并保留历史节点单号。复制与 PNG 生成在浏览器本地完成。节点翻译复用现有 DeepSeek 开关、速率限制、DLP 和低敏审计，服务端精确核对待翻译节点，模型不能读取客户端伪造的物流文本。
- 同步当前产品、系统和 API 文档；没有迁移、配置或新增前端依赖。

# 验证交接与限制

源码 [PR #506](https://github.com/CP11-gh/CRM/pull/506) squash 合入 `main=1f74077a56136cbd705d35251a3afd76849f82b6`；受影响构建输入与 subject 完全相同。按此合并 SHA 构建两个 `linux/amd64` 镜像，经私有归档哈希核对转入 staging Rootless Docker，使用现有 GHCR 凭据发布不可变摘要；旧三摘要、原单店人工发送与翻译范围保留。六摘要预取、受审 staging validate/deploy、私有数据库备份、迁移头、固定出口和运行摘要均已核对，见对应 TR 与[低敏部署证据](../../../release/evidence/staging/crm-staging-workspace-tracking-timeline-20261022.json)。

当前授权店铺没有已确认的真实跨境首程样本；增强接口的多包裹行为由确定性用例验证，不以此声称真实跨境通过。已部署页面的合成浏览器通过；Codex 对用户登录态标签读取超时，视觉点击结果待用户核对。GitHub Actions 本次两个 PR 作业在零步骤失败，不计 CI。生产 G8 保持 No-Go。
