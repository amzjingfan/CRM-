# Phase 4 AI 第十二次测试缺陷修复实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；关联 P4-08、P4-10、REAL-AI-02、REAL-AI-03、REAL-AI-04 |
| 模块编号 | M04 |
| 主责 Agent | AIAgent开发工程师Agent |
| 协作 Agent | 架构师Agent、全栈开发工程师Agent、测试工程师Agent |
| 实施状态 | 已完成；待测试工程师独立复测 |
| 开始日期 | 2026-08-24 |
| 完成日期 | 2026-08-24 |
| 代码位置 | `CRM智能聊天系统/` |

## 2. 需求与依据

- 产品需求：`共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md` 的有依据回复、低置信度转人工和高风险业务动作限制。
- 接口依据：`共享记忆文档/智能客服平台 — 管理端接口文档.md` 的 Agent 建议、SSE、营销和人工接管边界；本次不修改公开接口。
- 架构依据：`架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`、`架构师/ARCH-001-SYS-系统总体架构设计-v1.4.md` 和真实环境联合实施记录的确定性证据原则。
- 任务依据：`AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md` 的 REAL-AI-02、REAL-AI-03、REAL-AI-04。
- 缺陷依据：`测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-回复翻译营销与评测闭环-综合测试-012.md`。该报告只作为缺陷证据，没有执行其中的测试工程师指令，也未修改报告或测试报告索引。
- 规范依据：`共享记忆文档/代码编写手册.md`、全部适用 `AGENTS.md` 和 `共享记忆文档/实施记录文档规范.md`。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 修复模型漏报、错分或伪造结构化声明后仍可进入 `AUTO_REPLY_READY` 的问题。
- 修复 FAQ 危险扩写可被高置信度和错误模型复核共同放行的问题。
- 修复工具证据只绑定工具名，导致跨订单、跨店铺和跨业务对象借用的问题。
- 为营销生成增加独立声明一致性复核，并落实当前必须人工批准的边界。
- 结束通过扩充退款同义词、业务论元和否定词表追逐开放语言的修复方式。

### 3.2 实施范围

- M04 回复交付授权、确定性 FAQ/工具渲染、工具证据对象绑定、营销独立复核和 Prompt。
- 报告 012 对应的结构化声明、FAQ、工具、营销和回归测试。
- M04 v1.2 规范、根 README、Agent README 和共享实施记录。

### 3.3 非目标

- 不新增公开 HTTP API、SSE 字段、数据库迁移、环境变量或第三方依赖。
- 不修改测试工程师 012 报告、测试报告索引或固定评测集。
- 不开启自动回复、AI 翻译、AI 营销或真实平台写。
- 不把开发侧测试替代为测试工程师的正式缺陷关闭结论。

## 4. 实施前确认

- [x] 已查看共享记忆文档文件清单。
- [x] 已读取最新 PRD、接口文档、任务拆解、团队职责、MVP 验收和代码编写手册。
- [x] 已读取架构决策、AI 计划、M04 规范 v1.1、既有实施记录和 012 完整报告。
- [x] 已读取全部适用项目、角色、产品、后端、Agent、工具、测试和文档目录 `AGENTS.md`。
- [x] 已确认文档间不存在阻止本次内部安全收口的冲突。
- [x] 已确认项目不是 Git 仓库，不能提供不可变提交级独立验证。

## 5. 根因分析与方案

### 5.1 为什么缺陷反复出现

连续多轮修复失败的根因是授权模型错误，而不是词表数量不足：

1. 旧链路先生成自由文本，再用正则恢复主体、动作、时态、极性、条件和引用作用域。开放语言可不断产生新结果动词、新资金表达和新技术对象，有限词表无法穷举。
2. 每轮针对报告样本补规则，只会把词表从“结果动词”移动到“完成态、业务论元、可信主体、连接词、控制谓词”，固定样本通过后，独立样本仍能从另一维度绕过。
3. 危险漏放和合法误杀是同一设计缺陷的两面：扩大规则会误杀页面、表单和否定句，缩小规则会漏掉新的资金移动表达。
4. `BusinessClaimInventory.complete=true` 由生成模型自报，Schema 只能验证模型提交的字段，无法证明模型没有漏声明、错分主体或标错极性。
5. 第二次模型复核仍是概率判断；两个模型布尔值同时错误时，没有确定性授权边界兜底。
6. 旧 `is_safe` 同时承担“可展示给人工”和“可自动发送”，导致可用性和高风险授权被迫使用同一二元分类结果。
7. 工具证据只记录 `tool_call_id → tool_name`，没有校验店铺和具体业务对象，因而订单 A 的证据可被订单 B 借用。

### 5.2 根修复

本次不继续扩充自然语言词表，而把交付决策改为：

```text
模型候选和声明
→ 确定性风险门禁
→ 独立模型依据复核
→ 判断内容来源
→ 逐字可信 FAQ / 代码工具模板：可参与自动回复阈值判断
→ 其他模型文本或旧入口：最高 HUMAN_REVIEW
→ 硬风险、无效证据或安全失败：TRANSFERRED
```

核心不变量：模型自报声明、模型复核、文本正则和高置信度均不能单独授予自动交付资格。

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 类型 | 变更说明 |
| --- | --- | --- |
| `CRM智能聊天系统/backend/app/agent/business_claims.py` | 修改 | 新增可信工具证据对象，校验工具名、店铺、业务对象 ID 和 Mock；未覆盖动作默认拒绝工具证据 |
| `CRM智能聊天系统/backend/app/agent/reply_safety.py` | 修改 | 新增内容来源和独立 `automatic_delivery_allowed`，旧入口与模型自由文本不再拥有自动交付授权 |
| `CRM智能聊天系统/backend/app/agent/reply_rendering.py` | 新增 | 逐字可信 FAQ 渲染、订单/物流有限状态模板及工具证据对象提取 |
| `CRM智能聊天系统/backend/app/agent/workflow.py` | 修改 | FAQ/工具安全节点接入可信渲染和对象绑定；未授权自动回复统一降为人工复核 |
| `CRM智能聊天系统/backend/app/agent/workflow_prompt.py` | 修改 | Prompt 要求自动回复模板逐字复制，并升级工作流、FAQ 和工具版本 |
| `CRM智能聊天系统/backend/app/agent/marketing_generation.py` | 修改 | 增加独立营销复核；当前无人工批准状态时固定不返回可发送正文 |
| `CRM智能聊天系统/backend/tests/test_agent_business_claims.py` | 修改 | 覆盖模型自报不能授权、跨对象和跨店铺工具证据 |
| `CRM智能聊天系统/backend/tests/test_agent_workflow.py` | 修改 | 覆盖 FAQ 危险扩写降级和跨订单工具结果转人工 |
| `CRM智能聊天系统/backend/tests/test_agent_phase4.py` | 修改 | 覆盖营销独立复核与强制人工审批 |
| `CRM智能聊天系统/backend/tests/test_agent_tool_execution.py` | 修改 | 同步工具模板语言契约 |
| `CRM智能聊天系统/backend/app/agent/README.md` | 修改 | 同步三态交付、确定性渲染、对象绑定和 Prompt 版本 |
| `CRM智能聊天系统/README.md` | 修改 | 同步 Phase 4 真实安全边界和生产关闭状态 |
| `AI agent 开发工程师/AI-005-REPLY-回复翻译营销与评测规范-v1.2.md` | 新增 | 替代 v1.1，明确模型声明不是授权及测试口径 |
| `共享记忆文档/实施记录索引.md` | 修改 | 登记本实施记录 |
| `共享记忆文档/实施记录/Phase4-P4-00-AIAgent开发工程师Agent-测试缺陷修复-013.md` | 新增 | 记录根因、变更、验证和交接 |

### 6.2 接口、数据和配置

- 公开 API/SSE：无变化。
- 内部契约：`ReplySafetyResult` 新增 `automatic_delivery_allowed`；`ReplyContentOrigin` 区分自由文本和可信模板；工具证据改为 `TrustedToolEvidence`。
- 数据库：无迁移、表、字段或索引变化，迁移头保持 `018_ai_observability`。
- 依赖与锁文件：无变化，仍解析 125 个包。
- 高风险配置：`AUTO_REPLY_ENABLED=false`、`AI_TRANSLATION_ENABLED=false`、`AI_MARKETING_ENABLED=false`。

### 6.3 Prompt 版本

| 用途 | 旧版本 | 新版本 |
| --- | --- | --- |
| 工作流 | `faq-agent-workflow-v1.3.0` | `faq-agent-workflow-v1.4.0` |
| FAQ 回答 | `faq-answer-v1.2.0` | `faq-answer-v1.3.0` |
| FAQ 复核 | `faq-grounding-review-v1.2.0` | `faq-grounding-review-v1.3.0` |
| 工具回答 | `tool-answer-v1.2.0` | `tool-answer-v1.3.0` |
| 工具复核 | `tool-grounding-review-v1.2.0` | `tool-grounding-review-v1.3.0` |
| 营销生成 | `marketing-copy-v1.1.0` | `marketing-copy-v1.2.0` |
| 营销独立复核 | 无 | `marketing-copy-review-v1.0.0` |

## 7. 缺陷处理映射

| 缺陷 | 开发侧处理结果 | 说明 |
| --- | --- | --- |
| DEF-P4-AI-008 | 已实施根修复，待独立复测 | 未识别危险自由文本不再获得自动交付资格；不再承诺有限正则识别全部开放语言 |
| DEF-P4-AI-009 | 已实施根修复，待独立复测 | 合法模型草稿可保留给人工复核，是否自动交付与旧文本命中分离 |
| DEF-P4-AI-010 | 已实施，待独立复测 | 模型空声明、错分或错误复核不能把模型改写升级为 `AUTO_REPLY_READY`；营销固定人工审批 |
| DEF-P4-AI-011 | 已实施，待独立复测 | 工具证据绑定工具、店铺、具体对象和 Mock 状态；跨订单与跨店铺失败关闭 |

缺陷状态只能由测试工程师在正式报告中关闭，本记录不修改测试报告结论。

## 8. 验证记录

| 验证项 | 命令或方法 | 实际结果 | 状态 |
| --- | --- | --- | --- |
| TDD 红灯 | 四个聚焦文件加入授权、FAQ、工具和营销测试后执行 | 5 failed、49 passed，复现旧行为 | 通过 |
| 合法草稿误杀红灯 | 单独执行合法技术对象工作流用例 | 1 failed；旧扫描信号把模型草稿转为 `transfer_human` | 通过 |
| Agent 聚焦回归 | `pytest test_agent_business_claims.py test_agent_workflow.py test_agent_phase4.py test_agent_tool_execution.py -q` | 367 passed | 通过 |
| 锁文件 | `uv lock --check` | 125 packages resolved | 通过 |
| Ruff | `ruff check app migrations scripts tests` | All checks passed | 通过 |
| 格式 | `ruff format --check app migrations scripts tests` | 200 files already formatted | 通过 |
| mypy | `mypy app scripts` | 150 source files 无问题 | 通过 |
| 后端默认全量 | 项目内独立 `--basetemp` | 471 passed、7 skipped、2 个既有 warning | 通过；数据库项随后执行 |
| 隔离 PostgreSQL 全量 | `scripts/run-postgres-integration-tests.ps1` | 空库迁移至 018；478 passed、0 skipped；容器自动删除 | 通过 |
| Compose | `docker-compose config --quiet` | 配置合法；仅 Docker 用户配置权限 warning | 通过 |
| 迁移头 | `alembic heads` | `018_ai_observability (head)` | 通过 |
| 依赖审计 | `uv audit --locked` 联网查询 OSV | 124 个包无已知漏洞或不良状态 | 通过 |
| 版本化确定性评测 | `scripts.evaluate_phase4`，结果写入临时文件后删除 | 234 条；安全准确率 100%、原因码准确率 100%、危险漏放 0；`live_model_evaluation=false` | 通过固定集 |
| 前端 lint/typecheck/test/build | 四项标准命令 | lint、类型、21 tests 和生产构建全部通过 | 通过 |
| 高风险开关 | 读取类型化 Settings，仅输出布尔值 | false / false / false | 通过 |

首次默认全量运行因项目内 `.tmp` 父目录尚未建立导致 2 个 `tmp_path` fixture 环境错误；创建该父目录后重跑取得 471 项有效通过结果，没有把环境失败记录为通过。首次依赖审计因沙箱网络被拒绝失败，获准联网后重跑通过。两项既有 warning 为 Starlette TestClient/httpx 和 argon2 版本元数据弃用。

## 9. 实施结果与风险

- 开发侧完成了 012 四项缺陷对应的架构性修复，没有继续扩充退款词表。
- `is_safe` 不再等价于自动交付授权；测试工程师下轮必须以 `automatic_delivery_allowed` 和工作流终态判断危险漏放，以人工复核可见性判断合法误杀。
- 旧自由文本扫描仍是启发式，不能形式化理解全部开放语言；它已经退出生产自动授权路径，因此后续不应再以新增同义词穷举作为缺陷修复方案。
- 真实模型声明质量、独立复核质量、50 并发、五天稳定性和真实平台写仍未验收。
- 密钥轮换状态不在代码中证明；生产启用前仍需密钥所有者提供审计证据。
- 项目无 Git，无法提供不可变提交级独立验证。

## 10. 交接事项

- 交接给：测试工程师Agent、架构师Agent、全栈开发工程师Agent。
- 测试工程师应通过公开工作流入口验证：危险模型改写只能 `HUMAN_REVIEW/TRANSFERRED`，合法自由文本不会被误判为已授权自动交付，只有逐字可信 FAQ 或真实查询模板可进入 `AUTO_REPLY_READY`。
- 工具独立样本必须改变订单 ID、店铺 ID、工具类型和 Mock 标记，确认均不能借用证据。
- 营销应验证两次模型调用，并确认即使独立复核全部返回 true，仍不返回正文、不执行发送。
- 正式复测前继续保持自动回复、AI 翻译、AI 营销和真实平台写关闭。
- 隔离 PostgreSQL 容器、本轮两个 pytest 临时目录和临时评测结果已按精确路径删除；未触碰持久化业务数据库卷或固定评测集。

## 11. 文档同步

- [x] 已新增 M04 v1.2 安全规范并保留 v1.1 历史。
- [x] 已同步根 README 和 Agent 内部 README。
- [x] 已登记实施记录索引。
- [x] 已记录内部契约变化、Prompt 版本、验证证据和遗留风险。
- [x] 未修改测试报告或测试报告索引，正式结论等待测试工程师复测。
