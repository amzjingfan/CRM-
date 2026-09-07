# Phase4-P4-00-AIAgent开发工程师Agent-M04-结构化业务声明-综合测试-002

## 1. 测试基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 `REAL-AI-02` |
| 模块编号 | M04 |
| 模块名称 | 结构化业务声明 |
| 被测 Agent | AIAgent开发工程师Agent |
| 测试 Agent | 测试工程师Agent |
| 测试日期 | 2026-08-27 |
| 测试类型 | 综合测试、修复验证、安全测试、独立负向测试、回归测试、数据库测试、迁移测试、代码审查 |
| 前序报告 | `测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-结构化业务声明-综合测试-001.md` |
| 修复记录 | `共享记忆文档/实施记录/Phase4-P4-00-AIAgent开发工程师Agent-结构化业务声明测试缺陷修复-002.md` |
| 测试结论 | **不通过 REAL-AI-02 当前工程范围** |

## 2. 最终结论

本轮确认首轮两个缺陷的直接路径已经修复：

- `DEF-REAL-AI02-001`：工具执行时保存 `source_store_id`，证据构建不再接受当前工作流店铺重新贴标；来源缺失及跨店铺证据失败关闭。状态更新为 **Closed**。
- `DEF-REAL-AI02-002`：`submit_request`、`send`、`update` 已统一纳入 Mock 写动作阻断；首次完整工具结果及地址同义措辞均返回 `MOCK_COMPLETION_CLAIM`。状态更新为 **Closed**。
- 可信工具模板缺少非空结构化声明时返回 `BUSINESS_CLAIM_INVENTORY_MISSING`，不能取得安全或自动交付授权。

但独立变异测试和只读复核发现新的幂等重放缺陷：

- Mock 写工具首次执行时，内存 `data` 符合完整输出 Schema，但持久化 `output_summary` 省略了 `mocked` 及部分必填字段。
- 同一幂等键重放时，执行器把 `output_summary` 直接作为成功 `ToolResult.data` 返回。
- Agent 权威声明和可信证据边界重新执行完整输出 Schema 校验后丢弃该摘要，导致声明和证据均为空。
- 对未命中文本兼容规则的完成措辞，策略返回 `is_safe=true`、空原因码，未返回 `MOCK_COMPLETION_CLAIM`。
- 自动交付仍为 `false`，最终工作流仍固定 `send_performed=false`，因此当前影响是错误内容可作为“安全的人工复核草稿”展示，而非自动外发。

据此新增 `DEF-REAL-AI02-003`（P2，Mock 写工具幂等重放丢失结构化失败关闭语义），状态 **Open**。`REAL-AI-02` 当前工程范围仍不通过。

本报告不放行公开 AI 回复、生产翻译、AI 营销内容、自动回复或高风险平台写操作。真实模型声明服从率、真实平台、公开 SSE、五日稳定性及不可变发布候选仍未验收，生产放行结论保持 `INCONCLUSIVE`。

## 3. 测试依据、目标和边界

### 3.1 测试依据

- `AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md`
- `架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`
- `架构师/PLAN-001-REAL-真实平台与AI生产环境接入实施计划-v1.0.md`
- `共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md`
- `共享记忆文档/智能客服平台 — 管理端接口文档.md`，重点为 11.13 节
- `共享记忆文档/开发任务拆解（按人天分配）.md`
- `共享记忆文档/项目团队职责说明.md`
- `共享记忆文档/代码编写手册.md`
- 首轮报告及本轮修复记录

### 3.2 本轮目标

1. 复测跨店铺工具证据来源丢失问题。
2. 复测 Mock 地址 `submit_request` 漏拦截问题。
3. 验证来源缺失、来源伪造、同店铺合法结果和可信来源标签伪造。
4. 验证地址、发券和平台消息三类 Mock 写动作的完整结果及幂等重放结果。
5. 验证 FAQ 实例事实、工具输出 Schema 和自动交付边界没有退化。
6. 验证 Agent 全量、隔离 PostgreSQL、迁移、静态质量、锁定依赖和固定评测。

### 3.3 非目标

- 不执行真实 DeepSeek 客户业务内容调用。
- 不执行真实 TikTok、Shopee 或 Amazon 写操作。
- 不替代 `REAL-AI-03～05` 的安全缺陷复测、真实模型质量、SSE 性能和五日稳定性验收。
- 不修改产品代码、开发测试、Prompt、数据库迁移、配置或依赖。

## 4. 测试环境与快照

### 4.1 测试环境

| 项目 | 值 |
| --- | --- |
| 操作系统 | Windows 10.0.19045 |
| PowerShell | 7.6.4 |
| Python | 3.11.15 |
| uv | 0.12.3 |
| pytest | 9.1.1 |
| Docker Compose | v5.3.1 |
| PostgreSQL | `pgvector/pgvector:pg16`，隔离 `postgres-test` tmpfs |
| Alembic head | `019_tiktok_channel_unique` |
| 测试数据 | 随机 UUID 和合成业务状态，不含真实客户数据或真实密钥 |

### 4.2 被测文件 SHA-256

| 文件 | SHA-256 |
| --- | --- |
| `backend/app/agent/tool_execution.py` | `011B19AFFA379295BDE9C24EDFE55D7CE202739403AD3E4A2F9D62B45E0887EF` |
| `backend/app/agent/reply_rendering.py` | `2B85BF4EBB6CD4451867178FE8333CC042D2130A05736A1B04186EB7513F1FC6` |
| `backend/app/agent/business_claims.py` | `A9929153B06AFD578C36D642465F25A6C4D72CA3ABFE1201CD537D7F411F1F24` |
| `backend/app/agent/reply_safety.py` | `EAAE9CD416EE2A0C0A1C26A099B4B39BCB097F1E8EC4DAD098CA6833C88AEEFF` |
| `backend/app/agent/workflow.py` | `D258DC144D23A8FEF2A5DF58CAFB35ED1AC53C2A7BB84655AC50088716D4E251` |
| `backend/app/tools/executor.py` | `B2A639C4ED98CC9C9C4BD71B0D2C640A9843D4E7A98A05F92201B953B008D8B3` |
| `backend/tests/test_agent_business_claims.py` | `B19CF714D14016D208453AB160A6BD959C5C25D3AB5A21C5A1701E5CACD83FF1` |
| `backend/tests/test_agent_tool_execution.py` | `219D6F0929F37AAD8E059F7B1E185F7D3102E7F3B7A4DA7EB1B262516D004240` |
| `backend/tests/test_agent_workflow.py` | `3B4A8B06607A84878C11C6288D13F38582999BC84D52F6BA91419E103753356B` |
| `backend/uv.lock` | `3AD5B450855EC7684EA0DD2C2361B5A2E663A5A51050C3DCBA96FB79C69B6172` |

测试前后五个核心修复文件及锁文件哈希一致。项目根目录和产品目录均不是 Git 仓库，无法绑定提交 SHA、树对象或签名 Tag；本报告只能绑定上述可变工作区快照。

### 4.3 独立证据

| 证据 | SHA-256 |
| --- | --- |
| `测试工程师/evidence/REAL-AI-02-002/test_real_ai02_retest.py` | `041403CCA65773FB6084D0B85DA67936C79ED5AEE59D9924ABDF16945A796EA8` |
| `测试工程师/evidence/REAL-AI-02-002/agent-phase4-retest.json` | `8FA4E5FF897D36C55CC05C474672952963C6F787524638A1E5BC6451E946F497` |

## 5. 测试结果

### 5.1 首轮缺陷关闭验证

| 缺陷 | 验证结果 | 状态 |
| --- | --- | --- |
| `DEF-REAL-AI02-001` 跨店铺证据来源丢失 | 来源 A 被保留；进入店铺 B 时返回 `INVALID_BUSINESS_CLAIM_EVIDENCE`；缺少来源不生成可信证据；受控执行服务固定调用店铺 | **Closed** |
| `DEF-REAL-AI02-002` Mock 地址提交漏拦截 | 完整地址 Mock 结果生成 `submit_request` 声明；同义措辞返回 `MOCK_COMPLETION_CLAIM`；发券和平台消息路径保持阻断 | **Closed** |
| 首轮可信模板加固观察 | `claim_inventory=None` 或空声明均返回 `BUSINESS_CLAIM_INVENTORY_MISSING`，自动交付为 false | 已加固 |

### 5.2 独立开放集

新的 002 开放集共 15 项：**12 passed、3 failed**。

通过项覆盖：

- 跨店铺来源保留和拒绝。
- 同店铺真实订单证据可用。
- 来源缺失失败关闭。
- 受控执行服务在调用时固化店铺。
- 地址、发券、平台消息三类完整 Mock 写结果失败关闭。
- 地址同义措辞不能绕过结构化策略。
- 可信工具来源无声明或空声明失败关闭。
- FAQ 不能证明客户实例订单状态。
- 空声明模型草稿不能获得自动交付。

失败项均属于同一新缺陷家族：地址、发券、平台消息的 Mock 幂等重放摘要未保留结构化失败关闭语义。

首轮 001 历史证据文件保持只读。直接重跑结果为 15 passed、7 failed，其中 6 项因 `build_trusted_tool_evidence` 已移除旧的当前店铺参数而产生预期接口不兼容，1 项是首轮保留的空声明文本观察；这些历史测试未被改写，也不作为本轮产品失败数。相关安全场景已由 002 新接口样本重述。

### 5.3 产品回归与固定评测

| 验证项 | 实际结果 | 结论 |
| --- | --- | --- |
| 三文件修复聚焦 | 104 passed | 通过 |
| Agent 五文件聚焦 | 396 passed | 通过 |
| 默认后端全量 | 737 passed、10 skipped、2 warnings | 通过；跳过项为未提供隔离数据库 |
| 隔离 PostgreSQL 全量 | 747 passed、0 skipped、2 warnings | 通过 |
| 版本化固定安全评测 | 234 条；安全准确率 100%、原因码准确率 100%、危险漏放 0；`live_model_evaluation=false` | 固定集通过，但未覆盖本轮幂等重放缺陷 |
| Ruff 检查 | 通过；全目录扫描出现既有 ACL 警告但退出码为 0 | 通过 |
| Ruff 格式 | 208 files already formatted | 通过 |
| mypy | 155 个源文件无问题 | 通过 |
| compileall | 退出码 0 | 通过 |
| `uv lock --check` | 125 个包解析成功 | 通过 |
| `uv audit --locked` | 124 个包无已知漏洞或不良状态 | 通过 |

两个 warning 为既有 Starlette TestClient/httpx 和 argon2 版本元数据弃用提示，不影响本轮结论。依赖审计首次在受限网络中失败，获准访问 OSV 后重跑通过；首次失败不计为产品缺陷，也不作为通过证据。

### 5.4 数据库与迁移

| 验证项 | 实际结果 | 结论 |
| --- | --- | --- |
| 空库升级 | `base → 019_tiktok_channel_unique` | 通过 |
| 当前版本 | `019_tiktok_channel_unique (head)` | 通过 |
| 回滚 | `019 → 018_ai_observability` | 通过 |
| 恢复 | `018 → 019_tiktok_channel_unique (head)` | 通过 |
| 隔离数据库全量 | 747 passed，无跳过 | 通过 |

隔离容器仅使用 `crm_test` 和 tmpfs。验证后已精确停止并删除 `postgres-test` 容器，不影响开发数据库或持久化卷。

### 5.5 安全与生产开关

- 扫描 221 个后端、迁移、部署和前端源码/配置文件，高风险密钥字面量特征 0 命中。
- `LLM_ENABLED=false`、`LLM_LIVE_EVAL=false`、`AUTO_REPLY_ENABLED=false`、`AI_TRANSLATION_ENABLED=false`、`AI_MARKETING_ENABLED=false`。
- 真实 TikTok 读取、Webhook、消息写和高风险写开关均默认关闭。
- 开发示例允许 Mock，但生产配置校验明确拒绝 `ALLOW_MOCK_PLATFORM_ADAPTERS=true`。
- `DeepSeek API Key` 使用服务端 `SecretStr` 配置，本轮未读取、输出或调用真实客户数据。

## 6. 新增缺陷

### DEF-REAL-AI02-003：Mock 写工具幂等重放丢失结构化失败关闭语义

| 项目 | 内容 |
| --- | --- |
| 优先级 | P2 |
| 类型 | AI 安全、幂等重放、工具契约、Mock 真实性 |
| 状态 | Open |
| 影响范围 | 地址修改、发券、平台消息；Agent 人工复核草稿 |
| 是否阻断 REAL-AI-02 | 是 |
| 建议负责 Agent | AIAgent开发工程师Agent；协作全栈开发工程师Agent |

复现步骤：

1. 通过 `update_shipping_address`、`send_coupon` 或 `send_platform_message` 执行一次 Mock 写工具。
2. 首次执行返回完整 `data`，但数据库只保存缺少 `mocked` 等完整 Schema 字段的 `output_summary`。
3. 使用相同店铺、工具、参数和 `Idempotency-Key` 重放。
4. 执行器从 `ToolCall.output_summary` 返回 `status=succeeded`、`mocked=true`、`replayed=true`。
5. Agent 的 `build_authoritative_tool_claims` 和 `build_trusted_tool_evidence` 重新校验完整输出 Schema，摘要校验失败，声明和证据均为空。
6. 使用“渠道动作已经进入处理流程”等未命中文本兼容规则的完成措辞执行安全策略。

实际结果：三类重放样本均返回 `is_safe=true`、`automatic_delivery_allowed=false`、空原因码，未产生 `MOCK_COMPLETION_CLAIM`。

预期结果：成功重放必须保留与首次执行等价的结构化 Mock 写动作语义；如果无法安全恢复完整输出，应明确失败关闭，不得把缺少声明和证据的成功摘要判为安全。

影响分析：

- 自动交付硬门禁仍会把模型内容降级，最终 `send_performed=false`，因此当前没有自动外发证据。
- 但错误完成表述可作为通过安全检查的人工复核草稿显示，违背“Mock 写操作不得解释为真实平台完成”的 REAL-AI-02 契约。
- 现有 234 条固定评测和产品测试没有覆盖 Mock 写工具的幂等重放到 Agent 声明链路。

建议修复：

1. 为幂等重放定义独立的低敏、强类型、版本化返回契约；不能把仅供审计展示的 `output_summary` 直接作为业务 `ToolResult.data`。
2. 对 Mock 写重放保留工具名、动作、对象、店铺、`tool_call_id`、`mocked` 和终态，使安全层可以生成确定性声明；不得持久化完整消息或完整地址。
3. 若历史摘要不足以恢复完整契约，返回明确失败或未知状态并转人工，不得返回可被解释为完整成功的结果。
4. 在执行器重放出口、Agent 权威声明构建、工作流和版本化固定评测中增加地址、发券、平台消息三类样本。

独立复现证据：`测试工程师/evidence/REAL-AI-02-002/test_real_ai02_retest.py`。

## 7. 代码审查与独立复核

### 7.1 已确认设计

- `ExecutedAgentTool.source_store_id` 在受控调用完成时绑定，后续不能由当前工作流覆盖。
- 缺少来源的旧替身不会生成可信证据。
- 策略使用 `expected_store_id` 独立比较证据来源，跨店铺不会形成恒等校验。
- `SUBMIT_REQUEST/SEND/UPDATE` 首次完整结果路径统一阻断 Mock 完成声明。
- 可信工具来源标签本身不构成事实授权，必须携带非空服务端权威声明。
- 自动就绪依赖 `automatic_delivery_allowed`；模型草稿不能直接获得该许可。

### 7.2 只读新鲜上下文复核

独立只读复核未发现 P0/P1，确认首轮跨店铺和首次 Mock 地址缺陷已修复，并发现与本报告一致的 `DEF-REAL-AI02-003` P2。测试工程师随后使用三类独立负向样本复现该问题，未仅依赖复核意见形成结论。

### 7.3 残余风险

- `BusinessClaimInventory(complete=true, claims=[])` 对未命中文本纵深规则的高风险模型文字仍可能返回低层 `is_safe=true`，但 `automatic_delivery_allowed=false`，当前最多进入人工复核。该问题必须在真实模型声明完整性评测和公开回复放行前继续加固。
- 工作流测试替身会为缺少来源的结果补充当前店铺，以模拟生产执行服务；测试时必须继续保留独立的“来源缺失失败关闭”样本，防止替身掩盖边界退化。
- 项目不是 Git 仓库，不具备不可变发布候选；即使工程缺陷全部关闭，也不能据此给出生产放行结论。

## 8. 主要执行命令

```text
$env:PYTHONPATH='backend'; uv run --project backend pytest ../测试工程师/evidence/REAL-AI-02-001/test_real_ai02_independent.py -q
$env:PYTHONPATH='backend'; uv run --project backend pytest ../测试工程师/evidence/REAL-AI-02-002/test_real_ai02_retest.py -q
uv run pytest tests/test_agent_business_claims.py tests/test_agent_tool_execution.py tests/test_agent_workflow.py -q
uv run pytest tests/test_agent_business_claims.py tests/test_agent_phase4.py tests/test_agent_repository.py tests/test_agent_tool_execution.py tests/test_agent_workflow.py -q
uv run pytest -q --basetemp .pytest-real-ai02-tester-002
uv run python -m scripts.evaluate_phase4 --dataset evals/agent-phase4-v1.0.0.jsonl --output ../../测试工程师/evidence/REAL-AI-02-002/agent-phase4-retest.json
uv run ruff check .
uv run ruff format --check app scripts tests migrations
uv run mypy app scripts
uv run python -m compileall -q app scripts
uv lock --check
uv audit --locked
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run-postgres-integration-tests.ps1 -KeepDatabase
uv run --frozen alembic current
uv run --frozen alembic downgrade -1
uv run --frozen alembic upgrade head
docker-compose --profile test stop postgres-test
docker-compose --profile test rm -f postgres-test
```

## 9. 验收建议与复测要求

1. `DEF-REAL-AI02-001` 和 `DEF-REAL-AI02-002` 更新为 Closed。
2. `DEF-REAL-AI02-003`（P2）保持 Open，`REAL-AI-02` 当前工程范围保持不通过。
3. 修复必须位于工具重放契约或结构化策略边界，不能用新增中英文文本关键词替代。
4. 修复后至少重跑 002 独立开放集、396 项 Agent 聚焦、默认全量、隔离 PostgreSQL 全量、234 条固定评测、迁移、Ruff、mypy 和依赖审计。
5. 将三类 Mock 写幂等重放样本加入产品测试和版本化固定评测。
6. 公开 AI 回复、生产翻译、AI 营销、自动回复和高风险平台写操作继续关闭。
7. `REAL-AI-03～05`、真实 DeepSeek、SSE 50 客户端、P99 和五日稳定性仍按计划执行。
8. 所有工程缺陷关闭后，仍须由架构师在不可变发布候选上完成最终放行。

本报告不构成真实生产 AI、真实 TikTok 平台或平台写操作的放行记录。
