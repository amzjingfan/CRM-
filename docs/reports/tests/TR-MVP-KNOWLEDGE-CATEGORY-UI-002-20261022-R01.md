---
record_id: TR-MVP-KNOWLEDGE-CATEGORY-UI-002-20261022-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-KNOWLEDGE-CATEGORY-UI-002
tested_sha: 4244ad8cd36f3924897e558342d9e8b89eb457f1
implementation_record: docs/records/implementation/IR-MVP-KNOWLEDGE-CATEGORY-UI-002-20261022-R01.md
requirement_ids: [MVP-KNOWLEDGE-CATEGORY-UI-002]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: Windows local worktree; Next.js 16.3.8 production build on 127.0.0.1:41233; synthetic Chrome API interception
created_at: 2026-10-22T12:27:22Z
updated_at: 2026-10-22T12:27:22Z
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT: centralized`。前端契约位于 `src/tests/frontend/contract/`，浏览器交互位于 `src/tests/frontend/browser/`。本地浏览器拦截 API 返回合成店铺和分类，不写真实店铺数据。

# 命令和逐项结果

- 新增用例先红：缺少原型分类的知识库浏览器测试失败；跨店铺 URL 分类回归修复前失败，修复后通过。
- `npm run build`：通过，知识库与 Agent 路由均可生成。
- `npm run typecheck`：通过。
- `npm run lint`：0 error，5 条仓库既有 warning，本次知识库代码无新 warning。
- `npm run test`：48/48 通过。
- `UI_BASE_URL=http://127.0.0.1:41233 UI_CACHE_EXPECT_PRODUCTION=1 npm run test:ui`：生产构建浏览器测试 66/66 通过。
- `git diff --check`：无空白错误；源码提交仅含知识库页面、该页浏览器测试及产品事实文档。

# REQ/AC 或门禁与证据映射

- AC-01：浏览器断言五个预置分类、两个分组、实时数量及空预置项无虚构 ID；截图人工对照原型侧栏。
- AC-02：浏览器断言新增“店铺专属”进入自定义组、自动选中、写入当前店铺、刷新保持且切店隔离。
- AC-03：浏览器覆盖筛选时角标稳定、空预置项显式创建、同名拦截、失败反馈、跨店铺 URL 分类自动清除。
- AC-04：Agent 源文件无差异；全量浏览器中的 Agent 回归通过。

# 缺陷、未执行项与残余风险

开发模式的 HTML 缓存头测试与既有预期不符，改在生产构建下执行并通过。未运行后端测试，因为本次未改后端。未部署 staging，也未使用真实账号核对分类数据；大量自定义分类时多次计数请求的耗时需在实际规模下观察。

# 结论和复测条件

本次本地前端验收通过。若更改知识库源码、测试或交付说明，需重新绑定 subject SHA 并重跑受影响验证；staging 和 production 发布分别走既有门禁。
