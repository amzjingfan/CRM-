---
record_id: TR-MVP-DEPARTMENT-UNIFIED-DISPATCH-001-20261030-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-DEPARTMENT-UNIFIED-DISPATCH-001
tested_sha: f86458c35bf4a76c2d3dc8765d1186b41cf978e0
implementation_record: docs/records/implementation/IR-MVP-DEPARTMENT-UNIFIED-DISPATCH-001-20261030-R01.md
requirement_ids: [MVP-DEPARTMENT-UNIFIED-DISPATCH-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05, AC-06]
environment: Windows; Python uv locked environment; isolated Docker PostgreSQL 5433 at migration 045; Next.js 16.4.2 local production build
created_at: 2026-10-30T11:28:22Z
updated_at: 2026-10-30T11:28:22Z
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

TEST_LAYOUT: centralized。只使用隔离 `crm_test` PostgreSQL 和本地 3103 端口的生产构建浏览器；不连接 staging 业务数据库，不调用真实 TikTok，不向买家发送消息。

# 命令和逐项结果

- `TEST_DATABASE_URL=postgresql+asyncpg://crm_test:crm_test@127.0.0.1:5433/crm_test python -m pytest -q`：2730 passed、3 skipped、2 第三方弃用警告；隔离库迁移头 `045_dept_dispatch_login`。
- `python -m ruff check .`、`python -m ruff format --check .`：均通过，339 文件格式符合要求。`python -m mypy app scripts`：284 个源文件无问题。
- `npm run test`：55 passed。`npm run typecheck`、`npm run build`：通过。`npm run lint`：0 error、8 个既有 warning。
- `UI_BASE_URL=http://127.0.0.1:3103 npm run test:ui`：165 passed、0 failed、1 条按条件跳过；另以 `UI_CACHE_EXPECT_PRODUCTION=1` 对生产资源指纹用例单独复测，1 passed。账号目录、下拉多选和部门统一派单均包含在完整浏览器回归中。
- 额外建立一次性隔离数据库，从 044 插入两家店铺（一开一关）及同一客服（一开一关），升级到 045 后查询得 `045_dept_dispatch_login|true|true|2`；测试库已按精确名称删除。
- `git diff --check`：通过。

# REQ/AC 与证据映射

AC-01：浏览器账号编辑多选与视口菜单测试。AC-02/03：真实 PostgreSQL 主管权限、跨店候选、队列与人工归属集成测试。AC-04：认证会话与离线重派测试。AC-05：主管全账号只读浏览器测试及后端联系方式隐藏测试。AC-06：全量后端、前端、构建、迁移和审查。

# 缺陷、未执行项与残余风险

首次后端全量命令误把测试库端口写成 55433，导致末段集成连接失败；核对容器实际映射 5433 后在正确环境完整复跑通过。此前被修复的兼容失败不计本次最终结论。没有执行真实登录账号写入、真实平台入站、消息发送、退款、staging 或 production 部署；这些不属于本地源代码验收。

# 结论和复测条件

本地候选 PASS。发布前仍需从合并主线取得精确前后端镜像、私有备份、045 迁移预检、运行开关核对及现场只读验证。
