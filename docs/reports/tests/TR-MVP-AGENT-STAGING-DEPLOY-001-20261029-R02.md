---
record_id: TR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R02
record_type: test
revision: R02
status: PASS
task_id: MVP-AGENT-STAGING-DEPLOY-001
tested_sha: 00bc04a1ea8c6b23279ef95f8add8d9089a67a6c
implementation_record: docs/records/implementation/IR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R02.md
requirement_ids: [MVP-AGENT-STAGING-DEPLOY-001]
acceptance_ids: [AC-01, AC-02]
environment: Windows / synthetic deployment gates / authorized staging read-only preflight
created_at: 2026-10-29T09:36:00+08:00
updated_at: 2026-10-29T09:36:00+08:00
supersedes: docs/reports/tests/TR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R01.md
---

# 本次结果与复用

同 R01 的四个精确测试文件，在纳入 #629 后的 `0330e9f4` 再运行 **180 passed / 130.66 秒 / 零失败、错误和跳过**；随后 `00bc04a1` 仅合入 #630 状态文档，后端、前端、Docker、Compose、脚本与测试树逐项相同，明确复用该结果，没有声称在文档合并后再次跑全量。Ruff、格式、PowerShell AST 和 diff 检查通过。初次合流任务表的 git add 使用了后端目录相对路径而被拒绝，未产生部分提交；返回仓库根正确解决并完成合并后才记录候选 SHA。

产品完整回归由已合入的[多店授权 R02](TR-MVP-TIKTOK-MULTISHOP-AUTH-001-20261029-R02.md)提供：隔离 PostgreSQL **2394 passed / 3 Windows 条件跳过**，前端 **52 契约 / 134 生产浏览器**，迁移 `034→041→034→041`、类型、构建与静态检查通过。本任务没有重跑该应用全量，复用前须核对应用树与其受测源相同。

# 服务器准备事实

私有备份已核对：PostgreSQL 744414 字节、`pg_restore -l` 通过；MinIO 131716 字节、`gzip -t` 通过；环境和原容器/镜像快照仅存私有目录，不进入仓库。现网仍 12 容器和 034，没有执行迁移或切换。

使用现有 Provider、模型别名及 non-thinking 配置完成纯合成 `deployment_probe` 原生调用、工具结果回传和最终文本，两次 HTTP 200，1.5 秒。没有传业务数据、CRM 写入或平台发送；这只验证 Provider 协议，不冒充新 Agent 联合链路。Codex 浏览器自动 AX 绑定超时后，使用同一浏览器的文档化 DOM API 恢复，已登录只读查看 TikTok US 的现有 Agent、上下文和关闭的自动发送；未保存配置或运行业务调试。

# 结论

本地部署资产与组合源 PASS，服务器发布及新执行器现场验收尚未执行。当前备份与 Provider 探针不能替代部署、UI 或工具加 RAG 回答的验收；production G8 No-Go，所有平台外发仍禁止用于本测试。
