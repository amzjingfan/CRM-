---
record_id: IR-MVP-KNOWLEDGE-SIDEBAR-DIALOG-001-20261023-R02
record_type: implementation
revision: R02
status: FINAL
task_id: MVP-KNOWLEDGE-SIDEBAR-DIALOG-001
base_sha: bc542e7b34d7eac3ac97db0bb97b43ef74772cdb
final_sha: f7950619487a853fa2c6afb27ff6a0ca1bd76fdc
requirement_ids: [MVP-KNOWLEDGE-SIDEBAR-DIALOG-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
test_record: docs/reports/tests/TR-MVP-KNOWLEDGE-SIDEBAR-DIALOG-001-20261023-R02.md
review_record: null
created_at: 2026-10-23T02:27:11Z
updated_at: 2026-10-23T02:27:11Z
supersedes: docs/records/implementation/IR-MVP-KNOWLEDGE-SIDEBAR-DIALOG-001-20261023-R01.md
---

# 实施与部署

R01 的知识库页面修复不变：移除“按知识层级查看”整块侧栏及 `layer` 页面筛选状态；自定义分类删除改用站内确认弹窗，确认前不调用既有删除接口。Agent 管理、后端、检索和公共 API 未改。

源码 [PR #536](https://github.com/CP11-gh/CRM/pull/536) 已合入 `main=0a4f6739533218a57d77ce8423fd7fbfe203da03`。从该精确提交的干净源码构建 `linux/amd64` 前端镜像，OCI revision 与提交一致；远端清单和现场拉取验证摘要 `sha256:a867f62455c02a3d918cc9526d326ae92e003db8d50d28cad88ec101b3defa39`。构建辅助脚本在推送完成后因 PowerShell 内不可用的 buildx 命令退出非零，独立清单、拉取和摘要核对通过，未把该退出码记为成功。

部署前冻结三镜像摘要及单店人工发送模式，完成六角色预取、数据库私有备份、`ValidateOnly`；然后只切换 staging 前端到精确摘要。后端和检索摘要未改变，11 个容器运行。详细低敏哈希、门禁和页面结果见[部署证据](../../../release/evidence/staging/crm-staging-knowledge-sidebar-dialog-20261023.json)。

# 风险与回滚

真实店铺的分类未被删除，未外发消息；合成浏览器只验证已部署页面静态资源和交互，真实登录态须由用户刷新页面复核。若发现回归，可恢复记录中的先前前端摘要，重新核对运行模式和健康。production 未发布。
