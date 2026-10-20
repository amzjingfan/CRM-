---
record_id: TR-MVP-WORKSPACE-SEARCH-TRANSLATION-DEPLOY-001-20261020-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-WORKSPACE-SEARCH-TRANSLATION-DEPLOY-001
tested_sha: a48f7447dfb905dcea5b30028544c1b0c04e1014
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-SEARCH-TRANSLATION-DEPLOY-001-20261020-R01.md
requirement_ids: [MVP-WORKSPACE-SEARCH-TRANSLATION-DEPLOY-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: Windows 11 local checkout and in-app browser; staging Linux Rootless Docker; production unchanged
created_at: 2026-10-20T10:11:07Z
updated_at: 2026-10-20T10:11:07Z
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT: centralized`。本地测试源码在 `src/tests/`，临时构建与门禁辅助材料在忽略的 `src/tests/.artifacts/`；原始数据库备份、容器快照和门禁 JSON 仅在 staging 受限目录。仓库保存不含客户昵称、消息正文、店铺 UUID 或凭据的[低敏汇总](../../../release/evidence/staging/crm-staging-workspace-search-translation-deploy-20261020.json)。

# 命令和逐项结果

- 首次 staging 部署源码 `38197cfb...` 通过六摘要、validate/deploy、运行镜像及健康；随后真实工作台单项买家搜索错误显示 230 个会话。`POST /v1/workspace/sessions/search` 在代理记录为 200 且请求体不写访问日志；同一昵称批量搜索显示 1 个，数据库只读 `customers` 匹配数 1，定位到服务层空 `terms` 覆盖 `q`。
- `uv run pytest ../tests/backend/domain/test_workspace_search_translation.py::test_search_validates_batch_bounds_before_store_query -q` 修复前失败：仓储收到 `('buyer', ())`；修复后文件 4/4 通过。隔离 PostgreSQL 全量 `src/scripts/run-postgres-integration-tests.ps1` 在修复逻辑上为 2223 passed、3 skipped、2 条既有警告；随后仅调整测试格式。最终合并的 `main=a48f7447...` 与修复提交 Git tree 完全一致，针对该精确主线再次运行测试文件 4/4、Ruff check 和 format 检查均通过；全量未在格式调整后的合并 SHA 重跑。
- GitHub API 核对当前 main 与 staging 干净 checkout 均为 `a48f7447dfb905dcea5b30028544c1b0c04e1014`；Git bundle SHA-256 `97e53c96...e54a`。新后端 `sha256:005d58df...d477`、前端 `sha256:f1184f1c...cbce` 的 OCI revision、唯一 `linux/amd64` 子清单、按摘要拉回通过。六角色 Rootless 预取证据 `status=passed`，未切服务。
- 新窗口数据库 `pg_dump -Fc` 备份大小 381557 B、模式 `0600`、`pg_restore -l` 通过；11 容器快照保存。手动 `Test-StagingProductionGates.ps1 -ValidateOnly` 证据 `validated`，`-Deploy -Confirm:$false` 证据 `passed` 且 `production_release=false`。迁移头 `025_workspace_actions`，五个应用/出口进程与前端运行新摘要，检索保持原摘要；11 容器运行，三项公网健康独立 GET 均为 200，固定 TikTok 出口经门禁核对。
- 运行配置复核：Webhook 读取、工作台翻译和单店真实人工发送开启；自动回复、通用 LLM、高风险写入关闭。已登录工作台刷新后，在同一真实会话搜索买家昵称，修复后从 230 缩为 1 个；语言列表含英语、印尼语、西班牙语、葡萄牙语、法语、泰语。临时中文草稿选英语时“预览译文”按钮可用；未点击，随后草稿清空、语言恢复原文。
- [PR #470](https://github.com/CP11-gh/CRM/pull/470) 的两项 GitHub Actions 检查为 failure，但 Job API 显示各 `steps=0`、无 runner，不计为测试或部署证据。按用户决定没有用 CI/CD。临时 GHCR Docker 登录已在本机和 staging 注销，两处认证项均为 0。

# REQ/AC 或门禁与证据映射

AC-01 对应精确主线、不可变镜像、六角色预取和旧摘要；AC-02 对应受限备份、validate/deploy、运行摘要、固定出口及健康；AC-03 对应真实会话搜索前后计数和六语言预览入口；AC-04 对应低敏 JSON、凭据注销、恢复边界与生产 No-Go。原始私有证据 SHA-256 在低敏 JSON 中，可由受限主机复核。

# 缺陷、未执行项与残余风险

第一次 clean checkout 的 Git archive 字节验证因五个 CRLF 文件与 Linux 工作树不同失败；改由干净 Git checkout、精确主线 SHA、受审 origin 与 GitHub API 验证源码，没有放宽镜像或部署门禁。未执行真实 DeepSeek 翻译、译文质量评估、新 TikTok 买家消息、真实外发或旧镜像/数据库恢复演练；本结论不构成 production 放行。

# 结论和复测条件

**PASS，仅限 staging 部署和只读现场验收。** 搜索修复已在真实会话上得到 230→1 的可观察结果；译文仅证明入口可用，未证明模型返回质量。镜像、运行配置或公网状态变化时须重跑相应门禁。
