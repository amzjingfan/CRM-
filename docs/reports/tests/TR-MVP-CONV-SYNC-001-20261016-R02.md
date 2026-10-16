---
record_id: TR-MVP-CONV-SYNC-001-20261016-R02
record_type: test
revision: R02
status: PARTIAL
task_id: MVP-CONV-SYNC-001
tested_sha: 7fe97ea113b49925abc24a8438fda09e902ef519
implementation_record: docs/records/implementation/IR-MVP-CONV-SYNC-001-20261016-R02.md
requirement_ids: [MVP-CONV-SYNC-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: local Next.js production build and browser regression; authorized staging read-only service and TikTok GET; GitHub Actions
created_at: 2026-10-16T19:10:00+08:00
updated_at: 2026-10-16T19:10:00+08:00
supersedes: docs/reports/tests/TR-MVP-CONV-SYNC-001-20261016-R01.md
---

# 真实 TikTok 会话及工作台分页现场验证

## 源码与本地验证

R01 后端源码由 [PR #248](https://github.com/CP11-gh/CRM/pull/248) 合入 `main` `0fa1c5d`，隔离 PostgreSQL 完整后端为 **1882 passed、3 skipped**，Ruff、格式、mypy 通过。R02 前端候选 `7fe97ea` 的契约测试 **45 passed**，类型检查和生产构建通过；ESLint **0 errors、2 项既有警告**。对同一构建运行本地浏览器回归 **24 passed、1 skipped**（需生产缓存环境的项未启用）。[PR #250](https://github.com/CP11-gh/CRM/pull/250) 前后端 CI 均通过，并合入 `main` `d0c9e67485d9c1252e1747c73a793a531ea05691`。

## staging 只读实测

[首次预取 #38884784214](https://github.com/CP11-gh/CRM/actions/runs/38884784214)、[validate #38887474691](https://github.com/CP11-gh/CRM/actions/runs/38887474691)、[deploy #38887763981](https://github.com/CP11-gh/CRM/actions/runs/38887763981) 均通过，把 R01 后端 `sha256:26ad09bd…789cb1` 及首版前端 `sha256:134678aa…62140` 部署到 staging。运行态三个健康接口均为 200，TikTok 真实只读及周期同步开启，真实普通消息写入关闭，G5 SSE 窗口关闭。

受限会话内的只读查询返回授权工作台 TikTok 会话 **179** 个，按每页 30 条查询 6 页得到 **179** 个不重复会话；消息 **2018** 条，其中买家 202、人工客服/店铺 954、机器人 260、系统 602。渠道同步时间已推进，后续周期核对计数保持一致。用户截图目标会话存在、处于 TikTok 筛选第一页；官方平台 GET 全页返回原始 **29** 条，其中 `is_visible=true` 的 **25** 条全部出现在工作台详情。命令和证据均不输出客户标识、消息正文或凭据。原样[低敏只读计数](../../../release/evidence/staging/crm-staging-conv-sync-live-20261016.json) SHA-256 `44a6a9a08f97e151fad12c9efe9ab65ea9f3de7f4b2994d8946b5eb68243db59`。

R02 前端由[发布 #38890441975](https://github.com/CP11-gh/CRM/actions/runs/38890441975)生成 `ghcr.io/cp11-gh/crm-frontend@sha256:d0fc23c22cde2619ddcca095f6d48ae8a6121d851fdeb23878d2e596067e0fbb`，`linux/amd64` manifest `PASS`、`production_release=false`。原样[镜像证据](../../../release/evidence/staging/crm-staging-conv-sync-frontend-38890441975.json) SHA-256 `4d046d423286dc211a451593d8bde0ad56c57d85b0b0b45b9a45fb4aee4ed7b0`。新旧镜像[预取 #38890659187](https://github.com/CP11-gh/CRM/actions/runs/38890659187) 和当时 `main=d0c9e674` 的[validate #38891343316](https://github.com/CP11-gh/CRM/actions/runs/38891343316) 通过；原样[预取证据](../../../release/evidence/staging/crm-staging-conv-sync-prefetch-38890659187.json) SHA-256 `739100d6512108c16ebdb3f28da97899141953f5b92ab1573d37d3b04cfdfcd8`、[validate 证据](../../../release/evidence/staging/crm-staging-conv-sync-validate-38891343316.json) SHA-256 `2d5efb41d0e1378d16d1cacd4724ba046e254c4905c3f53406b26017ca472a5d`。**新前端尚未部署**。

验证后 `main` 合入其他 G5 工作，当前为 `23ac2ad0d8428a3ac03e982faf13335f4c4682d5`。为保证 validate/deploy 使用同一基线，重跑[validate #38891700438](https://github.com/CP11-gh/CRM/actions/runs/38891700438)，连续两次在 hosted `prepare_source` 作业启动前被 GitHub Actions 账单/支出上限拒绝，self-hosted staging 作业未执行。当前运行前端仍为旧摘要 `sha256:134678aa…62140`；旧页面只显示前 30 个会话。浏览器控制工具返回 `UI_UNAVAILABLE`，未取得新版工作台的视觉验收，不能以 API 计数代替页面实测。

AC-01 的真实回填与 AC-02 的历史接口及本地页面契约已验证。AC-03 的新版前端部署/页面现场待完成。AC-04 现场结论明确：staging 真实 TikTok 消息写入 `false`，G2 新消息 Webhook 和 G3 受控发送仍未通过，工作台目前不能向买家发送真实消息，也不承诺实时双向聊天。production 未发布。
