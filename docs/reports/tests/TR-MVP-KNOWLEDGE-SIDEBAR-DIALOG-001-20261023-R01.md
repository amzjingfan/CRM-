---
record_id: TR-MVP-KNOWLEDGE-SIDEBAR-DIALOG-001-20261023-R01
record_type: test
revision: R01
status: PARTIAL
task_id: MVP-KNOWLEDGE-SIDEBAR-DIALOG-001
tested_sha: f7950619487a853fa2c6afb27ff6a0ca1bd76fdc
implementation_record: docs/records/implementation/IR-MVP-KNOWLEDGE-SIDEBAR-DIALOG-001-20261023-R01.md
requirement_ids: [MVP-KNOWLEDGE-SIDEBAR-DIALOG-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: local Windows, Node.js and Next.js production build, Playwright Chromium with synthetic API responses
created_at: 2026-10-23T02:00:18Z
updated_at: 2026-10-23T02:00:18Z
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT: centralized`。测试源码位于 `src/tests/frontend/browser/` 与 `src/tests/frontend/contract/`。浏览器只访问本机前端，对 `/v1` 使用合成响应，未操作 staging 真实分类。

# 命令和逐项结果

- 修改前定向浏览器测试先复现：旧 `layer=A` 保留隐形筛选，删除按钮没有站内弹窗。
- 最终源码 `f7950619487a853fa2c6afb27ff6a0ca1bd76fdc` 上 `npm run build` 通过（含 TypeScript）；`npm run lint` 为 0 error、5 条既有 warning；`npm test` 为 48/48；生产构建上 `npm run test:ui` 为 66 passed、1 skipped、0 failed。
- 定向浏览器测试覆盖层级区块消失与旧 URL 清理；删除弹窗取消、Escape、409 失败、提交中禁用、成功、URL/刷新，以及预置和异店分类不显示删除入口。

# REQ/AC 或门禁与证据映射

- AC-01：浏览器断言侧栏无层级入口与 A/B/C/D 行，旧 `layer` 参数清理；合同测试不再要求层级筛选。
- AC-02：浏览器断言站内对话框且无原生框，取消/Escape 不发 DELETE，409 保留分类，成功后消失并清理 URL。
- AC-03：Git 差异限于知识库页面、CSS、对应测试和任务文档；未触及 Agent/后端/检索。
- AC-04：本地完整前端质量检查通过；staging 发布和已部署资源复核尚未执行。

# 缺陷、未执行项与残余风险

本记录仅覆盖源码和本地生产构建。staging 尚未部署，真实登录态与真实店铺的分类删除未执行。跳过的指纹缓存用例需生产环境开关；不将其计作通过。

# 结论和复测条件

本地修复验证通过；由于 AC-04 的 staging 部分待执行，任务总体 `PARTIAL`。发布后应重新核对运行镜像、页面资源及合成交互，形成后续修订。
