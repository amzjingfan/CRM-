---
record_id: TR-MVP-STAGING-BROWSER-FEEDBACK-002-20261026-R02
record_type: test
revision: R02
status: PASS
task_id: MVP-STAGING-BROWSER-FEEDBACK-002
tested_sha: 9f3e8ee4fc0c4c71aeaf03512a59bba3f1bf42b9
implementation_record: docs/records/implementation/IR-MVP-STAGING-BROWSER-FEEDBACK-002-20261026-R02.md
requirement_ids: [MVP-STAGING-BROWSER-FEEDBACK-002]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
environment: Windows isolated worktree; Next 16.4.2 production build; staging Rootless Docker and logged-in browser
created_at: 2026-10-26T05:00:00Z
updated_at: 2026-10-26T05:00:00Z
supersedes: docs/reports/tests/TR-MVP-STAGING-BROWSER-FEEDBACK-002-20261026-R01.md
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT: centralized`。R01 的本地测试绑定同一 subject SHA；本修订补记合并后 staging 前端直部署、运行门禁和已登录页面只读检查。源代码从 `main=4c8d2365e64e3a0d90df45107200bb8c72b32c81` 干净 worktree 构建，前端构建输入与 subject SHA 相同。

# 命令和逐项结果

- 本地 `npm run build` PASS；生产浏览器 `UI_CACHE_EXPECT_PRODUCTION=1; npm run test:ui` 113 passed、0 failed、0 skipped；前端契约 `npm run test` 48 passed；`npm run typecheck` PASS；`npm run lint` 0 error、8 warning；`git diff --check` PASS，详见 R01。
- 前端 OCI linux/amd64 构建并推送，远端不可变 index digest `sha256:0e46a68be38f0cc6e7a4871fb741db5e0d117db04246bdd163aed2138a49f316`；服务器验证 digest 后导入 Rootless Docker。其余三种镜像保持原摘要。
- PostgreSQL 私有备份 `pg_restore -l` 可读，环境与 MinIO 私有快照存在；手动 `ValidateOnly=validated`，`Deploy=passed`（2026-10-26T04:44:12.8198030Z），数据库返回 `heads_applied`，现场 head `033_file_version_approval`。12 个 CRM 容器运行，前端与代理健康，固定 TikTok 出口地址核对一致。
- 公网 `/healthz`、`/v1/health`、`/v1/health/ready`、`/login`、`/workspace`、三个基础接待 URL 均为 HTTP 200；页面 HTML 为 `no-store`，所引用指纹 JS 为 HTTP 200 且 `immutable`。
- 已登录 staging 浏览器：智能营销默认收起，展开后点击外部收起；`polojunky65` 的真实订单状态为“已送达”，聊天页显示“售后买家”；订单卡“详情”进入订单/物流/商品/付款分区，“收据”打开标注为内部只读摘要的弹窗，退款位置显示“退款暂未开放”。
- 现场运行门禁确认 TikTok Webhook 读取、一个既有店铺的人工发送、工作台翻译、文档摄取保持；自动回复、自动营销、通用 LLM 和高风险写入仍关闭。未发送测试消息或执行退款。

# REQ/AC 或门禁与证据映射

AC-01、AC-04 的界面行为由 R01 浏览器测试及线上营销菜单验证；AC-02、AC-03 由 R01 测试及线上已送达真实订单只读核对；AC-05 由本地质量门禁、不可变镜像、私有备份、手动部署门禁及公网与已登录浏览器结果支持。逐项摘要在[低敏证据](../../../release/evidence/staging/crm-staging-browser-feedback-20261026.json)。

# 缺陷、未执行项与残余风险

没有新建真实超时/欢迎策略、向真实买家发送、执行退款、生成平台发票或进行 production 发布。线上抽查仅覆盖一个已送达订单及菜单行为；合成浏览器覆盖其余状态。GitHub Actions 零步骤失败不计通过。临时 GHCR 登录已在本机和服务器注销，认证条目均为 0；本机临时 Docker 目录的删除被自动审批拒绝，保留无注册表认证的临时文件。

# 结论和复测条件

该 subject 的本地行为与限定 staging 直部署验收 **PASS**。后续若修改相关页面或订单接口，重跑受影响浏览器/契约测试并复核真实订单状态；production 另按 G8 门禁放行。
