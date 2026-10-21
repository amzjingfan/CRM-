---
record_id: TR-MVP-WORKSPACE-BROWSER-COMMENTS-001-20261021-R03
record_type: test
revision: R03
status: PARTIAL
task_id: MVP-WORKSPACE-BROWSER-COMMENTS-001
tested_sha: f951e294514bdfcd1eb79ab59228d9f953ba5d2b
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-BROWSER-COMMENTS-001-20261021-R03.md
requirement_ids: [MVP-WORKSPACE-BROWSER-COMMENTS-001]
acceptance_ids: [AC-02, AC-03]
environment: Windows local backend and production Next.js browser with intercepted synthetic APIs
created_at: 2026-10-21T09:27:22Z
updated_at: 2026-10-21T09:27:22Z
supersedes: docs/reports/tests/TR-MVP-WORKSPACE-BROWSER-COMMENTS-001-20261021-R02.md
---

# 测试范围、环境与 TEST_LAYOUT

遵守集中测试布局；浏览器用例只拦截 `/v1/` 并使用合成数据，不访问真实买家或平台。旧版缺陷先由订单卡用例复现为红灯：完成订单仍显示英文 `Delivered`，未知英文物流描述被误当成“物流状态”。

# 命令和逐项结果

- 最终源码 `f951e294`：从 `src/backend` 运行 `PYTHONPATH='.' .\.venv\Scripts\python.exe -m pytest -q`，2223 passed、29 skipped、2 个依赖弃用 warning；`ruff check . ../tests/backend ../tests/integration/postgres`、`ruff format --check ...`、`mypy app scripts` 通过。
- 从 `src/frontend` 运行 `npm run typecheck`、`npm run test`（47/47）、`npm run lint`（0 error、4 个既有 warning）、`npm run build` 均通过。
- 生产构建启动于 `127.0.0.1:3101`，`UI_CACHE_EXPECT_PRODUCTION=1 npm run test:ui`：52/52。新增用例覆盖 `Delivered`、派送中、运送中、退回、未知描述，验证翻译按点击触发、失败保留原文且不发送消息。
- 开发服务上运行完整浏览器用例曾 50 passed、1 failed、1 skipped：HTML 缓存测试要求生产 `no-store`，开发服务返回 `no-cache`；停止开发服务并使用上述生产构建重跑后 52/52，未修改缓存断言。

# REQ/AC 或门禁与证据映射

AC-02 的中文状态和小型翻译交互由新增浏览器与服务测试覆盖；翻译服务拒绝未核对的订单，已核对的关闭会话也可只读翻译，审计不包含原文。AC-03 的本地后端、前端、生产构建通过；staging 新版本发布及真实登录态视觉核对待完成。

# 缺陷、未执行项与残余风险

未调用真实 DeepSeek 或 TikTok 翻译接口，避免为合成验证产生外部调用；未把合成浏览器视为真实店铺验收。未知物流原文不会被猜为特定阶段，显示“状态待更新”。production 仍 No-Go。

# 结论和复测条件

本地回归通过，staging 尚未更新，因此任务整体 `PARTIAL` 并保留 `VERIFYING`。主线合并后按原有门禁部署，并在登录态订单卡复核中文状态及翻译按钮。
