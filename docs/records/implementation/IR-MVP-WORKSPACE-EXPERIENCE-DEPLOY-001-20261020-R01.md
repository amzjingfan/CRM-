---
record_id: IR-MVP-WORKSPACE-EXPERIENCE-DEPLOY-001-20261020-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-WORKSPACE-EXPERIENCE-DEPLOY-001
base_sha: 4cd019c26f15bcbff2fb83f5175021e6a672a5cb
final_sha: 4cd019c26f15bcbff2fb83f5175021e6a672a5cb
requirement_ids: [MVP-WORKSPACE-EXPERIENCE-DEPLOY-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
test_record: docs/reports/tests/TR-MVP-WORKSPACE-EXPERIENCE-DEPLOY-001-20261020-R01.md
review_record: docs/reports/reviews/RR-MVP-WORKSPACE-EXPERIENCE-DEPLOY-001-20261020-R01.md
created_at: 2026-10-20T14:28:00+08:00
updated_at: 2026-10-20T14:28:00+08:00
supersedes: null
---

# 实施目标与范围

将已合入 `main` 的工作台会话体验与操作交付到 staging。范围是现有单店 TikTok 人工辅助、已批准的真实收发边界和按需翻译；未扩大到其他店铺或 production，也未发送新的买家消息。

# 实际变更及原因

从 `main=4cd019c26f15bcbff2fb83f5175021e6a672a5cb` 的干净源码构建并手动推送后端、前端私有镜像，OCI revision 均为该 SHA。GHCR 原生直拉超时后，将两个单平台清单包装为各含一个 `linux/amd64` 子清单的 OCI index；镜像层未重建。使用受审分块 OCI 预取器按描述符与 SHA-256 校验导入 Rootless Docker；候选和旧版共六个角色均核对不可变 RepoDigest。临时 GHCR 登录目录在操作后删除。

通过现有 `Test-StagingProductionGates.ps1` 执行 staging 专用 validate 和 deploy：保留 TikTok Webhook 读取、单店人工发送、工作台翻译，关闭通用 LLM、自动回复与高风险写入。门禁依次拉取、检查固定出口、执行 Alembic 升级、更新容器与三项公网健康检查。运行中的后端、worker、jobs、agent-worker 和 tiktok-egress 使用新后端摘要；前端使用新前端摘要；检索镜像保持原摘要。

# 关键决定与偏差

按用户决定使用 GitHub 凭据和 staging 主机手动路径，不运行 GitHub Actions。部署过程中曾有旧 GitHub CLI OAuth 凭据进入本地命令错误输出；发现后立即停止使用，通过 GitHub 官方撤销接口撤销并验证旧凭据失效。用户授权设备重新登录后才继续镜像推送与部署；凭据正文未写入仓库或证据。原生直拉失效时只切换传输方式，未放宽摘要、架构或运行门禁。

# 数据、配置、接口、迁移或 Prompt 影响

本轮未改仓库源码或接口。已合入迁移 `025_workspace_actions` 在 staging 从 `024_tiktok_oauth_jobs` 升级，为会话增加内部星标和关闭时间列。staging 环境文件未持久改写，发送限定仍为原有一个授权店铺；无新 Prompt、模型或 production 配置变动。

# 验证交接

预检、镜像、数据库备份、迁移、运行摘要、固定出口、11 容器和三健康的事实见 [TR](../../reports/tests/TR-MVP-WORKSPACE-EXPERIENCE-DEPLOY-001-20261020-R01.md) 与[低敏证据](../../../release/evidence/staging/crm-staging-workspace-experience-deploy-20261020.json)。已登录浏览器刷新后只读确认真实会话的新工具栏、列表筛选、紧凑 AI 草稿和打开会话定位末尾。此前源功能的本地行为测试见 `MVP-WORKSPACE-EXPERIENCE-001` 的 TR。

# 限制、风险与回滚

旧版后端、前端、检索不可变摘要和 staging 部署前 PostgreSQL 自定义格式备份保存在受限主机。迁移 `025` 已生效，旧镜像直接运行旧 Alembic 头可能失败；若需回滚，应先冻结写入并保存部署后增量与内部标记，再评估使用当前受审镜像降级到 `024`、切回旧摘要和重新验证。降级会丢失新星标/关闭列，不能把整库备份覆盖当前真实对话；本轮未实际演练回滚。生产 G8 No-Go 与公网间歇故障风险仍在。
