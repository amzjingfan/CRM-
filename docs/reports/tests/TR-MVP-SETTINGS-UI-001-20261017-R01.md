---
record_id: TR-MVP-SETTINGS-UI-001-20261017-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-SETTINGS-UI-001
tested_sha: 6a4398491a6956b4e55ef998debf989834f74244
implementation_record: docs/records/implementation/IR-MVP-SETTINGS-UI-001-20261017-R01.md
requirement_ids: [MVP-SETTINGS-UI-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: Windows 本地 Node 24；Next.js 16.3.8；浏览器测试使用合成 API 响应；staging 真实店铺只读复核
created_at: 2026-10-17T10:02:00+08:00
updated_at: 2026-10-17T10:56:00+08:00
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

按 `centralized` 布局执行 `src/tests/frontend/` 合约与浏览器测试；从合入后的精确 `main` 源码构建 `linux/amd64` 前端候选。浏览器测试拦截 API，另对 staging 的真实页面做只读核验。

# 命令和逐项结果

- `npm run test`：47/47 通过。
- `npm run lint`：0 错误，2 个既有警告。
- `npm run typecheck`：通过。
- `npm run build`：通过。
- 本地 Next 服务上的 `npm run test:ui`：最终修订 27 通过、1 条按配置跳过；820px 窄屏状态单行及表格横向滚动得到覆盖。
- `git diff --check origin/main...HEAD`（源码 PR）：通过。
- PR #280、#282、#284 已合入；最终 subject `main=6a4398491a6956b4e55ef998debf989834f74244`。用户决定不运行 GitHub Actions。
- 最终 subject 再次执行 `npm test`：47/47；`docker buildx build` 通过 Next build/typecheck，OCI revision 精确匹配 subject。
- 手动镜像：`ghcr.io/cp11-gh/crm-frontend@sha256:8b2883bc0af901fa33470a2bb183fa4d2deb19b2066798453296c7353c6e7dfe`；单一 `linux/amd64` 运行清单（另有非运行 attestation），部署前在 staging 预取。
- 受审干净浅克隆源码 SHA 与 subject 一致，传输 tar 的 SHA-256 为 `dcd97a1cec8f9fc123ec519afd967b62c1ff8e6e59eb019cf1391c183356440b`。staging validate/deploy 均通过，保留后端与检索摘要，三公网健康端点均为 200，迁移为 `heads_applied`，production_release=false。见 [validate](../../../release/evidence/staging/crm-staging-settings-ui-validate-20261017-r03.json) 与 [deploy](../../../release/evidence/staging/crm-staging-settings-ui-deploy-20261017-r03.json)。
- 带身份 staging 页面刷新后：店铺列表显示 3 家真实接口返回店铺，状态“正常”单行且窄窗横向滚动；工作台真实 TikTok 会话列表显示 `10-16 15:46` 等最近消息时间，目标会话历史加载，发送输入及按钮仍禁用。

# REQ/AC 或门禁与证据映射

AC-01：合约测试覆盖有效、空值和坏时间；浏览器测试覆盖列表显示。AC-02：设置页只显示现有 API 数据；合约及浏览器筛选测试覆盖。AC-03：既有店铺新增、OAuth、员工表单等浏览器回归通过。AC-04：上述测试、静态检查和构建通过。

# 缺陷、未执行项与残余风险

本次未向 TikTok 买家发送消息，也未改变真实写入开关；授权和员工的写操作仅由合成浏览器回归覆盖，未在现场操作。一个生产缓存指纹测试按配置跳过；两个 lint 警告是既有项。

# 结论和复测条件

本地与 staging 只读验收通过。用户需刷新已有浏览器标签以取得新前端资源；真实发送能力继续关闭。
