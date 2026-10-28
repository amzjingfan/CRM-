---
record_id: TR-MVP-OAUTH-REDIRECT-DEPLOY-001-20260924-R01
record_type: test
revision: R01
status: PARTIAL
task_id: MVP-OAUTH-REDIRECT-DEPLOY-001
tested_sha: c72406349c56f55f9e433b64523b3626682c4adb
implementation_record: docs/records/implementation/IR-MVP-OAUTH-REDIRECT-DEPLOY-001-20260924-R01.md
requirement_ids: [MVP-OAUTH-REDIRECT-DEPLOY-001]
acceptance_ids: [staging-image, migration, health, isolation, real-oauth-callback]
environment: staging split-ingress; 38.55.145.52 BaoTa Nginx/TLS; 192.168.110.210 rootless CRM; production unchanged
created_at: 2026-09-24T18:10:00+08:00
updated_at: 2026-09-24T18:10:00+08:00
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

项目测试源码位于 `src/tests/`；正式现场低敏证据在 `release/evidence/staging/crm-staging-oauth-redirect-rollout-20260924.json` 与 `crm-staging-oauth-redirect-rollout-attempt-20260924.json`。本记录只评价合并代码的 staging 部署和真实回跳门禁，不扩大为 production 或完整 G1。

# 命令和逐项结果

- 镜像发布 `35975910518` 成功；三新摘要预检 `35977258653` 成功。部署 `35977511412` 的两次 GHCR 慢链路尝试在迁移前取消，随后旧容器、023 迁移头和公网健康 200 经现场核对。
- 用户只授权本次 staging 的旧检索摘要，混合预检 `35981557122` 与部署 `35981850368` 成功；下载的工作流证据为 `status=passed`、`production_release=false`、`database_migration=heads_applied`，三个公网端点均 200，固定出口配置及观测均为 `38.55.145.52`。
- 独立 SSH `docker --host unix:///run/user/1004/docker.sock ps` 显示 backend/worker/jobs/agent/helper 为 `3421003e...`，frontend 为 `33d7f388...`，检索仍为 `bc99dfa3...`，相关健康容器为 healthy。`docker exec crm-staging-backend-1 alembic current --check-heads` 返回 `024_tiktok_oauth_jobs (head)`。
- 独立公网 HTTPS 无跳过证书校验的 `curl`：`/healthz`、`/v1/health`、`/v1/health/ready` 均 200；未登录读取新 OAuth job 状态端点返回 401，合成无效 `state/code` 的 callback 返回 400。后两项只证明鉴权/失败关闭，不是有效授权回跳。
- 公司 system Docker 容器 ID 集合前后 SHA 均为 `c4839bff...`；边缘 vhost 文件集合前后 SHA 均为 `c9a5122a...`。PostgreSQL dump 可列目录、MinIO archive 可列文件，旧 env 在更新前与恢复副本相同；真实 restore/rollback 未执行。
- `MVP-OAUTH-REDIRECT-001` 的隔离测试 1662 passed/3 skipped、前端契约 41/41、合成浏览器 23/23、迁移升降级与 PR #53 CI 属代码任务历史结果，**不是**本次真实 TikTok 浏览器测试。

# REQ/AC 或门禁与证据映射

- `staging-image`：合并 main `c724063...` 的新 backend/frontend 摘要现场运行，旧检索摘要仅按本次许可保留并记录依赖锁偏差。
- `migration`：024 头现场通过；恢复副本可读但未做实际恢复。
- `health`：工作流及独立公网三健康 200，固定出口 `38.55.145.52`。
- `isolation`：Rootless CRM 变化仅在业务机；公司 system Docker 与边缘 vhost 摘要不变；production 未部署。
- `real-oauth-callback`：未通过。TikTok 官方页面返回 “This app is not available for your seller type”，未向 callback 发请求；不能验证真实 303、异步 job connected 或重复回调现场表现。

# 缺陷、未执行项与残余风险

当前 Partner Center 目标卖家截图为美国本土及“中国”跨境，编辑菜单仅有中国/韩国，没有单列香港；实际店铺元数据为美国市场、`CROSS_BORDER`、seller base region `HK`。官方资料将中国大陆和香港并列描述，现有“中国”是否覆盖这家店铺不能仅凭 UI 确定；此前还曾有官方成功页。需用户核对官方授权页选的是跨境卖家入口、是否使用店铺主账号，必要时向 Partner Center 支持提交资格问题，再由本人重授权；不要把凭据或完整 callback URL 发到聊天。旧检索镜像依赖锁偏差不等价、不延续；真实数据库/对象恢复与兼容回滚、生产放行未测。

# 结论和复测条件

`PARTIAL`：staging 镜像、迁移、健康、隔离门禁通过；真实 OAuth 成功回跳 AC 仍缺。官方卖家资格放行后，用普通 Chrome 从 CRM 发起同一店铺授权，观察 callback 立即 303 回渠道页、后台 job 变为 connected、同一店铺唯一绑定，并检查无 Token/授权 code 泄漏；再修订记录和审查，任务才能 `DONE`，之后进入 `MVP-002` 的 G1 只读验收。
