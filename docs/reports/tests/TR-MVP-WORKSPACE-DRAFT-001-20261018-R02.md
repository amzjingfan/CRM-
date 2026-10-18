---
record_id: TR-MVP-WORKSPACE-DRAFT-001-20261018-R02
record_type: test
revision: R02
status: PASS
task_id: MVP-WORKSPACE-DRAFT-001
tested_sha: 07dede246c793cf5252624f59e35938f0ae46244
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-DRAFT-001-20261018-R01.md
requirement_ids: [MVP-WORKSPACE-DRAFT-001]
acceptance_ids: [AC-01, AC-02, AC-03]
environment: staging 已登录的 in-app browser；Rootless Docker；公网健康接口
created_at: 2026-10-18T11:47:00+08:00
updated_at: 2026-10-18T11:47:00+08:00
supersedes: docs/reports/tests/TR-MVP-WORKSPACE-DRAFT-001-20261018-R01.md
---

# G5 恢复后的现场复核

`CANDIDATE_SUBJECT_SHA=07dede246c793cf5252624f59e35938f0ae46244`。R01 的本地测试、浏览器回归、镜像与手动部署证据继续有效；本修订只补足独立 G5 临时窗口结束后的当前运行模式与真实工作台复核。

- 2026-10-18 通过 staging SSH 只读查询 Rootless Docker：backend、worker、agent-worker、jobs、tiktok-egress 均运行原后端镜像 `8913c09ceffd`；frontend 运行修复镜像 `1addb6c82f9a`；检索服务运行 `feeee5a3327b`。完整不可变摘要及部署门禁见 [R01](TR-MVP-WORKSPACE-DRAFT-001-20261018-R01.md) 和 [低敏部署证据](../../../release/evidence/staging/crm-staging-workspace-composer-deploy-20261018-r01.json)。前次恢复后的只读配置核验显示 TikTok 真实读取、店铺限定人工消息发送和工作台翻译均启用，店铺允许范围存在；本轮没有输出店铺标识或密钥。
- 公网 `/healthz`、`/v1/health`、`/v1/health/ready` 本轮各返回 HTTP 200。
- 已登录 in-app browser 刷新受控 TikTok 真实会话后，工作台显示“真实 TikTok 发送”；597×894 视口内回复输入区与确认按钮可见。空草稿为 0/2000，按钮禁用；输入测试草稿后为 11/2000，按钮启用；清空后恢复 0/2000 与禁用。现场截图及 AX 状态留在本任务工具结果。
- 未点击“确认并发送”，未调用消息发送 API，消息列表未因此新增。没有运行 GitHub Actions，也没有发布 production。

# 结论与边界

AC-01～AC-03 对本任务通过。当前 staging 受控会话可直接输入草稿，并在有内容时启用人工确认按钮；该结果与 R01 的 100 条历史、长建议、三视口合成浏览器回归及手动部署证据共同构成验收。该 UI 验收不替代向真实买家再次发送，也不表示所有店铺或 production 已放行。其他任务的 G5 临时部署若再次切换后端，应在该窗口结束后重新核对运行模式。
