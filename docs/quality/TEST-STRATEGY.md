# 测试策略

## 目标与布局

本项目使用：

```text
TEST_LAYOUT: hybrid
```

测试遵循后端与前端框架的现有目录，同时把真实 PostgreSQL/pgvector 跨模块集成测试集中在仓库根 `tests/integration/`。不为尚无真实测试的层级创建空目录。

| 层级 | 权威路径或模式 | 当前适用性 | 目的 |
|---|---|---|---|
| 后端模块、领域与契约 | `backend/tests/test_*.py` | 适用 | 服务、仓储、路由契约、平台适配器、AI 工作流和确定性安全行为 |
| 后端安全 | `backend/tests/test_security.py`、`test_auth_cookies.py` 及相关领域测试 | 适用 | 认证、权限、店铺隔离、CSRF、DLP、幂等和失败关闭 |
| 跨模块集成 | `tests/integration/test_*.py` | 适用 | 真实 PostgreSQL/pgvector、迁移后的数据结构和跨模块事务行为 |
| 前端契约与行为 | `frontend/tests/*.test.mjs` | 适用 | 页面组合、API 使用、安全约束和 TikTok OAuth 前端契约 |
| 启动与健康冒烟 | `backend/tests/test_health.py` 与已登记的 `backend/scripts/verify_*.py` | 适用 | 健康检查和需要显式环境的专项运行时核对 |
| AI/RAG eval | `backend/evals/` 与对应评测脚本 | 适用 | 版本化意图、RAG、回复安全和真实模型门禁 |
| 浏览器核心闭环 E2E | 无权威自动化路径 | `N/A` | 当前真实 TikTok/DeepSeek 闭环需要隔离 staging、真实授权和低敏冻结数据；建立独立可重复入口后启用 |
| 正式低敏机器证据 | `release/evidence/` | 适用 | 保存发布基线必须长期存在的冻结机器结果，不保存普通临时测试输出 |

`backend/pyproject.toml` 的 pytest `testpaths` 同时发现 `backend/tests/` 与 `tests/integration/`。`frontend/package.json` 的 `npm run test` 发现 `frontend/tests/*.test.mjs`。准确执行命令见仓库根 `tests/README.md`。

## 环境分层

- **development/test**：使用 Mock 平台或固定合成数据，不需要真实密钥和外部网络；单元、契约和大部分安全测试在此运行。
- **integration**：允许隔离 PostgreSQL/pgvector、Redis、MinIO 或受控外部 Provider；必须使用测试专用资源、开关和低敏数据。
- **staging**：用于真实 TikTok OAuth/Webhook/只读/人工消息、DeepSeek、容量、稳定性、备份和回滚门禁；每次执行需要精确环境与授权。
- **production**：不运行真实模型离线评测或破坏性测试。生产发布后只执行已批准的低风险冒烟、监控和恢复确认。

单元测试不得依赖真实密钥、生产数据或公网。真实平台、真实模型、性能、稳定性与恢复演练不能由 Mock、合成数据或确定性测试替代。

## 数据、fixture 与 helper

- 测试输入必须固定、脱敏、可追踪，不包含真实密钥、Token、生产数据或未经脱敏的客户内容。
- 当前没有独立的共享 `fixtures/` 或 `helpers/` 权威目录。只有出现两个以上测试模块的真实复用需求时才新增，并在 `tests/README.md` 登记用途和发现方式。
- 后端测试数据优先通过测试函数或受控工厂构造；数据库集成测试使用隔离实例和可重复清理的测试记录。
- AI eval 数据集必须固定版本、摘要、允许字段和用途；把数据发给外部模型前还需满足项目的数据出境授权和环境限制。
- 凭证池、浏览器会话、性能原始日志和临时截图保存到仓库外安全路径或已忽略的测试输出目录，测试后按批准策略处理。

## 需求、任务与门禁追踪

- 产品验收来自 `docs/product.md`，当前任务状态来自 `docs/tasks/TASKS.md`，生产门禁来自 `docs/release-gates.md`。
- 自动化测试使用稳定测试名表达行为；在任务 TR 中把任务 ID、REQ/AC 或 G0～G8 门禁映射到具体命令和结果。
- 只有影响运行行为的任务需要最终 IR/TR；认证、权限、租户、迁移、公共契约、生产基础设施和关键 AI 变化默认还需要 RR。
- `docs/test-status.md` 只汇总当前仍有效的正式结论，历史结果不能当作新分支本次运行证据。

## 变更与验证矩阵

| 变更 | 最小验证 | 需要扩展的条件 |
|---|---|---|
| 纯 Markdown、导航或规则 | `git diff --check`、路径/链接、敏感信息与事实一致性检查 | 文档改变接口、配置、安全或发布结论时执行对应领域检查 |
| 后端 Python | Ruff、格式、mypy、相关 pytest | 跨模块、数据库、权限、平台或 AI 变化时扩展到完整 pytest 与集成测试 |
| 前端 TypeScript/React/CSS | lint、typecheck、相关前端测试 | 页面、构建配置或共享组件变化时增加生产 build 和浏览器核对 |
| 数据库迁移 | 相关测试、upgrade/downgrade/upgrade | 生产候选还需备份、恢复、兼容和回滚演练 |
| API 或外部平台契约 | 契约、权限、幂等、超时、unknown 与失败关闭测试 | 真实放行前执行隔离 staging 联调 |
| AI、Prompt、模型或评测基线 | 结构、DLP、引用、安全和冻结 eval | Provider、数据集、阈值或生产用途变化时执行真实模型与数据授权门禁 |
| 部署、CI 或发布 | 静态配置、脚本解析、目标环境门禁 | staging/production 操作仍需精确授权和真实冒烟 |

先运行最小充分验证。只有新失败、未解决风险、影响面扩大或门禁要求时才扩大范围；不得为证明勤奋重复无关测试。

## 输出与正式证据

- 测试源码：`backend/tests/`、`tests/integration/`、`frontend/tests/` 或已登记的 eval 路径。
- 临时覆盖率、日志、截图、浏览器结果与缓存：使用 `.pytest_cache/`、`.test-artifacts/`、`test-results/`、`playwright-report/`、`coverage/` 等已忽略目录，或仓库外安全路径。
- 正式测试记录：首次产生当前格式 TR 时保存到 `docs/reports/tests/`，并按 `docs/governance.md` 建立索引。
- 发布基线机器证据：只有必须长期固定且经过低敏检查的结果进入 `release/evidence/`；普通本地结果不得混入。

## 失败与完成判定

- 任一相关检查失败，任务返回 `DOING` 修复，或在不能继续时转 `BLOCKED`；不得删除测试、降低阈值或修改验收制造通过。
- `PASS` 只表示记录范围内的实际命令通过；未执行项、环境差异和残余风险必须同时记录。
- 影响交付内容的最后变更会产生新的 `CANDIDATE_SUBJECT_SHA`，并触发受影响测试重跑。最终 TR 不接受 `WORKTREE`。
- 测试通过不自动表示 PR 已合并、staging 已部署或 production 已放行。
