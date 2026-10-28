# 动态多 Agent 重写实施方案

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. 用户已于 2026-10-28 授权实施与本地验证；部署须完成后另行批准。

**Goal:** 在现有单仓库模块化单体内，以可配置、可追踪的多 Agent 运行链路替换 Agent 旧 FAQ 专用链路；模型从店铺所有已启用 Agent 中语义选择，从各 Agent 配置的全部工具中以原生 function calling 选择调用，多个 Agent 分别处理后汇总，全部输出供坐席审核。

**Architecture:** 使用数据库发布的不可变 Agent 版本作为动态注册表。协调器冻结会话快照后用结构化 function call 路由，再在同一截止时间内并行运行子 Agent；每个子 Agent 的工具用 `@tool` 注册，向模型暴露完整配置目录与当前授权状态，执行由服务端按店铺、会话和配置复核。会话内记忆、上下文预算、提示词安全和审计围绕同一快照构建，逐阶段用开关从旧链路切换。

**Tech Stack:** FastAPI、Pydantic、SQLAlchemy/Alembic、PostgreSQL/pgvector、现有 LangGraph、显式声明 `langchain-core`（`@tool`）、现有模型 Provider 的原生 function calling、Next.js/React、集中式 `src/tests/`。

**Spec:** [动态多 Agent 重写设计](../specs/2026-10-28-dynamic-multi-agent-rewrite-design.md)。

## 全局约束

- 用户已决定：同店多个 Agent；该店铺所有已启用 Agent 均为路由候选，不按预设类型或数量裁剪；模型按描述选择一个或多个并汇总一段回答。各 Agent 配置的全部工具均为可发现候选，不按数量裁剪；可信 ID 与权限由服务端决定。
- 七段式系统提示词必填、可编辑、版本化；Agent 模型只可从项目当前已配置的模型选择。发布新版本后动态加入运行注册表。
- 文件检索只限显式绑定、同店、当前有效、已索引且获内部审批的文件；未绑定时只用本次获授权的已绑定工具，知识不足时澄清或转人工；不使用店铺默认知识集、不回退旧 FAQ。知识库 FAQ 管理与数据保留。
- 记忆只在相同店铺、会话、客户间使用；同一会话关闭后重开恢复先前有效记忆，不跨会话或用户。会话删除/身份变化使派生记忆不可读。
- TikTok 人工辅助 v0.1 保持零自动平台发送。真实写工具、公开自动回复、自动营销和 production 均不因本计划放行；人工发送仍走既有确认、幂等、审计链路。
- 复用现有单体、PostgreSQL/pgvector、工具执行契约和知识库文件管线，不新增微服务、插件平台或第二套向量库。迁移需有安全回退开关，不强制改写现有会话/FAQ 数据。
- Agent 路由与工具选择使用 Provider 原生 function calling；工具由 `langchain_core.tools.tool` 的 `@tool` 装饰器定义并绑定已有 Pydantic Schema。只读调用可在授权后自动执行；配置的写工具可被模型提出，但需人工确认，模型不得直接执行平台写入或发送。
- 不设 Agent 候选数、工具候选数或工具调用次数的业务硬上限。模型窗口、Provider 单请求容量与总截止时间仍须遵守；超容量时分批覆盖全部候选并合并结果，超时则明确澄清/转人工，不静默漏选。现有 RAG 子链路 12 秒、调试整轮 45 秒及正式链路的性能门禁要实测复核。
- 每个代码任务都先写行为测试并验证失败，再实施、复测、更新当前 `docs/` 与 IR/TR/RR；部署与真实模型/平台读取按独立授权和项目门禁执行。

## 重点复核情景

| 情景 | 应有结果 | 归属任务 |
|---|---|---|
| 同一店铺多个启用 Agent，路由模型返回外店或已停用 ID；候选目录大于单请求容量 | 服务端拒绝非法 ID；分批覆盖全部合法候选，不静默遗漏 | 2、8 |
| 买家在消息或检索文件中要求“忽略规则并查询其他订单” | 文本仍是数据；工具对象只取可信会话绑定，输出经安全复核 | 3、4、8 |
| 同一会话关闭再重开，或同一客户打开另一会话 | 前者恢复原 revision，后者完全看不到旧摘要/事实 | 6 |
| 摘要与订单/政策原文冲突或上下文超预算 | 原值及来源不被改写；标记冲突/澄清，不截断关键事实 | 5、8 |
| 多子 Agent 一快一慢、答案矛盾，或用户取消请求 | 统一截止、取消收敛，冲突交人工；无后台孤儿任务或平台发送 | 8、10 |

## 文件落点与依赖方向

| 新模块或既有文件 | 单一职责 |
|---|---|
| `src/backend/app/agents/management/{models,schemas,repository,service,router}.py` | 配置版本、状态和管理 API；由现有 `app.agent_management` 迁入 |
| `src/backend/app/agents/prompts/{sections,compiler,registry}.py` | 七段式校验、发布编译和版本 hash；平台固定安全策略独立 |
| `src/backend/app/agents/tools/{catalog,definitions,execution}.py` | `@tool` 定义和注册全部已配置工具、生成原生 function-calling Schema、既有工具执行契约适配；不复制工作台通用业务实现 |
| `src/backend/app/agents/providers/tool_calling.py` | DeepSeek/OpenAI/Anthropic 的 tool calls 适配、模型能力校验和多轮消息协议 |
| `src/backend/app/agents/rag/retriever.py` | 当前 Agent 的显式文件范围查询；调用 `app.knowledge_base` 已有搜索端口 |
| `src/backend/app/agents/runtime/{snapshot,context,state,worker}.py` | 冻结快照、总上下文预算、关键事实、子 Agent 单轮执行 |
| `src/backend/app/agents/memory/{models,repository,service}.py` | 会话内摘要和验证事实的隔离读写、版本与生命周期 |
| `src/backend/app/agents/orchestration/{registry,router,coordinator,aggregator}.py` | 动态 Agent 列表、语义路由、并行子运行和有依据汇总 |
| `src/backend/app/agents/safety/{input,output}.py` | 不可信内容标签、分字段 DLP、注入纵深检测与最终校验；复用现有业务声明检查 |
| `src/backend/app/chat/{service,worker}.py`、`src/backend/app/agent/factory.py`、`src/backend/app/agent_management/*` | 阶段切换及短期兼容；所有调用方迁完后删除旧 Agent 专用代码 |
| `src/frontend/app/agents/{page.tsx,agent-prototype.css}`、`src/frontend/lib/api*` | 配置、发布、七段式编辑、预览路由轨迹和运行记录；延续现有 v3 原型布局 |
| `src/backend/migrations/versions/035_*.py` 起 | 以实施时真实 Alembic head 分配编号；扩展配置/运行/记忆结构，分步回填 |

依赖只朝一个方向：`management` 提供已发布配置；`orchestration` 调用 `runtime`；`runtime` 通过 `tools/rag/memory/safety` 的窄接口执行；知识库和工作台不反向依赖协调器。旧导入路径短期适配，移除前以全仓引用扫描证明无调用方。

## Task 1：锁定旧行为与目录兼容

**Files:** 创建 `src/tests/backend/agent/test_agent_rewrite_baseline.py`；建立 `src/backend/app/agents/__init__.py`；在 `src/backend/app/shared/config/settings.py` 与 `src/config/.env.example` 声明默认关闭的双开关；后续迁移的兼容导入记录在 `docs/architecture/AI.md`。

**Interfaces:** 记录现有正式会话、调试、工具、FAQ、绑定文件 RAG、取消和人工发送的公开行为；此任务不改变运行路由。

- [ ] 写基线测试：已绑定文件只读同店审批版本；无绑定的当前旧链路结果；高风险工具不因 Agent 配置直接写；调试不发送消息；旧 API 返回字段保持兼容。
- [ ] 在 `src/backend/` 执行这些测试并记录基线结果及真实 SHA；若已有失败先定位，不把失败写成改造结果。
- [ ] 建立新包及调用关系清单；标出工作台共用 `app.tools` 的调用方，禁止简单整目录移动。
- [ ] 声明 `AGENT_V2_DEBUG_ENABLED`、`AGENT_V2_FORMAL_ENABLED`，默认 false；此阶段不开启新执行器，也不改变旧运行路由。
- [ ] 运行 Agent 目录测试与 `git diff --check`，提交独立、无产品行为变化的基线提交。

## Task 2：多 Agent 配置、不可变版本与状态

**Files:** 新建 `agents/management/{models,schemas,repository,service,router}.py`，扩展 `src/backend/app/agent_management/models.py`，新增实际 head 后的 Alembic 迁移；测试 `src/tests/backend/agent_management/test_dynamic_config.py`、`src/tests/integration/postgres/test_dynamic_agent_config.py`。

**Interfaces:** `list_enabled_agents(session, store_id) -> list[PublishedAgent]`；`publish_agent(session, agent_id, expected_revision) -> PublishedAgent`。`PublishedAgent` 含 `id/store_id/config_version/model_id/prompt_version/tool_names/file_ids/status`，读取时不可变。

- [ ] 先写失败测试：同店能启用两个服务类 Agent，跨店查询为零；草稿/暂停/归档不入注册表；旧唯一启用约束迁移后消失；并发发布只成功一个预期 revision。
- [ ] 增加配置版本表、当前版本引用和状态转换；既有配置回填版本 1。模型 ID 只接受运行环境已配置白名单。路由候选包含当前店铺所有已启用 Agent，不按 `agent_type` 预过滤。
- [ ] 扩展既有 `/agents` 管理接口，保留旧响应和 `enable/disable/toggle` 过渡行为；发布新版本使用版本前提条件，避免覆盖并发修改。
- [ ] 在隔离 PostgreSQL/pgvector 验证迁移升降级：若多个 Agent 已启用，降级必须明确拒绝重建旧唯一索引，不删用户配置；回退运行模式不依赖降级。
- [ ] 通过定向测试、Ruff、mypy 和 API 契约后提交。

## Task 3：七段式提示词与输入安全

**Files:** 新建 `agents/prompts/{sections,compiler,registry}.py`、`agents/safety/input.py`；修改 Provider 请求构造与管理请求类型；测试 `src/tests/backend/agent/test_prompt_compilation.py`、`src/tests/backend/agent/test_prompt_input_safety.py`。

**Interfaces:** `compile_prompt(sections: SevenSections, platform_policy_version: str) -> PublishedPrompt`；输出只含已验证的固定平台策略和七段业务段落、hash、版本。`assess_input(segment: ContextSegment) -> SafetyDecision` 返回允许、脱敏或需人工复核及稳定原因码。

- [ ] 写失败测试：七段缺失/空白拒绝发布；已发布版本不可变；用户编辑不能开启自动发送、扩大工具或跨店；合法 SKU/政策编号不因地址规则误伤；凭证、完整地址、异常嵌套结构不得进入 Provider。
- [ ] 实现分段保存、预览与发布编译；平台固定规则不由运营人员编辑，调试/运行记录保存精确版本和 hash，不记录完整 Prompt。
- [ ] 将用户消息、RAG、工具自由文本、记忆和其他 Agent 输出标记来源；注入检测只增加拒绝/复核，不授予权限。保留现有 DLP 与业务声明门禁，按字段调整误报而非整体关闭。
- [ ] 跑上述测试、现有 Prompt/DLP 评测和静态检查后提交。

## Task 4：`@tool` 定义与原生 function calling

**Files:** 新建 `agents/tools/{catalog,definitions,execution}.py`、`agents/providers/tool_calling.py`；适配 `src/backend/app/tools/contracts.py`、`src/backend/app/agent/providers/{deepseek_provider,openai_provider,anthropic_provider}.py` 与现有 `app.agent.tool_execution`；在 `src/backend/pyproject.toml` 显式声明 `langchain-core` 并更新锁文件；测试 `src/tests/backend/agent/test_function_tool_calls.py`。

**Interfaces:** `configured_tools(agent, trusted_session) -> tuple[ToolDefinition, ...]` 返回配置的完整工具目录与当前可用性；`call_model_with_tools(messages, tools, deadline) -> ModelTurn` 返回原生 `tool_calls`；`execute_tool_call(call, snapshot) -> ToolResult` 执行前复核权限与强类型契约。可信订单/客户 ID 由服务端注入，不暴露为模型可指定参数。

- [ ] 写失败测试：中文/英文物流问题触发 `query_logistics` 原生 `tool_calls`；模型选择零个、多个、重复、无权限或未配置工具、非法 JSON/字段均有确定结果；写工具只形成待人工确认动作，不执行平台写入。
- [ ] 用 `langchain_core.tools.tool` 为现有业务工具和绑定文件检索定义带描述与 Pydantic `args_schema` 的 `@tool`；生成 Provider 原生 function Schema。所有 Agent 配置的工具均可被发现，授权状态明确标注；装饰器不替代服务端权限。
- [ ] Provider 发送 `tools` 与 `tool_choice=auto`，接收 `tool_call_id/name/arguments`，验证后执行并回传匹配的工具结果，循环直到模型产出回答或总截止时间到达；工具阶段与最终 JSON 回答阶段分离。DeepSeek 思考模式按官方协议回传必要状态；其他可配置模型在发布前验证原生 function-calling 能力。
- [ ] 服务端从授权会话解析订单与客户对象，执行层继续校验店铺、权限、超时、Schema 和审计；模型不得指定其他对象 ID。相同无效调用要收敛并记录原因，不能无限空转。平台写工具的选择只形成待审批动作。
- [ ] 在调试开关下先接入原生调用循环，真实模型误选率与旧正则漏调用样例进入版本化 eval；定向与安全测试通过后提交。

## Task 5：冻结快照、上下文预算和逐字事实

**Files:** 新建 `agents/runtime/{snapshot,context}.py`、`agents/memory/facts.py`；扩展 `agent_runs` 快照引用与配置版本字段的迁移；测试 `src/tests/backend/agent/test_context_assembly.py`、`src/tests/integration/postgres/test_agent_snapshot.py`。

**Interfaces:** `freeze_run_context(session, trigger_message_id, published_versions) -> RunSnapshot`；`build_context(snapshot, evidence, model_limits) -> ContextPackage`，其中 `literal_facts` 与 `compressible_summary` 分离并附来源/时间/token 用量。

- [ ] 写失败测试：触发后新增消息不进入当前快照；同一运行内配置、知识审批和记忆 revision 固定；撤销审批在展示前拦截；金额/币种/时间/状态/政策原句不被压缩改写。
- [ ] 从模型目录读取上下文窗口，按 `输入上限 = 窗口 - 输出保留 - 安全余量` 计数；先裁低相关证据与旧历史，再压缩摘要；必需事实超预算则澄清/人工复核，不截断原值。
- [ ] 快照只持久化最少版本引用、消息水位、授权范围、截止时间和 hash；必要的个人字段仅保留于授权业务表，运行日志不复制正文。
- [ ] 跑预算、并发、隔离和回收测试及静态检查后提交。

## Task 6：会话内分层记忆与生命周期

**Files:** 新建 `agents/memory/{models,repository,service}.py` 与 Alembic 迁移；测试 `src/tests/backend/agent/test_session_memory.py`、`src/tests/integration/postgres/test_session_memory_isolation.py`。

**Interfaces:** `load_memory(snapshot) -> SessionMemoryView`；`propose_memory_update(snapshot, source_refs, candidate) -> MemoryDecision`；`commit_memory(decision, expected_revision) -> int`。所有查询必须同时绑定 `store_id/conversation_id/customer_id`。

- [ ] 写失败测试：同一会话关闭再重开恢复有效摘要；同用户另一会话、他人会话、外店均读不到；身份变化、删除/撤权后不可读；并发写只有预期 revision 成功。
- [ ] 三层实现为运行内临时态、会话摘要、已核验关键事实；模型只能提出候选，写入模块按来源消息/工具/知识引用验证，再原子提交。旧订单/物流事实携时间并在新运行刷新或标为过期。
- [ ] 会话关闭冻结写入但不清空；重开同一会话恢复。会话/客户删除时清理派生摘要与事实；保留期限跟随会话现有数据生命周期，不建立跨会话向量记忆。
- [ ] 测试记忆污染、敏感字段、生命周期与数据库约束，通过后提交。

## Task 7：显式绑定文件 RAG 适配

**Files:** 新建 `agents/rag/retriever.py`；修改旧 `app.agent.rag/workflow/factory` 的切换点；测试 `src/tests/backend/agent/test_bound_file_rag.py`、`src/tests/integration/postgres/test_bound_file_retrieval.py`。

**Interfaces:** `retrieve_bound_files(snapshot, query, deadline) -> EvidenceBundle`；空 `file_ids` 返回无知识证据，不调用 FAQ 搜索；非空时复用 `app.knowledge_base.document_search` 的店铺、有效版本、审批门禁和现有 12 秒总时限。

- [ ] 写失败测试：零绑定不检索 FAQ；同店已审批绑定文件可引用；跨店/归档/撤销审批/旧版本/超时无证据；无证据问题以工具事实回答或澄清/人工复核。
- [ ] 将文件检索适配到新运行接口，保留 MinerU、分块、BGE-M3 与 pgvector 入库现状；禁止 Agent 直接检索全部店铺文件。
- [ ] 新执行器的零绑定路径明确不调用旧 FAQ；旧执行器暂时保持原状，待 Task 8、9 的新正式链路验收后由 Task 10 移除。保留 `app.knowledge_base` 的 FAQ 管理与数据。
- [ ] 跑 Agent、知识库和真实 pgvector 隔离测试，确认新路径无 FAQ 调用、无知识时安全退化，再提交。

## Task 8：多 Agent 语义路由、状态与汇总

**Files:** 新建 `agents/orchestration/{registry,router,coordinator,aggregator}.py`、`agents/runtime/{state,worker}.py`、`agents/safety/output.py`；扩展 `agent_runs` 的主子运行关联、阶段与低敏事件；修改 `src/backend/app/chat/{service,worker}.py`；测试 `src/tests/backend/agent/test_multi_agent_route.py`、`test_multi_agent_aggregate.py`、`src/tests/integration/postgres/test_multi_agent_runs.py`。

**Interfaces:** `route(question, all_enabled_agents, snapshot) -> RoutePlan`；`run_selected(plan, snapshot) -> list[SpecialistResult]`；`aggregate(question, results) -> ReviewedSuggestion`。路由通过结构化 function call 返回任意数量的同店启用 Agent ID 与子问题；汇总只见经校验的草稿、事实引用和不确定项。

- [ ] 写失败测试：单 Agent、双 Agent 混合问题、多于三个 Agent、零匹配、同名职责、外店/停用 ID、重复 ID、候选目录分批、子 Agent 失败、冲突事实、取消和总超时均形成稳定结果；不得产生孤儿任务或平台发送。
- [ ] 协调器在一次冻结快照和截止时间下并发运行子 Agent；Agent 私有临时记忆不共享，公共已核验事实按权限裁剪。多个结果汇总为一段，冲突或缺证据进入人工复核。
- [ ] 在展示前验证汇总内容的引用、业务声明和敏感字段；子 Agent 或汇总模型的输出均不能替代服务端权限及安全判定。
- [ ] 保持现有 `AgentRun.status` 对外值兼容；新增阶段和主子运行关系，状态转换采用条件更新、幂等键与超时收敛。模型路由和工具选择的解释只存稳定枚举/低敏摘要。
- [ ] 从预览调试开关启用，完成确定性、隔离数据库与真实模型 eval，再接入正式人工建议开关；性能未达门禁不扩大正式范围。
- [ ] 通过旧工作台、消息任务、审计与发送回归后提交。

## Task 9：管理页、预览调试与公开契约

**Files:** 修改 `src/frontend/app/agents/page.tsx`、`agent-prototype.css`、`src/frontend/lib/api*`、`agents/management/router.py`；测试 `src/tests/frontend/contract/agent-config.test.mjs` 与 `src/tests/frontend/browser/agent-prototype.test.mjs`。

**Interfaces:** 管理页保持现有五个页签和 v3 原型整体交互；模型、七段式 Prompt、工具和文件绑定真实保存；预览显示路由的 Agent、各自工具/RAG 状态、引用、汇总、超时和追踪号。

- [ ] 写前端契约与浏览器失败测试：多 Agent 启用、七段保存/发布/刷新、跨店切换、禁用工具、文件撤销、同会话重开记忆、混合问题调试、迟到响应不串店。
- [ ] 扩展现有 API 与 UI，区分草稿和已发布版本；调试仅使用当前授权店铺/会话，停用 Agent 的单体调试不把它加入正式路由。
- [ ] 运行 `npm run test`、`npm run test:ui`、`npm run lint`、`npm run typecheck`、`npm run build`，更新 `docs/architecture/API.md` 与 `docs/product/PRODUCT.md` 后提交。

## Task 10：评测、切流、旧码清理与恢复

**Files:** `src/tests/ai/datasets/` 的版本化路由/工具/注入/记忆样例，`src/tests/ai/results/` 的低敏结果；`src/backend/app/shared/config/settings.py` 与 `src/config/.env.example` 的切流配置；`docs/architecture/{AI,SYSTEM}.md`、`docs/operations/DEPLOYMENT.md`、`docs/tasks/TASKS.md` 及 IR/TR/RR。

**Interfaces:** `AGENT_V2_DEBUG_ENABLED` 和 `AGENT_V2_FORMAL_ENABLED` 已在 Task 1 默认关闭，两者独立控制预览与正式建议。清理旧 FAQ 前可回切旧执行器；清理后关闭新执行器时走无知识的安全澄清/转人工路径，故障版本回滚依赖保留的上一发布产物。任何回退都不回滚或丢弃新配置/记忆数据。

- [ ] 对最终源码在本地跑完整后端与隔离 PostgreSQL/pgvector、前端、类型/格式/构建、权限隔离、Prompt 注入、记忆污染和版本化 AI eval；真实模型/只读平台现场验证待用户批准部署后另行执行，不发送消息。
- [ ] 比较单/多 Agent 的路由正确性、function call 参数与结果关联、工具调用、引用、总耗时与成本；覆盖超过 3 个 Agent、超过 2 次工具调用及超容量分批。现有 50 客户端安全首输出及总耗时 P99 严格小于 5 秒的完整 MVP 门禁必须以现场实测判断；失败则保持人工建议与旧模式或关闭新正式开关，不虚报通过。
- [ ] 本地分别验证影子路由、调试执行、正式人工建议的开关与失败关闭；部署获批后再分店铺灰度，并核对现场错误率、超时、店铺隔离、零平台发送和恢复动作。
- [ ] 在新正式链路验收、全仓调用方迁移且适用门禁通过后，独立清理分支删除旧 `app.agent`/`app.agent_management` 中已无用的 FAQ 专用路径、正则路由和兼容导入；保留知识库 FAQ 数据与工作台共享工具。删除形成精确 diff、上一发布产物回滚方法和清理批次。
- [ ] 生成最终 IR/TR/RR、更新当前文档与任务状态；按项目 PR/CI 门禁合并。staging 部署和 production 放行仍为各自独立动作。

## 执行和验收顺序

Tasks 1→2→3→4→5→6→7→8→9→10 中，3/4 的基础契约可在 2 后独立开发，但与 7/8 的集成必须串行。本次在一个 Agent 重写功能分支上按阶段提交；实际旧文件清理按项目治理另建可审阅清理批次。数据库采取先扩展、回填、切读、最后删旧字段的顺序。**任何一段出现安全或旧功能回归，停止切流，保留旧服务并修复同一阶段；不得通过删测试或放宽阈值制造通过。**

本计划已按用户确认开始本地实施；先锁定实际 `origin/main`、迁移 head、现有测试基线与任务 ID，再按此顺序执行。Agent 和工具不设固定数量上限；容量、耗时或权限不足时需给出可观察原因，不伪装成完整执行。完成全部本地验证后等待用户批准部署。

## 本地实施核对（2026-10-28）

Tasks 1–9 的本地实现已落入候选，Task 10 正在最终验收。实际编排是 asyncio 协调器和显式状态机，langchain-core 提供 @tool；无 LangGraph 运行或 checkpoint。旧 FAQ 工作流、正则路由、旧调试和专属 Schema/Prompt 及无调用的 LangGraph 依赖已移除，共享知识库管理保留。两轴审查发现的最终依据复核、汇总期间撤权、历史/服务范围路由和草稿并发覆盖已补修，另补工具记忆权限复核。全部本地验证与记录定稿后按项目合并门禁处理；真实模型语义准确率、TikTok 只读现场和性能验收仍在用户批准部署后的范围，本次不部署。
