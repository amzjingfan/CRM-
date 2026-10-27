---
record_id: TR-MVP-AGENT-LIVE-DEBUG-001-20261026-R01
record_type: test
revision: R01
status: PARTIAL
task_id: MVP-AGENT-LIVE-DEBUG-001
tested_sha: 9302bb6d4d16b67d942f23251e58d7356e116ac5
implementation_record: docs/records/implementation/IR-MVP-AGENT-LIVE-DEBUG-001-20261026-R01.md
requirement_ids: [MVP-AGENT-LIVE-DEBUG-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: Windows isolated PostgreSQL; local production frontend; staging manual deployment, TikTok US test store
created_at: 2026-10-26T06:10:01Z
updated_at: 2026-10-26T06:10:01Z
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT: centralized`。本地测试针对 subject `9302bb6d4d16b67d942f23251e58d7356e116ac5`；staging 用同一 OCI revision 的前后端镜像、迁移 034、独立调试开关。现场按用户要求选中 TikTok US 测试店铺。

# 命令和逐项结果

- `src/scripts/run-postgres-integration-tests.ps1`：2426 passed、3 skipped，迁移 034 应用成功；跳过项为 Windows 无法运行的 POSIX Bash 场景。
- Ruff 检查与格式、mypy 211 个源码文件通过；前端类型、lint（0 error，8 条既有 warning）、48 项契约、生产构建、113 项浏览器测试通过。
- 手动 staging 私有 PostgreSQL/MinIO/环境备份，`ValidateOnly` 与 `Deploy` 均通过；后端、前端精确摘要、健康接口 200、`AGENT_DEBUG_ENABLED=true`、`LLM_ENABLED=false`、迁移头 034 已复核。未使用 GitHub Actions。
- 合成 G5 店铺无绑定文件调试：trace `72c402cb-5207-4a64-a47d-1ad1eea43070`，真实 DeepSeek `deepseek-v4-flash` 运行 `succeeded`、动作 `human_review`、审计 1 条、零引用/工具/客户会话；试验后恢复原工具配置。
- TikTok US 测试店铺无会话合成问题：trace `635d20c0-4788-41cb-a389-bc702d012638`，真实 DeepSeek `deepseek-v4-flash` 运行 `succeeded`、动作 `human_review`、审计 1 条、零引用/工具/客户会话。没有创建客户消息，也没有平台发送。

# REQ/AC 或门禁与证据映射

- AC-01：页面与 API 真实调试、追踪回显在本地浏览器与 staging 登录态通过；无绑定文件时请求成功并保守转人工。
- AC-02：当前店铺、权限、只读工具交集与无会话禁工具在隔离后端测试通过；TikTok US 因零订单和未选客户会话，成功工具返回未现场验证。
- AC-03：CSRF、权限、限流、超时、审计、开关与迁移在隔离测试和部署门禁通过。
- AC-04：本地完整回归及 staging 部署/真实模型调用通过；TikTok US 店铺零导入文件，绑定文件命中未现场验证。

# 缺陷、未执行项与残余风险

TikTok US 测试店铺当前没有导入文件和订单，因此不能在该店铺证明 RAG 命中、引用质量或订单/物流工具的成功调用。没有选取真实买家会话，避免把客户数据送入第三方模型。GitHub Actions 未使用；当前短期分支尚未合并主线。低敏现场事实见[部署证据](../../../release/evidence/staging/crm-staging-agent-live-debug-20261026.json)。

# 结论和复测条件

本地实现与 staging 真实模型调试 **PASS**；用户指定店铺的绑定文件与工具成功路径缺少样本，任务综合 **PARTIAL**。导入并人工审批一份非敏感测试文件、绑定 Agent 后复测引用；提供授权的合成会话/订单后复测只读工具，再审定任务完整验收。production 不放行。
