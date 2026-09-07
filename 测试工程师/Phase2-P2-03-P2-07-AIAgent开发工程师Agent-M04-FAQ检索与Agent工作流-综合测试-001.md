# Phase 2 P2-03/P2-07 M04 FAQ 检索与 Agent 工作流综合测试报告

## 1. 报告信息

| 项目 | 内容 |
| --- | --- |
| 测试报告编号 | Phase2-P2-03-P2-07-M04-001 |
| 测试阶段 | Phase 2 |
| 测试任务 | P2-03 FAQ 检索；P2-07 Agent 对话编排 |
| 模块编号 | M04 |
| 被测主责 Agent | AIAgent开发工程师Agent |
| 测试执行 Agent | 测试工程师 Agent |
| 测试日期 | 2026-08-20 |
| 测试类型 | 综合测试、AI 评测、回归测试、安全测试、集成测试 |
| 被测版本 | AI Agent Phase 2，数据库迁移 head 013 |

## 2. 测试依据与范围

### 2.1 测试依据

- `共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md`
- `共享记忆文档/智能客服平台 — 管理端接口文档.md`
- `共享记忆文档/MVP范围与验收标准.md`
- `共享记忆文档/开发任务拆解（按人天分配）.md`
- `AI agent 开发工程师/PLAN-001-AI-Agent工程实施计划-v1.0.md`
- `AI agent 开发工程师/AI-002-RAG-FAQ检索与Agent工作流规范-v1.0.md`
- `共享记忆文档/实施记录/Phase2-P2-03-AIAgent开发工程师Agent-FAQ向量检索-001.md`
- `共享记忆文档/实施记录/Phase2-P2-07-AIAgent开发工程师Agent-Agent对话编排-001.md`

### 2.2 本次覆盖

- Embedding Provider 错误分类、重试上限、维度和有限数值校验。
- FAQ Token 切分、问题前缀、批量向量化和版本漂移保护。
- 店铺隔离、`published + ready + current version` 检索门禁、Top 5 和最低分数。
- LangGraph 状态流转、工具需求门禁、无知识转人工、引用合法性和安全复核。
- 意图/检索/依据三项置信度聚合、`0.60/0.80` 阈值和 `send_performed=false`。
- `agent_runs` 单次运行追踪、节点路径、引用 UUID、Prompt 版本和敏感信息不落库。
- Phase 1 AI 适配层回归、RAG 评测集数量校验和项目静态质量门禁。

### 2.3 明确不纳入本次结论

- 真实 OpenAI Embedding 和 LLM live gate。
- 公开 `/suggest`、SSE、工具真正执行、平台发送和前端页面。
- 真实 TikTok、Shopee、Amazon 联调。

## 3. 测试环境

| 项目 | 环境 |
| --- | --- |
| 操作系统 | Windows，PowerShell |
| Python | 项目基线 3.11.15 |
| 后端 | FastAPI、SQLAlchemy 异步模式、LangGraph 1.2.11、tiktoken 0.13.0 |
| 数据库 | PostgreSQL 16 + pgvector，目标迁移 head 013 |
| Redis/MinIO | Compose 服务依赖 |
| 测试模式 | 默认离线确定性 Provider，不访问公网模型 |
| 运行限制 | Windows 主机访问 Docker 暴露 PostgreSQL 端口时 asyncpg 连接被重置；Compose backend 端口存在并行容器占用风险 |

密钥安全：未在报告、日志或测试输出中记录任何 API Key；由于无法确认风险密钥已经轮换，未执行真实模型测试。

## 4. 测试执行命令与结果

### 4.1 本地质量门禁

| 命令 | 实际结果 | 状态 |
| --- | --- | --- |
| `uv --offline --cache-dir .uv-cache lock --check` | 锁文件解析通过 | 通过 |
| `uv --offline --cache-dir .uv-cache run ruff check app migrations scripts tests` | All checks passed | 通过 |
| `uv --offline --cache-dir .uv-cache run ruff format --check app migrations scripts tests` | 144 files already formatted | 通过 |
| `uv --offline --cache-dir .uv-cache run mypy app scripts` | 110 个源文件无类型错误 | 通过 |
| `uv --offline --cache-dir .uv-cache run pytest -q` | 64 passed，2 skipped，2 warnings | 通过 |
| Agent 专项测试及领域测试 | 54 passed，1 warning | 通过 |

### 4.2 Compose 与运行检查

| 检查项 | 实际结果 | 状态 |
| --- | --- | --- |
| `docker-compose config --services` | redis、minio、postgres、backend、frontend、jobs、worker 均可解析 | 通过 |
| `GET http://localhost:8000/v1/health` | `code=0`、`status=ok`、版本 `0.1.0` | 通过 |
| `docker-compose exec -T backend alembic current` | `013_marketing (head)` | 通过 |
| backend 启动 | 曾出现 8000 端口被并行 QA 容器占用，清理运行环境后可获得健康响应 | 环境风险 |

### 4.3 PostgreSQL/pgvector 集成证据

集成用例覆盖：

1. 店铺隔离、发布状态、向量化状态、当前文档版本和最低相似度过滤。
2. 两个 Worker 并发 `FOR UPDATE SKIP LOCKED` 认领不同 pending 文档。

AI 工程师实施记录提供的容器网络执行证据为 `2 passed`。本次测试工程师在 Windows 主机上使用隔离临时数据库复测时，两个用例均在数据库连接/清理阶段出现 `WinError 10054` / `ConnectionDoesNotExistError`，原因是主机到 Docker PostgreSQL 暴露端口的 asyncpg 连接被远端关闭，不能判定为产品断言失败。

临时数据库 `crm_ai_phase2_test` 已删除，不影响项目数据库。

## 5. 测试场景与结果

| 场景 | 预期 | 结果 |
| --- | --- | --- |
| Embedding 返回 1536 维向量 | 接受并返回统一结果 | 通过 |
| 向量维度错误、NaN、Infinity | 稳定拒绝，不写入 | 通过 |
| 超时、限流、连接失败 | 按稳定错误码和有限重试处理 | 通过 |
| 认证、权限、非法请求错误 | 不降级绕过，立即失败 | 通过 |
| FAQ 长文本切分 | 单片段不超过 800 Token，重叠 80 Token并保留问题前缀 | 通过 |
| 文档版本在向量化期间变化 | 旧任务不能覆盖新版本 | 通过 |
| 多 Worker 认领 pending 文档 | 同一文档只被一个 Worker 认领 | 通过；容器证据 2 passed，本机复测受网络阻塞 |
| 跨店铺 FAQ 检索 | 不返回其他店铺内容 | 通过；容器证据 2 passed，本机复测受网络阻塞 |
| draft、archived、failed、旧版本 FAQ | 不参与正式检索 | 通过 |
| Top 5 和分数门禁 | 最多返回 5 条，低于 0.70 排除 | 通过 |
| 正常 FAQ 工作流 | 意图→RAG→回答→安全→置信度 | 通过 |
| 未知、混合、上下文不足 | `intent=null` 并转人工 | 通过 |
| 订单/物流实时请求 | 只声明白名单工具需求，不执行工具并转人工 | 通过 |
| 无知识或低分检索 | 不生成猜测答案，转人工 | 通过 |
| 空引用、越界引用、非法引用 | 安全复核失败，置信度归零并转人工 | 通过 |
| Prompt 注入知识 | 知识按不可信数据处理，不执行其中指令 | 通过 |
| 0.60 和 0.80 阈值 | 分别进入人工复核和自动回复就绪 | 通过 |
| 自动回复就绪 | `AUTO_REPLY_READY`，且 `send_performed=false` | 通过 |
| Agent 运行追踪 | 只保存摘要、节点、引用 UUID、Prompt 版本等安全字段 | 通过 |
| 取消、超时、异常 | 写入稳定失败状态和错误码，不丢运行记录 | 通过 |

## 6. AI 评测集检查

评测集 `backend/evals/faq-rag-v1.0.0.jsonl` 已通过确定性结构检查：

- 有目标 FAQ 样本：50 条。
- 无答案、混合、越权和 Prompt 注入样本：20 条。
- 总样本：70 条。
- 覆盖中英文和多类边界输入。

正式质量门禁 `Recall@5 >= 90%`、无答案正确拒判率 `>= 90%`、引用合法率 `100%` 需要真实 Embedding 与 LLM 执行。本次未将 Fake Provider 或离线结构测试作为正式 AI 质量通过结论。

## 7. 安全审查

- 未发现生产代码、实施记录和本报告中出现 API Key、客户原文、FAQ 完整正文或完整模型响应的证据。
- 输入摘要使用字符数、消息数和 SHA-256，不保存原始消息。
- Agent 不直接写会话、消息、订单等业务表，不直接访问平台适配器。
- 模型不能自行决定动作；置信度和转人工由代码计算。
- 工具需求只产生白名单声明，Phase 2 未执行工具。
- 自动回复动作没有发送副作用。

## 8. 缺陷与风险

### DEF-M04-001：真实模型 RAG 质量门禁未执行

| 属性 | 内容 |
| --- | --- |
| 优先级 | P0，验收阻塞 |
| 类型 | 环境/安全前置条件未满足 |
| 现象 | 未确认风险密钥已轮换，真实 OpenAI Embedding 与回答评测未执行 |
| 复现/确认步骤 | 配置 `EMBEDDING_ENABLED=true` 和 `LLM_LIVE_EVAL=true` 前，无法安全启动真实评测 |
| 影响 | 无法确认 Recall@5、拒答率、引用合法率等正式质量指标 |
| 处理建议 | 先轮换并确认密钥，再由测试工程师执行 live gate，生成独立 AI 评测报告 |
| 当前状态 | 未关闭 |

### ENV-M04-002：Windows 主机 PostgreSQL 集成测试连接重置

| 属性 | 内容 |
| --- | --- |
| 优先级 | P1，环境阻塞 |
| 现象 | 主机 asyncpg 访问 Docker 暴露的 5432 时收到 WinError 10054/64 |
| 影响 | 本次无法在主机侧复现两个 PostgreSQL 集成用例；不能据此判定产品失败 |
| 已有证据 | AI 工程师实施记录提供的容器网络执行结果为 2 passed |
| 建议 | 在 CI 或同一 Docker 网络中执行数据库集成测试，并避免 8000 端口并行容器冲突 |
| 当前状态 | 环境遗留 |

## 9. 回归结果

Phase 1 既有测试未被破坏；完整 pytest 结果为 `64 passed, 2 skipped`。2 个跳过用例为未提供隔离 `TEST_DATABASE_URL` 的 PostgreSQL 集成测试，不是业务断言跳过。Agent 专项测试为 `54 passed`。

项目代码质量门禁通过，数据库 head 保持 013，未发现公开 API、前端或业务表被本阶段 AI 实现越界修改。

## 10. 测试结论与验收建议

### 10.1 当前结论

M04 P2-03 和 P2-07 的工程实现、离线功能测试、静态质量、安全边界和工作流逻辑测试通过；未发现代码级缺陷。

### 10.2 是否建议验收

**建议：有条件通过，不建议发布为正式 AI 质量验收通过。**

通过条件：

- 轮换并确认 OpenAI 密钥后执行真实 RAG live gate。
- 在 Docker 网络或 CI 环境重新执行 PostgreSQL/pgvector 两个集成用例。
- 真实评测达到 `Recall@5 >= 90%`、无答案正确拒判率 `>= 90%`、引用合法率 `100%`。
- 测试工程师补充正式 AI 评测报告并关闭 DEF-M04-001。

当前阶段不得把 `AUTO_REPLY_READY` 当作已经发送消息，也不得把确定性 Fake Provider 结果作为真实模型质量结论。

