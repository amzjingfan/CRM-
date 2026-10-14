# 测试策略

## 目标与布局

本项目使用：

```text
TEST_LAYOUT: centralized
```

测试源码、测试专用数据、普通 AI eval 输入/结果和项目内临时输出统一位于 `src/tests/`，按测试对象和运行方式分类：

```text
src/tests/
├─ backend/
├─ frontend/
│  ├─ contract/
│  ├─ browser/
│  └─ helpers/
├─ integration/
│  └─ postgres/
├─ ai/
│  ├─ datasets/
│  └─ results/
├─ .artifacts/  # 已忽略，按需生成
└─ README.md
```

不为尚无真实测试的层级创建空目录。正式 TR 和必须长期保存的低敏发布证据不属于测试资产，分别保留在 `docs/reports/tests/` 和 `release/evidence/`。

| 层级 | 权威路径或模式 | 当前适用性 | 目的 |
|---|---|---|---|
| 后端模块、领域与契约 | `src/tests/backend/**/test_*.py` | 适用 | 服务、仓储、路由契约、平台适配器、AI 工作流和确定性安全行为 |
| 后端安全 | `src/tests/backend/auth_security/` 及相关领域测试 | 适用 | 认证、权限、店铺隔离、CSRF、DLP、幂等和失败关闭 |
| 跨模块集成 | `src/tests/integration/postgres/test_*.py` | 适用 | 真实 PostgreSQL/pgvector、迁移后的数据结构和跨模块事务行为 |
| 前端契约与行为 | `src/tests/frontend/contract/*.test.mjs` | 适用 | 页面组合、API 使用、安全约束和 TikTok OAuth 前端契约 |
| 隔离浏览器交互回归 | `src/tests/frontend/browser/*.test.mjs` | 适用（本地 Next 服务和 Chrome） | 合成店铺与拦截 API 下验证空状态、表单反馈、筛选与错误提示；不证明真实平台闭环 |
| 启动与健康冒烟 | `src/tests/backend/runtime_infrastructure/test_health.py` 与已登记的 `src/backend/scripts/verify_*.py` | 适用 | 健康检查和需要显式环境的专项运行时核对 |
| AI/RAG eval | `src/tests/ai/datasets/`、`src/tests/ai/results/` 与对应评测脚本 | 适用 | 版本化意图、RAG、回复安全和真实模型门禁 |
| 浏览器核心闭环 E2E | 无权威自动化路径 | `N/A` | 当前真实 TikTok/DeepSeek 闭环需要隔离 staging、真实授权和低敏冻结数据；建立独立可重复入口后启用 |
| 正式低敏机器证据 | `release/evidence/` | 适用 | 保存发布基线必须长期存在的冻结机器结果，不保存普通临时测试输出 |

`src/backend/pyproject.toml` 的 pytest `testpaths` 同时发现 `src/tests/backend/` 与 `src/tests/integration/postgres/`。`src/frontend/package.json` 的 `npm run test` 发现 `src/tests/frontend/contract/*.test.mjs`，`npm run lint` 同时检查前端产品源码和兄弟测试目录。准确执行命令见 `src/tests/README.md`。

## 环境分层

- **development/test**：使用 Mock 平台或固定合成数据，不需要真实密钥和外部网络；单元、契约和大部分安全测试在此运行。
- **integration**：允许隔离 PostgreSQL/pgvector、Redis、MinIO 或受控外部 Provider；必须使用测试专用资源、开关和低敏数据。
- **staging**：用于真实 TikTok OAuth/Webhook/只读/人工消息、DeepSeek、容量、稳定性、备份和回滚门禁；每次执行需要精确环境与授权。
- **production**：不运行真实模型离线评测或破坏性测试。生产发布后只执行已批准的低风险冒烟、监控和恢复确认。

单元测试不得依赖真实密钥、生产数据或公网。真实平台、真实模型、性能、稳定性与恢复演练不能由 Mock、合成数据或确定性测试替代。

## 数据、fixture 与 helper

- 测试输入必须固定、脱敏、可追踪，不包含真实密钥、Token、生产数据或未经脱敏的客户内容。
- 当前前端契约测试共享 `src/tests/frontend/helpers/paths.mjs` 的路径根；没有跨类别共享 `fixtures/` 目录。只有出现两个以上测试模块的真实复用需求时才新增 fixture/helper，并在 `src/tests/README.md` 登记用途和发现方式。
- 后端测试数据优先通过测试函数或受控工厂构造；数据库集成测试使用隔离实例和可重复清理的测试记录。
- AI eval 数据集必须固定版本、摘要、允许字段和用途；把数据发给外部模型前还需满足项目的数据出境授权和环境限制。
- 凭证池和浏览器会话保存到仓库外安全路径；不含敏感数据的性能原始日志和临时截图如果必须位于项目内，只能保存到 `src/tests/.artifacts/`，测试后按批准策略处理。

## 需求、任务与门禁追踪

- 产品验收来自 `docs/product/PRODUCT.md`，当前任务状态来自 `docs/tasks/TASKS.md`，生产门禁来自 `docs/operations/RELEASE-GATES.md`。
- 自动化测试使用稳定测试名表达行为；在任务 TR 中把任务 ID、REQ/AC 或 G0～G8 门禁映射到具体命令和结果。
- 只有影响运行行为的任务需要最终 IR/TR；认证、权限、租户、迁移、公共契约、生产基础设施和关键 AI 变化默认还需要 RR。
- `docs/quality/TEST-STATUS.md` 只汇总当前仍有效的正式结论，历史结果不能当作新分支本次运行证据。

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

G4 的 `policy-repair-v1` 先用确定性 Fake Provider 验证单次修复、两阶段独立判分、预算上限、标签隔离、DLP 与失败关闭，并静态核对工作流低敏白名单及 PowerShell 语法。此类本地测试不等于真实模型质量。首次 `live` #38359902457 的首轮 32/34、终态 28/36、合法样本误拦 4，说明安全校验通过的修复不能冒充最终质量通过。后续低敏诊断仅允许固定 DLP 规则类别；`repair_success_count` 与 `repair_final_pass_count` 分别报告政策校验与终态冻结判分。真实复测须核对首轮、终态、逐项失败、误拦、Token/费用和延迟；`prepare` 始终为零 Provider 调用。

候选 `policy-repair-dlp-regeneration-v1` 的新增确定性测试须覆盖：仅分隔符疑似首稿可触发第二次请求、第二次只含已验证原始合成输入而不含被拒草稿、明确地址及其他 PII 仍直接拦截、第二稿再过 DLP/政策、预算和 Provider 故障时失败关闭、政策修复与再生成绝不形成第三次调用。工作流的低敏白名单与调用总数上限同步验证；这些测试不能代替后续获批的 staging 真实模型复测。

Provider 失败细分诊断的确定性测试覆盖首轮、政策修复与 DLP 再生成的错误码关联，以及 DeepSeek 未正常结束、空内容、JSON 或 Schema 校验失败的固定类别；报告和工作流白名单拒绝自由文本、请求 ID 与原始异常。旧报告不补算细分类型，离线通过不替代新的获批 staging 真实评测。

政策证据指代回归同时覆盖：可信 `faq_chunk` 明确肯定条件规则且合成提问给出平台批准条件时通过；证据否定、无条件提问、错误批准者、跨句否定掩盖个案批准断言及引用不匹配时失败关闭或仅进入一次受控修复。用固定 Provider 跑离线评测入口，验证安全失败与合格草稿的终态分流；本地通过不替代 staging 的 36 条冻结集 live。

## 输出与正式证据

- 测试源码与普通 eval 资产：`src/tests/backend/`、`src/tests/frontend/`、`src/tests/integration/postgres/` 与 `src/tests/ai/`。
- 项目内临时覆盖率、日志、截图、浏览器结果、eval 输出与缓存：只能使用已忽略的 `src/tests/.artifacts/`。保留现有通用忽略规则只是为工具兼容，不得把它们作为新的项目内输出根；敏感或大体积输出使用仓库外安全路径。
- 正式测试记录：首次产生当前格式 TR 时保存到 `docs/reports/tests/`，并按 `docs/governance/GOVERNANCE.md` 建立索引。
- 发布基线机器证据：只有必须长期固定且经过低敏检查的结果进入 `release/evidence/`；普通本地结果不得混入。

## 失败与完成判定

- 任一相关检查失败，任务返回 `DOING` 修复，或在不能继续时转 `BLOCKED`；不得删除测试、降低阈值或修改验收制造通过。
- `PASS` 只表示记录范围内的实际命令通过；未执行项、环境差异和残余风险必须同时记录。
- 影响交付内容的最后变更会产生新的 `CANDIDATE_SUBJECT_SHA`，并触发受影响测试重跑。最终 TR 不接受 `WORKTREE`。
- 测试通过不自动表示 PR 已合并、staging 已部署或 production 已放行。
