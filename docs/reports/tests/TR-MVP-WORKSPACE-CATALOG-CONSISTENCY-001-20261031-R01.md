---
record_id: TR-MVP-WORKSPACE-CATALOG-CONSISTENCY-001-20261031-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-WORKSPACE-CATALOG-CONSISTENCY-001
tested_sha: a1be18c4c266293b8fdc6c6f88514f990cfd1d19
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-CATALOG-CONSISTENCY-001-20261031-R01.md
requirement_ids: [MVP-WORKSPACE-CATALOG-CONSISTENCY-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
environment: Windows PowerShell, Python 3.12/uv, Node 22, Next.js 16.4.2 production build on 127.0.0.1:3101, Playwright synthetic /v1 fixtures
created_at: 2026-10-31T07:50:35Z
updated_at: 2026-10-31T07:50:35Z
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT: centralized`。测试源码在 `src/tests/backend/domain/`、`src/tests/backend/agent/` 和 `src/tests/frontend/`。浏览器仅拦截合成 `/v1/` 数据，不向 TikTok 买家发送消息，不触发退款。subject 在最新 `origin/main` 6074c4b0 上重放后为 `a1be18c4`。

# 命令和逐项结果

| 命令 | 最终 subject 结果 |
|---|---|
| `uv run python -m pytest -c pyproject.toml ../tests/backend/domain ../tests/backend/agent -q` | PASS：1795，1 条件跳过，1 第三方弃用警告 |
| `uv run ruff check app/workspace/sidebar.py ../tests/backend/domain/test_workspace_catalog_availability.py` | PASS |
| `uv run ruff format --check app/workspace/sidebar.py ../tests/backend/domain/test_workspace_catalog_availability.py` | PASS：2 文件已格式化（重放前同内容） |
| `uv run mypy app/workspace/sidebar.py` | PASS |
| `npm run test` | PASS：78/78 契约 |
| `npm run typecheck` | PASS |
| `npm run lint` | PASS：0 错误、12 条图片及导航用法警告 |
| `npm run build` | PASS：Next 生产构建 |
| `node --test ../tests/frontend/browser/ui-regressions.test.mjs ../tests/frontend/browser/workspace-experience.test.mjs ../tests/frontend/browser/agent-prototype.test.mjs` | PASS：138/138，0 跳过 |
| `git diff --check` | PASS（待证据尾再次核对） |

# REQ/AC 或门禁与证据映射

- AC-01：`ui-regressions`、`agent-prototype` 的知识库/Agent 侧栏与既有工作台导航同构断言通过。
- AC-02：后端专用目录测试覆盖商品列表、按 ID、详情二次校验、优惠券状态与领取时段；Agent 工具相关测试纳入 1795 项。浏览器覆盖下架、零/未知库存、不可用券，以及筛选后空页继续分页。
- AC-03：九种订单状态浏览器断言基础字段顺序与缺值展示一致。
- AC-04：摘要预览和草稿文本断言通过，合成发送调用计数为 0。
- AC-05：相关后端、前端契约、类型、lint、构建及浏览器范围通过。

# 缺陷、未执行项与残余风险

探索性 `npm run test:ui` 曾在重放前报告 161 通过、56 失败、1 跳过：多数无关套件硬编码 3124/3146 端口而本轮只运行 3101；三个旧展示断言已随实现更新。该结果不作为最终候选门禁。最终 subject 的相关三套浏览器文件 138/138 通过；未启动无关端口套件。未用真实店铺数据核对平台时间窗/库存差异；未进行 staging 登录态验收或任何部署。

# 结论和复测条件

本地候选 PASS。合并后若单独发布 staging，需复核真实店铺列表、Agent 工具结果、订单九状态与现有人工发送开关；若平台字段与合成数据不一致，回到同任务修复。
