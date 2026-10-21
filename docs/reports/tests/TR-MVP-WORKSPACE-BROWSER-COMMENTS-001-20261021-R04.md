---
record_id: TR-MVP-WORKSPACE-BROWSER-COMMENTS-001-20261021-R04
record_type: test
revision: R04
status: PASS
task_id: MVP-WORKSPACE-BROWSER-COMMENTS-001
tested_sha: ef0ec3aa4948c22c5823646abf5a0019e8c9ede0
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-BROWSER-COMMENTS-001-20261021-R04.md
requirement_ids: [MVP-WORKSPACE-BROWSER-COMMENTS-001]
acceptance_ids: [AC-02, AC-03]
environment: Windows local production Next.js and staging merged-main containers; synthetic browser API interception plus user authenticated visual check
created_at: 2026-10-21T10:27:16Z
updated_at: 2026-10-21T10:27:16Z
supersedes: docs/reports/tests/TR-MVP-WORKSPACE-BROWSER-COMMENTS-001-20261021-R03.md
---

# 测试范围、环境与 TEST_LAYOUT

前端测试位于 `src/tests/frontend/`，合成浏览器拦截 `/v1/`，无真实买家发送。R03 已在前一 subject 验证后端权限、买家隔离及完整工作台回归；本轮后端内容不变，验证集中于翻译展示与部署。

# 命令和逐项结果

- 在 `src/frontend` 执行 `npm run typecheck`、`npm run test`：通过，契约 47/47；`npm run lint`：0 error、4 个既有 warning；`npm run build`：通过。
- 本地生产构建上执行 `node --test --test-name-pattern "tracking description replaces|failed tracking translation" ../tests/frontend/browser/workspace-experience.test.mjs`：2/2。翻译成功后原文不再并列显示，可切回，往返切换只调用一次翻译；失败保留原文。
- 合入 `main=f98dca4e` 后与 subject 比较，`src/frontend`、`src/tests/frontend`、`docs/product/PRODUCT.md` 无差异；在部署后的 staging 页面重复定向合成浏览器测试：2/2。
- staging CheckOnly、六摘要预取、ValidateOnly、Deploy 均通过；迁移头 `025_workspace_actions`，11 服务，后端/前端/检索镜像健康且摘要与证据一致；`/healthz`、`/v1/health`、`/v1/health/ready`、`/workspace` 均 HTTP 200。
- 用户在登录态订单卡刷新后回复“已完成”，对应所问的译文原位替换与“查看原文”切回英文两项核对。低敏部署摘要见 `release/evidence/staging/crm-staging-workspace-tracking-display-20261021.json`。

# REQ/AC 或门禁与证据映射

AC-02 的中文物流状态由上轮用户确认，本轮原位翻译由定向测试和现场确认支持；AC-03 的合入源码、手动 staging 发布、回滚镜像与健康验证由本轮证据支持。没有自动外发、退款、发券或 production 发布。

# 缺陷、未执行项与残余风险

GitHub Actions 两个作业在任何步骤前失败，不计为 CI 通过；本地受影响门禁已执行。Codex 内置浏览器读取真实登录态仍超时，记录 `UI_UNAVAILABLE`，实际界面结论来自用户现场回复而非工具截图。未对本次前端文案调整重跑后端全量测试，后端代码与 R03 完整回归的输入相同。

# 结论和复测条件

本轮范围 `PASS`。如翻译返回的原文与卡片当前描述不一致，前端仍拒绝展示并提示刷新；若后续改变订单来源或翻译服务，须重新验证店铺/买家隔离和失败关闭。Production G8 维持 No-Go。
