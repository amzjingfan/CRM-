---
record_id: TR-MVP-OAUTH-STATUS-UI-001-20261008-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-OAUTH-STATUS-UI-001
tested_sha: 039487e6a4ec0bfe6b7a20f026c07604f02144b1
implementation_record: docs/records/implementation/IR-MVP-OAUTH-STATUS-UI-001-20261008-R01.md
requirement_ids: [G1]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: Windows local, Node.js, Chrome headless, isolated local Next.js server with synthetic API responses
created_at: 2026-10-08T14:35:00+08:00
updated_at: 2026-10-08T14:35:00+08:00
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT: centralized`。浏览器测试位于 `src/tests/frontend/browser/`，只访问本地 Next 页面并拦截 `/v1/` 使用合成数据；无真实 TikTok 或 staging 写入。本机 `npm ci` 在依赖准备中停滞，随后从同版本已安装包补齐本 worktree 的 Next 与图标包；CI 的干净依赖安装仍须通过。

# 命令和逐项结果

- 修复前：`node --test --test-name-pattern='connected URL does not claim success' ../tests/frontend/browser/ui-regressions.test.mjs`：浏览器页面加载后期望的失败提示超时，复现 URL 宣称成功但 job 实际 failed 的缺陷。
- 修复后同命令：1 passed。
- 最终生产构建服务上：`node --test --test-name-pattern='TikTok OAuth processing return|connected URL' ../tests/frontend/browser/ui-regressions.test.mjs`：3 passed，覆盖真实 job 状态成功、失败、缺失 job。
- `node --test ../tests/frontend/contract/*.test.mjs`：41 passed。
- `node frontend/node_modules/eslint/bin/eslint.js --config eslint.config.mjs frontend tests/frontend`：0 errors；既有 2 warnings 位于 login/AppShell，与本任务无关。
- `node node_modules/typescript/bin/tsc --noEmit`：通过。
- `node node_modules/next/dist/bin/next build`：通过，生产构建包含 `/settings/channels`。
- `git diff --check` 与新证据 JSON 解析：通过。

# REQ/AC 或门禁与证据映射

AC-01/02 由三个隔离浏览器用例覆盖；AC-03 由点击处理中的 `setNotice("")` 与代码复核覆盖；AC-04 由上述静态检查、契约测试与构建覆盖。现场入口/数据库低敏汇总证明新授权未完成，不属于该页面修复的通过结论。

# 缺陷、未执行项与残余风险

本地首次浏览器运行因不完整 `node_modules/next` 失败在编译前，未当作缺陷红灯；补齐后才观察到真实业务断言失败。未发布新前端镜像，未执行 staging 页面复验或 TikTok 同一 callback 重放。G1 保持部分通过，production 未放行。

# 结论和复测条件

对候选代码 `039487e6a4ec0bfe6b7a20f026c07604f02144b1` 的页面修复为 PASS。合并后若发布到 staging，仍须核对镜像摘要、页面提示和真实回调；不能以本 TR 代替 G1。
