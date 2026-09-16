# 测试入口与执行约定

本目录是跨模块集成测试的仓库根入口。项目整体采用 `hybrid` 布局，测试策略见 [`../docs/quality/TEST-STRATEGY.md`](../docs/quality/TEST-STRATEGY.md)。

## 权威路径与发现规则

| 路径 | 发现规则 | 说明 |
|---|---|---|
| `backend/tests/` | `test_*.py`，由 `backend/pyproject.toml` 的 pytest 配置发现 | 后端模块、领域、契约、安全、平台和 AI 确定性测试 |
| `tests/integration/` | `test_*.py`，由同一 pytest 配置的 `../tests/integration` 发现 | 真实 PostgreSQL/pgvector 跨模块集成测试 |
| `frontend/tests/` | `*.test.mjs`，由 `npm run test` 执行 | 前端组合、API 使用与安全契约 |
| `backend/evals/` | 版本化 JSONL/manifest 和受控结果 | AI/RAG 数据集与评测输入，不由普通 pytest 自动执行 |
| `release/evidence/` | 发布基线显式引用 | 低敏冻结机器证据，不是普通测试输出目录 |

更具体的 PostgreSQL 集成测试边界见 [`integration/README.md`](integration/README.md)。

## 后端质量命令

从仓库根执行：

```powershell
Set-Location backend
uv sync --frozen --all-groups
uv lock --check
uv run ruff check .
uv run ruff format --check .
uv run mypy app scripts
uv run pytest
Set-Location ..
```

`uv run pytest` 会按 `backend/pyproject.toml` 同时发现 `backend/tests/` 和仓库根 `tests/integration/`。如果只运行相关用例，必须在测试记录中写出精确路径和未运行范围，不能把局部结果描述为完整后端回归。

## 前端质量命令

从仓库根执行：

```powershell
Set-Location frontend
npm ci
npm run lint
npm run typecheck
npm run test
npm run build
Set-Location ..
```

依赖已由可信缓存或当前工作区完整提供时，可按任务风险跳过重复安装，但必须记录实际环境。生产构建只证明前端构建成功，不替代浏览器、真实网络或 staging 验收。

## 隔离 PostgreSQL/pgvector 集成测试

从仓库根执行：

```powershell
.\scripts\run-postgres-integration-tests.ps1
```

脚本使用 Compose `test` profile 的隔离 `postgres-test` 服务、执行迁移和完整 pytest，并在结束后清理测试服务。不要使用会抢占正式后端端口的一次性容器方式代替该入口。

## 冒烟、真实平台与 AI eval

- `backend/tests/test_health.py` 是确定性健康检查入口。
- `backend/scripts/verify_*.py` 只在其 README、任务或门禁明确要求的环境运行；脚本存在不代表真实环境已验收。
- 真实 TikTok、真实 DeepSeek、50 客户端 SSE、五日稳定性、备份和回滚需要隔离 integration/staging、精确授权、低敏数据和对应门禁记录。
- `backend/evals/` 中的数据集和结果受版本、摘要、Provider、环境和数据用途约束。普通测试不得静默替换数据集、阈值或模型。
- 生产环境不运行真实模型离线评测或破坏性测试。

## fixture、helper 与测试数据

- 当前没有独立共享 `tests/fixtures/` 或 `tests/helpers/`。只有出现真实跨测试复用时才创建，禁止空目录占位。
- 测试数据必须固定、脱敏、可追踪；不得使用真实密钥、Token、生产数据或未经脱敏的客户消息。
- 本地管理员密码、OAuth/会话凭证和性能凭证池只能通过环境变量或仓库外安全文件注入，命令结束后按批准策略清理。
- 测试不得绕过店铺隔离、权限、CSRF、幂等、审计、DLP、真实平台开关或失败关闭。

## 输出、报告与证据

- 临时日志、截图、覆盖率、浏览器结果和缓存写入已忽略的 `.test-artifacts/`、`test-results/`、`playwright-report/`、`coverage/` 等目录，或仓库外安全路径。
- 当前格式的正式 TR 只在产生真实测试事实时创建于 `docs/reports/tests/`，不得用计划或空模板代替。
- `release/evidence/` 只保存发布基线必须长期存在且通过低敏检查的机器证据。
- 每次交付列出真实命令、结果、环境、测试 SHA、覆盖的需求/门禁、未执行项和残余风险。历史结果不能冒充本次运行结果。
