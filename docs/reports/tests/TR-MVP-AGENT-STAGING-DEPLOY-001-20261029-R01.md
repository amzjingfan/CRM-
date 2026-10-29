---
record_id: TR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-AGENT-STAGING-DEPLOY-001
tested_sha: d5c044ba1be05a26140554dc6dce5ad6d0360e65
implementation_record: docs/records/implementation/IR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R01.md
requirement_ids: [MVP-AGENT-STAGING-DEPLOY-001]
acceptance_ids: [AC-02]
environment: Windows / Python 3.11.15 / PowerShell / Docker Compose / synthetic fixtures
created_at: 2026-10-29T09:19:00+08:00
updated_at: 2026-10-29T09:19:00+08:00
supersedes: null
---

# 本次本地验证

TEST_LAYOUT 为 centralized。使用现有已安装 Python 环境，以本工作树 `src/backend/pyproject.toml` 显式配置运行：

```text
python -m pytest -c pyproject.toml ../tests/backend/runtime_infrastructure/test_production_gate_scripts.py ../tests/backend/runtime_infrastructure/test_rootless_staging_assets.py ../tests/backend/runtime_infrastructure/test_document_staging_contract.py ../tests/backend/agent/test_agent_v2_debug_switch.py -q --tb=short
```

结果 **180 passed，135.83 秒，零失败/错误/跳过**。测试覆盖真实 Compose 解析、调试显式启用、正式入口关闭、缺失 v2 开关拒绝、意外正式入口拒绝、容器运行态漂移、默认恢复、Rootless 和文档模式。

新增断言首次运行真实失败于 `AGENT_V2_DEBUG_ENABLED` 与 v2 收据缺失；修复后两个相关用例通过，再运行上述完整受影响集合。最初复用解释器未显式指定配置导致 `_support` 收集失败，修正为 `-c pyproject.toml` 和当前测试根后才取得有效结果。首次 Ruff 从根目录未指定后端配置，产生错误格式建议；没有应用该建议，以后端配置重跑 lint/format 均通过。PowerShell AST 解析和 `git diff --check` 通过。

# 现场只读预检与限制

SSH、现网 12 容器、旧迁移头 034、公网健康/ready 200 已只读核对；没有切换服务。现有 Provider 的只读 `/models` 返回 200，公开元数据支持 1048576 上下文；未调用模型生成或平台业务 API。Codex 浏览器页面绑定两次超时，记 `UI_UNAVAILABLE`，没有将页面或模型回答记为通过。

日志与 JUnit 保存在忽略的 `src/tests/.artifacts/agent-staging-deploy-20261029/`。本轮未重跑全量应用回归，因为应用树未改变；组合产品回归由多店授权集成任务提供，部署前还须核对最终树。此 PASS 仅指上述本地资产测试，实际部署和联合验收尚未执行。
