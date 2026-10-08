---
record_id: IR-MVP-OAUTH-STATUS-UI-001-20261008-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-OAUTH-STATUS-UI-001
base_sha: 06ea611a41c3283d49d4e49e441e650eacee8ccb
final_sha: 039487e6a4ec0bfe6b7a20f026c07604f02144b1
requirement_ids: [G1]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
test_record: docs/reports/tests/TR-MVP-OAUTH-STATUS-UI-001-20261008-R01.md
review_record: docs/reports/reviews/RR-MVP-OAUTH-STATUS-UI-001-20261008-R01.md
created_at: 2026-10-08T14:35:00+08:00
updated_at: 2026-10-08T14:35:00+08:00
supersedes: null
---

# 实施目标与范围

渠道页不能凭回跳 URL 的 `status=connected` 自行宣称本次 TikTok 授权完成；只有当前用户可读取的 OAuth job 返回 `connected` 才显示成功。发起新授权时清除旧提示。后端 OAuth、密钥、数据结构、部署配置与 production 均未修改。

# 实际变更及原因

`src/frontend/app/settings/channels/page.tsx` 将 `connected` 和 `processing` 回跳统一交给既有 job 状态轮询；缺失或无效 job 时显示无法确认。点击授权按钮先清空上一次提示。浏览器回归增加服务端 job 为 failed 以及缺失 job 两种负例；原 processing 后成功的正例保留。

# 关键决定与偏差

2026-10-08 13:32、13:51（北京时间）两次 staging 授权发起均返回 200，但公网入口没有新 callback，数据库仍只有 11:13 完成的旧 job。该事实与本次页面修复分开记录；不能据此签署 G1。低敏现场证据见 `release/evidence/staging/crm-staging-g1-oauth-no-new-callback-20261008-pm.json`。

# 数据、配置、接口、迁移或 Prompt 影响

无。页面继续通过已有受权限控制的 job 状态接口查询，未增加 Token 或回调参数暴露。

# 验证交接

测试命令、结果与本机依赖准备限制见对应 TR。PR 合并只交付代码；staging 镜像发布与部署需独立门禁，当前运行页面尚未包含修复。

# 限制、风险与回滚

无法从未到达的 TikTok callback 判明第三方页面、浏览器或网络的准确失败原因。回滚代码使用合并提交的 `git revert`；已连接渠道与现有加密凭证不受本次前端变更影响。
