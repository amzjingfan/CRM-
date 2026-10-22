---
record_id: TR-MVP-WORKSPACE-TRACKING-TIMELINE-001-20261022-R02
record_type: test
revision: R02
status: PARTIAL
task_id: MVP-WORKSPACE-TRACKING-TIMELINE-001
tested_sha: 39244eb15b6c11db9b7463656304de1a92153c9d
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-TRACKING-TIMELINE-001-20261022-R02.md
requirement_ids: [MVP-WORKSPACE-TRACKING-TIMELINE-001]
acceptance_ids: [AC-03, AC-04, AC-05]
environment: Windows isolated worktree; CPython 3.11 from existing project venv; Node 22; local Chrome with intercepted synthetic API
created_at: 2026-10-22T03:09:10Z
updated_at: 2026-10-22T03:09:10Z
supersedes: docs/reports/tests/TR-MVP-WORKSPACE-TRACKING-TIMELINE-001-20261022-R01.md
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT=centralized`；后端测试在 `src/tests/backend/`，前端合成浏览器测试在 `src/tests/frontend/browser/`。浏览器拦截全部 `/v1/` 请求，未接触真实店铺或买家。

# 命令和逐项结果

- 修复前新增后端两项测试确实因缺少批量服务失败；实现后 `test_workspace_translation.py`：9 passed。新增前端测试修复前因逐节点按钮而失败，实施后覆盖两包裹一次翻译、重新翻译、切回原文、单号复制、草稿预填且发送计数 0；失败保留原文与重试也通过。
- 从 `src/backend/` 执行项目 pytest 全量入口：2229 passed、29 skipped、2 条既有依赖弃用 warning。最初从仓库根直接运行时因未按 `src/tests/README.md` 配置 `_support` 搜索路径，22 项收集失败；改用权威入口后通过，不将失败尝试计作通过。
- 受影响后端文件 `ruff check` 与 `ruff format --check`：通过。受影响三服务文件 mypy：无代码错误；本机 venv 缺少既有 `passlib` 类型桩，使用 `--disable-error-code=import-untyped` 核对改动文件通过，完整严格 mypy 未通过且未冒充。
- `npm run lint`：0 errors、4 条既有 warning；`npm run typecheck`、`npm run build`：通过；`npm run test`：47 passed。
- 本地开发浏览器 `workspace-experience.test.mjs`：27 passed；生产构建同文件并启用生产缓存断言：27 passed。受影响用例额外复测通过；合成截图核对顶部动作、包裹标签、单号复制和草稿入口。
- `git diff --check`：通过；未新增密钥、迁移、依赖或真实平台写入。

# AC 映射、剩余项与结论

AC-03：一键替换全部包裹轨迹、原文切换、重新翻译、失败重试的合成浏览器验证通过。AC-04：服务端买家核对、敏感节点拒绝模型调用、响应逐项匹配、失败保留原文与低敏审计验证通过。AC-05：单号复制和物流卡片仅预填草稿、未调用消息发送通过。尚未运行 staging 发布门禁及真实登录态点击；真实 DeepSeek 成功路径未现场验证。`PARTIAL`，不能声称 staging 或 production 已放行。
