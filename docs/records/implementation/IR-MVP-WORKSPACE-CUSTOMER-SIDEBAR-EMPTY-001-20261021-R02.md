---
record_id: IR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-EMPTY-001-20261021-R02
record_type: implementation
revision: R02
status: FINAL
task_id: MVP-WORKSPACE-CUSTOMER-SIDEBAR-EMPTY-001
base_sha: 3e01d7fc752e46c3105946ca3f3165b44c5c8aba
final_sha: 7cd8e43e27544036027f2b2d8be2a5fc411d97ca
requirement_ids: [MVP-WORKSPACE-CUSTOMER-SIDEBAR-EMPTY-001]
acceptance_ids: [AC-01, AC-02, AC-03]
test_record: docs/reports/tests/TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-EMPTY-001-20261021-R02.md
review_record: docs/reports/reviews/RR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-EMPTY-001-20261021-R01.md
created_at: 2026-10-21T01:25:29Z
updated_at: 2026-10-21T01:25:29Z
supersedes: docs/records/implementation/IR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-EMPTY-001-20261021-R01.md
---

# 实施目标与范围

R01 的最小只读解析修复已由源码 [PR #485](https://github.com/CP11-gh/CRM/pull/485) squash 合入 `main=f487ea1b6723e4fc1afbc2601e43ce64ac3db911`。本修订记录手动发布 staging 与恢复入口；不扩大店铺权限或平台写入。

# 实际变更及原因

本机从合入主线构建并推送后端不可变镜像 `ghcr.io/cp11-gh/crm-backend@sha256:cd287496ab80ec4763319f9b761b98e2eb8d7af13d545ce542cdea00c686d764`，镜像 revision 为合入主线 SHA；经 Git 核对该提交的 backend 构建输入与 R01 的 subject SHA 完全相同。frontend 与检索镜像仍使用原不可变摘要。staging 新建干净审核源码 checkout，主线 GitHub SHA 核对、原摘要和受限私有备份通过，再完成六摘要预取、validate 与 deploy；复核原单店人工发送、Webhook 只读和翻译开关。

# 关键决定与偏差

用户此前决定不使用 GitHub Actions 部署。本次 PR 自动触发的两个 Actions 作业均在零步骤处失败，未作为质量证据；采用候选提交上的本地完整后端测试和 staging 手动门禁。内置浏览器自动化连接超时记为 `UI_UNAVAILABLE`，用户刷新后直接确认页面显示“暂无订单”且错误消失。

# 数据、配置、接口、迁移或 Prompt 影响

无迁移、配置或公开接口变更。staging `database_migration=heads_applied`；人工发送仍限原一店，自动回复和高风险写入继续关闭。

# 验证交接

机器证据位于 `release/evidence/staging/crm-staging-empty-orders-*-20261021.json`，详情见 R02 TR。用户可在工作台选中原会话并查看“订单”栏；该买家确无订单，正常显示空态。

# 限制、风险与回滚

新后端异常时，先保存切换后可能产生的新消息，再按受审手动门禁将 backend 恢复到 `sha256:fe2f0cf8ce2fe3ae6351226236efb9922c04909016cca0afbd8b4700063c9b40`，frontend 与检索使用本记录的旧摘要。切换前私有 `pg_dump` 存于 staging `crmdeploy` 私有缓存，SHA-256 见只读证据；该文件不提交仓库。回滚旧后端会恢复本次零订单误报。production 仍 No-Go。
