---
record_id: TR-MVP-UI-CACHE-DEPLOY-001-20260924-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-UI-CACHE-DEPLOY-001
tested_sha: a9d36c04fb8f71d163deabc22d64b5ce5efbe3e3
implementation_record: docs/records/implementation/IR-MVP-UI-CACHE-DEPLOY-001-20260924-R01.md
requirement_ids: [MVP-UI-CACHE-DEPLOY-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: staging split-ingress; 38.55.145.52 BaoTa Nginx/TLS; 192.168.110.210 rootless CRM; local Windows production-mode Next.js and synthetic Playwright
created_at: 2026-09-24T12:44:00+08:00
updated_at: 2026-09-24T12:44:00+08:00
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

项目测试为 `centralized`：代码测试位于 `src/tests/backend/` 与 `src/tests/frontend/browser/`；正式现场低敏证据在 `release/evidence/staging/crm-staging-html-cache-rollout-20260924.json`。本记录只关闭 staging 发布及缓存故障，不是 G1～G8 或 production 验收。

# 命令和逐项结果

- Git 对比 `118ba775... a9d36c... -- src/backend src/frontend src/docker`：零差异；镜像发布工作流 `35948442592` 成功。混合摘要预检 `35953530870`、部署 `35953792293` 均成功，迁移头应用、固定出口配置和观测均为 `38.55.145.52`，三条公网健康为 200。
- 业务机 rootless `docker ps` 显示新 backend/frontend、旧检索、PostgreSQL/MinIO/Redis 与出口 helper 均运行，相关健康容器为 healthy；现场 `Config.Image` 已核对三个不可变摘要。公司 system Docker 稳定字段摘要部署前后均为 `bf370603...`。
- 边缘 vhost SHA 从 `1c5d047e...` 变为受审 `a0a3c2b5...`，`nginx -t` 通过，其他 vhost 摘要前后均为 `61a63183...`，`18080` 只监听 `127.0.0.1`。
- 公网无 query GET `/login`、`/marketing`、`/knowledge`、`/settings/stores` 均 200，`Cache-Control: private, no-cache, no-store, max-age=0, must-revalidate`，不再有 `X-Nextjs-Cache: HIT`。首页为 307 且唯一 `Location: /dashboard`；`/healthz`、`/v1/health`、`/v1/health/ready` 为 200；带指纹 JS 200 且 `public, max-age=31536000, immutable`。
- 合并后的 `verify-split-ingress.sh` 在 edge `public` 与 business `business` 两角色实际执行通过。其测试覆盖正常首页、重复 Location 恶意首尾位置、错误单值、缺失头；后端全量 `pytest` 1639 passed、15 skipped，Ruff、格式和 Bash 语法通过。独立只读复审后 PR #49/#50 的前后端 CI 均通过并 squash 合并。
- 本机 `npm run build` 后，隔离生产模式服务上运行 `UI_CACHE_EXPECT_PRODUCTION=1 npm run test:ui`：22/22 passed、0 skipped；使用合成 `/v1/` 响应和本机浏览器，不读取真实店铺数据。

# REQ/AC 或门禁与证据映射

- AC-01 不可变发布与 staging-only：三摘要实际运行、混合部署工作流成功，production_release=false。
- AC-02 精确路径：四条无 query HTML 不缓存旧页；指纹 JS 保持 immutable。
- AC-03 安全与恢复：数据库/对象存储/env 与 vhost 受限备份，Nginx 语法、固定出口、公司负载及其他站点边界复核。
- AC-04 合并后验证：PR #49/#50 合并、两机使用最终脚本通过，生产模式合成浏览器回归 22/22。

# 缺陷、未执行项与残余风险

首次全新检索镜像拉取失败不被抹除；本次用户批准旧检索摘要，依赖锁偏差已记录，不能作为生产或后续 staging 镜像等价依据。带身份的 staging 全按钮点击矩阵、真实 TikTok 授权/消息、真实数据库/对象存储恢复和上一版镜像兼容回滚未执行。公网 `/health` 为 404 是非契约路径；契约是 `/healthz` 和两个 `/v1/health*`。

# 结论和复测条件

`PASS` 仅针对本次 staging 发布、缓存修复与入口门禁。若镜像、vhost、域名或入口脚本再变化，重做对应现场验证；production 需单独批准和 G0～G8 门禁。
