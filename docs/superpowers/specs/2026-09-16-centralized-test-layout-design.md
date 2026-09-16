# 统一测试目录设计

## 状态与范围

```text
Task ID: TEST-001
Status: APPROVED_IN_CHAT_PENDING_WRITTEN_REVIEW
Base SHA: 17bb9bf9501ead60aafe8eed6bddc331f26c43f0
Branch: feature/unified-test-layout
```

本设计把测试源码、测试专用数据、AI/RAG eval 数据集及版本化 eval 结果统一归入 `src/tests/`，并按测试对象和职责分类。迁移不改变产品行为、测试断言、数据内容、模型阈值或生产门禁结论。

正式 TR 继续位于 `docs/reports/tests/`，发布基线必须长期保存的低敏机器证据继续位于 `release/evidence/`；它们是治理与发布证据，不属于测试源码目录。历史 `docs/superpowers/` 计划、历史记录和冻结发布基线中的旧路径作为当时事实保留，不批量改写。

## 目标结构

```text
src/tests/
├─ backend/
│  ├─ agent/
│  ├─ auth_security/
│  ├─ domain/
│  ├─ platform/
│  └─ runtime_infrastructure/
├─ frontend/
│  └─ contract/
├─ integration/
│  └─ postgres/
├─ ai/
│  ├─ datasets/
│  └─ results/
└─ README.md
```

`src/tests/.artifacts/` 是唯一项目内测试临时输出根，由 `.gitignore` 排除，不提交空目录、缓存、日志、覆盖率、截图或临时结果。只有真实出现跨测试复用时才新增 `fixtures/` 或 `helpers/`，不得建立空占位目录。

迁移完成后禁止重新创建 `src/backend/tests/`、`src/frontend/tests/` 或 `src/backend/evals/`。应用源码目录只保存运行代码、迁移、脚本和运行资产。

## 分类与迁移映射

| 当前内容 | 目标 | 分类规则 |
|---|---|---|
| `src/backend/tests/test_agent_*.py` | `src/tests/backend/agent/` | Agent 领域、工作流、Provider、RAG、向量化和工具执行 |
| BGE、retrieval、Prompt、模型评测及知识安全相关后端测试 | `src/tests/backend/agent/` | AI/RAG 与 Agent 运行契约 |
| `test_auth_cookies.py`、`test_security.py` | `src/tests/backend/auth_security/` | 认证、授权、CSRF、店铺隔离和失败关闭 |
| Phase 3/4 领域及营销复核测试 | `src/tests/backend/domain/` | 非平台专属的业务领域规则 |
| 平台适配器及 `test_tiktok_*.py` | `src/tests/backend/platform/` | TikTok OAuth、读取、写入和适配器契约 |
| 健康、日志、配置、SSE、仓库布局、发布脚本和 rootless staging 测试 | `src/tests/backend/runtime_infrastructure/` | 运行时、部署、容量和工程契约 |
| `src/frontend/tests/*.test.mjs` | `src/tests/frontend/contract/` | 前端页面组合、API 使用和安全契约 |
| `src/tests/integration/test_*.py` 与其 README | `src/tests/integration/postgres/` | PostgreSQL/pgvector 跨模块集成行为 |
| `src/backend/evals/*.jsonl` 与 manifest | `src/tests/ai/datasets/` | 版本化、脱敏、可追踪的 eval 输入 |
| `src/backend/evals/results/*` | `src/tests/ai/results/` | 已登记的版本化 eval 结果 |

文件移动使用 Git 可审阅的 rename，不复制出第二份测试资产。分类存在歧义时以测试的主要风险对象为准，并在 `src/tests/README.md` 维护边界说明。

## 测试发现与开发命令

后端仍从 `src/backend/` 管理 Python 依赖和运行命令：

- `src/backend/pyproject.toml` 的 pytest `testpaths` 改为 `../tests/backend` 与 `../tests/integration/postgres`。
- `pythonpath` 继续指向后端工程根，使应用导入保持 `app.*`，不把产品源码复制到测试目录。
- pytest 缓存改到 `../tests/.artifacts/pytest-cache`。
- Ruff 和格式检查同时覆盖后端源码、`src/tests/backend/` 与 `src/tests/integration/postgres/`；mypy 仍以当前已批准的 `app scripts` 范围为准。
- `uv run pytest` 仍作为完整后端测试入口，局部运行必须写出精确新路径。

前端仍从 `src/frontend/` 管理 Node 依赖：

- `npm run test` 改为执行 `../tests/frontend/contract/*.test.mjs`。
- ESLint 同时覆盖前端源码和新的前端测试目录。
- 前端测试中基于 `import.meta.url` 的源码定位统一改为从新目录解析 `src/frontend/`、`src/` 和仓库根，不依赖调用者当前目录。
- typecheck 与 Next.js build 范围保持不变；测试目录中的 `.mjs` 继续由 Node test runner 执行。

CI 的 backend/frontend 工作目录保持不变，只调整 lint、format 和测试发现参数。`src/scripts/run-postgres-integration-tests.ps1` 仍是隔离数据库入口，但必须显式证明新 `integration/postgres/` 目录被完整收集。

## AI eval 与路径契约

AI eval 数据集、manifest 和版本化结果全部迁入 `src/tests/ai/`。`evaluate_intents.py`、`evaluate_rag.py`、`evaluate_phase4.py`、`evaluate_real_model.py` 及相关测试改为从脚本文件位置推导 `src/`，再定位 `tests/ai/`，避免依赖当前工作目录。

README 中的人工命令使用新路径。新生成但尚未审查的结果默认写入 `src/tests/.artifacts/ai/`；只有满足版本、低敏、摘要和用途要求的结果才进入 `src/tests/ai/results/`。正式发布证据仍进入 `release/evidence/`。

后端生产镜像当前以 `src/backend/` 为构建上下文。迁移后 eval 数据不再被 `COPY . .` 带入生产镜像；运行代码不得依赖 eval 文件，评测只能在仓库/CI 或明确挂载数据的受控环境执行。`src/backend/.dockerignore` 中失效的 `evals/` 规则随迁移清理。

`release/baselines/v0.1.0-mvp.20260907.json` 等冻结记录中的旧路径描述历史候选，不改写。当前活动文档、命令、脚本和机器清单必须使用新路径；若某个当前机器清单要求文件可解析，则通过当前记录修正，而不是静默篡改历史标签事实。

## 路径安全与布局门禁

现有路径敏感测试不得继续使用固定 `parents[n]` 猜测工程根。仓库身份使用 Git 或向上查找 `.git`；`src/`、backend、frontend 和 tests 根从已验证的仓库根派生。前端测试使用一个清晰的路径入口或等价的显式 URL 推导，避免每个测试自行猜层级。

仓库布局测试迁入 `src/tests/backend/runtime_infrastructure/`，并增加以下失败条件：

- 任一跟踪测试源码、eval 数据集或普通 eval 结果出现在 `src/tests/` 外；
- `src/backend/tests/`、`src/frontend/tests/` 或 `src/backend/evals/` 重新出现；
- pytest、Node test、CI 或活动文档仍引用旧目录；
- 项目内测试临时输出写到 `src/tests/.artifacts/` 之外；
- 迁移导致正式 `release/evidence/` 或 TR 被错误并入测试源码目录。

门禁只检查稳定的路径和配置契约，不对普通源码文本做脆弱的全仓正则断言。

## 文档与治理同步

以下当前事实必须同步：

- 根 `AGENTS.md`：把固定 `hybrid` 改为统一 `centralized` 布局，并规定唯一测试根。
- `docs/governance/GOVERNANCE.md`：更新 TEST_LAYOUT 和权威路径。
- `docs/quality/TEST-STRATEGY.md`：更新分类、发现、数据、输出与验证矩阵。
- `docs/engineering/DEVELOPMENT.md`：禁止在产品模块下新增测试目录。
- `src/tests/README.md`、根 `README.md`、Agent README：更新执行命令和 eval 路径。
- `.github/workflows/ci.yml`、`src/backend/pyproject.toml`、`src/frontend/package.json`、`.gitignore` 和受影响脚本：更新机器入口。
- `docs/tasks/TASKS.md`、`docs/memory/PROJECT-STATE.md` 及按风险要求产生的 IR/TR/RR：记录实际状态和证据。

历史设计、历史计划、冻结发布记录只保留当时事实，不纳入“活动旧路径必须清零”的扫描范围。

## 验证与验收标准

1. `git ls-files` 显示全部测试源码、普通 eval 数据集与普通 eval 结果只位于 `src/tests/`；正式证据例外仅限 `docs/reports/tests/` 与 `release/evidence/`。
2. 旧目录 `src/backend/tests/`、`src/frontend/tests/`、`src/backend/evals/` 不存在且无跟踪内容。
3. 后端 format、Ruff、mypy、完整 pytest 和隔离 PostgreSQL 集成入口通过；测试收集数量不得因移动意外减少。
4. 前端 lint、typecheck、Node 测试和生产 build 通过；现有 40 个 Node 断言全部保留。
5. 所有 AI 数据集、manifest 和结果在移动前后逐文件 SHA-256 不变；eval 脚本默认路径和显式路径均通过测试。
6. CI YAML、PowerShell 脚本、JSON/manifest、Markdown 本地链接和 Compose 组合解析通过。
7. 后端与前端镜像构建通过；后端运行镜像不包含 `src/tests/` 或 eval 数据，健康启动保持正常。
8. 活动文档与机器入口无旧测试路径；历史规格、计划和冻结发布记录中的旧事实允许保留并在扫描中明确排除。
9. 增加测试布局契约，未来在模块目录新增测试或 eval 内容会使验证失败。
10. 最终 IR/TR 绑定真实 `CANDIDATE_SUBJECT_SHA`，独立审查关闭路径、CI、镜像和测试收集风险后，任务才能进入 `DONE`。

## 回滚

迁移提交必须保持纯 rename 与配置/路径修正可区分。合并前可通过普通 Git 提交恢复旧路径；合并后使用 `git revert` 回滚相关提交，不使用破坏性历史重写。若任何测试收集减少、数据摘要变化或运行镜像启动失败，任务返回 `DOING`，优先恢复路径后再定位原因。
