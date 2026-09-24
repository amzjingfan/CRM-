---
record_id: IR-MVP-UI-CACHE-DEPLOY-001-20260924-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-UI-CACHE-DEPLOY-001
base_sha: 118ba775e291b88998bd033b7bca3410e29f8b88
final_sha: a9d36c04fb8f71d163deabc22d64b5ce5efbe3e3
requirement_ids: [MVP-UI-CACHE-DEPLOY-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
test_record: docs/reports/tests/TR-MVP-UI-CACHE-DEPLOY-001-20260924-R01.md
review_record: docs/reports/reviews/RR-MVP-UI-CACHE-DEPLOY-001-20260924-R01.md
created_at: 2026-09-24T12:44:00+08:00
updated_at: 2026-09-24T12:44:00+08:00
supersedes: null
---

# 实施目标与范围

合并后仅在 staging 部署管理端 HTML 缓存修复，关闭旧页面长期命中的故障；production 与公司现有负载不变。

# 实际变更及原因

- 从 `main=118ba775...` 的发布工作流 `35948442592` 取得 backend/frontend 不可变镜像。首次三新摘要部署因约 8 GB 检索镜像下载停滞，在切换前取消，历史失败事实保留在 `release/evidence/staging/crm-staging-html-cache-rollout-attempt-20260924.json`。
- 用户重新明确授权**仅本次 staging**复用旧检索镜像。混合摘要预检 `35953530870` 与部署 `35953792293` 成功；业务机实际运行新 backend/frontend，检索服务保留旧摘要。
- 部署后发现业务机 HTML 已为 `no-store`，但公网精确路径仍由宝塔 Nginx 继承的 `proxy_cache cache_one` 命中旧 HTML。PR #49 合并为 `504f288...`，仅 staging HTTPS vhost 加 `proxy_cache off`，保存单文件备份、`nginx -t` 并 reload；公网四个精确 HTML 路径恢复为 `no-store`，指纹 JS 仍 `immutable`。
- 旧入口验收脚本把合法首页 `307 → /dashboard` 错判为失败。PR #50 合并为 `a9d36c...`，严格校验恰好一个指向 `/dashboard` 的 `Location`，而三条健康路径仍要求 200。合并后的脚本在两台主机现场只读执行通过。

# 关键决定与偏差

新旧检索服务源码与 Dockerfile 输入相同，但后端依赖清单/锁文件不同；旧镜像**不视为版本等价**。豁免仅覆盖本次 staging，未来发布和 production 不得继承。`118ba775...` 至最终 subject 的 backend/frontend 构建输入经 Git 比较无差异，因此新镜像仍对应最终已合并配置基线。

# 数据、配置、接口、迁移或 Prompt 影响

数据库迁移头在部署工作流应用；未做不可逆数据迁移。边缘只改 staging vhost，其他站点配置摘要不变；公司 system Docker 摘要前后不变。未改 production、真实能力开关、接口、Prompt 或模型权重。

# 验证交接

现场低敏证据：`release/evidence/staging/crm-staging-html-cache-rollout-20260924.json`。本机生产构建合成数据 Playwright 22/22，后端全量 1639 passed、15 skipped；公网精确 HTML、指纹资源、健康、DNS/TLS/监听和双机入口脚本通过。详见 TR。

# 限制、风险与回滚

已保存 root-only PostgreSQL dump、MinIO archive、环境文件和 staging vhost 原件。若入口异常，按受限备份恢复精确 vhost 并做 `nginx -t`/reload；若应用异常，按不可变摘要回退。真实数据恢复及兼容镜像回滚尚未演练，属 `MVP-008`；带身份 staging 逐按钮测试和真实 TikTok OAuth 尚未执行，不以本部署任务声称通过。
