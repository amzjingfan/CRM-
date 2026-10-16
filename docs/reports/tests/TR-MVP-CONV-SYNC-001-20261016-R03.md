---
record_id: TR-MVP-CONV-SYNC-001-20261016-R03
record_type: test
revision: R03
status: PASS
task_id: MVP-CONV-SYNC-001
tested_sha: 7fe97ea113b49925abc24a8438fda09e902ef519
implementation_record: docs/records/implementation/IR-MVP-CONV-SYNC-001-20261016-R02.md
requirement_ids: [MVP-CONV-SYNC-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: local frontend verification; authorized read-only TikTok staging; manual immutable-image staging gate; live CRM browser
created_at: 2026-10-16T20:55:00+08:00
updated_at: 2026-10-16T20:55:00+08:00
supersedes: docs/reports/tests/TR-MVP-CONV-SYNC-001-20261016-R02.md
---

# 真实 TikTok 会话、历史与 staging 工作台最终验证

## 范围和源码

[R01](TR-MVP-CONV-SYNC-001-20261016-R01.md) 已验证真实只读回填和店铺隔离；[R02](TR-MVP-CONV-SYNC-001-20261016-R02.md) 已验证前端契约、生产构建、浏览器回归和已合入的 [PR #250](https://github.com/CP11-gh/CRM/pull/250)。本次仅补全被 GitHub Actions 账单拒绝的 staging 新前端部署与现场页面验收。用户明确授权使用现有 GitHub 凭据执行等效手动 staging 路径，并授权为该凭据增添 `read:packages`；不使用 GitHub Actions 完成这次部署。

以 `main` 精确提交 `23ac2ad0d8428a3ac03e982faf13335f4c4682d5` 执行 `git archive`，本地与 staging 两端核对 tar SHA-256 均为 `e850f4152daf7c13d9b49d90a384a165bcb965068fd6266d514a86fef58173ab`。独立解包、初始化仅用于脚本路径边界核对的本地 Git 仓库；其 HEAD 不冒充上游提交。前端候选为 `ghcr.io/cp11-gh/crm-frontend@sha256:d0fc23c22cde2619ddcca095f6d48ae8a6121d851fdeb23878d2e596067e0fbb`；后端和检索镜像复用 R02 已核对的不可变摘要。

## 手动 staging 门禁

在 `crmdeploy` Rootless Docker 上使用受审 `Test-StagingProductionGates.ps1`，输入 `staging` 精确确认、三条不可变摘要、固定 HTTPS 基址、仓库外 staging 环境文件及 `-EnableTikTokWebhookRead`，先运行 `-ValidateOnly` 再运行 `-Deploy`。validate 的 [原样低敏证据](../../../release/evidence/staging/crm-staging-conv-sync-manual-validate-20261016.json) SHA-256 `91877626eda6ac5ed796f956b3d485b43a20c6b1e526d8a04cea3686889e5f2e`，状态 `validated`；部署的 [原样低敏证据](../../../release/evidence/staging/crm-staging-conv-sync-manual-deploy-20261016.json) SHA-256 `f61241980a5953b8c71923f446b61c5fd10c4b32cd0d270f338dc89bb18721ea`，状态 `passed`、`production_release=false`，`/healthz`、`/v1/health`、`/v1/health/ready` 均为 HTTP 200。运行前端容器独立核对为上述新摘要，临时 GHCR 登录目录在部署后已不存在。

首次 validate 因从 `/root` 启动非特权进程而在 Docker 操作前失败，切换到解包目录后通过。首次 deploy 因原 GitHub OAuth 凭据缺 `read:packages` 在镜像拉取阶段收到 403，容器未变更；用户完成增权后，GitHub 包 API 可读，重跑同一脚本通过。失败尝试无通过证据，活动前端在成功部署前仍为旧摘要。没有修改 staging 密钥文件或向真实买家发送消息。

## 真实数据与工作台现场

R02 的授权店铺只读对账返回 **179 个 TikTok 会话、2018 条可见消息**；按 30 条每页查询 6 页得到 179 个不重复会话。截图目标平台原始 29 条中 `is_visible=true` 的 25 条均由 CRM 详情接口返回。部署后在已登录的 staging 工作台浏览器刷新 `/workspace?platform=tiktok`，页面实际显示总数 **179**、TikTok 筛选及目标真实会话；目标详情显示真实历史正文和客服、机器人、系统来源标签。列表首次显示 30 条；点击“加载更多会话”后同一页面显示 **60** 条且按钮继续存在，证明后续页在页面可达。未逐个点击全部 179 条；完整分页与不重复性由 R02 接口对账和前端契约测试覆盖。浏览器现场未保存含买家正文的截图，避免把生产客户资料写入 Git。

目标详情标示“发送已关闭”，回复输入框与“确认并发送”按钮均禁用。运行中 backend 配置核对为 `real_tiktok_read_enabled=true`、`real_message_write_enabled=false`、`sync_enabled=false`；worker 为 `real_tiktok_read_enabled=true`、`real_message_write_enabled=false`、`sync_enabled=true`，符合只由 worker 周期同步的设计。本次没有执行任何平台消息写入。真实新消息 Webhook 投递、审计/重试与 G3 单次受控发送仍未通过，因此工作台**现在不能与买家互相发送真实消息**，历史读取依赖周期只读同步，不能据此宣称实时双向聊天。production 未发布。

## 结论和边界

AC-01 全页历史与店铺可见性、AC-02 来源区分和列表/历史分页、AC-03 staging 真店铺页面对账及写入关闭、AC-04 双向发送现场状态均已有本次或所引用的 R01/R02 证据，故本任务测试结论为 `PASS`。G2/G3 和 production 门禁独立保持未通过；本结论不放行真实消息发送。
