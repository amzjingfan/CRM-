---
record_id: TR-MVP-WORKSPACE-BROWSER-COMMENTS-001-20261021-R01
record_type: test
revision: R01
status: PARTIAL
task_id: MVP-WORKSPACE-BROWSER-COMMENTS-001
tested_sha: 975430475a03d04d91ccc6142eecfb8e0e70aaa7
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-BROWSER-COMMENTS-001-20261021-R01.md
requirement_ids: [MVP-WORKSPACE-BROWSER-COMMENTS-001]
acceptance_ids: [AC-01, AC-02, AC-03]
environment: Windows, Python uv, Node 24, local Next production server, intercepted synthetic API
created_at: 2026-10-21T07:15:44Z
updated_at: 2026-10-21T07:15:44Z
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

后端测试位于 `src/tests/backend/`，前端契约及浏览器测试位于 `src/tests/frontend/`。浏览器拦截 `/v1/` 使用合成数据，没有真实 TikTok 调用、买家消息、退款或发券。

# 命令和逐项结果

- 对最终源码 SHA 运行 `uv run python -m pytest ../tests/backend/domain/test_workspace_search_translation.py -q`：6 passed；`uv run mypy app/workspace`：7 个文件通过；`uv run ruff check app/workspace` 与 `uv run ruff format --check app/workspace`：通过。
- 提交前运行完整后端套件：2222 passed、3 skipped、2 warnings；最后仅撤回不可靠的轨迹动作码映射，撤回后定向测试 19 passed。完整套件没有在最终提交上重跑。
- 对最终源码 SHA 运行 `npm run typecheck`：通过；`npm run lint`：0 error、4 个既有 warning；`npm test`：47/47；`npm run build`：通过。
- 对最终源码 SHA 的本地生产构建，`UI_BASE_URL=http://127.0.0.1:3102 UI_CACHE_EXPECT_PRODUCTION=1 npm run test:ui`：49/49；包含会话及商品触底翻页、多词搜索、AI 草稿、复制值、订单字段同显、原始轨迹状态和商品图片。
- `git diff --check`：通过；未运行 GitHub Actions。

# REQ/AC 或门禁与证据映射

- AC-01：后端未读总数范围测试及前端 49 条浏览器用例中对应的滚动、搜索和 AI 用例。
- AC-02：浏览器用例验证真实值复制、卡片整组字段、物流原文、商品图片和规格/货号；无自动发送。
- AC-03：本地静态、契约、生产构建及浏览器均通过；staging 手动部署与登录态现场核对尚待执行。

# 缺陷、未执行项与残余风险

完整后端套件提交后未重跑；本次新增的后端路径已做定向复测。真实店铺图片、物流和上游时延尚需 staging 现场核对。生产未放行。

# 结论和复测条件

本地实现通过，整体因 staging 尚未发布与现场核对为 `PARTIAL`。发布后形成新的现场 TR 修订。
