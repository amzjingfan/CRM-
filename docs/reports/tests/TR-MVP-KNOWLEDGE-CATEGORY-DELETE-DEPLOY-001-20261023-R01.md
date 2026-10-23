---
record_id: TR-MVP-KNOWLEDGE-CATEGORY-DELETE-DEPLOY-001-20261023-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-KNOWLEDGE-CATEGORY-DELETE-DEPLOY-001
tested_sha: 2ccc93b2939781ae68e35abe6c3ef4470f69ab69
implementation_record: docs/records/implementation/IR-MVP-KNOWLEDGE-CATEGORY-DELETE-DEPLOY-001-20261023-R01.md
requirement_ids: [MVP-KNOWLEDGE-CATEGORY-DELETE-DEPLOY-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: staging Rootless Docker linux/amd64; clean main bundle for image build; local frontend checks; deployed assets via synthetic browser with live API blocked
created_at: 2026-10-23T01:23:48Z
updated_at: 2026-10-23T01:23:48Z
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT: centralized`。本次验证对象是从精确 `main=2ccc93b2939781ae68e35abe6c3ef4470f69ab69` 发布到 staging 的前端镜像与知识库页面；前端合同测试位于 `src/tests/frontend/contract/`，页面合成测试使用现有浏览器用例。私有运行证据只存 staging，低敏汇总在 [部署证据](../../../release/evidence/staging/crm-staging-knowledge-category-delete-20261023.json)。

# 命令和逐项结果

- 干净 Git bundle SHA-256、源码 HEAD 与工作区清洁度核对通过；前端 Docker `linux/amd64` 生产构建通过，OCI revision 为 subject SHA。手动 `docker push` 返回候选摘要；staging 导入后镜像摘要、标签和 revision 一致。
- `npm run test`：48/48 通过；`npm run typecheck`：通过；`npm run lint`：0 error、5 条既有 warning。Docker 内 Next.js 生产构建通过。
- 六角色不可变镜像预取：`passed`；配置 `ValidateOnly`：`validated`；PostgreSQL 私有备份：权限 `0600`、`pg_restore -l` 可读；staging `Deploy`：`passed`。
- 部署后运行前端摘要精确匹配新候选，后端与检索摘要保持原值；11 个容器、迁移头 `027_tiktok_direct_store_oauth`、固定出口与原单店人工辅助模式核对通过。公网 `/healthz`、`/v1/health`、`/v1/health/ready`、`/knowledge` 均为 HTTP 200；无查询参数 `/knowledge` 返回 `private, no-cache, no-store`，页面引用的指纹 CSS/JS 返回 200 且为 immutable。
- 通过本地代理读取**已部署 staging 静态资源**，代理拒绝所有真实 `/v1` 请求，再以合成 API 数据执行浏览器交互：自定义分类删除确认、失败、成功及刷新 1/1 通过；自定义分类新增、归入“自定义分类”并选中 1/1 通过。

# REQ/AC 或门禁与证据映射

- AC-01：精确主线源码、构建平台、OCI revision、新前端不可变摘要，以及后端和部署输入不变的对比。
- AC-02：原三摘要和人工辅助模式冻结、六角色预取、`ValidateOnly`、可读私有备份后才 `Deploy`；各门禁结论与私有原件哈希见部署证据。
- AC-03：运行三摘要、11 容器、迁移头、固定出口、公网健康、缓存头、指纹资源与部署资源合成浏览器交互通过。
- AC-04：未执行真实店铺修改、外部消息或 production 部署；自动回复和高风险写入保持关闭。

# 缺陷、未执行项与残余风险

官方 GitHub Actions 发布运行在零步骤失败，不能记为 CI 通过。手动推送给出摘要，但独立远端 manifest 查询发生 TLS 超时；候选镜像已在 staging 导入并按该摘要运行。未直接用真实登录态和真实店铺数据点击删除；合成浏览器拦截全部实时 API，故不能推断真实店铺权限或删除结果。本任务无后端代码变化，未重跑后端全量测试。production G8 仍为 No-Go。

# 结论和复测条件

按本次 staging 部署与合成交互验收范围为 `PASS`。若镜像摘要、前端源码或运行模式改变，应重新执行对应构建、门禁和页面验证；真实登录态交互若作为后续验收要求，需单独核对且不得操作真实有内容的分类。
