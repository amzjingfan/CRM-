---
record_id: IR-MVP-TIKTOK-OAUTH-UX-STAGING-001-20261030-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-TIKTOK-OAUTH-UX-STAGING-001
base_sha: 1eb6dbd1fa44688660fb2809ae3df8ee19108027
final_sha: 18a0d7bb0b0ca6b2bb601de32af7128d1a41a9ec
requirement_ids: [MVP-TIKTOK-OAUTH-UX-STAGING-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
test_record: docs/reports/tests/TR-MVP-TIKTOK-OAUTH-UX-STAGING-001-20261030-R01.md
review_record: docs/reports/reviews/RR-MVP-TIKTOK-OAUTH-UX-STAGING-001-20261030-R01.md
created_at: 2026-10-30T04:04:03Z
updated_at: 2026-10-30T04:04:03Z
supersedes: null
---

# 实施目标与范围

按用户本轮授权，将已合入主线的 TikTok 店铺授权单入口修复先部署 staging。production、真实 OAuth 重授权、买家消息发送及全店人工发送扩权均不在本轮操作中。

# 实际变更及原因

- 只读核对部署前运行源码 b21f59a7、12 服务、044 迁移头与功能开关。与目标主线 18a0d7bb 对比，产品代码仅有已批准 OAuth 修复的 5 个文件变化；1eb6dbd1 与 18a0d7bb 的前后端构建输入、Dockerfile、Compose 和门禁脚本 Git 对象一致。
- GHCR 的后端和前端发布工作流分别在 run 40998702571、40998706414 零步骤失败；未记为 CI 通过。依项目本地替代门禁，用干净源码构建 linux/amd64 两镜像并以 OCI revision=18a0d7bb 推送 GHCR，按不可变摘要在 staging Rootless Docker 导入、拉取和核对。检索与文档解析器镜像不变。
- 从 18a0d7bb 导出 Git 归档，双方 SHA-256 一致，服务端解包逐文件校验并保存在持久目录。切换前建立受限 PostgreSQL、MinIO 与环境配置备份，PostgreSQL pg_restore 清单可读；前后镜像摘要均可用于恢复。
- 以原单店 allowlist、Webhook 只读、工作台翻译、Agent 调试与正式人工建议、文档解析的同组参数执行 ValidateOnly 与 Deploy。门禁通过后独立复核 12 服务、镜像 revision、功能开关、044 迁移头、持久只读代理挂载及公网资源。

# 关键决定与偏差

发布工作流的两个作业均无运行步骤，故采用既有本地构建/推送与现场不可变摘要验证。主线在构建期间只增加部门发布文档提交，不改变任何构建输入；最终镜像标签、源归档与发布 subject 统一为 18a0d7bb。文档任务行 rebase 冲突只保留双方独立任务记录，未改变源码或运行配置。

# 数据、配置、接口、迁移或 Prompt 影响

本轮无数据结构、Prompt、生产配置或生产发布变更。现有 044 迁移已处于 head，部署门禁仍执行 upgrade head 与 current --check-heads；没有新增迁移。TikTok 真实写入仍仅允许原 1 家店铺，自动回复、营销、主动通知和高风险写入未开启。

# 验证交接

现场结果、摘要和受限原始门禁文件 SHA-256 见 TR 及 release/evidence/staging/crm-staging-oauth-single-entry-20261030.json。原授权行为测试的 5 个产品文件与部署主线逐 blob 相同，本次另重跑 4 项前端 OAuth 契约测试。

# 限制、风险与回滚

未触发真实 TikTok 授权回跳，也未用已登录浏览器点击真实店铺；部署与静态页面检查不代替真实 OAuth 全链路验收。异常时从已缓存的 b21f59a7 前后端摘要恢复原模式，保留部署后的数据库和 MinIO 增量，不直接覆盖备份；私有备份仅作恢复点，未执行整库恢复演练。production 继续 No-Go。
