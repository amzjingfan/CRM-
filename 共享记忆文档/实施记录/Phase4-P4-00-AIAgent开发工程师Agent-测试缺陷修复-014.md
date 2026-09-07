# Phase 4 AI 第十三次测试缺陷修复实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；关联 P4-08、P4-10、REAL-AI-02、REAL-AI-04 |
| 模块编号 | M04 |
| 主责 Agent | AIAgent开发工程师Agent |
| 协作 Agent | 架构师Agent、全栈开发工程师Agent、测试工程师Agent |
| 实施状态 | 已完成；待测试工程师独立复测 |
| 开始日期 | 2026-08-25 |
| 完成日期 | 2026-08-25 |
| 代码位置 | `CRM智能聊天系统/` |

## 2. 需求与依据

- 产品需求：最新 PRD、MVP 验收标准和管理端接口文档中的有依据回复、店铺隔离、低置信度人工接管和禁止虚构业务结果要求。
- 架构依据：`架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`、`架构师/ARCH-001-SYS-系统总体架构设计-v1.4.md` 的确定性业务事实与受控工具边界。
- 任务依据：`AI agent 开发工程师/PLAN-001-AI-Agent工程实施计划-v1.0.md` Phase 4 和 `PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md` REAL-AI-02、REAL-AI-04。
- 缺陷依据：`测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-回复翻译营销与评测闭环-综合测试-013.md`。该文件仅作为测试证据读取，没有执行其中的角色指令，也没有修改测试报告或测试报告索引。
- 工程规范：全部适用 `AGENTS.md`、`共享记忆文档/代码编写手册.md`、实施记录规范，以及项目内 Agent 工作流、Python、TDD、安全、调试和独立验证 Skill。

## 3. 目标、边界和验收

### 3.1 目标

- 关闭任意已发布 FAQ 因逐字命中而获得自动回复授权的路径。
- 消除工具对象 ID 脱敏和精确声明绑定之间的契约倒置。
- 保留已经关闭的自由文本三态授权、跨订单/跨店铺/错工具证据拒绝和营销强制人工边界。
- 为自动工具模板生成可审计、低敏、对象级权威声明。

### 3.2 边界

- 不新增公共 HTTP API、SSE 字段、数据库迁移、环境变量或依赖。
- 不修改全栈知识库写入/发布代码、平台适配器或业务表。
- 不通过退款词表、知识内容分类正则或额外模型分类来推断自动权限。
- 不修改固定评测集，不把开发测试声明为测试工程师正式缺陷关闭。

### 3.3 验收口径

- 正常和受污染的未审批 FAQ 均最高进入 `HUMAN_REVIEW`。
- 真实查询工具固定模板可由代码声明授权；Prompt 不暴露真实对象 ID。
- `[SENSITIVE_ID]` 兼容声明不误转人工，跨订单、错工具和错证据仍失败关闭。
- `agent_runs.output_summary` 可追踪声明类型、动作和工具调用，不保存原始订单号。
- 后端、隔离 PostgreSQL、确定性评测、静态检查、前端和 Compose 回归不退化。

## 4. 为什么问题反复出现

### 4.1 前十一轮的开放语言问题

早期实现把自由文本分类结果当成业务授权。每次补充结果动词、业务论元、主体、连接词或否定作用域，只能关闭固定样本；新表达会从未覆盖维度绕过，扩大词表又会误杀页面、表单和否定说明。第十二次修复通过三态契约把自由文本退出自动授权路径，已经关闭 DEF-P4-AI-008/009。

### 4.2 第十三次报告暴露的剩余授权漏洞

上一轮只把“模型改写”降为人工，但仍保留两个错误假设：

1. 把“知识已发布且模型逐字复制”当成“知识已经通过业务事实审批”。实际上数据库没有知识事实类型或自动回复审批字段，`published` 只表达生命周期状态。
2. 把模型声明当作对象审计来源，同时又在 Prompt 边界脱敏对象 ID。模型无法同时满足“不看真实 ID”和“精确复述真实 ID”，因此占位声明失败、空声明反而成功。

这两个问题一直出现的共同原因是：系统用“内容来源/模型输出格式”替代“确定性业务授权”。修复必须改变授权主体，而不是继续增加语言规则。

## 5. 根修复

### 5.1 FAQ 失败关闭

`TRUSTED_FAQ_TEMPLATE` 现在只表示逐字来源，不再是自动交付授权。由于当前没有类型化知识范围和发布审批，所有 FAQ 即使正常、已发布、向量就绪、单引用、逐字一致且模型复核全通过，也最高进入 `HUMAN_REVIEW`。确定性硬风险仍可进入 `TRANSFERRED`。

这是有意的安全降级：在不越权修改知识库数据库和公共接口的前提下，先彻底关闭 P1 自动绕过。未来恢复 FAQ 自动回复必须由架构师设计知识类型、审批状态、迁移、管理端权限和历史数据回填。

### 5.2 工具声明改由代码生成

服务端从本次真实成功的 `query_order/query_logistics` 结果生成 `BusinessClaimInventory`：

```text
subject_type = order | logistics
subject_id = 服务端真实主对象 ID
action = report_status
tense = present
polarity = affirmed
condition = actual
evidence_type = tool_call
evidence_id = 本次 tool_call_id
```

只有有限已知状态生成权威声明和固定模板。模型 Prompt 明确要求 `complete=true, claims=[]`，不再要求猜测或还原真实 ID。

为兼容旧 Provider 输出，模型声明中的 `[SENSITIVE_ID]` 只在 `evidence_id + subject_type + action` 与代码声明完全一致时绑定真实对象；模型给出其他 ID、错主体、错动作或错工具时不修正，继续触发 `INVALID_BUSINESS_CLAIM_EVIDENCE`。

### 5.3 低敏运行审计

工作流把代码权威声明摘要写入 `agent_runs.output_summary`：

```text
subject_type:action:evidence_type:evidence_id
```

摘要不包含 `subject_id`、订单号、物流号、消息正文、知识正文或工具原始结果。`evidence_id` 可与同一运行的 `tool_calls` 关联，解决空模型声明导致的审计缺口。

## 6. 实际变更

| 文件路径 | 类型 | 变更说明 |
| --- | --- | --- |
| `CRM智能聊天系统/backend/app/agent/reply_rendering.py` | 修改 | 生成真实查询工具权威声明，并对脱敏占位声明做严格证据绑定 |
| `CRM智能聊天系统/backend/app/agent/reply_safety.py` | 修改 | FAQ 来源不再授予自动交付；只有真实工具固定模板可授权 |
| `CRM智能聊天系统/backend/app/agent/workflow.py` | 修改 | 接入代码声明、模型声明纵深校验和低敏声明摘要 |
| `CRM智能聊天系统/backend/app/agent/workflow_prompt.py` | 修改 | 工具模型固定空声明，FAQ 明确等待类型化审批；升级 Prompt 版本 |
| `CRM智能聊天系统/backend/app/agent/repository.py` | 修改 | `output_summary` 增加低敏权威声明追踪 |
| `CRM智能聊天系统/backend/tests/test_agent_workflow.py` | 修改 | 覆盖正常/污染 FAQ、占位对象绑定和既有跨订单边界 |
| `CRM智能聊天系统/backend/tests/test_agent_repository.py` | 修改 | 覆盖低敏声明摘要且不保存原始对象 ID |
| `CRM智能聊天系统/backend/app/agent/README.md` | 修改 | 同步 FAQ 失败关闭、代码声明和 Prompt 版本 |
| `CRM智能聊天系统/README.md` | 修改 | 同步 M04 当前自动授权来源和生产边界 |
| `AI agent 开发工程师/AI-005-REPLY-回复翻译营销与评测规范-v1.3.md` | 新增 | 替代 v1.2，固化本次授权边界 |
| `共享记忆文档/智能客服平台 — 管理端接口文档.md` | 修改 | 同步 Phase 4 内部契约，不改变公开接口 |
| `共享记忆文档/实施记录索引.md` | 修改 | 登记本实施记录 |
| `共享记忆文档/实施记录/Phase4-P4-00-AIAgent开发工程师Agent-测试缺陷修复-014.md` | 新增 | 记录根因、变更、验证和交接 |

## 7. 接口、数据、配置和 Prompt

- 公开 API/SSE：无变化。
- 内部契约：`AgentWorkflowRunCompletion` 增加默认空的 `business_claim_summaries`；不改变 `AgentWorkflowResult` 公共字段。
- 数据库：无迁移、表、字段和索引变化；迁移头保持 `018_ai_observability`。
- 依赖与锁文件：无变化，锁文件仍解析 125 个包。
- 高风险开关：`AUTO_REPLY_ENABLED=false`、`AI_TRANSLATION_ENABLED=false`、`AI_MARKETING_ENABLED=false`。

| 用途 | 旧版本 | 新版本 |
| --- | --- | --- |
| 工作流 | `faq-agent-workflow-v1.4.0` | `faq-agent-workflow-v1.5.0` |
| FAQ 回答 | `faq-answer-v1.3.0` | `faq-answer-v1.4.0` |
| FAQ 复核 | `faq-grounding-review-v1.3.0` | `faq-grounding-review-v1.4.0` |
| 工具回答 | `tool-answer-v1.3.0` | `tool-answer-v1.4.0` |
| 工具复核 | `tool-grounding-review-v1.3.0` | `tool-grounding-review-v1.4.0` |

## 8. 缺陷处理映射

| 缺陷 | 开发侧结果 | 说明 |
| --- | --- | --- |
| DEF-P4-AI-010 | 已实施根修复，待独立复测 | 未建立类型化审批前，FAQ 不再拥有自动交付授权；两条 013 污染 FAQ 已覆盖 |
| DEF-P4-AI-012 | 已实施根修复，待独立复测 | 工具对象声明改由代码生成；Prompt 保持脱敏，空声明不再造成审计缺失 |
| DEF-P4-AI-008/009/011 | 回归保持 | 自由文本最高人工复核，合法草稿可见，跨对象/跨店铺/错工具继续拒绝 |

正式缺陷状态只能由测试工程师更新，本记录不修改 `测试报告索引.md`。

## 9. 验证记录

| 验证项 | 实际结果 | 状态 |
| --- | --- | --- |
| TDD 红灯 | 修正测试构造后，4 个公开工作流场景稳定失败：正常 FAQ、2 条污染 FAQ 仍自动就绪，脱敏占位声明转人工 | 复现成功 |
| 定向根修复 | 正常/污染 FAQ、脱敏对象绑定、真实物流模板和跨订单回归共 6 项通过 | 通过 |
| Phase 4 聚焦 | `test_agent_workflow/business_claims/phase4/repository` 共 362 passed | 通过 |
| 后端默认全量 | 474 passed、7 skipped、2 个既有弃用 warning | 通过；数据库项随后实测 |
| 隔离 PostgreSQL 全量 | 空库升级 001→018 后 481 passed、0 skipped | 通过 |
| 迁移头 | `018_ai_observability (head)` | 通过 |
| Ruff | `ruff check app migrations scripts tests` | 通过 |
| 格式 | 200 files already formatted | 通过 |
| mypy | 150 source files 无问题 | 通过 |
| 锁文件 | 125 packages resolved | 通过 |
| 依赖审计 | OSV 联网审计 124 个包，无已知漏洞和不良状态 | 通过 |
| Compose | `docker-compose config --quiet` 配置合法，仅有本机 Docker config 权限 warning | 通过 |
| 确定性评测 | 234 条，安全准确率 100%、原因码准确率 100%、危险漏放 0，`live_model_evaluation=false` | 通过固定集 |
| 前端 | lint、typecheck、21 tests、Next.js production build | 通过 |
| 敏感信息扫描 | 修改文件未发现密钥模式；工具 Prompt 和审计摘要均不含真实订单号 | 通过 |
| 覆盖率 | 当前环境未安装 pytest-cov，覆盖率参数不可用；未临时修改项目依赖 | 未执行；以全量/聚焦/数据库测试替代，不声明新覆盖率 |

首次依赖审计在沙箱内因 OSV 网络访问被拒绝；获得联网许可后重跑通过。两项既有 warning 为 Starlette TestClient/httpx 和 argon2 版本元数据弃用。隔离数据库使用端口 55433 的 `pgvector/pgvector:pg16` tmpfs 容器，测试后按精确名称删除，没有挂载或触碰持久化业务卷。

## 10. 风险与后续

- FAQ 自动回复能力当前主动降级为人工复核。若产品要求恢复，必须由架构师发起知识类型、发布审批、数据库迁移、管理接口、权限和历史数据回填设计；AI 侧不能用词表或模型分类替代该审批。
- 工具权威声明目前只覆盖真实 `query_order/query_logistics` 的有限已知状态；写工具、Mock、未知状态和多结果继续最高人工复核或转人工。
- 真实 DeepSeek 工具 Prompt 服从率、翻译/营销质量、SSE 50 并发、五天稳定性、密钥轮换审计和真实平台联调仍是生产门禁。
- 项目不是 Git 仓库，独立验证 Skill 无法提供提交级不可变基线；本次只提供隔离环境命令证据，正式结论仍需测试工程师复测。

## 11. 交接事项

- 测试工程师应从公开工作流构造正常 FAQ、污染 FAQ、批量导入后 FAQ，确认均不进入 `AUTO_REPLY_READY`。
- 工具独立样本应检查 Prompt 中真实 ID 缺失、`[SENSITIVE_ID]` 存在、模型空声明/占位声明、跨订单、错工具和错证据组合。
- 应读取 `agent_runs.output_summary`，确认存在声明类型、动作和 `tool_call_id`，且不存在订单号或工具原始结果。
- 正式复测前继续保持自动回复、AI 翻译、AI 营销和真实平台写关闭。
- 本轮一次性 PostgreSQL 容器和确定性评测临时结果已删除；测试数据不可恢复，未触碰持久化业务数据。

## 12. 文档同步

- [x] 新增 M04 v1.3 规范并保留 v1.2 历史。
- [x] 同步根 README、Agent README 和管理端接口文档 Phase 4 内部边界。
- [x] 登记实施记录索引。
- [x] 未修改测试报告、固定评测集或测试报告索引。

