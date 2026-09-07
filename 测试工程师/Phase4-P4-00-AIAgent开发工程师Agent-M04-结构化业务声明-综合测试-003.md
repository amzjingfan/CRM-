# Phase4-P4-00-AIAgent开发工程师Agent-M04-结构化业务声明-综合测试-003

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
| 前序报告 | `测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-结构化业务声明-综合测试-002.md` |
| 修复记录 | `共享记忆文档/实施记录/Phase4-P4-00-AIAgent开发工程师Agent-结构化业务声明幂等重放缺陷修复-003.md` |
| 测试结论 | **不通过 REAL-AI-02 当前工程范围** |

## 2. 最终结论

本轮确认 `DEF-REAL-AI02-003` 的根因已经修复，状态更新为 **Closed**：

- 地址修改、发券和平台消息三类新写操作只有在低敏 `output_summary` 通过完整输出 Schema 校验后才能保存为成功终态。
- 三类完整低敏摘要可安全重放，且不持久化完整地址或消息正文。
- 历史不完整成功摘要统一返回 `unknown + TOOL_RESULT_UNKNOWN`，不再伪装成功，也不会进入自动重试。
- Mock 结果缺少非空权威声明时，不依赖中英文完成措辞，统一返回 `MOCK_COMPLETION_CLAIM`；不安全草稿不会向人工复核结果暴露。
- 上一轮 002 独立开放集已由 12 通过、3 失败恢复为 **15 passed**。

但是，修复对所有成功重放一律执行完整 `TOOL_OUTPUT_SCHEMAS` 校验，导致三个只读查询工具出现新回归：

- `query_order`、`query_logistics`、`query_customer_profile` 首次成功时只保存低敏审计摘要，不保存完整业务 DTO。
- 使用相同店铺、工具、参数和幂等键重放时，执行器把低敏摘要按完整 DTO 校验并返回 `failed + TOOL_OUTPUT_INVALID`。
- 查询工具原本标记为 `idempotency_required=false`，且属于可安全重试的只读操作；当前行为会把已成功的查询变成失败，导致 Agent 失去订单、物流或客户证据并降级转人工。

据此新增 `DEF-REAL-AI02-004`（P2，只读查询工具成功重放被误判为输出无效），状态 **Open**。`REAL-AI-02` 当前工程范围仍不通过。

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
- 002 号报告及 003 号修复记录

### 3.2 本轮目标

1. 复测 `DEF-REAL-AI02-003` 的三类 Mock 写工具幂等重放。
2. 验证历史不完整摘要返回未知，不能伪装成功或自动重试。
3. 验证新写操作只能持久化可按完整输出 Schema 重放的低敏摘要。
4. 使用不命中文本兼容词表的中英文措辞验证 Mock 空声明失败关闭。
5. 验证修复没有破坏查询工具、可信证据和自动交付边界。
6. 执行产品聚焦、固定评测、默认全量、隔离 PostgreSQL、迁移、静态质量、锁定依赖和依赖审计。

### 3.3 非目标

- 不执行真实 DeepSeek 客户业务内容调用。
- 不执行真实 TikTok、Shopee 或 Amazon 写操作。
- 不替代 `REAL-AI-03～05` 的真实模型质量、公开 SSE 性能和五日稳定性验收。
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
| `backend/app/agent/reply_safety.py` | `62F8F5E92EC55BC8714A616B9073164727B89E0140DEE0EC311B6091E0CB0DB9` |
| `backend/app/agent/workflow.py` | `28599B683A677A4BAC4C4544C63D170DA952AA9042493CA2B902D08E91B99EDA` |
| `backend/app/tools/executor.py` | `44C520830F54753199DBB1E54EDEABF6C377B4AE627A251B2F519BA4D92CB9BB` |
| `backend/tests/test_tool_executor.py` | `7814554A09F3DBC570A7979C14AF296E1C70C665D5456891CFB16CD85D94E86D` |
| `backend/tests/test_agent_business_claims.py` | `C2F457CBBD204BBEA0E8FC957CC7AA0134226E8B69A7D86C0C8B8199BCE2A586` |
| `backend/tests/test_agent_workflow.py` | `3B4A8B06607A84878C11C6288D13F38582999BC84D52F6BA91419E103753356B` |
| `backend/evals/agent-phase4-v1.0.0.jsonl` | `97EA9C18FCCE3390BFD2084EF63CDCD4EF066DA1C919102B88D7D4ED238FB471` |
| `backend/uv.lock` | `3AD5B450855EC7684EA0DD2C2361B5A2E663A5A51050C3DCBA96FB79C69B6172` |

测试前后核心修复文件和锁文件哈希一致。项目根目录和产品目录均不是 Git 仓库，无法绑定提交 SHA、树对象或签名 Tag；本报告只能绑定上述可变工作区快照。

### 4.3 独立证据

| 证据 | SHA-256 |
| --- | --- |
| `测试工程师/evidence/REAL-AI-02-003/test_real_ai02_third_retest.py` | `E82135D7E3F3DF26504279C65BB327840A6A5202DAAC8E52BCB5E1F9DCB42C11` |
| `测试工程师/evidence/REAL-AI-02-003/agent-phase4-retest.json` | `BF8C271C80443A4E1532CF034BE63BB0B7683359136972CFE2F19DCDD98F9953` |

## 5. 测试结果

### 5.1 缺陷关闭验证

| 缺陷 | 验证结果 | 状态 |
| --- | --- | --- |
| `DEF-REAL-AI02-001` 跨店铺证据来源丢失 | 002 历史开放集保持通过，代码边界未回退 | **Closed** |
| `DEF-REAL-AI02-002` Mock 地址提交漏拦截 | 002 历史开放集保持通过，Mock 写动作仍由结构化策略阻断 | **Closed** |
| `DEF-REAL-AI02-003` Mock 写幂等重放丢失失败关闭语义 | 三类完整摘要重放成功；三类历史不完整摘要返回 `unknown + TOOL_RESULT_UNKNOWN`；Mock 空声明替代措辞均返回 `MOCK_COMPLETION_CLAIM` | **Closed** |

### 5.2 独立开放集

- 上一轮 002 开放集：**15 passed**。
- 本轮 003 开放集：**12 passed、3 failed**。

本轮通过项覆盖：

- 地址、发券和平台消息三类完整低敏摘要可成功重放。
- 三类历史不完整摘要失败关闭为 `unknown`。
- 三类新写成功结果只有完整摘要可进入成功持久化出口。
- 三种未命中文本兼容词表的中英文 Mock 完成措辞均由空声明硬门禁阻断。

失败项均属于同一新缺陷家族：订单、物流、客户画像三类只读查询成功重放被误判为 `TOOL_OUTPUT_INVALID`。

### 5.3 产品回归与固定评测

| 验证项 | 实际结果 | 结论 |
| --- | --- | --- |
| Agent 与工具五文件聚焦 | 402 passed | 通过 |
| 默认后端全量 | 744 passed、10 skipped、2 warnings | 通过；跳过项为未提供隔离数据库 |
| 隔离 PostgreSQL 全量 | 754 passed、0 skipped、2 warnings | 通过 |
| 版本化固定安全评测 | 237 条；安全准确率 100%、原因码准确率 100%、危险漏放 0；`live_model_evaluation=false` | 固定集通过，但未覆盖查询重放回归 |
| Ruff 检查 | All checks passed；存在既有 ACL 警告 | 通过 |
| Ruff 格式 | 208 files already formatted | 通过 |
| mypy | 155 个源文件无问题 | 通过 |
| compileall | 退出码 0 | 通过 |
| `uv lock --check` | 125 个包解析成功 | 通过 |
| `uv audit --locked` | 124 个包无已知漏洞或不良状态 | 通过 |

两个 warning 为既有 Starlette TestClient/httpx 和 argon2 版本元数据弃用提示，不影响本轮结论。全目录 Ruff 格式首次受工作区 ACL 影响崩溃，改为对 `app/tests/scripts/migrations` 208 个正式文件扫描后通过；依赖审计首次受受限网络影响失败，获准访问 OSV 后重跑通过。首次环境失败均不计为产品缺陷，也不作为通过证据。

### 5.4 数据库与迁移

| 验证项 | 实际结果 | 结论 |
| --- | --- | --- |
| 空库升级 | `base → 019_tiktok_channel_unique` | 通过 |
| 当前版本 | `019_tiktok_channel_unique (head)` | 通过 |
| 回滚 | `019 → 018_ai_observability` | 通过 |
| 恢复 | `018 → 019_tiktok_channel_unique (head)` | 通过 |
| 隔离数据库全量 | 754 passed，无跳过 | 通过 |

隔离容器仅使用 `crm_test` 和 tmpfs。验证后已精确停止并删除 `postgres-test` 容器，不影响开发数据库或持久化卷。

### 5.5 安全与生产开关

- 扫描 219 个正式源码与配置文件，高风险密钥字面量特征只命中 3 处测试夹具，产品代码命中 0。
- `LLM_ENABLED=false`、`LLM_LIVE_EVAL=false`、`AUTO_REPLY_ENABLED=false`、`AI_TRANSLATION_ENABLED=false`、`AI_MARKETING_ENABLED=false`。
- 真实 TikTok 读取、Webhook、消息写和高风险写开关均默认关闭。
- 本轮未读取或输出真实平台凭证、DeepSeek Key、真实客户消息或完整地址，也未调用真实模型和真实平台写操作。

## 6. 新增缺陷

### DEF-REAL-AI02-004：只读查询工具成功重放被误判为输出无效

| 项目 | 内容 |
| --- | --- |
| 优先级 | P2 |
| 类型 | 工具契约、幂等重放、可用性、AI 证据链 |
| 状态 | Open |
| 影响范围 | `query_order`、`query_logistics`、`query_customer_profile`；Agent 查询重试与恢复 |
| 是否阻断 REAL-AI-02 | 是 |
| 建议负责 Agent | AIAgent开发工程师Agent；协作全栈开发工程师Agent |

复现步骤：

1. 执行订单、物流或客户画像只读工具并产生成功 `tool_calls` 记录。
2. 首次执行只保存低敏 `output_summary`：订单只含 `order_id/status`，物流只含 `order_id/tracking_status`，客户画像只含 `customer_id/order_count`。
3. 使用相同店铺、工具、参数和幂等键重放。
4. 执行器在 `backend/app/tools/executor.py:104` 进入统一重放分支，并在第 121 行把低敏摘要按完整工具输出 Schema 校验。
5. 完整查询输出 Schema 还要求订单外部 ID、金额、币种等字段，或物流外部订单 ID等字段，或客户标签和消费金额等字段，因此校验失败。

实际结果：三类查询均返回 `status=failed`、`error_code=TOOL_OUTPUT_INVALID`、`replayed=true`。

预期结果：只读查询应保持安全可重试；不得把审计用低敏摘要当作完整业务 DTO。可选择在重放时重新执行受控只读查询，或定义不泄露敏感信息且能恢复完整结果的独立版本化重放契约。

影响分析：

- 不会导致平台写操作或错误自动发送，安全门禁仍失败关闭。
- 会使已成功的订单、物流或客户画像查询在工作流重试、恢复或同幂等键再次执行时变成失败，丢失 Agent 事实证据并不必要地转人工。
- 产品 402 项聚焦和 754 项数据库全量没有覆盖成功查询记录的重复执行，因此常规全量测试未发现该回归。

独立复现证据：`测试工程师/evidence/REAL-AI-02-003/test_real_ai02_third_retest.py`。

## 7. 代码审查与独立复核

### 7.1 已确认设计

- 写工具成功出口会先校验重放摘要，历史不可恢复摘要返回 `unknown`。
- 地址和平台消息摘要不包含正文；发券摘要只保留既有低敏识别字段。
- `ReplySafetyPolicy` 在观察到 Mock 结果但没有非空声明时直接追加 `MOCK_COMPLETION_CLAIM`。
- 工作流对上述失败关闭路径不暴露不安全草稿，且不授予自动交付权限。
- `DEF-REAL-AI02-001/002` 的来源绑定和 Mock 动作阻断未回退。

### 7.2 只读新鲜上下文复核

独立只读复核确认冻结哈希与本轮快照一致，未修改任何文件。其结论与独立动态样本一致：`DEF-REAL-AI02-003` 已关闭；`backend/app/tools/executor.py:104` 对所有成功重放执行完整 Schema 校验，而三个查询实现从第 281、306、330 行起只生成低敏不完整摘要，因此同键重放确定返回 `failed/TOOL_OUTPUT_INVALID`。该回归会被工作流当作工具失败并降级，定级为 P2，阻断 `REAL-AI-02` 当前工程验收。

### 7.3 残余风险

- 真实 DeepSeek 对结构化声明的输出服从率尚未进入 `REAL-AI-05` 正式评测，本轮 237 条结果仅代表确定性代码门禁。
- 项目不是 Git 仓库，不具备不可变发布候选；即使当前工程缺陷全部关闭，也不能据此给出生产放行结论。
- 查询重放缺陷修复时不得持久化完整物流号、客户联系方式或其他敏感字段；优先重新执行只读查询或采用专门的低敏重放契约。

## 8. 主要执行命令

```text
$env:PYTHONPATH='backend'; uv run --project backend pytest ../测试工程师/evidence/REAL-AI-02-002/test_real_ai02_retest.py -q
$env:PYTHONPATH='backend'; uv run --project backend pytest ../测试工程师/evidence/REAL-AI-02-003/test_real_ai02_third_retest.py -q
uv run pytest tests/test_tool_executor.py tests/test_agent_business_claims.py tests/test_agent_tool_execution.py tests/test_agent_workflow.py tests/test_agent_phase4.py -q
uv run pytest -q --basetemp .pytest-tmp-real-ai02-003
uv run python scripts/evaluate_phase4.py --dataset evals/agent-phase4-v1.0.0.jsonl --output ../../测试工程师/evidence/REAL-AI-02-003/agent-phase4-retest.json
uv run ruff check .
uv run ruff format --check app tests scripts migrations
uv run mypy app scripts
uv run python -m compileall -q app scripts
uv lock --check
uv audit --locked
docker-compose --profile test up -d --wait postgres-test
uv run --frozen alembic upgrade head
uv run --frozen pytest -q -rs
uv run --frozen alembic current
uv run --frozen alembic downgrade -1
uv run --frozen alembic upgrade head
docker-compose --profile test stop postgres-test
docker-compose --profile test rm -f postgres-test
```

## 9. 验收建议与复测要求

1. `DEF-REAL-AI02-003` 更新为 Closed；`DEF-REAL-AI02-001/002` 保持 Closed。
2. `DEF-REAL-AI02-004`（P2）保持 Open，`REAL-AI-02` 当前工程范围保持不通过。
3. 修复必须区分写操作成功重放和只读查询安全重试，不能把低敏审计摘要直接当完整业务 DTO，也不能通过保存敏感明文规避校验。
4. 修复后至少重跑 002、003 独立开放集、402 项聚焦、默认全量、隔离 PostgreSQL 全量、237 条固定评测、迁移、Ruff、mypy 和依赖审计。
5. 在产品测试中加入三个查询工具的首次成功后同键重放场景。
6. 公开 AI 回复、生产翻译、AI 营销、自动回复和高风险平台写操作继续关闭。
7. `REAL-AI-03～05`、真实 DeepSeek、SSE 50 客户端、P99 和五日稳定性仍按计划执行。
8. 所有工程缺陷关闭后，仍须由架构师在不可变发布候选上完成最终放行。

本报告不构成真实生产 AI、真实 TikTok 平台或平台写操作的放行记录。
