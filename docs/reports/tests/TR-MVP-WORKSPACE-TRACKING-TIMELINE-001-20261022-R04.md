---
record_id: TR-MVP-WORKSPACE-TRACKING-TIMELINE-001-20261022-R04
record_type: test
revision: R04
status: PARTIAL
task_id: MVP-WORKSPACE-TRACKING-TIMELINE-001
tested_sha: 97c5d6bb6f7734e27eaafcf779df8f8a0ff74541
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-TRACKING-TIMELINE-001-20261022-R04.md
requirement_ids: [MVP-WORKSPACE-TRACKING-TIMELINE-001]
acceptance_ids: [AC-05]
environment: Windows isolated worktree; CPython 3.11 and uv offline cache; Node 22; local Next production build with intercepted Chrome browser API
created_at: 2026-10-22T04:08:00Z
updated_at: 2026-10-22T04:08:00Z
supersedes: docs/reports/tests/TR-MVP-WORKSPACE-TRACKING-TIMELINE-001-20261022-R03.md
---

# 范围与命令结果

`TEST_LAYOUT=centralized`。从 `src/backend/` 在最终 subject 上运行 `uv run --frozen --offline pytest -q`：2233 passed、29 skipped、2 条既有依赖弃用 warning。首次全量运行时，一条历史测试构造未显式赋 `message_type` 的未落库消息，触发新响应字段校验失败；补上文本默认兼容后，相关定向测试 37 passed，并在最终提交上重跑全量通过。一次显式路径运行曾因误设 `PYTHONPATH` 导致 `_support` 收集错误；按项目 `uv run pytest` 权威入口复跑通过。

`ruff check . ../tests/backend ../tests/integration/postgres` 与 `ruff format --check . ../tests/backend ../tests/integration/postgres` 通过，324 文件已格式化；`mypy app scripts` 无错误，188 个源文件。前端 `npm run typecheck`、`npm run build` 通过；`npm run lint` 为 0 error、5 warning，其中一条是新卡片图片的性能提示，其余为既有导航和图片提示。`npm run test`：47 passed；在本地生产构建并拦截全部 `/v1/` 请求的 `workspace-experience.test.mjs`：27 passed。

# AC-05 与限制

浏览器合成用例验证两包裹切换后卡片留在发送栏、点击前和审阅弹窗中零发送、确认后只调用一次卡片 POST 且普通文本 POST 零次；已发卡片的“查看详情”显示同一完整轨迹弹窗。合成 HTTP 测试核对 TikTok `LOGISTICS_CARD`、`order_id`/`package_id` 的双层 JSON；后端行为测试验证错误包裹在发送前被拒绝、官方增强轨迹可确认订单行暂缺的包裹 ID。复制、截图与翻译沿 R03 已验收只读弹窗复用。

尚未在合入主线后部署 staging，也未用真实 TikTok 买家实际发送原生卡片；当前 `PARTIAL` 不代表平台写入成功或 production 放行。真实发送只允许坐席自行审阅并确认，结果不明时按现有对账流程处理。
