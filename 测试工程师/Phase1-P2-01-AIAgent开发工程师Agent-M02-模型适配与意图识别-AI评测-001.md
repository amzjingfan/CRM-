# AI Agent Phase 1 模型适配与意图识别测试报告

## 1. 测试基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase1（AI Agent 工程计划） |
| 任务编号 | P2-01；关联 P2-02 |
| 模块编号 | M02（临时编号，架构师尚未正式确认） |
| 模块名称 | 模型适配与意图识别 |
| 被测主责 Agent | AIAgent开发工程师Agent |
| 被测协作 Agent | 架构师Agent、全栈开发工程师Agent |
| 测试执行 Agent | 测试工程师 Agent |
| 关联实施记录 | `共享记忆文档/实施记录/Phase1-P2-01-AIAgent开发工程师Agent-模型适配与意图识别-001.md` |
| 测试类型 | AI评测、回归测试、安全测试、集成测试 |
| 执行日期 | 2026-08-20 |
| 测试结论 | 不通过；修复 P1 截断响应缺陷并完成真实模型评测前，不建议最终验收 |

> 说明：项目当前没有正式 AI 模块编号。本报告依据测试报告命名规范，临时使用已有示例中的 `M02`，不代表架构编号已确认。

## 2. 测试范围

### 2.1 包含范围

- OpenAI Responses API 和 Anthropic Claude Messages API 适配器。
- Provider 错误分类、超时、限流、连接失败、认证失败、权限失败和服务端错误映射。
- 结构化输出 Pydantic 校验、拒绝、截断和非法输出路径。
- 五类意图：物流查询、退货政策、尺码指南、价格咨询、一般问题。
- `unknown`、`mixed`、`insufficient_context`、`model_refusal` 保守拒判。
- 0.6 置信度阈值与 `human_review`/`transfer_human` 动作。
- 消息长度、历史条数、上下文总长度和 PII 脱敏。
- `agent_runs` 模型、Repository、009 迁移、索引、外键、检查约束和失败记录。
- 130 条版本化评测集、默认关闭的 live gate 和评测报告生成命令。
- Phase 1 对现有 FastAPI 应用、Compose 和健康检查的回归影响。

### 2.2 不包含范围

- 真实 OpenAI/Claude 质量评测：因当前环境没有授权 API Key，未访问公网。
- FAQ RAG、工具调用、自动回复、平台发送、`/suggest`、SSE 和前端页面。
- 正式压力测试和供应商数据处理合规审查。

## 3. 测试环境

| 项目 | 环境 |
| --- | --- |
| 操作系统 | Windows |
| Python | 3.11.15 |
| pytest | 9.1.1 |
| pytest-asyncio | 1.4.0 |
| OpenAI SDK | 2.54.0 |
| Anthropic SDK | 0.120.2 |
| 数据库 | PostgreSQL 16 + pgvector Docker 容器 |
| Redis/MinIO | Docker Compose 服务 |
| 后端 | FastAPI，开发环境，`LLM_ENABLED=false` |
| 数据库版本 | `009_agent_runs` |
| 真实密钥 | 未提供；未写入报告、日志或配置 |

## 4. 测试执行记录

### 4.1 自动化和工程质量

| 验证项 | 命令 | 结果 |
| --- | --- | --- |
| Ruff | `backend/.venv/Scripts/ruff.exe check app migrations scripts tests` | 通过 |
| 格式 | `backend/.venv/Scripts/ruff.exe format --check app migrations scripts tests` | 99 files already formatted |
| mypy | `backend/.venv/Scripts/mypy.exe app scripts` | 74 个源文件无错误 |
| 编译 | `python -m compileall -q app migrations scripts tests` | 通过 |
| 单元/集成回归 | `backend/.venv/Scripts/pytest.exe` | 30 passed |
| 依赖安全 | `uv audit --locked` | 61 个包无已知漏洞 |

pytest 产生 2 条非阻断上游弃用警告：Starlette TestClient/httpx 兼容性、passlib 访问 argon2 版本属性。

### 4.2 数据库和应用

| 验证项 | 方法 | 结果 |
| --- | --- | --- |
| Compose 配置 | `docker-compose config --quiet` | 通过 |
| 迁移升级 | `docker-compose run --rm backend alembic upgrade head` | 通过 |
| 迁移回滚 | `docker-compose run --rm backend alembic downgrade 008_webhooks_audit` | 通过 |
| 迁移重升 | `docker-compose run --rm backend alembic upgrade head` | 通过 |
| 迁移版本 | PostgreSQL 查询 `alembic_version` | `009_agent_runs` |
| Agent 索引 | 查询 `pg_indexes` | 主键、会话时间索引、店铺时间索引存在 |
| Agent 约束 | 查询 `pg_constraint` | 3 个检查约束、3 个外键和主键存在 |
| 模型注册 | 导入 `app.shared.database.models.AgentRun` | 注册成功 |
| 应用健康 | `GET http://localhost:8000/v1/health` | HTTP 200，`code=0` |

### 4.3 安全和拒判

| 场景 | 预期 | 实际 |
| --- | --- | --- |
| 邮箱、手机号、订单/物流长标识 | 发送模型前脱敏 | 自动化测试通过 |
| API Key | 使用 `SecretStr`，不进入日志/报告 | 自动化测试通过 |
| Prompt 注入 | 不改变系统分类规则 | Prompt 与评测样本覆盖 |
| 高置信度分类 | Phase 1 只能 `human_review` | 自动化测试通过 |
| 低置信度/未知/混合/上下文不足 | `transfer_human` 且空意图 | 自动化测试通过 |
| 模型拒绝 | 不换模型绕过，转人工 | 自动化测试通过 |
| live gate 默认关闭 | 不访问公网、不生成伪报告 | 退出码 2，未生成报告 |

## 5. 通过项

- 统一 Provider 接口、OpenAI/Claude 配置切换和 SDK 重试关闭逻辑已覆盖。
- 超时、限流、连接、认证、权限、非法请求、供应商错误和拒绝映射测试通过。
- 五类意图及拒判状态的 Pydantic 契约、边界分数和动作计算测试通过。
- 130 条 JSONL 数据集数量和分布校验通过：五类各 20 条，三类拒判各 10 条。
- `agent_runs` 在模型调用前创建 running 记录，失败终态独立提交的 Repository 单元测试通过。
- 009 迁移可升级、可回滚、可重新升级，数据库索引、外键和检查约束存在。
- AI 默认关闭不影响既有服务启动；健康检查和全量 30 项自动化回归通过。
- 依赖安全审计无已知漏洞。

## 6. 失败项和缺陷

### DEF-AI-001：Provider 接受截断的结构化响应

| 项目 | 内容 |
| --- | --- |
| 优先级 | P1 |
| 状态 | 待修复 |
| 影响 | 不完整的模型输出可能被当作合法意图，进入 `human_review`，污染分类结果和运行追踪 |
| 责任 Agent | AIAgent开发工程师Agent |
| 关联要求 | 计划要求处理模型拒绝、截断和异常输出 |

复现步骤：

1. 使用测试客户端返回合法 `output_parsed`，同时设置 OpenAI `incomplete_details.reason=max_output_tokens`。
2. 调用 `OpenAIProvider.generate_structured(...)`。
3. 实际结果为成功的 `ProviderResult`，测试输出：`TRUNCATION_ACCEPTED=True`。
4. 使用 Claude 测试客户端返回合法 `parsed_output`，同时设置 `stop_reason=max_tokens`。
5. 实际结果同样被接受，测试输出：`TRUNCATION_ACCEPTED=True`。

预期结果：

- OpenAI 截断应转换为 `LLM_OUTPUT_INVALID`，允许一次结构重生成或进入失败终态。
- Claude `max_tokens` 截断应转换为 `LLM_OUTPUT_INVALID`，不得继续使用该分类结果。

修复建议：在读取 `output_parsed/parsed_output` 前检查供应商终止状态；对 OpenAI 的 `incomplete_details.reason` 和 Claude 的 `stop_reason` 增加截断分支，并补充两个回归测试。

### DEF-AI-002：真实模型质量门禁未执行

| 项目 | 内容 |
| --- | --- |
| 优先级 | P0（验收阻塞） |
| 状态 | 环境阻塞，非代码失败 |
| 影响 | 无法证明五类准确率 ≥85%、边界正确拒判率 ≥90% |
| 责任 Agent | 测试工程师Agent、AIAgent开发工程师Agent |

复现步骤：

1. 在未配置 `LLM_LIVE_EVAL=true` 和真实 API Key 的环境执行 `python -m scripts.evaluate_intents`。
2. 实际退出码为 2。
3. 实际提示“真实模型评测未启用”，且没有生成报告。

处理要求：由项目负责人提供合规授权的模型配置后，重新执行 130 条 live 评测；不得使用 Scripted/Fake Provider 代替正式质量门禁。

## 7. 回归结果

Phase 1 AI Agent 变更未破坏既有 Phase 1/Phase 2 工程基线：

- FastAPI 健康检查正常。
- PostgreSQL/Redis/MinIO Compose 配置和后端容器正常。
- 001–009 迁移链路正常。
- 认证 Cookie、平台适配器和安全测试仍通过。
- 未新增 AI HTTP API，未改变前端和业务消息链路。

## 8. 验收建议

当前结论：不通过，暂不建议最终验收。

原因：

1. `DEF-AI-001` 是计划明确要求覆盖的模型截断处理缺陷，可能接受不完整结果。
2. `DEF-AI-002` 导致 85%/90% 真实模型质量门禁尚无证据。
3. 架构师尚未确认模块编号 `M02`，本报告使用临时编号并已显式标注。

建议验收前置条件：

- 修复 DEF-AI-001，并完成 OpenAI/Claude 截断回归测试。
- 提供真实模型评测所需的合规 Key、模型名和网络环境，生成正式 AI 评测报告。
- 架构师确认 AI 模块正式编号，并按确认编号修订本报告或生成新序号报告，不覆盖当前报告。

## 9. 附件和证据

- 被测实施记录：`共享记忆文档/实施记录/Phase1-P2-01-AIAgent开发工程师Agent-模型适配与意图识别-001.md`
- 评测集：`CRM智能聊天系统/backend/evals/intent-classifier-v1.0.0.jsonl`
- Provider 测试：`CRM智能聊天系统/backend/tests/test_agent_providers.py`
- 分类与重试测试：`CRM智能聊天系统/backend/tests/test_agent_service.py`
- Repository 测试：`CRM智能聊天系统/backend/tests/test_agent_repository.py`
- 迁移：`CRM智能聊天系统/backend/migrations/versions/009_create_agent_runs.py`
