# 模型适配与意图识别实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase1（AI Agent 工程计划） |
| 任务编号 | P2-01；关联 P2-02 |
| 模块编号 | M04（经 ADR-001-AI 正式确认；原记录曾填写 M01） |
| 主责 Agent | AIAgent开发工程师Agent |
| 协作 Agent | 架构师Agent、全栈开发工程师Agent、测试工程师Agent |
| 实施状态 | 部分完成 |
| 开始日期 | 2026-08-20 |
| 完成日期 | 未完成（待真实模型评测） |
| 代码位置 | `CRM智能聊天系统/backend/app/agent/` |

## 2. 需求与依据

- 产品需求：`共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md` 中 AI 客服、意图识别和转人工要求。
- 接口依据：`共享记忆文档/智能客服平台 — 管理端接口文档.md`；本阶段不新增外部 API，`/suggest` 留待 RAG 阶段。
- 架构依据：`架构师/ARCH-001-SYS-系统总体架构设计-v1.1.md`、`架构师/ARCH-003-DATA-数据库与向量库初版设计-v1.0.md`。
- 任务依据：`共享记忆文档/开发任务拆解（按人天分配）.md` 中 P2-01、P2-02。
- 验收依据：`共享记忆文档/MVP范围与验收标准.md` 和用户确认的《AI Agent Phase 1：模型适配层与意图识别实施计划》。
- 代码规范：`共享记忆文档/代码编写手册.md`。
- 前置交接：Phase1 工程地基与认证、Phase2 平台接入会话与客服工作台实施记录。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 在模块化单体中提供 OpenAI/Claude 统一结构化输出适配、五类意图分类、保守拒判、运行追踪和离线/真实模型评测门禁。

### 3.2 实施范围

- `agent` 领域类型、Prompt、脱敏、Provider、分类服务、Repository 和指标计算。
- `agent_runs` ORM 模型和可逆 009 迁移。
- 130 条版本化 JSONL 数据集和 live 评测命令。
- AI 环境变量、依赖锁文件、README 和 AI 工程规范文档。

### 3.3 非目标

- 不实现 FAQ RAG、工具调用、自动回复、平台发送、`/suggest`、SSE 或前端改动。
- 不使用 Fake Provider 冒充真实模型评测。
- 不直接查询或修改订单、消息、会话等业务数据。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单。
- [x] 已读取相关 PRD、接口、任务拆解和验收标准。
- [x] 涉及代码时已读取代码编写手册和适用 Skill。
- [x] 已确认 Phase、任务编号和主责 Agent；模块编号待架构师补充。
- [x] 已确认依赖、风险和验收方式。

## 5. 实施方案

### 5.1 方案说明

调用方传入已完成租户校验的安全上下文，分类服务先独立提交 `running` 记录，再对消息和最近历史脱敏并调用 Provider。应用层最多执行主模型两次、备用模型一次。所有输出再次经过 Pydantic 校验，动作由代码计算；成功或失败在独立提交中更新 `agent_runs`。

### 5.2 依赖关系

- 前置依赖：Phase1 认证/RBAC、Phase2 店铺/会话/消息模型、PostgreSQL 迁移 008。
- 后续依赖：AI Agent Phase2 FAQ RAG 与工作流、全栈 `/suggest` 接口、测试工程师真实模型评测。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 模型不可用或限流 | 分类失败或延迟增加 | 15 秒超时、最多三次预算、可选备用 Provider、稳定错误码 |
| 模型错误自信 | 客服误操作 | 0.6 阈值、非 classified 强制空意图、Phase1 全部人工参与 |
| 隐私或密钥泄露 | 合规与安全风险 | `SecretStr`、输入脱敏、安全摘要、禁止记录 Prompt/正文/Key |
| 无真实密钥 | 无法证明 85%/90% 门槛 | 状态保持“部分完成”，由测试工程师执行 live gate |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `backend/app/agent/` | 新增 | 领域契约、Prompt、脱敏、Provider、分类、追踪、评测指标 | AIAgent开发工程师Agent |
| `backend/migrations/versions/009_create_agent_runs.py` | 新增 | Agent 运行表、外键、检查约束和索引 | AIAgent开发工程师Agent |
| `backend/app/shared/database/models.py` | 修改 | 注册 `AgentRun` 到 Alembic metadata | AIAgent开发工程师Agent |
| `backend/app/shared/config/settings.py` | 修改 | 增加类型化 AI 配置与 `SecretStr` Key | AIAgent开发工程师Agent |
| `backend/evals/intent-classifier-v1.0.0.jsonl` | 新增 | 100 条分类、30 条拒判样本 | AIAgent开发工程师Agent |
| `backend/scripts/evaluate_intents.py` | 新增 | 真实模型评测、指标报告和质量门禁 | AIAgent开发工程师Agent |
| `backend/tests/test_agent_*.py` | 新增 | 领域、Provider、分类、Repository、评测确定性测试 | AIAgent开发工程师Agent |
| `backend/pyproject.toml`、`backend/uv.lock` | 修改 | 锁定 AI SDK并升级安全测试基线 | AIAgent开发工程师Agent |
| `.env.example`、`README.md` | 修改 | 配置模板、边界、运行和评测说明 | AIAgent开发工程师Agent |
| `AI agent 开发工程师/AI-001-MODEL-模型适配与意图评测规范-v1.0.md` | 新增 | 模型边界和评测规范 | AIAgent开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：不适用；本阶段刻意不暴露 AI HTTP 接口。
- 数据库：新增 `agent_runs`；迁移 `008_webhooks_audit → 009_agent_runs`，支持反向回滚。
- 配置项：`LLM_ENABLED`、`LLM_LIVE_EVAL`、主/备用 Provider 和模型、两类 API Key、超时、总尝试次数、最大输出 Token。
- AI：Prompt `intent-classifier-v1.0.0`；五类意图；0.6 保守阈值；OpenAI 2.54.0、Anthropic 0.120.2。
- 测试依赖安全变更：pytest 9.1.1、pytest-asyncio 1.4.0；用于修复审计发现的 pytest 临时目录漏洞。

### 6.3 关键实现说明

- SDK 内建重试关闭，应用层最多三次总调用；认证、权限、非法参数和配置错误不重试。
- 模型拒绝直接转换为 `model_refusal + transfer_human`，不切换模型绕过拒绝。
- `classified && confidence >= 0.6` 也只能进入 `human_review`；其余转人工；不产生 `auto_reply`。
- `input_summary` 只保存消息数、字符数和 SHA-256，`output_summary` 只保存状态和意图。
- 运行日志不记录消息原文、历史、Prompt、模型正文或 Key。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| 锁文件 | `uv lock --check` | 锁文件与声明一致 | 62 个包解析一致 | 通过 |
| 静态检查 | `uv run ruff check app migrations scripts tests` | 无问题 | All checks passed | 通过 |
| 格式检查 | `uv run ruff format --check app migrations scripts tests` | 全部已格式化 | 99 files already formatted | 通过 |
| 类型检查 | `uv run mypy app scripts` | 无错误 | 74 个源文件无错误 | 通过 |
| 自动化测试 | `uv run pytest` | 全量通过 | 30 passed，2 条上游弃用警告 | 通过 |
| 依赖审计 | `uv audit --locked` | 无已知漏洞 | 61 个包无已知漏洞 | 通过 |
| Compose | `docker-compose config --quiet` | 配置可解析 | 通过 | 通过 |
| 数据库迁移 | 009 升级、回滚、重新升级 | 三步均成功 | 当前版本 `009_agent_runs` | 通过 |
| 数据库结构 | 查询 `pg_indexes`、`pg_constraint` | 索引和约束存在 | 3 索引、9 约束（含主键/外键） | 通过 |
| 应用回归 | `GET /v1/health` | AI 关闭时返回 200 | `code=0,status=ok` | 通过 |
| live gate 默认关闭 | 未配置 Key 运行评测命令 | 拒绝执行且不写报告 | 退出码 2，未生成报告 | 通过 |
| 真实模型评测 | 配置真实 Key 后运行 130 条评测 | 85%/90% 门槛 | 未执行：当前无真实 API Key | 未执行 |

## 8. 实施结果

- 完成项：代码、迁移、配置、SDK 锁定、130 条数据集、确定性测试、安全审计、文档和显式 live gate。
- 未完成项：OpenAI/Claude 真实模型评测及 85%/90% 指标确认。
- 与原方案差异：因安全审计发现漏洞，将 pytest/pytest-asyncio 升级到 9.1.1/1.4.0；无业务接口差异。
- 当前状态：部分完成；工程实现和离线验证完成，但未达到“真实模型指标已证实”的最终验收条件。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-001 | 缺少真实 API Key，尚未验证 85%/90% 指标 | P0 | 测试工程师Agent、AIAgent开发工程师Agent | Phase1/P2-02 验收 |
| R-002 | 生产启用前需确认供应商数据处理、保留、地域和隐私政策 | P1 | 架构师Agent | 上线前架构决策 |
| R-003 | Starlette TestClient 与 passlib 各有一条上游弃用警告 | P2 | 全栈开发工程师Agent | 后续依赖维护 |
| R-004 | 当前没有 `/suggest`，工作台仍显示等待 AI 接入 | P1 | 全栈开发工程师Agent、AIAgent开发工程师Agent | AI Phase2 |

## 10. 交接事项

- 交接给：测试工程师Agent、全栈开发工程师Agent、架构师Agent。
- 后续任务：测试工程师使用授权密钥生成正式 AI 评测报告；AI Phase2 实现店铺级 FAQ RAG 和回复工作流；全栈工程师在契约确认后接入 `/suggest`。
- 必须注意：AI 默认关闭；不得把 Scripted/Fake Provider 测试写成真实模型评测通过；不得绕过店铺权限、人工复核和平台发送边界。

## 11. 文档同步

- [x] 已同步接口变化（确认本阶段无外部 API）。
- [x] 已同步架构决策和模型边界。
- [x] 已同步任务状态为“部分完成”。
- [x] 已通知测试工程师需要覆盖的真实模型评测范围。
- [x] 测试报告索引将在正式测试完成后更新。
- [x] 已根据 `架构师/ADR-001-AI-模型适配与意图识别模块编号确认为M04-v1.0.md` 将正式模块编号同步为 M04；历史测试报告文件名保留。
