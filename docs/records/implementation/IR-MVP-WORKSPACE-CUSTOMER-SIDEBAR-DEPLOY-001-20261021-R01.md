---
record_id: IR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-DEPLOY-001-20261021-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-WORKSPACE-CUSTOMER-SIDEBAR-DEPLOY-001
base_sha: 433f340de451202e776c41ae1a59739f90dc385e
final_sha: 433f340de451202e776c41ae1a59739f90dc385e
requirement_ids: [MVP-WORKSPACE-CUSTOMER-SIDEBAR-DEPLOY-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
test_record: docs/reports/tests/TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-DEPLOY-001-20261021-R01.md
review_record: docs/reports/reviews/RR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-DEPLOY-001-20261021-R01.md
created_at: 2026-10-20T17:36:39Z
updated_at: 2026-10-20T17:36:39Z
supersedes: null
---

# 实施目标与范围

将已合并客户侧栏及真实买家订单只读修复，从 `main=433f340de451202e776c41ae1a59739f90dc385e` 手动发布 staging，核对订单、商品、优惠券读取。仅保留原一个店铺的人工发送边界；不发送买家消息、不进行退款或发券、不发布 production。

# 实际变更及原因

- 从精确合并主线构建并核对后端镜像 `ghcr.io/cp11-gh/crm-backend@sha256:67da479a185419d08f356c24ce3ff018315573ab39dea897c3364d5bbcc22281` 与前端镜像 `ghcr.io/cp11-gh/crm-frontend@sha256:d3a9f84a489075c977becfff01263356f3fe955e94e4646bc063903abc2b1de0`；检索服务保持 `sha256:feeee5a3…23059`。
- staging 使用现有手动门禁 `validate/deploy`；发布前保留旧镜像和运行模式的私有快照，以及模式 `0600` 的 PostgreSQL 备份。未执行新迁移。
- 服务层真实只读探针在已授权会话查到官方买家订单 1 笔，带金额、商品和物流；订单号搜索命中 1 笔，未授权会话返回 404。当前店铺商品总数 27、优惠券总数 19。

# 关键决定与偏差

用户要求尽量不用 CI/CD，本轮以手动构建、门禁与健康作为发布依据。已登录 Codex 浏览器连接连续超时，标记 `UI_UNAVAILABLE`；服务层成功不等于侧栏视觉与交互验收。

# 数据、配置、接口、迁移或 Prompt 影响

部署复用已合并源码；数据库仍位于 `025_workspace_actions`。原单店人工发送、Webhook 读取和工作台翻译开关保持，`production_release=false`。

# 验证交接

预检为 `validated`、部署为 `passed`；Rootless Docker 11 个容器运行，公网 `/healthz`、`/v1/health`、`/v1/health/ready` 均 HTTP 200，固定 TikTok 出口通过。低敏证据见[预检](../../../release/evidence/staging/crm-staging-customer-sidebar-orders-validate-20261021.json)、[部署](../../../release/evidence/staging/crm-staging-customer-sidebar-orders-deploy-20261021.json)、[只读核对](../../../release/evidence/staging/crm-staging-customer-sidebar-orders-readonly-20261021.json)及关联 TR/RR。

# 限制、风险与回滚

真实登录态客户侧栏截图尚未核对，部署任务保持 VERIFYING。恢复前须保护发布后新增消息，不能直接用旧数据库备份覆盖。旧镜像与受限备份保留；production G8 No-Go。
