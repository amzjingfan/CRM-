---
record_id: TR-MVP-OAUTH-REDIRECT-001-20260924-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-OAUTH-REDIRECT-001
tested_sha: 8a1b81f44478f2c71c4f275873cb68d0b8f4528f
implementation_record: docs/records/implementation/IR-MVP-OAUTH-REDIRECT-001-20260924-R01.md
requirement_ids: [MVP-OAUTH-REDIRECT-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: Windows PowerShell; uv/Python 3.11; isolated PostgreSQL 5433 tmpfs; Node.js and Next.js 16.3.4 local production build; synthetic browser API data
created_at: 2026-09-24T16:18:00+08:00
updated_at: 2026-09-24T16:23:00+08:00
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

`centralized`：新增后端行为测试在 `src/tests/backend/platform/`，真实事务与双 worker 交错测试在 `src/tests/integration/postgres/`，前端契约和本机生产模式浏览器测试在 `src/tests/frontend/`。测试只用合成数据和隔离 PostgreSQL，没有调用 TikTok、staging 业务数据或 production。

# 命令和逐项结果

- 修复前新后端行为测试 3 个预期失败；修复后针对 OAuth 的 36 项通过。
- 最终 subject `8a1b81f` 提交后，`src/scripts/run-postgres-integration-tests.ps1`：1662 passed、3 skipped、2 个既有依赖弃用 warning；跳过的 3 项均需要 POSIX bash。包含任务去重、双 worker 成功/失败持锁、崩溃回滚与单条失败审计测试。该 subject 相较已全量验证的源码提交 `dc5dff4` 只修正 README/部署文档迁移头描述。
- 同一隔离库 `alembic current --check-heads → downgrade -1 → upgrade head → current --check-heads` 全部退出 0，最终头为 `024_tiktok_oauth_jobs`。测试容器 `crm-postgres-test-1` 已停止并删除，`docker compose ... ps postgres-test` 为空；tmpfs 测试数据被删除，不涉及开发或生产库。
- `ruff check`、`ruff format --check` 和 `mypy app scripts` 通过。
- 最终 subject 上 `npm run lint` 0 error、既有 2 条内部导航 warning；`npm run typecheck`、`npm run test` 41/41、`npm run build` 通过。对本机生产构建执行 `UI_CACHE_EXPECT_PRODUCTION=1 npm run test:ui`：23/23、0 skipped，包括 OAuth 回跳轮询与结果反馈；本机服务随后停止。
- `git diff --check` 通过；独立只读复审已关闭初审的并发与崩溃窗口。

# REQ/AC 与证据映射

- AC-01：公开成功 callback 在平台调用前提交加密任务并返回固定站内 303；不在 URL、响应或任务明文字段暴露授权材料。
- AC-02：重复 callback 复用任务、state GETDEL 一次性消费，失败、重放和超长密文受控；真实 PostgreSQL 双 worker 不重复领取。
- AC-03：成功渠道/审计/任务终态同事务；失败保存点、持锁收尾与崩溃回滚测试通过。
- AC-04：任务状态限原发起用户及仍有效店铺权限；前端轮询显示结果，production 构建浏览器合成测试通过。

# 缺陷、未执行项与残余风险

本 TR 仅关闭代码与隔离测试。未部署 staging，也未在真实 TikTok 成功页完成新版回跳测试。当前 TikTok 对美国店铺授权报卖家类型不适用，官方页面未请求 callback；需先核对目标卖家配置。没有执行 production、真实读取、Webhook、消息写入、LLM 或自动回复。依赖弃用 warning 和 3 项 Windows 不可运行测试如上保留。

# 结论和复测条件

本机代码候选 PASS，可进入 PR/CI；真实 staging 行为须在单独部署任务留证。若 subject 构建输入变化，重跑受影响测试与复审。
