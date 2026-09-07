# Phase 4 REAL-AI-04 回复、翻译和营销草稿独立综合测试报告

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 `REAL-AI-04` |
| 模块编号 | M04 |
| 模块名称 | REAL-AI-04 回复、翻译和营销草稿 |
| 被测主责 Agent | AIAgent开发工程师Agent |
| 测试执行 Agent | 测试工程师Agent |
| 测试类型 | 综合测试、接口与集成测试、安全测试、回归测试、数据库测试、部署检查、代码审查 |
| 测试日期 | 2026-09-02 |
| 本轮结论 | **不通过** |

## 2. 测试依据

- `AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md`
- `架构师/PLAN-001-REAL-真实平台与AI生产环境接入实施计划-v1.0.md`
- `架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`
- `共享记忆文档/客户服务 PRD（AI 智能客服）.md`
- `共享记忆文档/智能客服平台 — 管理端接口文档.md`
- `共享记忆文档/MVP范围与验收标准.md`
- `共享记忆文档/代码编写手册.md`
- `共享记忆文档/实施记录/Phase4-P4-00-AIAgent开发工程师Agent-REAL-AI-04回复翻译营销草稿-026.md`
- `测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-REAL-AI-03缺陷关闭-综合测试-009.md`
- `测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-回复翻译营销与评测闭环-综合测试-014.md`

## 3. 测试目标、范围与非范围

本轮验证 REAL-AI-04 是否实现以下明确要求：

- 回复继续复用当前 Agent 状态、RAG、受控工具和 SSE 结果契约，不新增平台发送权。
- 客户语言识别、客户回复和运营人员翻译保持分离；翻译关联触发消息 UUID 和原文 SHA-256，模型输入先脱敏。
- 翻译模型失败、超时或取消不得把 Agent 运行记为成功。
- AI 营销只生成可供人工审核的安全草稿，不调用平台发送；无证据的优惠、库存、物流、退款和时效承诺必须失败关闭。
- SSE 中断或取消不得把未完成交付的运行记录标记为成功。
- `DEF-P4-AI-008/009` 及既有安全边界不得回归。

本轮不调用真实 DeepSeek，不评测真实模型语言质量，不执行公开回复、自动回复、AI 营销发送、真实 TikTok 写操作、50 客户端 SSE 压测或五日稳定性观察。测试工程师未修改产品代码、开发测试、固定评测集、依赖锁文件、计划或实施记录。

## 4. 基线冻结与独立方法

### 4.1 当前基线

- 当前目录不是 Git 仓库，无法声明提交级不可变基线。
- 对 `backend/app` 和 `backend/tests` 下 176 个 `.py/.toml/.ini` 文件按完整路径排序，分别计算 SHA-256，再将小写文件哈希以 LF 拼接后计算聚合 SHA-256：

```text
e5000c158313f712f2905a1c06257fccb8aa28e79c29093fa3336901ab994c19
```

- 测试仅产生常规缓存、构建输出和一次性数据库数据；未改写上述产品代码与开发测试。

### 4.2 独立探针

除开发测试外，本轮以内存 Stub 和路由级探针独立验证：

1. 安全弃单草稿经确定性检查和独立复核后是否保留正文、保持 `requires_human=true`、`send_performed=false`。
2. 语言不一致和独立复核拒绝时是否隐藏营销正文。
3. 翻译输入中的电子邮箱、订单标识是否脱敏，原文 SHA-256 是否准确。
4. 客户语言与运营语言相同时是否跳过翻译模型。
5. SSE 在工作流已经完成、但 `result` 事件尚未交付前断开时，运行记录是否仍被标记成功。

独立探针没有写入产品测试集，避免仅重复开发者固定样本。

## 5. 测试环境

| 组件 | 版本或状态 |
| --- | --- |
| PowerShell | 7.6.4 |
| Python | 3.11.15 |
| uv | 0.12.3 |
| Docker | 29.7.2 |
| Docker Compose | 5.3.1，使用 `docker-compose` 独立命令 |
| Node.js | 24.19.0 |
| npm | 11.17.0 |
| 前端框架 | Next.js 15.5.23 |
| 隔离数据库 | `pgvector/pgvector:pg16`，宿主端口 `55640`，一次性 `--rm` + `tmpfs` 容器 |
| Alembic head | `021_message_unknown` |
| 运行服务 | backend/frontend/postgres/redis/minio 健康，worker/jobs 运行 |
| 真实 DeepSeek | 未调用；本轮只验收确定性工程和失败关闭边界 |

## 6. 执行结果汇总

| 验证项 | 预期 | 实际 | 结果 |
| --- | --- | --- | --- |
| REAL-AI 聚焦回归 | 无失败 | 722 passed、1 warning | 通过 |
| 默认后端全量 | 无失败 | 1184 passed、10 skipped、2 warnings | 通过 |
| 隔离 PostgreSQL 全量 | 无失败、无数据库跳过 | 1194 passed、2 warnings | 通过 |
| 独立营销/翻译开放探针 | 安全草稿、危险隐藏、脱敏和哈希正确、零发送 | 5/5 通过，`send_performed=true` 为 0 | 通过 |
| SSE 结果前断开探针 | 未交付结果不得保留成功终态 | 无 `result` 事件，但 `agent_runs.status=succeeded` | **失败** |
| 营销草稿人工审核闭环 | 安全候选可被运营人员取得并审核 | Worker 将所有 REAL-AI-04 结果置为失败，候选正文未持久化且接口不返回 | **失败** |
| `DEF-P4-AI-008/009` 回归 | 保持关闭 | 聚焦和全量回归通过，未发现自动发送或既有安全门禁回归 | 通过 |
| Ruff check | 无错误 | 通过 | 通过 |
| Ruff format check | 无格式差异 | 220 files already formatted | 通过 |
| mypy | 无错误 | 161 个源文件通过 | 通过 |
| compileall | 无语法错误 | 通过 | 通过 |
| 前端 lint/typecheck | 无错误 | 均通过 | 通过 |
| 前端测试 | 无失败 | 31 passed | 通过 |
| 前端生产构建 | 构建成功 | 14 个静态路由生成成功 | 通过 |
| Compose 配置与运行态 | 配置有效、核心服务健康 | 通过；七个服务运行正常 | 通过 |
| `/v1/health` | HTTP 200 | HTTP 200，`status=ok`，版本 0.1.0 | 通过 |
| Python 锁定依赖审计 | 无已知漏洞 | `transformers 5.5.4` 命中 1 个已知漏洞 | **失败（继承门禁）** |

默认全量的 10 项跳过均为需要 `TEST_DATABASE_URL` 的 PostgreSQL 集成测试；隔离数据库升级到 head 后已执行并通过全部 1194 项。隔离数据库第一次回归因尚未迁移而报告 `stores` 表不存在；完成 `001 → 021` 后相同测试全部通过，因此该结果属于测试环境准备问题，不登记为产品缺陷。

## 7. 功能与安全审查

### 7.1 回复与翻译

- 现有回复结果继续保持 `send_performed=false`，本轮未发现 AI 直接调用平台适配器或受控写工具的新增路径。
- 翻译失败不再被工作流吞掉；开发测试覆盖 Provider 失败/超时进入失败终态。
- 独立翻译探针确认电子邮箱和订单标识在进入模型前被替换，结果保留触发消息 UUID 和准确原文 SHA-256。
- 客户语言与运营语言相同时不会调用翻译模型。
- 真实 DeepSeek 翻译准确率、风格保持、多语言长文本和生产超时降级不属于本轮已执行证据，仍为后续生产门禁。

### 7.2 营销草稿

`MarketingCopyService` 的安全边界符合以下单元级契约：

- 双重安全检查通过时保留候选正文。
- 业务承诺、语言不一致或独立复核失败时隐藏正文。
- 结果固定为 `requires_human=true`、`send_performed=false`，不会直接产生平台副作用。

但当前集成链路存在不可达闭环：服务对安全候选也固定返回 `is_safe=false`；`MarketingCycleWorker` 又规定 `not result.is_safe` 时抛出 `AI_MARKETING_REVIEW_REQUIRED`。因此安全候选在 Worker 中被记为失败，`marketing_events` 没有草稿字段，`MarketingEventView` 也不返回草稿。产品中不存在运营人员可取得、审核和批准该候选的路径。

### 7.3 SSE 断开与取消

当前 SSE 路由先等待 `suggest_for_user()` 完整结束。Agent Repository 在工作流返回前已经把运行写为 `succeeded`；路由随后才检查客户端是否断开。若客户端在首个 `delta/result` 前断开：

```text
Agent 工作流完成并提交 succeeded
→ SSE 进入 finalizing
→ request.is_disconnected() = true
→ 只输出 done(reason=disconnected)
→ result 未交付
→ AgentRun 未改为中断、取消或失败
```

路由捕获 `asyncio.CancelledError` 后也直接返回，没有补写运行或交付状态。该行为与计划“`SSE 中断、取消或模型失败不得把运行记录标记为成功`”冲突。

## 8. 缺陷与阻断

### DEF-REAL-AI04-001：SSE 在结果交付前断开仍保留成功运行

| 项目 | 内容 |
| --- | --- |
| 优先级 | **P1** |
| 状态 | **Open** |
| 类型 | 状态一致性、SSE 取消、运行追踪 |
| 影响范围 | `/v1/chat/stream`、Agent 运行指标、成功率、审计与重试判断 |
| 是否阻断 | 是，阻断 REAL-AI-04 验收和公开 SSE 放行 |
| 建议负责 Agent | AIAgent开发工程师Agent、全栈开发工程师Agent；架构师Agent确认运行成功与交付成功语义 |

复现步骤：

1. 使用 Stub 让 `suggest_for_user()` 完成工作流并把运行状态写为 `succeeded`。
2. 在 SSE 路由准备发送正文前令 `request.is_disconnected()` 返回 `true`。
3. 消费 `StreamingResponse` 事件流并读取 Agent 运行状态。

实际结果：

```text
SSE_DISCONNECT_REPRODUCED result_delivered=false run_status=succeeded
```

事件流没有 `result`，仅以 `done(reason=disconnected)` 结束，但运行状态保持成功。

预期结果：必须明确区分“模型/工作流计算成功”和“结果已交付”。按照当前 PLAN-002 的直接要求，结果交付前断开或取消不能保留单一 `succeeded` 终态；修复方案应由架构师确认，可采用独立 `delivery_status`，或在断开时写入 `cancelled/interrupted` 终态和稳定错误码，同时避免覆盖已完成计算的审计事实。

代码证据：

- `CRM智能聊天系统/backend/app/chat/router.py:94`：先执行完整 `suggest_for_user()`。
- `CRM智能聊天系统/backend/app/chat/router.py:110`：工作流完成后才检查断开。
- `CRM智能聊天系统/backend/app/chat/router.py:119`：取消异常直接返回。
- `CRM智能聊天系统/backend/app/agent/repository.py:266`：完整工作流完成时直接写 `SUCCEEDED`。

### DEF-REAL-AI04-002：安全营销候选无法进入人工审核闭环

| 项目 | 内容 |
| --- | --- |
| 优先级 | **P1** |
| 状态 | **Open** |
| 类型 | 跨模块集成、人工审核、状态机 |
| 影响范围 | AI 营销草稿、`MarketingCycleWorker`、营销事件和运营端审核 |
| 是否阻断 | 是，阻断 REAL-AI-04“生成待人工审核草稿”的端到端验收 |
| 建议负责 Agent | AIAgent开发工程师Agent、全栈开发工程师Agent、架构师Agent |

复现步骤：

1. 让营销模型返回无业务承诺、语言一致且独立复核通过的候选文案。
2. `MarketingCopyService.generate()` 返回有正文的结果。
3. 将结果交给真实 `MarketingCycleWorker._generate_ai_content()` 分支。
4. 查询营销事件和管理端事件返回结构。

实际结果：

- 安全候选正文存在，但结果固定 `is_safe=false`。
- Worker 在 `not result.is_safe` 时抛出 `AI_MARKETING_REVIEW_REQUIRED`，把事件处理为失败。
- `marketing_events` 无草稿正文/审核状态字段，`MarketingEventView` 无草稿字段。
- 运营人员没有接口取得该候选并执行审核；正文仅存在于当前函数返回对象的短暂内存中。

预期结果：安全候选应以不可发送、低权限、可审计的待审核状态保存，并提供店铺隔离的查询/批准/拒绝契约；未批准前不得调用发券、消息或平台写操作。若此闭环明确属于全栈后续任务，则 PLAN-002 和任务状态必须标记为“AI 组件完成、REAL-AI-04 端到端未完成”，不能把当前阶段整体标记完成。

代码证据：

- `CRM智能聊天系统/backend/app/agent/marketing_generation.py:198`：安全时可返回候选正文。
- `CRM智能聊天系统/backend/app/agent/marketing_generation.py:200`：结果固定 `is_safe=false`。
- `CRM智能聊天系统/backend/app/marketing/worker.py:386`：Worker 对该结果必然拒绝并抛错。
- `CRM智能聊天系统/backend/app/marketing/models.py:55`：营销事件无审核草稿字段。
- `CRM智能聊天系统/backend/app/marketing/schemas.py:77`：事件 API 无审核草稿输出。
- 026 号实施记录 `R-003` 已将“没有独立运营审核持久化/发布接口”列为 P1 风险，本轮确认它会阻断实际审核链路。

### 继承门禁：Transformers 锁定版本存在已知漏洞

本项已在 REAL-FS-04 报告和实施记录中登记为继承风险 `R-REAL-FS04-002`，本轮不重复创建缺陷编号：

```text
transformers 5.5.4
GHSA-xrqw-3rrv-vx5w / CVE-2026-9856
save_pretrained path traversal allows arbitrary file writes through chat template names
Fixed in: 5.10.0
```

本轮扫描 47 个 Agent、Chat 和 Marketing Python 文件，没有发现 `save_pretrained` 调用，也没有发现潜在明文密钥特征，因此没有证明当前在线请求路径可直接触发该漏洞；但锁定依赖审计仍失败，生产镜像不得据此放行。应由 AIAgent开发工程师Agent评估升级至已修复版本并执行 BGE 模型加载、Embedding、Rerank、GPU/CPU 和离线资产兼容回归。

## 9. 自动化、数据库与运行态证据

### 9.1 后端命令

| 命令 | 结果 |
| --- | --- |
| `uv lock --check` | 通过；解析 125 个包 |
| `uv run ruff check app migrations scripts tests` | All checks passed |
| `uv run ruff format --check app migrations scripts tests` | 220 files already formatted |
| `uv run mypy app scripts` | 通过；161 个源文件 |
| `uv run python -m compileall -q app scripts` | 通过 |
| `uv run pytest -q tests/test_agent_phase4.py tests/test_agent_workflow.py tests/test_agent_providers.py tests/test_phase4_domain.py tests/test_sse_load_test.py` | 722 passed、1 warning |
| `uv run pytest -q` | 1184 passed、10 skipped、2 warnings |
| 设置隔离 `TEST_DATABASE_URL` 后 `uv run pytest -q` | 1194 passed、2 warnings |
| `uv audit --locked` | 失败；1 个已知漏洞、124 个包无其他不利状态 |

两项全量警告来自 Starlette TestClient/httpx 与 `argon2.__version__` 弃用提示，不阻断本轮功能结论。

### 9.2 数据库

| 场景 | 结果 |
| --- | --- |
| 空隔离数据库 `001 → 021` | 通过 |
| `alembic current` | `021_message_unknown (head)` |
| 隔离 PostgreSQL 全量 | 1194 passed、0 skipped |
| 临时容器清理 | `crm-real-ai04-test-001` 已停止并因 `--rm` 自动删除 |

REAL-AI-04 没有新增迁移，本轮不重复执行 `021 → 020 → 021` 迁移往返；最新 REAL-FS-04 002 号报告已覆盖该 head 往返，本轮重点验证空库升级和当前代码的完整数据库回归。

### 9.3 前端、Compose 与健康检查

| 验证项 | 结果 |
| --- | --- |
| `npm run lint` | 通过 |
| `npm run typecheck` | 通过 |
| `npm run test` | 31 passed |
| `npm run build` | Next.js 15.5.23 构建通过，14 个静态路由生成成功 |
| `docker-compose config --quiet` | 通过 |
| `docker-compose ps` | backend/frontend/postgres/redis/minio 健康，worker/jobs 运行 |
| `GET /v1/health` | HTTP 200，`status=ok`，版本 0.1.0 |

运行环境为 development。`auto_reply_enabled=false`、`ai_marketing_enabled=false`、TikTok 普通/高风险真实写入均为 `false`、`allow_mock_platform_adapters=false`，未发生真实发送。当前开发容器启用了内部 LLM/翻译运行面，不代表生产翻译或公开 AI 已放行。

## 10. 尚未完成的生产门禁

除本报告两个 Open 缺陷外，以下门禁仍未完成：

- 真实 DeepSeek 回复、翻译和营销草稿开放集质量评测。
- 真实模型业务事实服从率、数据出境、脱敏和生产错误降级验收。
- 50 个授权客户端 SSE 首输出、P99、错误率、断线/取消和恢复测试。
- 连续五日稳定性和 99.5% 可用性。
- `transformers` 漏洞升级及 BGE 兼容复测。
- 真实 TikTok 店铺联调、真实人工消息发送和联合回滚。
- Git 提交或其他不可变发布候选冻结。

公开 AI 回复、生产翻译、AI 营销、自动回复及 AI 触发的平台写操作必须继续关闭。

## 11. 最终结论

**REAL-AI-04 回复、翻译和营销草稿独立综合测试不通过。**

- 确定性回复/翻译/营销安全组件、722 项聚焦、1194 项隔离 PostgreSQL 全量、31 项前端、静态质量、构建、Compose 和健康检查通过。
- 翻译脱敏、触发消息关联、原文哈希、同语言跳过模型、安全营销候选保留、危险候选隐藏和零发送通过独立探针。
- `DEF-P4-AI-008/009` 未发现回归，继续保持 Closed。
- 新增 `DEF-REAL-AI04-001`（P1/Open）：SSE 在结果交付前断开仍把运行保留为成功。
- 新增 `DEF-REAL-AI04-002`（P1/Open）：安全营销候选在 Worker 中被失败关闭，产品没有运营审核持久化和读取路径。
- Python 锁定依赖仍有 1 个已知漏洞，作为已登记的继承生产门禁继续 Open。
- 在两个新 P1、依赖安全、真实模型和稳定性门禁关闭前，不得放行公开 AI 回复、生产翻译、AI 营销、自动回复或 AI 触发的平台写操作。

## 12. 清理与交接

- 测试工程师仅新增本报告并更新 `共享记忆文档/测试报告索引.md`，未修改产品代码或开发测试。
- 一次性 PostgreSQL 容器 `crm-real-ai04-test-001` 已停止并自动删除，复核无残留；其 `tmpfs` 临时测试数据不可恢复。
- 现有项目 backend/frontend/postgres/redis/minio/worker/jobs 服务未受清理影响。
- `DEF-REAL-AI04-001` 交由 AI 与全栈共同修复，并由架构师明确“计算成功/交付成功”状态模型。
- `DEF-REAL-AI04-002` 交由 AI、全栈和架构师联合补齐不可发送的人工审核闭环。
- 修复后应由测试工程师执行第二次独立综合复测；不得只重复开发固定测试。
