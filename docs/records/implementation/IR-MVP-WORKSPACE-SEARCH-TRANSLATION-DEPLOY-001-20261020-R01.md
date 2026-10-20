---
record_id: IR-MVP-WORKSPACE-SEARCH-TRANSLATION-DEPLOY-001-20261020-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-WORKSPACE-SEARCH-TRANSLATION-DEPLOY-001
base_sha: 38197cfbdee49fec77ddc47e5da3d9653eb11712
final_sha: a48f7447dfb905dcea5b30028544c1b0c04e1014
requirement_ids: [MVP-WORKSPACE-SEARCH-TRANSLATION-DEPLOY-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
test_record: docs/reports/tests/TR-MVP-WORKSPACE-SEARCH-TRANSLATION-DEPLOY-001-20261020-R01.md
review_record: docs/reports/reviews/RR-MVP-WORKSPACE-SEARCH-TRANSLATION-DEPLOY-001-20261020-R01.md
created_at: 2026-10-20T10:11:07Z
updated_at: 2026-10-20T10:11:07Z
supersedes: null
---

# 实施目标与范围

将统一会话搜索及六种语言的人工译文预览发布到 staging，并在已登录真实会话中只读复核。用户选择 GitHub 凭据的手动部署路径，不使用 GitHub Actions 进行构建或部署；原有单店 TikTok 人工发送边界保持不变，production 不放行。

# 实际变更及原因

- 首次从 `main=38197cfbdee49fec77ddc47e5da3d9653eb11712` 构建、发布并通过 staging 手动门禁。已登录工作台现场发现单项买家搜索仍返回全部 230 个会话，批量搜索同一昵称返回 1 个；数据库该昵称只匹配 1 位买家。服务层把 API 默认的空 `terms=[]` 当成有效批量条件，忽略了非空 `q`。
- 在 `get_session_list` 中仅当 `terms` 非空时优先使用批量词，否则使用 `q`；增加合成买家昵称的回归断言。修复提交 `9f37eb45ffaf3a93667bccda2769b8bf3ccf467c` 经 [PR #470](https://github.com/CP11-gh/CRM/pull/470) squash 合入 `main=a48f7447dfb905dcea5b30028544c1b0c04e1014`，两者 Git tree 一致。无新增接口、配置、依赖、迁移或 Prompt。
- 从该精确主线干净源码重建并手动推送后端、前端私有镜像；各 OCI index 只有一个 `linux/amd64` 子清单，revision 与主线一致，按不可变摘要拉回核对。检索镜像保持原版，六个候选/回滚角色在 staging Rootless Docker 完整预取。
- 在受限目录制作模式 `0600` 的 PostgreSQL 自定义格式备份与 11 容器快照，经现有 staging `ValidateOnly` 和 `Deploy` 门禁切换服务。后端、worker、jobs、agent-worker、TikTok 出口运行新后端摘要，前端运行新前端摘要；数据库仍为 `025_workspace_actions`。

# 关键决定与偏差

Windows 生成的 Git archive 对五个历史 CRLF 文件保留原始 blob 字节，而 Linux 干净 Git checkout 将其规范化，逐字节归档校验因此未通过。未绕过验证：最终门禁改用精确 Git bundle 建立的干净 checkout、受审 GitHub origin 和当前 `main` SHA；本地归档及转移哈希仅作诊断，不作为最终源码门禁。此前归档尝试未修改活动服务。

# 数据、配置、接口、迁移或 Prompt 影响

服务层修复只纠正单项搜索词选择；搜索仍在授权店铺、状态、平台边界内执行，查询词放在 POST JSON 而非 URL。部署未运行新迁移，未改 staging 常驻环境文件；单店人工发送、Webhook 读取与按需翻译开启，自动回复、通用 LLM、高风险写入关闭。临时 GHCR Docker 登录已注销，本机及 staging 的认证项均为 0。

# 验证交接

命令、现场前后计数、镜像摘要、备份与原始门禁证据 SHA-256 见 [TR](../../reports/tests/TR-MVP-WORKSPACE-SEARCH-TRANSLATION-DEPLOY-001-20261020-R01.md) 及[低敏汇总](../../../release/evidence/staging/crm-staging-workspace-search-translation-deploy-20261020.json)。已登录真实会话的单项搜索从 230 个缩为 1 个；六种目标语言存在，临时中文草稿选英语时预览按钮可用，随后草稿与语言已恢复。未请求真实模型译文，也未发送 TikTok 消息。

# 限制、风险与回滚

原后端、前端、检索摘要及部署前备份保留在 staging 受限主机；尚未实际演练切回。若需恢复，应先保存切换后真实对话增量，不得直接以旧数据库备份覆盖消息。真实 DeepSeek 可用性和翻译质量、真实买家新消息及 production 发布未在本任务验证；生产 G8 No-Go 不变。
