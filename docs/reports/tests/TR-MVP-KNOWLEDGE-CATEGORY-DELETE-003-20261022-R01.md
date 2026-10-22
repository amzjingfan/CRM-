---
record_id: TR-MVP-KNOWLEDGE-CATEGORY-DELETE-003-20261022-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-KNOWLEDGE-CATEGORY-DELETE-003
tested_sha: a915c575753093f0620285b20357c39c2df83671
implementation_record: docs/records/implementation/IR-MVP-KNOWLEDGE-CATEGORY-DELETE-003-20261022-R01.md
requirement_ids: [MVP-KNOWLEDGE-CATEGORY-DELETE-003]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: Windows local worktree; Next.js 16.3.8 production build on 127.0.0.1:41234; synthetic Chrome API interception
created_at: 2026-10-22T13:10:10Z
updated_at: 2026-10-22T13:10:10Z
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT: centralized`。浏览器用例在 `src/tests/frontend/browser/`，契约用例在 `src/tests/frontend/contract/`。浏览器拦截 API 并使用合成店铺、分类与知识，不访问真实业务数据。

# 命令和逐项结果

- 新增删除用例在实现前因侧栏缺少删除按钮而失败，修复后通过。
- `npm run build`：通过，Next.js 生产构建和 TypeScript 阶段通过。
- `npm run typecheck`：通过。
- `npm run lint`：0 error、5 条既有 warning，本次文件无新 warning。
- `npm run test`：48/48 通过。
- `UI_BASE_URL=http://127.0.0.1:41234 UI_CACHE_EXPECT_PRODUCTION=1 npm run test:ui`：67/67 通过；新增用例的定向复跑 1/1 通过。
- `git diff --check`、`git diff --cached --check`：无空白错误。

# REQ/AC 或门禁与证据映射

- AC-01：浏览器验证仅自定义分类显示侧栏删除入口，预置与他店分类无入口，取消确认后零请求。
- AC-02：浏览器模拟 204 成功，验证当前分类、URL、侧栏及刷新状态；服务端现有实现只删除没有子分类、FAQ 或文档的空分类。
- AC-03：浏览器模拟 409，分类保留并显示错误；断言删除请求仅指向当前店铺分类且带幂等键。延迟 DELETE 后切回待删分类的用例验证最新状态与 URL。
- AC-04：Agent 页面及公共 API 无差异；生产浏览器全量包含 Agent 回归。

# 缺陷、未执行项与残余风险

只读 UI 审查发现删除期间切换分类的旧闭包请求竞态、演示文件静默改归属和管理弹窗按钮重名，已修复后复审未发现阻断问题。演示文件删除前阻止逻辑由代码审查确认，未单独模拟上传后删除。未运行后端测试或部署 staging/production；真实登录态、真实店铺权限和数据由独立发布验收核对。GitHub Actions 结果不由本地测试推断。

# 结论和复测条件

本地前端验收通过。若改变知识库源码、浏览器测试或交付说明，须重新绑定 subject SHA 并重跑受影响验证；staging/production 走独立门禁。
