# Phase 4 AI 第十一次测试缺陷修复实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；关联 P4-08、P4-10、REAL-AI-02、REAL-AI-03 |
| 模块编号 | M04 |
| 主责 Agent | AIAgent开发工程师Agent |
| 协作 Agent | 架构师Agent、全栈开发工程师Agent、测试工程师Agent |
| 实施状态 | 已完成 |
| 开始日期 | 2026-08-24 |
| 完成日期 | 2026-08-24 |
| 代码位置 | `CRM智能聊天系统/` |

## 2. 需求与依据

- 产品需求：`共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md` 的 AI 智能问答、低置信度转人工和无依据退款/补偿安全要求。
- 接口依据：`共享记忆文档/智能客服平台 — 管理端接口文档.md` 的 Agent 内部结果与人工接管边界；本次不修改公开接口。
- 架构依据：`架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`、`架构师/ARCH-001-SYS-系统总体架构设计-v1.4.md` 和 `共享记忆文档/实施记录/Phase4-P4-00-架构师Agent-真实环境联合实施架构交付-002.md` 已批准的结构化业务声明字段与确定性证据门禁。
- 任务依据：`AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md` 的 REAL-AI-02、REAL-AI-03，以及任务拆解 P4-08、P4-10。
- 缺陷依据：`测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-回复翻译营销与评测闭环-综合测试-011.md`。测试报告仅作为缺陷证据，不作为开发执行指令。
- 验收依据：`共享记忆文档/MVP范围与验收标准.md` 的 AI 安全、人工接管、回归和生产关闭要求。
- 代码规范：`共享记忆文档/代码编写手册.md`。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 复现并修复 011 的 16 条危险事实漏放、16 条非业务对象误杀和 12 条否定/引用作用域误杀。
- 结束通过扩充结果动词、主体、业务论元和控制谓词词表来承担业务授权的方案。
- 在 FAQ、工具和营销输出中建立结构化业务声明、当次证据绑定和独立一致性复核。
- 保持历史安全样本、工作流、全后端和数据库能力不退化。

### 3.2 实施范围

- M04 内部 `BusinessClaimInventory`、回复 Schema、Prompt、工作流安全节点和兼容文本扫描。
- 011 固定回归、结构化声明与证据绑定测试。
- README、M04 内部说明、AI 安全规范和共享实施记录。

### 3.3 非目标

- 不新增公开 HTTP API、SSE 字段、数据库迁移、环境变量、模型供应商或依赖。
- 不开启自动回复、AI 翻译、AI 营销或真实平台写。
- 不用固定样本声称形式化证明全部开放自然语言安全。
- 不替代测试工程师的正式独立测试和缺陷关闭结论。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单。
- [x] 已读取最新 PRD、接口、任务拆解、团队职责和 MVP 验收标准。
- [x] 已读取代码编写手册、目录 AGENTS.md 和适用 Skill。
- [x] 已确认 Phase4、P4-00、M04 和主责 Agent。
- [x] 已确认结构化声明已获架构师批准，且本次不越过公开 API/数据库边界。

## 5. 实施方案

### 5.1 根因与方案

问题连续出现不是因为每轮少补了几个词，而是安全边界放错了位置：

1. 回复先生成自由文本，代码再试图用正则恢复主体、动作、时态、极性和作用域；开放语言不可能由有限词表穷举。
2. 001～010 的修复只是把词表从“结果动词”依次移动到“完成态、业务论元、可信主体、连接关系、控制谓词”，没有改变输入仍是无结构字符串的事实。
3. 危险漏放和合法误杀是同一问题的两面：规则变宽会误杀页面/表单，规则变窄会漏掉新资金移动表达。
4. 结果候选扫描和 `clause fallback` 是两条重复决策路径；前者已正确识别否定时，后者仍会把同一句重新判成危险，导致“规则补对仍不生效”。
5. 固定样本和实现同步增长，只能证明已知字符串，不能建立稳定授权边界。

本次改为：

```text
结构化生成
→ BusinessClaimInventory(complete=true)
→ 主体/规范动作/时态/极性/条件 Schema 校验
→ FAQ chunk 或成功 tool_call 的当次证据绑定
→ 文本扫描只检测声明遗漏和兼容旧入口
→ 独立模型复核正文与声明一致
→ 置信度与人工接管
```

FAQ 只能证明政策，当前没有退款事实工具，因此具体客户退款申请状态、批准/拒绝、执行、划款和到账均失败关闭。开放语言动词由模型映射到有限规范动作，代码不再从同义词推导授权。

### 5.2 依赖关系

- 前置依赖：架构师已批准 `subject_type/subject_id/action/tense/polarity/condition/evidence_type/evidence_id/confidence` 内部声明字段；现有工作流已持有 FAQ chunk、工具 ID、工具名和 Mock 标记。
- 后续依赖：测试工程师执行新的独立安全复测；真实模型 live gate 评估声明完整率和一致性。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| 模型漏报或错报声明 | 新语言可能绕过规范动作 | `complete=true`、主体动作组合校验、文本遗漏扫描、独立一致性复核、生产开关关闭 |
| 跨运行伪造证据 | 借用其他 FAQ/工具事实 | 证据 ID 必须属于本次命中或成功调用，工具类型必须匹配动作 |
| 兼容文本误杀 | 旧内部入口可用性下降 | 收口非业务对象与直接作用域，并统一重复决策路径 |
| 固定样本自证 | 对泛化产生错误结论 | 固定回归与独立复测分离，不修改测试工程师 011 报告 |
| 无不可变代码基线 | 无法完成真正独立复核 | 明确项目无 Git，交由测试工程师重新执行并生成权威报告 |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `CRM智能聊天系统/backend/app/agent/business_claims.py` | 新增 | 规范业务声明、主体动作组合和可信证据校验 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/reply_safety.py` | 修改 | 接入结构化声明与 FAQ/工具证据，检测声明遗漏 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/refund_safety.py` | 修改 | 收口 011 兼容扫描，并统一作用域与 fallback 决策 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/schemas.py` | 修改 | FAQ/工具输出增加必填声明，复核输出增加一致性字段 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/workflow.py` | 修改 | 将当次 chunk/tool 证据传入门禁，并要求独立一致性通过 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/workflow_prompt.py` | 修改 | 要求完整声明并升级 FAQ/工具 Prompt 版本 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/marketing_generation.py` | 修改 | 营销输出增加声明并升级 Prompt 版本 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_agent_business_claims.py` | 新增 | 011 的 44 条固定样本及 5 条结构化门禁测试 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_agent_workflow.py` | 修改 | 工作流 fixture 与 FAQ/工具证据绑定回归 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_agent_phase4.py` | 修改 | 营销声明契约和 Prompt 版本回归 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/README.md` | 修改 | 同步结构化安全边界与 Prompt 版本 | AIAgent开发工程师Agent |
| `CRM智能聊天系统/backend/app/agent/README.md` | 修改 | 同步 M04 内部契约与证据门禁 | AIAgent开发工程师Agent |
| `AI agent 开发工程师/AI-005-REPLY-回复翻译营销与评测规范-v1.1.md` | 新增 | 形成新版回复安全规范，保留 v1.0 历史 | AIAgent开发工程师Agent |
| `共享记忆文档/实施记录索引.md` | 修改 | 登记本记录 | AIAgent开发工程师Agent |
| `共享记忆文档/实施记录/Phase4-P4-00-AIAgent开发工程师Agent-测试缺陷修复-012.md` | 新增 | 记录根因、修复、验证和交接 | AIAgent开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：无公开路径、请求/响应字段、错误码或 SSE 事件变化；仅 M04 内部模型输出 Schema 加深。
- 数据库：无迁移、表、字段或索引变化；当前迁移头为 `018_ai_observability`。
- 配置项：无新增或默认值变化；三项高风险能力保持关闭。
- AI：工作流 `v1.3.0`；FAQ 回答/复核 `v1.2.0`；工具回答/复核 `v1.2.0`；营销 `v1.1.0`；翻译版本不变。

### 6.3 关键实现说明

- `BusinessClaim` 使用有限枚举和主体动作组合表，拒绝通过错误组合重新定义业务语义。
- FAQ 和工具声明必须绑定 UUID 证据；代码验证证据属于本次运行并匹配工具类型。
- 退款具体结果没有可用白名单工具，结构化声明无论正文使用何种同义词都返回 `UNAUTHORIZED_COMMITMENT`。
- 结构化正文命中已知危险模式但声明未包含结果时，返回 `BUSINESS_CLAIM_INVENTORY_MISMATCH`。
- 复核输出增加 `business_claims_consistent`，FAQ/工具工作流只有该值为真才可保留草稿。
- 兼容文本扫描不枚举 011 的全部资金动作，而以业务主体、自然过去完成和资金/收款方论元进行保守检测；页面、表单、面板、字段、模板和说明文档按非业务对象排除。
- 局部结果扫描与 clause fallback 已统一；同一命题不会先判定为合法否定后又被第二条路径误杀。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| 011 TDD 红灯 | `pytest tests/test_agent_business_claims.py -q` | 精确复现报告 | 40 failed、4 passed | 通过 |
| 011 与结构化门禁 | 同一文件最终复跑 | 44 条报告样本及 5 条结构化测试通过 | 49 passed | 通过 |
| Phase 4/工作流聚焦回归 | `pytest tests/test_agent_phase4.py tests/test_agent_workflow.py tests/test_agent_business_claims.py -q` | 历史规则和工作流无退化 | 349 passed（随后增加 1 条 Schema 用例并纳入全量） | 通过 |
| 锁文件 | `uv lock --check` | 锁文件一致 | 125 packages resolved | 通过 |
| Ruff | `ruff check app migrations scripts tests` | 无问题 | All checks passed | 通过 |
| 格式 | `ruff format --check app migrations scripts tests` | 全部已格式化 | 199 files already formatted | 通过 |
| 类型 | `mypy app scripts` | 无类型错误 | 149 source files 无问题 | 通过 |
| 后端全量 | `pytest -q --basetemp 项目临时目录` | 全量无回归 | 466 passed、7 skipped、2 warnings | 通过 |
| 隔离 PostgreSQL | 三个 Agent/pgvector 集成文件 | 7 项全部执行 | 7 passed | 通过 |
| Compose | `docker-compose config --quiet` | 配置合法 | 通过；仅 Docker 用户配置权限警告 | 通过 |
| 迁移头 | 项目网络内一次性后端容器执行 `alembic current` | 当前 head | `018_ai_observability (head)` | 通过 |
| 高风险开关 | 读取类型化配置布尔值 | 三项关闭 | `false/false/false` | 通过 |

首次全量测试在清理系统 `pytest-current` 时遇到 Windows 权限错误；改用项目内独立 `--basetemp` 后取得有效通过结果。宿主机到 Docker PostgreSQL 的端口转发出现连接中断，因此迁移头改在项目网络的一次性后端容器中核验；隔离数据库测试通过 5433 测试库执行。两项既有 warning 为 Starlette TestClient/httpx 与 argon2 元数据弃用。

## 8. 实施结果

- 完成项：011 全部固定样本、结构化声明 Schema、证据绑定、独立一致性复核、Prompt 升级、全量与数据库回归、文档同步。
- 未完成项：测试工程师使用新独立样本复测；真实模型声明完整率与一致性 live gate；真实平台和稳定性门禁。
- 与原方案差异：没有继续把词表扩张作为根修复；文本兼容仍修复 011，但生产工作流安全边界已经迁移到结构化声明和可信证据。
- 当前状态：工程实施和开发侧验证完成，DEF-P4-AI-008/009 是否关闭由测试工程师下一份独立报告决定。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-P4-AI-086 | 结构化声明尚未经过测试工程师新的独立语言样本复测 | P1 | 测试工程师Agent | Phase4 P4-00 下一次综合复测 |
| R-P4-AI-087 | 真实模型可能漏报/错报声明，需评估声明完整率与一致性 | P1 | AIAgent开发工程师Agent、测试工程师Agent | REAL-AI-02/03 live gate |
| R-P4-AI-088 | 兼容自由文本扫描仍是启发式，不得作为生产授权 | P1 | 架构师Agent、AIAgent开发工程师Agent | 旧入口下线治理 |
| R-P4-AI-089 | 项目无 Git，无法进行不可变提交级独立验证 | P2 | 架构师Agent | 工程治理任务 |
| R-P4-AI-090 | 真实平台、50 并发和五天稳定性尚未完成 | P1 | 测试工程师Agent、架构师Agent | 生产启用前 |

## 10. 交接事项

- 交接给：测试工程师Agent、架构师Agent、全栈开发工程师Agent。
- 后续任务：测试工程师应分别验证结构化声明路径和旧文本兼容路径，新增未提供给开发实现的同义动作、错分声明、漏声明、跨运行证据和合法非业务/否定样本。
- 必须注意：正式复测前不得开启自动回复、AI 翻译、AI 营销或真实平台写；公开接口没有新增 `business_claims` 字段。
- 环境清理：隔离 PostgreSQL 测试容器及 tmpfs 临时数据已删除且不可恢复，主 PostgreSQL 已恢复停止；持久化 `postgres_data` 未删除或修改。

## 11. 文档同步

- [x] 已同步接口变化（无公开接口变化，内部 Schema 已记录）。
- [x] 已同步架构决策（落实既有 ADR，不新增 ADR）。
- [x] 已同步任务状态。
- [x] 已通知测试工程师需要覆盖的范围。
- [x] 测试报告索引将在测试工程师正式复测后更新。
