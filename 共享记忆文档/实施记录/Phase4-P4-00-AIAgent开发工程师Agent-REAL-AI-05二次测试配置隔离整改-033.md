# REAL-AI-05 二次测试配置隔离整改实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 `REAL-AI-05` |
| 模块编号 | M04 |
| 主责 Agent | AIAgent开发工程师Agent |
| 协作 Agent | 架构师Agent、全栈开发工程师Agent、测试工程师Agent |
| 实施状态 | 部分完成 |
| 开始日期 | 2026-09-05 |
| 完成日期 | 未完成 |
| 代码位置 | `CRM智能聊天系统/` |

“部分完成”表示 `DEF-REAL-AI05-004` 已完成开发侧整改和验证，正式关闭仍等待测试工程师独立复测；`DEF-REAL-AI05-002` 因具体独立开放集尚未取得外部数据出境授权而保持 Open。本轮没有调用真实 DeepSeek，也没有开放任何生产 AI 能力。

## 2. 需求与依据

- 产品需求：`共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md` 的 AI 回复、翻译和营销边界。
- 接口依据：`共享记忆文档/智能客服平台 — 管理端接口文档.md` 第 11.16、11.18 节。
- 架构依据：`架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`、`架构师/ADR-005-AI-知识语义类型与发布审批边界-v1.0.md`。
- 任务依据：`AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md` 的 `REAL-AI-05`。
- 测试依据：`测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-REAL-AI-05版本化真实模型评测-AI评测-002.md`。
- 验收依据：`共享记忆文档/MVP范围与验收标准.md` 和 REAL-AI-05 固定质量门禁。
- 代码规范：`共享记忆文档/代码编写手册.md`。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 修复根 `.env` 中一次性真实评测开关污染常驻 Python 服务和 Alembic 的问题。
- 用可执行回归测试固定“常驻服务必须显式关闭 `LLM_LIVE_EVAL`”的配置契约。
- 如实同步第二次独立报告结论，不把开发侧修复写成正式缺陷关闭。

### 3.2 实施范围

- 开发 Compose 中五个常驻 Python 服务的真实评测开关隔离。
- 本地根环境的安全默认值、示例配置、运行说明和 AI 任务状态。
- 配置回归测试、运行态恢复、全量后端与隔离 PostgreSQL 回归。

### 3.3 非目标

- 不在未获授权时把测试工程师的 36 条独立合成载荷发送到 DeepSeek。
- 不替测试工程师关闭 `DEF-REAL-AI05-002/004` 或生成正式测试报告。
- 不修复全栈主责的前端依赖漏洞、SSE 50 客户端或五日稳定性问题。
- 不初始化 Git，不伪造提交级不可变候选。
- 不升级当前开发数据库，不修改迁移或 AI Prompt、Provider、判分器和冻结数据集。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单。
- [x] 已读取相关 PRD、接口、任务拆解和验收标准。
- [x] 涉及代码时已读取代码编写手册和适用 Skill。
- [x] 已确认 Phase4、P4-00、M04 和主责 Agent。
- [x] 已确认配置隔离、外部数据授权、正式复测和生产关闭边界。

## 5. 实施方案

### 5.1 方案说明

`LLM_LIVE_EVAL` 是一次性、受审批的外部数据评测开关，不是常驻业务服务能力开关。根 `.env` 被 backend、worker、jobs、agent-worker 和本地检索模型服务共同加载；一旦将该开关长期保存为 `true`，所有进程都会在 `Settings` 构造阶段要求完整计价元组，导致普通服务和 Alembic 在尚未进入业务逻辑前失败。

本次采用双层失败关闭：根 `.env` 恢复 `false`，同时在五个常驻 Python 服务的 Compose `environment` 中显式覆盖为字符串 `"false"`。即使后续有人误改根环境文件，常驻服务仍不会继承一次性评测授权。真实评测只能在获准的 `integration/staging` 隔离进程中，通过进程级环境覆盖完整注入模型、密钥、费率和清单上下文；评测结束后立即清除覆盖。

### 5.2 依赖关系

- 前置依赖：REAL-AI-01～04、REAL-AI-05 030/031 实施记录、002 号独立测试报告。
- 后续依赖：测试工程师复测 `DEF-REAL-AI05-004`；用户批准特定数据集摘要后复测 `DEF-REAL-AI05-002`；架构师维护生产放行清单和不可变候选。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 根环境再次误设真实评测 | 常驻服务或迁移启动失败，也可能扩大外部调用面 | Compose 五服务显式覆盖为 `false`，并增加回归测试 |
| 隔离过度导致专用评测不可运行 | 无法取得真实模型证据 | 仅锁定常驻服务；CLI 仍允许在获批隔离进程用进程级变量运行 |
| 把合成数据等同于自动获准出境 | 未授权外部数据传输 | 未取得针对数据集摘要、供应商和用途的明确授权前不执行真实调用 |
| 开发侧结论覆盖测试权威状态 | 生产门禁被误判 | 文档统一标记“开发侧已修复、待独立复测” |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `CRM智能聊天系统/docker-compose.yml` | 修改 | 五个常驻 Python 服务显式设置 `LLM_LIVE_EVAL=false` | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_real_runtime_config.py` | 修改 | 增加五服务配置隔离参数化回归测试 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/.env` | 修改 | 本地忽略文件只将一次性评测开关恢复为安全默认值；未记录或修改密钥 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/.env.example` | 修改 | 明确根环境和常驻服务保持关闭，仅批准的隔离进程可临时覆盖 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/README.md` | 修改 | 补充真实评测进程隔离、配置清理和具体数据集出境授权要求 | AIAgent开发工程师Agent |
| `AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md` | 修改 | 同步 002 号报告缺陷状态与开发整改状态 | AIAgent开发工程师Agent |
| `共享记忆文档/实施记录索引.md` | 修改 | 登记本实施记录 | AIAgent开发工程师Agent |
| `共享记忆文档/实施记录/Phase4-P4-00-AIAgent开发工程师Agent-REAL-AI-05二次测试配置隔离整改-033.md` | 新增 | 记录本轮诊断、整改、验证与交接 | AIAgent开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：无公共 API 变化。
- 数据库：无迁移、表、字段或索引变化；当前开发库为 `022_ai_marketing_review`，代码 head 为 `023_marketing_review_idempotency`，本轮未越权升级开发库。
- 配置项：`LLM_LIVE_EVAL` 在根开发环境和五个常驻 Compose 服务中保持 `false`；没有新增配置项或记录真实密钥。
- AI：不修改 Prompt、模型、RAG、工具、阈值、Provider 或评测标签。

### 6.3 关键实现说明

- 回归测试直接按 Compose 服务块检查精确的非注释配置行，不依赖本机 Docker，可在普通 pytest 中及时发现开关继承回归，也不会被同文注释伪通过。
- 覆盖范围包含 backend、webhook worker、jobs worker、agent worker 和 retrieval model service；这些服务均会加载项目环境文件或 Python 配置。
- 真实评测 CLI 不作为 Compose 常驻服务，因此仍可在获批隔离进程中显式覆盖开关，不会被本次 Compose 安全默认阻断。
- 本轮首先复现 `Settings` 导入失败，再编写失败测试，随后补齐五服务覆盖并验证恢复，符合 TDD 红—绿流程。
- 没有将外部开放集、API Key、Token、完整 Prompt 或模型正文写入日志、实施记录或测试产物。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| 原缺陷复现 | 根环境保持修复前开关后构造 `Settings()` | 缺少批准计价元组时失败关闭 | 复现配置校验错误，确认 backend 日志同因失败 | 通过 |
| TDD RED | 先对四服务、再扩展到检索服务运行新参数化测试 | 未配置显式覆盖时失败 | 首轮 4/4 失败；扩展后 1 失败、4 通过 | 通过 |
| 配置聚焦测试 | `uv run pytest -q --basetemp .pytest-ai05-fix-focused tests/test_real_runtime_config.py tests/test_real_model_evaluation.py tests/test_real_model_evaluation_remediation.py tests/test_agent_providers.py tests/test_security.py` | 配置及 AI 相关回归通过 | 177 passed，1 个既有 argon2 警告 | 通过 |
| 独立报告复核脚本 | `uv run pytest -q -c pyproject.toml --basetemp .pytest-ai05-002-recheck ../../测试工程师/evidence/REAL-AI-05-002/test_real_ai05_second_retest.py` | 不对外调用时本地门禁通过 | 12 passed | 通过 |
| Ruff | `uv run ruff check app tests scripts migrations` | 无规则错误 | All checks passed | 通过 |
| 格式 | `uv run ruff format --check app tests scripts migrations` | 全部格式正确 | 233 files already formatted | 通过 |
| mypy | `uv run mypy app scripts` | 无类型错误 | 166 source files 通过 | 通过 |
| 默认后端全量 | `uv run pytest -q --basetemp .pytest-ai05-fix-full` | 无回归 | 1321 passed，12 skipped，2 warnings | 通过 |
| 隔离 PostgreSQL 全量 | `scripts/run-postgres-integration-tests.ps1` | 空库迁移至 head 后执行全量 | 001→023；1333 passed，2 warnings；测试容器已删除 | 通过 |
| 编译 | `uv run python -m compileall -q app scripts tests` | 无编译错误 | 退出码 0 | 通过 |
| 锁文件 | `uv lock --check` | 锁文件一致 | 125 packages resolved | 通过 |
| 依赖审计 | `uv audit --locked` | 无已知漏洞 | 联网复核 124 个锁定包无已知漏洞或不良状态 | 通过 |
| Compose 解析 | `docker compose config --quiet` | 配置合法 | 退出码 0 | 通过 |
| 常驻进程环境 | 容器内只读取 `LLM_LIVE_EVAL` | 三个已启动 Python 服务均为关闭 | backend、worker、jobs 均输出 `false` | 通过 |
| 运行健康 | `/v1/health`、`/v1/health/ready` | API 和依赖就绪 | 分别返回 `status=ok`、`status=ready` | 通过 |
| Alembic 可达性 | 容器内 `alembic current` 与 `alembic heads` | 不再因 Settings 导入失败 | 命令可执行；开发库 022，代码 head 023 | 通过（存在版本差异） |
| 建议性只读审查 | 当前工作树配置和测试边界复核 | 无 Critical/Important；测试不被注释伪命中 | 无 Critical/Important；唯一 Minor 已收紧为精确非注释行断言 | 通过（非不可变验证） |
| 真实独立模型评测 | 测试工程师 36 条开放集调用 DeepSeek | 取得独立质量证据 | 未执行：尚无针对该数据集摘要和用途的明确出境授权 | 未执行 |

pytest 的两个既有警告为 Starlette/httpx 与 argon2 兼容弃用提示。最终全量回归第一次执行异常停在无输出状态，超过两分钟后被人工中止；随后收集 1333 项成功，并以新的隔离临时目录重跑默认套件取得 1321 passed、12 skipped，未把中止运行计作通过。`uv audit` 首次在受限网络中因无法连接 OSV 退出；取得联网权限后使用同一锁文件重跑并通过。主机 Alembic 仍受 Windows asyncpg 连接中断影响，容器内命令可达且不再出现配置导入错误。

## 8. 实施结果

- 完成项：`DEF-REAL-AI05-004` 的根因定位、配置隔离、回归测试、服务恢复、文档和开发侧全量验证。
- 未完成项：测试工程师对 004 的正式复测；取得明确数据出境授权后对 002 执行一次冻结开放集真实 DeepSeek 评测；提交级不可变候选、SSE 和五日稳定性门禁。
- 与原方案差异：未执行任何真实模型调用；原因是 002 号报告明确指出当前具体载荷没有外部发送授权。
- 当前状态：部分完成。开发运行面已恢复，生产 AI 继续关闭，REAL-AI-05 仍不满足生产验收。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-033-001 | 36 条独立合成载荷没有针对数据集摘要、DeepSeek 和一次离线评测用途的明确出境授权，`DEF-REAL-AI05-002` 保持 Open | P1 | 人类责任人、测试工程师Agent、AIAgent开发工程师Agent | Phase4 / REAL-AI-05 独立复测 |
| R-033-002 | `DEF-REAL-AI05-004` 尚未由测试工程师递增序号报告正式复测关闭 | P1 | 测试工程师Agent | Phase4 / REAL-AI-05 配置复测 |
| R-033-003 | 当前开发数据库 022 落后代码 head 023；隔离空库验证通过但开发库升级需由数据库/全栈主责确认 | P2 | 全栈开发工程师Agent | Phase4 / 运行环境维护 |
| R-033-004 | 当前目录无 Git，不能形成提交级不可变候选 | P1 | 架构师Agent、全栈开发工程师Agent | 生产发布治理 |
| R-033-005 | 002 号测试报告引用的 `共享记忆文档/生产放行检查清单.md` 当前不存在 | P2 | 架构师Agent、共享记忆文档Agent | 生产放行文档治理 |
| R-033-006 | `DEF-REAL-AI04-005` 的开发修复等待正式复测，前端 `DEF-REAL-FS01-005` 仍为全栈主责开放缺陷 | P1 | 测试工程师Agent、全栈开发工程师Agent | Phase4 对应专项 |

## 10. 交接事项

- 交接给：测试工程师Agent、架构师Agent、全栈开发工程师Agent。
- 后续任务：测试工程师复测配置隔离和运行健康；获得明确授权后以同一冻结摘要执行一次独立 DeepSeek 评测；全栈确认开发库 023 升级和前端依赖缺陷；架构师补齐生产放行文档与不可变候选要求。
- 必须注意：不得把开发侧健康恢复解释为 REAL-AI-05 质量验收通过；`AI_PUBLIC_REPLY_ENABLED`、`AI_MARKETING_CONTENT_ENABLED`、`AI_AUTO_REPLY_ENABLED` 和 `AUTO_REPLY_ENABLED` 必须继续关闭。

## 11. 文档同步

- [x] 已同步接口变化：无公共接口变化。
- [x] 已同步架构决策：未改变 ADR，仅落实一次性评测与常驻服务隔离。
- [x] 已同步任务状态：001/003 已由 002 号报告关闭，002 保持 Open，004 开发侧已修复待复测。
- [x] 已通知测试工程师需要覆盖的配置、运行健康和真实评测授权边界。
- [ ] 测试报告索引将在测试工程师递增序号正式复测后更新。
