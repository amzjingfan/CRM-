---
record_id: TR-MVP-WORKSPACE-LIVE-FEEDBACK-001-20261031-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-WORKSPACE-LIVE-FEEDBACK-001
tested_sha: 550316f4e8f6784c9ef6d05a4a9e5837dc8e86e6
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-LIVE-FEEDBACK-001-20261031-R01.md
requirement_ids: [MVP-WORKSPACE-LIVE-FEEDBACK-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
environment: Windows PowerShell, uv/Python 3.11, isolated PostgreSQL/pgvector Docker test service, Node/Next.js 16.4.2 production build on 127.0.0.1:3101, synthetic Playwright API interception
created_at: 2026-10-31T11:13:26Z
updated_at: 2026-10-31T11:25:14Z
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT: centralized`。从重放到 `origin/main=433715ec` 后的 subject `550316f4` 执行，浏览器只拦截合成 `/v1/` 响应；不读取真实买家正文、不发测试消息、不退款。

# 命令和逐项结果

| 命令 | 结果 |
|---|---|
| `uv run pytest -q`（`src/backend/`，重跑） | PASS：2901 通过、277 条件跳过、2 第三方弃用警告 |
| `./src/scripts/run-postgres-integration-tests.ps1 -TestPort 56875 -ProjectName crm-workspace-card-20261031 -PytestArgs @('-q')` | PASS：隔离 PostgreSQL 迁移到 head，3173 通过、5 条件跳过、2 第三方弃用警告；临时容器已移除 |
| `uv run pytest ../tests/backend/agent/test_prompt_semantic_review.py::test_late_model_approval_cannot_publish_after_its_deadline -q` | PASS：1/1；用于核查首次全量运行的单项失败 |
| `uv run ruff check . ../tests/backend ../tests/integration/postgres` | PASS |
| `uv run ruff format --check . ../tests/backend ../tests/integration/postgres` | PASS：587 文件已格式化 |
| `uv run mypy app scripts` | PASS：308 个源码文件 |
| `npm run lint` | PASS：0 错误、12 条已有图片/导航用法警告 |
| `npm run typecheck`、`npm run test`、`npm run build` | PASS：78/78 前端契约、类型及生产构建 |
| `node --test ../tests/frontend/browser/workspace-experience.test.mjs`（生产构建） | PASS：60/60 工作台合成浏览器 |
| `git diff --check` | PASS |

# REQ/AC 或门禁与证据映射

- AC-01：九种订单状态合成数据中缺独立支付状态、但有付款时间时显示已付款；已取消的曾付款订单明确标记退款待核实。
- AC-02：浏览器断言订单卡片草稿没有文本编辑框，二次确认后只调用 `order-card`，无普通文本发送；平台 MockTransport 断言官方请求体是 `type=ORDER_CARD` 且 content 只含订单号。
- AC-03：服务层测试覆盖确认前零读取、跨买家订单拒绝及核验后发送；既有全量后端回归覆盖权限、CSRF、幂等、同店熔断及未知对账。
- AC-04：上述前后端静态、构建和合成浏览器通过；真实买家零试发。
- AC-05：TK app 会话只读测试显示一笔已送达 CBT 订单的通用 202309 轨迹返回 14 条；本任务不改写缺失平台物流数据。

# 缺陷、未执行项与残余风险

首次全量 `uv run pytest -q` 为 2900 通过、1 失败、277 跳过；失败点是未改动的 `test_late_model_approval_cannot_publish_after_its_deadline` 超时断言。该用例单独通过，整套重跑 2901 通过，保留首次波动记录。随后在隔离 PostgreSQL/pgvector 测试库上完成迁移和全量回归，3173 通过、5 条件跳过。探索性完整 `npm run test:ui` 曾在无关 Agent 模板套件长时间无输出后人工中断，不算通过；本任务受影响的工作台文件 60/60 通过。尚未实际向 TikTok 买家发送卡片；平台最终卡片外观、staging 登录态及发布门禁待验证。

# 结论和复测条件

本地源码与合成行为 PASS；发布验收仍未完成。合并后若 staging 安全边界和候选源码可核对，再做私有备份、精确镜像、双预检、部署及只读订单 UI 检查；真实卡片发送仍需另获精确测试目标与正文授权。
