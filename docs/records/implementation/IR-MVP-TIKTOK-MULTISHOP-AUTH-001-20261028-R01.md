---
record_id: IR-MVP-TIKTOK-MULTISHOP-AUTH-001-20261028-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-TIKTOK-MULTISHOP-AUTH-001
base_sha: 48c079fb36475f429cd86e4b6365cebd9e1abb43
final_sha: bfb470e5e76d1ddc52facee21708ffead73c16d3
requirement_ids: [MVP-TIKTOK-MULTISHOP-AUTH-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
test_record: docs/reports/tests/TR-MVP-TIKTOK-MULTISHOP-AUTH-001-20261028-R01.md
review_record: docs/reports/reviews/RR-MVP-TIKTOK-MULTISHOP-AUTH-001-20261028-R01.md
created_at: 2026-10-28T09:09:46Z
updated_at: 2026-10-28T09:09:46Z
supersedes: null
---

# 实施目标与范围

`tkw api` Custom 应用一次卖家授权返回多家店铺时，由原发起系统管理员明确选择接入店铺；每家店保持独立 CRM 店铺 ID、权限和业务历史。本轮仅在本地开发、测试和合并，不部署 staging 或 production，不调用真实 TikTok。

# 实际变更及原因

- OAuth worker 对单店继续自动连接；对多店保存 10 分钟加密授权材料并返回低敏候选清单。选择接口重新核对 Token、Scope、平台店铺和本地绑定，行锁及唯一约束保护原子提交。
- 新增卖家级加密凭证与渠道关联。共享 Token 按卖家行锁一次轮换、逐店核验授权；读取仍从当前渠道取得其专属 `shop_cipher`。单店旧密文路径保留，平台返回新增店铺时旧店可继续刷新。
- 旧单店重新授权时保留店铺 ID 并迁入共享凭证。共享凭证轮换前复核所有受影响在线店铺的渠道管理权；删除或平台撤销一家店不会停用其他在线店。
- 店铺页增加多店勾选和暂存后继续入口；前后端与真实 PostgreSQL 集成测试覆盖关键路径。

# 关键决定与偏差

多店采用卖家级 Token、店铺级渠道绑定。一次最多接受并选择 200 家店铺，以限制平台响应和选择提交规模。单店继续旧格式，待重授权或新增多店时平滑迁移；没有批量改写既有凭证。

# 数据、配置、接口与迁移影响

迁移 `035_tiktok_seller_multishop` 新增 `tiktok_seller_authorizations`、渠道可空外键、OAuth 待选择字段；无新环境变量。新增 `POST /settings/channels/tiktok/oauth/jobs/{job_id}/shops`，任务状态增加 `selection_required`。已有共享授权或待选择任务时迁移降级失败关闭，需先显式处理数据。当前事实文档已同步至 API、SYSTEM 和 PRODUCT。

# 验证交接

最终 subject `bfb470e5e76d1ddc52facee21708ffead73c16d3` 的完整命令与结果见 [TR](../../reports/tests/TR-MVP-TIKTOK-MULTISHOP-AUTH-001-20261028-R01.md)；安全与兼容审查见 [RR](../../reports/reviews/RR-MVP-TIKTOK-MULTISHOP-AUTH-001-20261028-R01.md)。

# 限制、风险与回滚

真实 TikTok 多店授权、Webhook 与人工发送仍需独立 staging 验收。回滚前先确认是否存在共享授权或待选择任务；有数据时 `035` 拒绝降级，不能直接覆盖或丢弃店铺历史。
