---
record_id: IR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-AGENT-STAGING-DEPLOY-001
base_sha: 7cee8b4cf5703b1f4bd3213a7219e3162f4272e0
final_sha: d5c044ba1be05a26140554dc6dce5ad6d0360e65
requirement_ids: [MVP-AGENT-STAGING-DEPLOY-001]
acceptance_ids: [AC-02]
test_record: docs/reports/tests/TR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R01.md
review_record: docs/reports/reviews/RR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R01.md
created_at: 2026-10-29T09:19:00+08:00
updated_at: 2026-10-29T09:19:00+08:00
supersedes: null
---

# 部署补齐

用户批准 staging 部署及与另一授权会话协调；本执行者唯一负责镜像、迁移及切换，另一会话负责多店授权集成与兼容验证。预检确认现网 12 容器、旧数据库 034、Agent 调试和 Embedding 已开启，但原覆盖层没有传入新执行器需要的 `AGENT_V2_DEBUG_ENABLED`，直接发布主线会令调试仍然 503。

沿用 `-EnableAgentDebug`：仅 backend 开启旧/新调试开关，主/备用上下文窗口显式从部署配置传入；默认进程及正式入口固定关闭。合并 Compose 和实际容器均检查三个 Agent 开关，低敏部署收据记录 v2 状态。未新增模型、业务工具、迁移、依赖或部署入口，后端和前端应用树与基线一致。

# 验证与边界

先在真实 Compose 合并和 PowerShell 门禁用例中复现缺少变量/收据，再补齐配置；180 项相关回归通过。此记录只覆盖本地部署资产，不代表已部署或真实模型生成成功。实际服务器切换等待多店授权组合主线及精确候选验证。恢复须关闭调试并保护新增版本、记忆、协作记录及业务增量，不能盲目降低数据库迁移。
