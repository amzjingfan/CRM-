---
record_id: TR-MVP-STORE-VIEW-CONSISTENCY-001-20261025-R02
record_type: test
revision: R02
status: PASS
task_id: MVP-STORE-VIEW-CONSISTENCY-001
tested_sha: aadf5087969ceb8ccb2b533ce8a42c191c3f96d9
implementation_record: docs/records/implementation/IR-MVP-STORE-VIEW-CONSISTENCY-001-20261025-R02.md
requirement_ids: [MVP-STORE-VIEW-CONSISTENCY-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
environment: Windows merged-main worktree; local isolated PostgreSQL and synthetic production browser; staging Rootless Docker and public HTTPS
created_at: 2026-10-25T03:49:00Z
updated_at: 2026-10-25T03:49:00Z
supersedes: docs/reports/tests/TR-MVP-STORE-VIEW-CONSISTENCY-001-20261025-R01.md
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT: centralized`。R01 的本地后端 2398 passed/3 skipped、前端契约 48/48、生产浏览器 108/108、类型、构建、格式、lint 及隔离迁移验收绑定源候选 `35c3929e`；合并 `main=aadf5087` 的后端、前端和 Dockerfile 构建输入与该候选相同。本修订验证从合并主线制作的 staging 镜像和部署现场；未在 staging 写入测试知识或发送买家消息。

# 命令和逐项结果

- [PR #553](https://github.com/CP11-gh/CRM/pull/553) 为 `MERGED`，合并提交 `aadf5087969ceb8ccb2b533ce8a42c191c3f96d9`，运行镜像 OCI revision 与之精确相同。后端 `sha256:46fe1edc…6697c`、前端 `sha256:92744d14…236a8` 均为 linux/amd64 不可变摘要，检索及解析器沿用旧摘要。
- 私有 `0700` 目录内 PostgreSQL `0600` 备份 672943 字节且 `pg_restore -l` 可读；MinIO 受限备份 358400 字节。手动 `ValidateOnly=validated`、`Deploy=passed`；两个私有门禁证据 SHA-256 见[低敏对账](../../../release/evidence/staging/crm-staging-store-view-consistency-20261025.json)。MinerU 离线资产验证和固定 TikTok 出口均通过。
- 迁移头为 `032_knowledge_file_archive`；12 个 CRM 容器运行。只读统计为现有知识文件 11、归档 0；运行后端/前端摘要匹配，Webhook 读取、单店人工发送、翻译及文档解析保持，自动回复、AI 营销和通用 LLM 关闭。
- 公网 `/healthz`、`/v1/health`、`/v1/health/ready`、`/login`、`/knowledge`、`/dashboard`、`/marketing`、`/workspace`、`/settings/stores` 均返回 200。无查询参数 HTML 的 `Cache-Control` 含 `no-store`，知识库引用的指纹 JS 返回 200 和 `immutable`。

# REQ/AC 或门禁与证据映射

AC-01～AC-05 的行为、租户隔离和迁移验证以 R01 本地真实测试记录为准；本修订确认完全相同的构建输入已发布到 staging，数据库迁移、运行模式和公网可访问性通过。没有把健康 200 解释为已登录交互全通过。

# 缺陷、未执行项与残余风险

GitHub Actions 两次运行在零步骤失败，不计 CI 通过；用户明确要求本次直接 staging 部署。内置浏览器建页及绑定两次超时，记 `UI_UNAVAILABLE`，未做真实已登录切店/归档/删除点击。自动审批拒绝复制网关 SSH 私钥到受限临时文件，因此未从网关主机复核 Nginx；本次未改动其配置。系统 Docker 的 `sucai-remote-redis-1` 现场为自动重启，观察时累计 5464 次；CRM 使用独立 Rootless daemon，未改动系统 Docker，但不能断言全部公司负载状态不变。

# 结论和复测条件

本次授权范围的源码、本地行为验证和 staging 手动部署门禁为 **PASS**。用户可刷新已登录 staging 进行跨店铺页面验收；若其实际操作与合成测试不同，按店铺和路径复现后修复。production 仍需单独 G8 放行；含归档记录后回滚须保护增量，不能直接降级或用旧备份覆盖。