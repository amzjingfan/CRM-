---
record_id: TR-MVP-AGENT-AUTOMATION-FULL-001-20261102-R01
record_type: test
revision: R01
status: PASS
tested_sha: c76e046de745bef6c18b475fe203664de378df54
implementation_record: docs/records/implementation/IR-MVP-AGENT-AUTOMATION-FULL-001-20261102-R01.md
environment: isolated Windows PostgreSQL/pgvector; production Next; opt-in real DeepSeek/BGE component
task_id: MVP-AGENT-AUTOMATION-FULL-001
requirement_ids: [USER-AGENT-FULL-CHAIN]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05, AC-06]
created_at: 2026-11-02T10:25:00Z
updated_at: 2026-11-02T10:25:00Z
supersedes: null
---

# 本地验证范围

TEST_LAYOUT=centralized。全部临时日志位于 src/tests/.artifacts/agent-automation-20261102，不提交密钥、原始买家资料或凭证。

| 验证 | 本次实际结果 | 覆盖 |
|---|---|---|
| 后端最终全量 pytest，回环独立 PostgreSQL/pgvector | 3581 passed / 5 skipped / 0 failed，375.94 秒；之前发现的超时批准竞态已修复后重新执行全量 | AC-01～05 |
| 提示词语义复核专项 | 10 passed；新增过期取消被吞回归先失败后通过 | AC-05 |
| Ruff 全量 lint/format、mypy、锁文件 | 通过；mypy 321 source files，uv lock 187 packages；最新两文件再定向检查通过 | AC-01～05 |
| 前端 lint/typecheck/生产 build/contract | 0 errors、12 既有 warnings；82 contract passed | AC-01/02/04/05 |
| 生产版本地浏览器 | 237 passed / 0 failed / 0 skipped | AC-01/02/04/05 |
| 050 隔离空库升级、降级、重升级 | 通过；最终含物流 authorization_json | AC-05 |
| 安全确定性 eval | 237 samples，accuracy=1，unsafe_escape=0，passed | AC-01～05 |
| 实际模型双语模拟物流 R07 | en/zh 均通过；真实 DeepSeek-v4-flash、BGE embedding、数据库检索、BGE rerank、四工具及独立复核；零出站/通知/投递行 | AC-03/06 |

# 证据与失败保留

隔离物流证据：[低敏摘要](../../../release/evidence/agent/agent-automation-local-20261102.json)。准则 logistics-component-owned-evidence-v2 要求引用来自实际命中的两个冻结相关片段之一、原文/店铺/文件/版本一致。43 个离线用例通过，未知/未命中/错版本引用仍失败。R01～R05 失败、R06 环境失败保留，不追溯改写为通过；R07 为新执行。

正式 API runner 的 20 个离线合同测试通过，不等于现场已执行。模型组件平台事实明确为模拟，知识为预解析合成片段，不能替代 HTTP 认证、UI、真实 TikTok 或买家送达。CUA 绑定 staging 超时，记录 UI_UNAVAILABLE；生产本地浏览器已执行。

# 未执行与结论

本记录仅覆盖合并前本地门禁；staging 部署、双入口正式认证真实模型验收、测试数据清理和两店开启仍需执行并登记 R02。GitHub CI 的实际作业情况在创建 PR 后核对；未运行 CI 不写作通过。production 未发布，测试未向买家发送消息。

# 主线集成追加验证

主线 #713 的四个只读订单展示文件完整保留，独立窄复审通过。集成 subject 为 c76e046de745bef6c18b475fe203664de378df54；git diff --quiet 证实 backend/compose/scripts/backendtests/PGtests 与已通过最终全量的 4179df985f2c1702e3f85829ca75a4b1eba750e4 完全相同，因此后端结果按相同测试树关联，没有冒充再次执行。合并后重新生产 build/typecheck、84 个前端契约及受影响 workspace 生产浏览器 65/65 通过；全部前端 lint 0 errors、12 既有 warnings。原237项生产浏览器为集成前本任务结果，65项为追加实际重跑。
