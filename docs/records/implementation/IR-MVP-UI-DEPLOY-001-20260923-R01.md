---
record_id: IR-MVP-UI-DEPLOY-001-20260923-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-UI-DEPLOY-001
base_sha: 58263b1108e96d0d6afa21a6bbfae271fb5c7a87
final_sha: 58263b1108e96d0d6afa21a6bbfae271fb5c7a87
requirement_ids: [MVP-UI-DEPLOY-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
test_record: docs/reports/tests/TR-MVP-UI-DEPLOY-001-20260923-R01.md
review_record: docs/reports/reviews/RR-MVP-UI-DEPLOY-001-20260923-R01.md
created_at: 2026-09-23T18:42:00+08:00
updated_at: 2026-09-23T18:42:00+08:00
supersedes: null
---

# 实施目标与结果

在 PR #43、#44 已合并后，将远端 `main` 的 `58263b1108e96d0d6afa21a6bbfae271fb5c7a87` 单独部署到 `staging.overselfx.com`，不触碰 production。镜像发布 `35844221980` 成功；本轮 UI 改动的前端构建输入与此前运行版确有差异，因此实际切换至新前端摘要。backend 亦切换到同一 `main` 发布摘要，现有检索镜像继续运行。机器证据见 [`crm-staging-ui-rollout-20260923.json`](../../../release/evidence/staging/crm-staging-ui-rollout-20260923.json)。

# 镜像差异与限定授权

完整同源组合预检 `35845274792` 通过，但正式运行 `35845426383` 在约 8 GB 新检索镜像下载阶段被取消；取消前只有 backend/frontend 镜像下载完成，运行容器尚未替换，公网健康仍为 200。用户随后明确授权**仅本次 staging UI 部署**保留现有健康检索镜像，并如实记录依赖锁版本偏差。旧检索镜像源为 `5099fc08...`；检索服务源码和 Dockerfile 与当前 `main` 相同，但 `src/backend/pyproject.toml`、`uv.lock` 不同，不能声称三镜像同源。该授权不适用于 production 或下一次镜像升级。

原 staging 环境文件在受限备份后只临时改过检索镜像引用；全量尝试取消且确认没有容器切换后，逐字核对其余配置未变，并原子恢复旧引用，所有者及模式继续为 `crmdeploy:crmdeploy:0600`。例外组合预检 `35849293069`、部署 `35849490309` 均通过。

# 数据、配置和恢复边界

部署前保存 root-only 的 PostgreSQL 自定义格式转储、MinIO 数据快照与 staging 环境文件，验证转储可列目录、对象存储快照结构可读；恢复点只留在业务服务器，不进 Git。门禁完成 Alembic head、固定出口 IP 和三个公网健康端点检查；独立现场复核了运行镜像摘要、容器健康、迁移头、入口隧道，以及公司 system Docker 和受保护监听的前后摘要一致。真实能力开关保持 false。

本轮没有执行数据库/对象存储实际恢复或兼容版本回滚演练，仍属 `MVP-008`；没有运行带身份的 staging 浏览器逐按钮验收，也没有启用真实 TikTok/DeepSeek 能力。production 未部署或放行。
