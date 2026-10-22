---
record_id: TR-MVP-KNOWLEDGE-PROTOTYPE-UI-001-20261022-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-KNOWLEDGE-PROTOTYPE-UI-001
tested_sha: 64e41b62c476ec97020dd9edc5a6b6d574dbf711
implementation_record: docs/records/implementation/IR-MVP-KNOWLEDGE-PROTOTYPE-UI-001-20261022-R01.md
requirement_ids: [MVP-KNOWLEDGE-PROTOTYPE-UI-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: Windows local worktree; Next.js 16.3.8 production build on 127.0.0.1:39471; synthetic Chrome API interception
created_at: 2026-10-22T10:42:16Z
updated_at: 2026-10-22T10:42:16Z
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT: centralized`。前端契约位于 `src/tests/frontend/contract/`，浏览器交互位于 `src/tests/frontend/browser/`；截图只写入已忽略的 `src/tests/.artifacts/`。测试在原型 UI subject 已重放到最新 `origin/main` 后执行，未连接真实店铺或上传生产文件。

# 命令和逐项结果

- `npm run typecheck`：通过。
- `npm run lint`：0 error、5 条仓库既有 warning；本次知识库代码无新 warning。
- `npm run test`：48/48 通过。
- `npm run build`：通过，`/knowledge` 与 `/agents` 均可生成。
- `UI_BASE_URL=http://127.0.0.1:39471 UI_CACHE_EXPECT_PRODUCTION=1 npm run test:ui`：生产构建 64/64 通过，包含 HTML 缓存头、知识库页面交互和 Agent 回归。
- `git diff --check`：无空白错误。`git diff origin/main...HEAD --name-only` 不包含 `src/frontend/app/agents/page.tsx`。

# REQ/AC 与证据映射

- AC-01：合成浏览器截图人工核对原型布局；760px 视口无页面级横向溢出；导航、抽屉、弹窗交互用例通过。
- AC-02：浏览器用例覆盖店铺前置、分类选择、类型筛选、详情与 Escape、归档失败反馈；现有 FAQ、层级与向量化契约继续通过。
- AC-03：浏览器用例证实 PDF 未触发导入 POST 且刷新清空，CSV 触发既有导入 POST；参数调整在本页生效且刷新恢复默认。
- AC-04：Agent 源页面无差异，生产浏览器中的 Agent 相关回归通过。

# 缺陷、未执行项与残余风险

开发服务器上的 HTML 缓存头用例返回 `no-cache`，这是已有的开发模式差异；同一用例在本次生产构建下通过。未运行后端测试，因为没有后端改动。未部署 staging，未进行真实登录态业务页面人工验收；浏览器数据为合成响应，不证明真实店铺的内容质量。

# 结论和复测条件

本任务定义的本地前端验收通过。若后续修改知识库源码、相关测试或交付说明，须重新绑定 subject SHA 并重跑受影响验证；staging/production 发布仍走独立门禁。
