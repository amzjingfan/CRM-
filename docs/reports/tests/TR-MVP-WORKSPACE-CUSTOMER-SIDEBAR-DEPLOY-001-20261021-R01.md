---
record_id: TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-DEPLOY-001-20261021-R01
record_type: test
revision: R01
status: PARTIAL
task_id: MVP-WORKSPACE-CUSTOMER-SIDEBAR-DEPLOY-001
tested_sha: 433f340de451202e776c41ae1a59739f90dc385e
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-DEPLOY-001-20261021-R01.md
requirement_ids: [MVP-WORKSPACE-CUSTOMER-SIDEBAR-DEPLOY-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: staging Rootless Docker; public HTTPS; official TikTok read-only API
created_at: 2026-10-20T17:36:39Z
updated_at: 2026-10-20T17:58:20Z
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT=centralized`。镜像构建输入为已合并 `main=433f340de451202e776c41ae1a59739f90dc385e`。订单源码候选 `6f8f6c05` 的本地回归见其独立 [TR](TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-ORDERS-001-20261021-R01.md)：隔离 PostgreSQL 2232 passed/3 skipped，前端契约 47/47，生产浏览器 42/42。部署不使用 GitHub Actions 作为门禁。

# 命令和逐项结果

- 手动 `Test-StagingProductionGates.ps1 -ValidateOnly` 返回 `validated`，`-Deploy` 返回 `passed`；完整镜像摘要、运行模式与开关见关联 IR 的两份低敏 JSON。
- 部署后 Rootless Docker 11 个容器运行、迁移头 `025_workspace_actions`；公网 `/healthz`、`/v1/health`、`/v1/health/ready` 为 HTTP 200，固定 TikTok 出口通过。
- 官方只读探针：授权会话订单数 1、订单号搜索结果 1，商品项/金额/物流字段存在；未授权会话返回 404。店铺商品第一页 20/总 27，优惠券第一页 15/总 19。探针只验证服务端响应，不证明浏览器卡片呈现。
- 当前 staging 前端已更新为合并主线 `e4e4622c` 构建的发送栏镜像；在该已部署页面拦截 `/v1/` 注入合成会话运行两项客户侧栏浏览器交互测试，订单状态/物流号搜索/金额明细和商品 SKU/优惠券填入草稿均通过（2/2）。三张本地诊断截图可见订单、商品、优惠券卡片；测试未使用真实买家资料，也未调用真实发送接口。
- 对同一 staging 前端以 375px 视口注入合成会话，打开客户侧栏抽屉，核对其边界位于视口内；展开订单金额明细与商品 SKU 表，再切换优惠券，三个卡片均可见且无横向溢出。本地诊断截图保存在忽略的测试临时目录，不作为真实登录态证据。
- Codex 已登录浏览器连接连续超时，标记 `UI_UNAVAILABLE`；未取得真实用户会话侧栏截图。

# REQ/AC 或门禁与证据映射

- AC-01：合并主线、不可变镜像及旧运行快照已核对。
- AC-02：手动预检、部署、健康、固定出口、数据库头与原单店运行边界通过。
- AC-03：服务层订单/商品/优惠券与隔离只读通过；已登录工作台 UI 待核对，因此 AC-03 未完成。
- AC-04：低敏机器证据、旧镜像和私有备份已留存；无外发、退款、发券或 production 发布。

# 缺陷、未执行项与残余风险

浏览器连接不可用，尚未核对真实订单卡、产品与优惠券在已登录侧栏的视觉呈现、搜索/分页交互。当前 staging 随后只替换了前端发送栏镜像 `e3e286a8…5ee8606`，后端订单读取镜像 `67da479a…22281` 保持；合成浏览器 2/2 只证明当前前端资产和交互可用，真实 UI 核对须以当前页面为准。

# 结论和复测条件

部署与官方只读服务响应通过，整体 `PARTIAL`。取得真实登录态侧栏截图并核对订单、商品、优惠券及无权限表现后，才能将部署任务标记 DONE。
