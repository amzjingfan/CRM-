---
record_id: TR-MVP-WORKSPACE-COMPOSER-MENU-001-20261020-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-WORKSPACE-COMPOSER-MENU-001
tested_sha: fdb08729d7decd74f473c9f6dfc25d2a5e919415
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-COMPOSER-MENU-001-20261020-R01.md
requirement_ids: [MVP-WORKSPACE-COMPOSER-MENU-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: Windows local build and isolated browser; Rootless Docker staging and signed-in browser
created_at: 2026-10-20T12:06:01Z
updated_at: 2026-10-20T13:07:03Z
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT=centralized`。源码候选 `128580d92dd82de2b2508b03a12a2df1916e0ebb` 的受测构建输入与合入主线 `fdb08729d7decd74f473c9f6dfc25d2a5e919415` 相同。后端测试位于 `src/tests/backend/` 与 `src/tests/integration/postgres/`；前端契约和浏览器交互分别位于 `src/tests/frontend/contract/`、`src/tests/frontend/browser/`。浏览器用合成数据拦截 `/v1/`，不向真实 TikTok 发送。

# 命令和逐项结果

- 后端 `uv run ruff check . ../tests/backend ../tests/integration/postgres` 与 `uv run ruff format --check . ../tests/backend ../tests/integration/postgres`：通过；`uv run mypy app scripts`：187 个源文件通过。
- 后端 PowerShell 中 `$env:PYTHONPATH='.'; uv run pytest -q`：2198 passed、29 skipped、2 个既有 warning，279.89 秒；翻译领域定向用例 37/37 通过。首次定向调用未设置 `PYTHONPATH` 导致 `app` 导入失败，设为 `.` 后正常，未改代码来掩盖错误。
- 前端 `npm run lint`：0 错误、2 个未改动文件的既有 warning；`npm run typecheck`、`npm run test`（47/47）、`npm run build` 均通过。
- 前端生产构建 + `npm run test:ui`：39/39 通过。开发服务冷编译曾令整轮浏览器测试超时，改用生产构建后完整通过；最终菜单/异步选择修订后受影响的工作台浏览器 9/9、生产构建和 lint 再次通过。
- staging 手动 `Test-StagingProductionGates.ps1 -ValidateOnly/-Deploy`：分别为 `validated` / `passed`；前后端运行镜像源码 revision 均为 `fdb08729d7decd74f473c9f6dfc25d2a5e919415`。迁移头 `025_workspace_actions`，固定 TikTok 出口、Rootless 运行模式、11 个容器及三个公网健康端点 HTTP 200 均通过。原单店人工发送、Webhook 读取和工作台翻译开启；自动回复、通用 LLM、高风险写入关闭。见[预检](../../../release/evidence/staging/crm-staging-composer-menu-validate-20261020.json)与[部署](../../../release/evidence/staging/crm-staging-composer-menu-deploy-20261020.json)。用户已明确不使用 GitHub Actions 作为本轮门禁。GitHub Actions run `39416873637` 的两项作业均为零步骤、无 runner，不能计为测试通过。
- staging 已登录真实授权会话的浏览器烟测：打开英语与“更多”菜单，12 个扩展语言均显示；发送方式菜单显示“直接发送”和“翻译后发送”。合成草稿进入直接发送审阅后退出；同一合成中文草稿调用现有 DeepSeek，得到英文 `Interface test, do not send`，进入翻译后发送审阅后退出。两种方式均仍需单独点击“确认并发送”。最后清空草稿，计数回到 `0/2000`，翻译和发送按钮禁用。本轮没有向买家外发。

# REQ/AC 或门禁与证据映射

- AC-01：2000 字限制、计数和 Enter/Shift+Enter/输入法组合态由前端浏览器回归覆盖。
- AC-02：英语/更多语言选择、翻译预览及草稿或语言切换导致的预览失效由浏览器、API/Prompt 契约和后端领域测试覆盖。
- AC-03：直接原文与翻译后待发送正文进入同一审阅弹窗；异步响应过期不得打开审阅，且最终发送仍需独立人工确认；浏览器和既有服务契约覆盖。
- AC-04：上述 staging 不可变镜像、手动门禁、公网健康及已登录页面核对均通过。

# 缺陷、未执行项与残余风险

本轮不逐语言评价真实 DeepSeek 翻译质量，不向 TikTok 买家外发测试消息。Production G8 No-Go 不变。

# 结论和复测条件

本地与 staging 现场验收均通过，范围限定为本任务的发送栏和受控英语合成翻译烟测；production 不在本结论内。
