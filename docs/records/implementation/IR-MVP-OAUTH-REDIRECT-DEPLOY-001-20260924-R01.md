---
record_id: IR-MVP-OAUTH-REDIRECT-DEPLOY-001-20260924-R01
record_type: implementation
revision: R01
status: DRAFT
task_id: MVP-OAUTH-REDIRECT-DEPLOY-001
base_sha: c72406349c56f55f9e433b64523b3626682c4adb
final_sha: c72406349c56f55f9e433b64523b3626682c4adb
requirement_ids: [MVP-OAUTH-REDIRECT-DEPLOY-001]
acceptance_ids: [staging-image, migration, health, isolation, real-oauth-callback]
test_record: docs/reports/tests/TR-MVP-OAUTH-REDIRECT-DEPLOY-001-20260924-R01.md
review_record: null
created_at: 2026-09-24T18:10:00+08:00
updated_at: 2026-09-24T18:10:00+08:00
supersedes: null
---

# 实施目标与范围

将已由 PR #53 合并的 TikTok OAuth 快速回跳代码仅部署到 staging；production 与边缘入口配置不变。真实平台成功回跳仍是本任务剩余验收，不能用镜像健康或合成测试代替。

# 实际变更及原因

- 镜像发布 `35975910518`、全新摘要预检 `35977258653` 成功。完整三新镜像部署 `35977511412` 的两次尝试均在首个 GHCR 拉取缓慢、迁移和容器切换之前取消；旧服务、023 迁移头与公网健康复核无漂移。
- 用户随后明确批准**仅本次 staging**保留旧检索镜像。活动 env 只将检索摘要恢复为 `bc99dfa3...`，与变更前 root-only 备份逐字节一致，`crmdeploy:crmdeploy:0600` 不变。混合摘要预检 `35981557122`、部署 `35981850368` 成功。
- 业务机实际运行新 backend/helper/worker/jobs/agent `3421003e...`、新 frontend `33d7f388...`、原健康检索 `bc99dfa3...`；数据库到 `024_tiktok_oauth_jobs`。固定出口配置/观测均为 `38.55.145.52`，三个公网健康 200。公司 system Docker 与边缘 vhost 集合 SHA 均无变化。

# 关键决定与偏差

旧检索镜像的源码及 Dockerfile 输入虽与新候选一致，后端依赖清单及锁文件不同，不能称为新镜像或版本等价。用户授权只适用于这一次 staging；下一次部署及 production 不继承。普通 Chrome 重授权被 TikTok 官方以卖家类型不适用拒绝，错误发生在 callback 前；真实成功页自动回跳与后台 job 完成未测，因此任务保持 `VERIFYING`。

# 数据、配置、接口、迁移或 Prompt 影响

仅 staging 应用/数据库迁移至 024；没有 production 迁移、真实能力开关扩大、密钥明文输出、边缘 Nginx 改动或其他公司容器改动。新 OAuth job 状态 API 未登录返回 401，合成无效 callback 返回 400；这些只验证失败关闭，不证明真实 303。

# 验证交接

正式低敏现场证据见 `release/evidence/staging/crm-staging-oauth-redirect-rollout-20260924.json`，首次尝试见同目录 `crm-staging-oauth-redirect-rollout-attempt-20260924.json`。代码/隔离数据库回归由 `MVP-OAUTH-REDIRECT-001` R01 绑定；本次部署证据与未执行项见本任务 TR R01。

# 限制、风险与回滚

业务机 root-only 恢复点 `/var/backups/crm-staging/releases/20260924T0835Z-c724063-oauth` 的 PostgreSQL dump、MinIO archive 和旧 env 均可读；未实际执行数据库/对象恢复或上一版镜像兼容回滚，属 `MVP-008`。若 staging 异常，先按受限恢复点与不可变上一版摘要执行专门回滚门禁，不得猜测恢复成功。Partner Center 美国目标卖家已勾选跨境商家（中国），编辑菜单没有单列香港；不能仅凭 `seller_base_region=HK` 认定缺项。真实 TikTok 回跳待用户核对授权页跨境入口和店铺主账号资格后由本人重新授权验证；若仍被平台拒绝，需走官方支持。未完成前不关闭本任务或启动 G1 真实店铺验收。
