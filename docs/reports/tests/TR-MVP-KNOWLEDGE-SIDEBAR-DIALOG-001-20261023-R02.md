---
record_id: TR-MVP-KNOWLEDGE-SIDEBAR-DIALOG-001-20261023-R02
record_type: test
revision: R02
status: PASS
task_id: MVP-KNOWLEDGE-SIDEBAR-DIALOG-001
tested_sha: f7950619487a853fa2c6afb27ff6a0ca1bd76fdc
implementation_record: docs/records/implementation/IR-MVP-KNOWLEDGE-SIDEBAR-DIALOG-001-20261023-R02.md
requirement_ids: [MVP-KNOWLEDGE-SIDEBAR-DIALOG-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: local Windows production build and Playwright; deployed staging page with synthetic /v1 responses
created_at: 2026-10-23T02:27:11Z
updated_at: 2026-10-23T02:27:11Z
supersedes: docs/reports/tests/TR-MVP-KNOWLEDGE-SIDEBAR-DIALOG-001-20261023-R01.md
---

# 结果

`TEST_LAYOUT: centralized`。R01 的本地最终源码验证为：`npm run build` 通过（含 TypeScript），`npm run lint` 0 error、5 条既有 warning，`npm test` 48/48，生产构建上 `npm run test:ui` 66 passed、1 skipped、0 failed。定向测试先复现旧问题，再覆盖旧 `layer` URL 清理、站内弹窗、取消/Escape/409/忙碌/成功路径及店铺隔离。

本次 staging 手动门禁：六角色镜像预取和 `ValidateOnly` 通过；私有数据库备份 0600、`pg_restore -l` 可读；`Deploy` 返回 `DEPLOY_PASSED_EXACT_DIGEST`。运行前端与受审镜像摘要一致，后端/检索保持，11 容器运行；公网 `/healthz`、`/v1/health`、`/v1/health/ready`、`/knowledge` 均为 HTTP 200。知识页面不缓存，已加载的 10 个指纹 JS/CSS 资源均为 HTTP 200 且 `immutable`。

Playwright 访问**已部署**的 `https://staging.overselfx.com/knowledge`，拦截所有 `/v1/**` 请求并提供合成店铺和分类数据：确认侧栏无“按知识层级查看”，自定义分类删除打开站内“删除自定义分类”弹窗；取消后弹窗关闭且 `DELETE` 请求数为 0。截图仅保存在本机忽略的测试产物目录。真实分类未删除，也未发外部消息。低敏结果见[部署证据](../../../release/evidence/staging/crm-staging-knowledge-sidebar-dialog-20261023.json)。

# 限制与结论

GitHub Actions 的两作业在执行任何步骤前失败，不计作 CI 通过；由本地生产检查和手动 staging 门禁覆盖。真实登录态页面未直接验收，真实删除动作有意不执行；本记录 `PASS` 仅针对 AC-01～04 的限定范围。production 仍为 No-Go。
