---
record_id: TR-MVP-WORKSPACE-COMPOSER-FLYOUT-001-20261021-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-WORKSPACE-COMPOSER-FLYOUT-001
tested_sha: ac46e7a4461a3c41588f321f31eed6f0c59c52ff
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-COMPOSER-FLYOUT-001-20261021-R01.md
requirement_ids: [MVP-WORKSPACE-COMPOSER-FLYOUT-001]
acceptance_ids: [AC-01, AC-02, AC-03]
environment: Windows local; Next.js 16.3.8 webpack production build; Chrome synthetic browser
created_at: 2026-10-20T17:11:01Z
updated_at: 2026-10-20T17:11:01Z
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT=centralized`，前端契约位于 `src/tests/frontend/contract/`，浏览器行为位于 `src/tests/frontend/browser/`。浏览器路由使用合成数据，不调用真实 TikTok 发送或 DeepSeek。

# 命令和逐项结果

- 修复前新增定向浏览器用例失败：计数实际为 `0/2000 · 真实 TikTok 发送`，参考图要求只显示 `0/2000`。
- 修复后 `npm run lint`：0 error、4 个既有 warning；`npm run typecheck`：通过；`npm run test`：47/47 通过。
- `npm run build -- --webpack`：生产构建通过；对最终候选 SHA 执行 `UI_BASE_URL=http://127.0.0.1:3133`、`UI_CACHE_EXPECT_PRODUCTION=1` 的 `npm run test:ui`：43/43 通过，含菜单与窄屏新用例。
- 曾在开发服务器运行完整浏览器套件：41 passed、1 failed、1 skipped；唯一失败是生产缓存头用例在开发模式得到 `no-cache`。改用生产构建后完整 43/43 通过，未更改该用例或门禁。
- 生产构建的合成页面截图人工核对：1440×900 布局中计数左置、按钮右置，语言子菜单在主菜单右侧；375px 测试确认子菜单仍在视口内。

# REQ/AC 或门禁与证据映射

- AC-01：计数字符串和按钮布局由新浏览器用例及合成截图核对。
- AC-02：主/子菜单相邻、桌面和窄屏边界由新用例核对；原直接发送与翻译后发送仍分别进入人工审阅，现有用例通过。
- AC-03：lint、类型、契约、生产构建和完整浏览器结果如上。本任务为本地源码验收，staging 由 `MVP-WORKSPACE-COMPOSER-FLYOUT-DEPLOY-001` 独立核对。

# 缺陷、未执行项与残余风险

未在已登录 staging 页面核对新代码；该项不计入本 TR 的 PASS，部署任务完成前不能称为线上界面已修复。未向真实买家外发，production No-Go。

# 结论和复测条件

本地源码候选 `ac46e7a4461a3c41588f321f31eed6f0c59c52ff` 的相关验证通过。若前端源码或测试再次改变，重跑受影响检查；staging 发布后另行现场验收。
