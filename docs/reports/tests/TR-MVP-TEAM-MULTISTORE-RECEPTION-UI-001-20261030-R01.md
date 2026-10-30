---
record_id: TR-MVP-TEAM-MULTISTORE-RECEPTION-UI-001-20261030-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-TEAM-MULTISTORE-RECEPTION-UI-001
tested_sha: 0d8b66e067bad3b96e9e78db3f98cef0acc93c9e
implementation_record: docs/records/implementation/IR-MVP-TEAM-MULTISTORE-RECEPTION-UI-001-20261030-R01.md
requirement_ids: [MVP-TEAM-MULTISTORE-RECEPTION-UI-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: local Next.js 16.4.2 and Chrome headless, API mocks, no real buyer messages
created_at: 2026-10-30T16:17:31+08:00
updated_at: 2026-10-30T16:17:31+08:00
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT=centralized`；行为测试位于 `src/tests/frontend/browser/ui-regressions.test.mjs`。使用本地 `127.0.0.1:3102` Next 开发服务和模拟管理 API，不接触 staging 数据写入。

# 命令和逐项结果

- `npm ci --no-audit --no-fund`：通过。
- `npm run typecheck`：通过。
- `npm run lint`：0 错误，8 条现有其他文件警告。
- `npm test`：55/55 通过。
- `npm run build`：通过。
- `UI_BASE_URL=http://127.0.0.1:3102 node --test src/tests/frontend/browser/ui-regressions.test.mjs`：58/58 通过。
- `git diff --check`：通过。

# REQ/AC 与证据映射

AC-01：账号列表角色名称和店铺范围浏览器断言。AC-02：双店创建、编辑角色与店铺、仅改基础资料不提交 `assignments` 的请求体断言。AC-03：派单保存后已开启但无人可接待、管理员资格不可勾选和工作台心跳解释的浏览器断言。AC-04：类型、lint、契约、构建和全浏览器回归。

# 缺陷、未执行项与残余风险

第一次针对性测试因旧提示语断言失败，已更新断言后重跑通过。未对 staging 真实账号执行写操作，未验证真实 TikTok 入站或自动派单。

# 结论和复测条件

本地源码验收通过。发布 staging 后仍需只读页面、运行镜像和安全开关核对。
