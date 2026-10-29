---
record_id: TR-MVP-RECEPTION-TEAM-FEEDBACK-001-20261029-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-RECEPTION-TEAM-FEEDBACK-001
tested_sha: a156d8dc8330a3f9d7a8ae56e6d8932a71d4b481
implementation_record: docs/records/implementation/IR-MVP-RECEPTION-TEAM-FEEDBACK-001-20261029-R01.md
requirement_ids: [REQ-01, REQ-02, REQ-03, REQ-04]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: Windows, Node 24.19.0, local Next webpack production build, synthetic Playwright browser at localhost:3101
created_at: 2026-10-29T18:19:44+08:00
updated_at: 2026-10-29T18:19:44+08:00
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

集中式 `src/tests/`。浏览器使用合成账号、店铺及策略，所有 `/v1` 请求拦截；没有请求真实平台或删除真实账号。测试源于 subject SHA 对应工作树，提交只固定相同文件内容。

# 命令和逐项结果

- `npm run typecheck`：通过。
- `npm run lint`：0 error，8 条既有 warning；改动文件无告警。
- `npm run test`：52/52 前端契约通过。
- `npm run build -- --webpack`：前端生产构建通过。
- `node --test src/tests/frontend/browser/reception-management.test.mjs`：25/25 通过。覆盖欢迎语/超时更新请求无 `kind`、完整店铺名单、操作布局、已有有效期和配置行为。
- `node --test --test-name-pattern='team form|account deletion requires|department members' src/tests/frontend/browser/ui-regressions.test.mjs`：4/4 通过。覆盖启用账号不能删、已停用账号二次确认及合成 DELETE。
- `git diff --check`：通过。

# REQ/AC 与证据映射

AC-01：策略 PATCH 测试桩拒绝多余 `kind`，欢迎语和超时编辑通过。AC-02：双策略店铺名单 hover/focus 通过。AC-03：双策略操作按钮不重叠、更多菜单可用。AC-04：账号删除限制及确认浏览器测试通过，后端既有路由与服务源码核对。

# 缺陷、未执行项与残余风险

最初用 `127.0.0.1` 访问本地开发服务器时，Next 开发 HMR 跨源保护使页面停在登录检查；改用其服务地址 `localhost` 后回归通过。没有在 staging 触发真实策略写入或真实账号删除；未重跑未修改的后端全套测试。本次未测试实际有业务引用的真实员工账号删除。

# 结论和复测条件

本地改动通过；staging 需在协调发布后以已登录只读 UI 验证，并用合成策略验证编辑写入。真实永久删除不属于本次验收。
