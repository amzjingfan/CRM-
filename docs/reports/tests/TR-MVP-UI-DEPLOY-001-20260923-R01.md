---
record_id: TR-MVP-UI-DEPLOY-001-20260923-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-UI-DEPLOY-001
tested_sha: 58263b1108e96d0d6afa21a6bbfae271fb5c7a87
implementation_record: docs/records/implementation/IR-MVP-UI-DEPLOY-001-20260923-R01.md
requirement_ids: [MVP-UI-DEPLOY-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: 192.168.110.210 crmdeploy Rootless staging, 38.55.145.52 split-ingress, public HTTPS
created_at: 2026-09-23T18:42:00+08:00
updated_at: 2026-09-23T18:42:00+08:00
supersedes: null
---

# 范围与结论

`PASS` 只证明已合并 UI 修复的 staging 镜像部署、健康与保护边界；不替代 [`TR-MVP-UI-001-20260923-R01.md`](TR-MVP-UI-001-20260923-R01.md) 的隔离数据逐按钮测试，也不签署真实 TikTok 或 production。机器证据见 [`crm-staging-ui-rollout-20260923.json`](../../../release/evidence/staging/crm-staging-ui-rollout-20260923.json)。

| 检查 | 实际结果 |
|---|---|
| 远端 `main` 和镜像发布 | `main=58263b1...`；`35844221980` 成功，三个完整 RepoDigest 记录在工作流 artifact |
| 备份 | PostgreSQL 自定义格式转储非空且 `pg_restore -l` 成功；MinIO 快照目录存在；环境文件备份为 root-only `0600` |
| 全量镜像尝试 | `35845274792` 预检通过；`35845426383` 在下载新检索镜像时取消，取消前运行容器未切换；不记为部署通过 |
| 限定例外预检 | `35849293069` 通过；四层 Compose、旧检索摘要与恢复后的 env 匹配，真实能力关闭 |
| 限定例外部署 | `35849490309` 通过；固定出口配置/观测均为 `38.55.145.52`，迁移头应用，三个公网健康端点 200 |
| 独立现场镜像与迁移 | frontend、backend、worker/jobs/agent-worker/helper 为新摘要；retrieval 为批准保留的旧摘要；关键容器健康；`023_marketing_review_idempotency (head)` |
| 公网前端资源 | `/login`、`/settings/channels`、`/knowledge`、`/marketing` 均 200；登录页引用的 Next JavaScript 资源返回 200 |
| 公司负载和隧道 | system Docker 与受保护监听前后 SHA-256 逐字相同；入口隧道 active/running |

# 未执行项与风险

本轮未用真实账号在 staging 逐按钮点击，也未运行真实 TikTok OAuth、Webhook、消息、DeepSeek、50 客户端 SSE、五日稳定性、数据库/对象存储恢复或兼容版本回滚。旧检索镜像的依赖锁与当前 `main` 不同，已取得仅本次 staging 授权并明确记录，不能推广为下次或 production 的供应链验收。项目现有本机合成数据 UI 回归和 PR CI 证据仍由 `MVP-UI-001` R01 记录承担。
