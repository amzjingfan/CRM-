# Phase4-P4-00-AIAgent开发工程师Agent-M04-结构化业务声明-综合测试-004

## 1. 测试基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 `REAL-AI-02` |
| 模块编号 | M04 |
| 模块名称 | 结构化业务声明 |
| 被测主责 Agent | AIAgent开发工程师Agent |
| 被测协作 Agent | 全栈开发工程师Agent、架构师Agent |
| 测试执行 Agent | 测试工程师Agent |
| 关联实施记录 | `共享记忆文档/实施记录/Phase4-P4-00-AIAgent开发工程师Agent-结构化业务声明只读重放缺陷修复-004.md` |
| 前序报告 | `测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-结构化业务声明-综合测试-003.md` |
| 测试类型 | 综合测试、修复验证、安全测试、独立负向测试、回归测试、数据库测试、迁移测试、代码审查 |
| 执行日期 | 2026-08-27 |
| 测试结论 | **有条件通过 REAL-AI-02 当前确定性工程范围** |

## 2. 最终结论

本轮确认 `DEF-REAL-AI02-004` 已完成根因修复，状态更新为 **Closed**：

- `query_order`、`query_logistics` 和 `query_customer_profile` 的成功低敏摘要使用内部 `READ_TOOL_REPLAY_OUTPUT_SCHEMAS` v1 校验，不再按完整业务 DTO 误判。
- 合法重放返回 `succeeded`、`replayed=true` 和 `replay_contract_version=1`，可继续生成同店铺对象级权威声明、可信证据和已收录状态模板。
- 缺少字段、额外字段、未知版本、版本标识不完整、未知状态和写工具伪用只读契约均失败关闭，不能生成可授权声明或固定模板。
- 重放前重新校验当前权限；权限撤销时返回 `TOOL_PERMISSION_DENIED`，不返回历史摘要，也不覆盖原成功审计终态。
- 低敏快照只证明其中明确保存的对象、有限状态或订单数量，不扩展为外部订单号、金额、物流单号、联系方式、地址或其他未保存事实。
- 跨店铺来源继续返回 `INVALID_BUSINESS_CLAIM_EVIDENCE`，不能取得安全或自动交付授权。

历史 002、003 独立开放集均为 **15 passed**；本轮 004 独立开放集为 **20 passed**。产品聚焦、默认全量、隔离 PostgreSQL、固定安全评测、迁移、静态质量和依赖审计全部通过，未发现新的 P0/P1/P2/P3 缺陷。因此 `REAL-AI-02` 当前确定性工程范围 **有条件通过**，`DEF-REAL-AI02-001～004` 全部 Closed。

本结论不等同生产放行：真实 DeepSeek 结构化声明服从率、`REAL-AI-03～05`、真实模型回复/翻译/营销评测、公开 SSE 50 客户端、P99、五日稳定性和不可变发布候选仍未验收。公开 AI 回复、生产翻译、AI 营销、自动回复和高风险平台写操作继续关闭；生产放行结论保持 `INCONCLUSIVE`。

## 3. 测试依据、目标和边界

### 3.1 测试依据

- `AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md`
- `架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`
- `架构师/PLAN-001-REAL-真实平台与AI生产环境接入实施计划-v1.0.md`
- `共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md`
- `共享记忆文档/智能客服平台 — 管理端接口文档.md` 第 11.13 节
- `共享记忆文档/MVP范围与验收标准.md`
- `共享记忆文档/开发任务拆解（按人天分配）.md`
- `共享记忆文档/项目团队职责说明.md`
- `共享记忆文档/代码编写手册.md`
- 003 号正式报告和 004 号修复实施记录

### 3.2 本轮目标

1. 复测 `DEF-REAL-AI02-004` 的三个只读工具成功重放。
2. 验证 v1 低敏 Schema 的必填字段、额外字段和类型边界。
3. 验证 `replayed` 与版本标识不能单独或交叉伪造可信结果。
4. 验证写工具不能借用只读重放契约。
5. 验证权限撤销、跨店铺来源、未知状态和未保存事实继续失败关闭。
6. 验证 `DEF-REAL-AI02-001～003` 和写操作重放边界没有回退。
7. 执行聚焦、固定评测、默认全量、隔离 PostgreSQL、迁移、静态质量、锁定依赖和依赖审计。

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
| `backend/app/tools/contracts.py` | `E61CFF569F4C177E176765F627E628552C23E0550F689CDBC12A2FCB8CCA9362` |
| `backend/app/tools/executor.py` | `58B2ADC811102A46D17BB7145FB4D5B24CB0FA3A0DBE598502FD43FEA78948A5` |
| `backend/app/agent/reply_rendering.py` | `036DFDE79C8C4C7ABB4815748B15E78D61D23D16E9FF9ACCFA6A114EDE5E4866` |
| `backend/app/agent/tool_execution.py` | `011B19AFFA379295BDE9C24EDFE55D7CE202739403AD3E4A2F9D62B45E0887EF` |
| `backend/app/agent/business_claims.py` | `A9929153B06AFD578C36D642465F25A6C4D72CA3ABFE1201CD537D7F411F1F24` |
| `backend/app/agent/reply_safety.py` | `62F8F5E92EC55BC8714A616B9073164727B89E0140DEE0EC311B6091E0CB0DB9` |
| `backend/app/agent/workflow.py` | `28599B683A677A4BAC4C4544C63D170DA952AA9042493CA2B902D08E91B99EDA` |
| `backend/tests/test_tool_executor.py` | `C781B3373CDE6179BB5F05836BD23FD5DF668265BA21A766034A0B4135DF2083` |
| `backend/tests/test_agent_business_claims.py` | `77304ACA157524BAF2CAC2DEE21E56FB0811C4C9BBE6CDB87F4D22889BE06D6E` |
| `backend/tests/test_agent_workflow.py` | `3B4A8B06607A84878C11C6288D13F38582999BC84D52F6BA91419E103753356B` |
| `backend/evals/agent-phase4-v1.0.0.jsonl` | `97EA9C18FCCE3390BFD2084EF63CDCD4EF066DA1C919102B88D7D4ED238FB471` |
| `backend/uv.lock` | `3AD5B450855EC7684EA0DD2C2361B5A2E663A5A51050C3DCBA96FB79C69B6172` |

测试前后核心文件及锁文件哈希一致。项目根目录和产品目录均不是 Git 仓库，无法绑定提交 SHA、树对象或签名 Tag；本报告只能绑定上述可变工作区快照，不能作为不可变发布候选批准。

### 4.3 独立证据

| 证据 | SHA-256 |
| --- | --- |
| `测试工程师/evidence/REAL-AI-02-004/test_real_ai02_fourth_retest.py` | `557E706FE92FE8752259051633A4C5C05BD43B74AAC1956C1962E90AFE272A9C` |
| `测试工程师/evidence/REAL-AI-02-004/agent-phase4-retest.json` | `BF8C271C80443A4E1532CF034BE63BB0B7683359136972CFE2F19DCDD98F9953` |

## 5. 测试结果

### 5.1 缺陷关闭验证

| 缺陷 | 验证结果 | 状态 |
| --- | --- | --- |
| `DEF-REAL-AI02-001` 跨店铺证据来源丢失 | 合法 v1 重放仍保留执行来源；跨店铺策略返回 `INVALID_BUSINESS_CLAIM_EVIDENCE` | **Closed** |
| `DEF-REAL-AI02-002` Mock 地址提交漏拦截 | 002 历史开放集保持 15/15，通过边界未回退 | **Closed** |
| `DEF-REAL-AI02-003` Mock 写幂等重放丢失失败关闭语义 | 003 历史开放集保持 15/15，写工具不能借用只读 v1 契约 | **Closed** |
| `DEF-REAL-AI02-004` 只读查询成功重放误判 | 三类合法低敏摘要均返回 `succeeded/replayed/version=1`，可生成对应对象级声明与证据 | **Closed** |

### 5.2 独立开放集

| 开放集 | 结果 | 结论 |
| --- | --- | --- |
| 002 历史开放集 | 15 passed | 通过 |
| 003 历史开放集 | 15 passed | 通过 |
| 004 新开放集 | 20 passed | 通过 |

004 开放集覆盖：

- 订单、物流、客户画像三类合法只读重放。
- 三类当前权限撤销且不改写历史审计。
- 三类额外敏感或未登记字段拒绝。
- 三类低敏结果生成对象级声明和同店铺可信证据。
- `replayed/version` 缺失、未知版本和标识组合伪造。
- 写工具伪用只读契约、未保存事实、跨店铺来源和未知状态。

### 5.3 产品回归与固定评测

| 验证项 | 实际结果 | 结论 |
| --- | --- | --- |
| Agent 与工具六文件聚焦 | 413 passed | 通过 |
| 默认后端全量 | 751 passed、10 skipped、2 warnings | 通过；跳过项为未提供隔离数据库 |
| 隔离 PostgreSQL 全量 | 761 passed、0 skipped、2 warnings | 通过 |
| 版本化固定安全评测 | 237 条；安全准确率 100%、原因码准确率 100%、危险漏放 0；`live_model_evaluation=false` | 通过；仅代表确定性门禁 |
| Ruff 检查 | All checks passed | 通过 |
| Ruff 格式 | 208 files already formatted | 通过 |
| mypy | 155 个源文件无问题 | 通过 |
| compileall | 退出码 0 | 通过 |
| `uv lock --check` | 125 个包解析成功 | 通过 |
| `uv audit --locked` | 124 个包无已知漏洞或不良状态 | 通过 |

两个 warning 为既有 Starlette TestClient/httpx 和 argon2 版本元数据弃用提示，不影响本轮结论。

### 5.4 数据库与迁移

| 验证项 | 实际结果 | 结论 |
| --- | --- | --- |
| 空库升级 | `base → 019_tiktok_channel_unique` | 通过 |
| 当前版本 | `019_tiktok_channel_unique (head)` | 通过 |
| 回滚 | `019 → 018_ai_observability` | 通过 |
| 恢复 | `018 → 019_tiktok_channel_unique (head)` | 通过 |
| 隔离数据库全量 | 761 passed，无跳过 | 通过 |

隔离容器仅使用 `crm_test` 和 tmpfs。验证后已精确停止并删除 `postgres-test` 容器，不影响开发数据库或持久化卷。

### 5.5 安全与生产开关

- 扫描 219 个正式源码与配置文件，高风险密钥字面量特征只命中 3 处测试夹具，产品代码命中 0。
- `LLM_ENABLED=false`、`LLM_LIVE_EVAL=false`、`AUTO_REPLY_ENABLED=false`、`AI_TRANSLATION_ENABLED=false`、`AI_MARKETING_ENABLED=false`。
- 真实 TikTok 读取、Webhook、消息写和高风险写开关均默认关闭。
- 本轮未读取或输出真实平台凭证、DeepSeek Key、真实客户消息或完整地址，也未调用真实模型和真实平台写操作。

## 6. 缺陷与观察

### 6.1 缺陷状态

本轮无新增 P0/P1/P2/P3 缺陷。`DEF-REAL-AI02-001～004` 全部 Closed。

### 6.2 非阻断观察

1. `READ_TOOL_REPLAY_OUTPUT_SCHEMAS` v1 只恢复有限低敏事实；需要金额、外部订单号、物流单号、标签等信息时必须使用新 Agent Run 重新查询，不能扩展旧快照含义。
2. 未知订单或物流状态虽然可以通过基础低敏 Schema，但不会生成权威状态声明和固定模板，按现有工作流转人工；该失败关闭行为符合接口契约。
3. 当前工作区不是 Git 仓库；独立复核只能绑定文件哈希，无法形成不可变发布候选，因此生产发布仍需 Git 提交、树哈希或等效受保护制品基线。

## 7. 代码审查与独立复核

### 7.1 已确认设计

- `backend/app/tools/contracts.py:130` 固定 v1 版本，133～151 行定义三个严格低敏 Schema，206～210 行只注册三个查询工具。
- `backend/app/tools/executor.py:106` 在返回重放数据前检查当前权限；126～170 行分离读写重放校验并仅为合法只读结果赋予 v1 标识。
- `backend/app/agent/reply_rendering.py:301` 在模板、声明和证据共同入口再次校验：只有 `replayed=true + version=1` 使用低敏 Schema，其他结果继续使用完整 DTO。
- 订单和物流权威声明仍只接受固定已知状态；写工具不在只读映射中，无法借重放标识生成成功声明。
- 原店铺来源由 `ExecutedAgentTool.source_store_id` 保留，策略继续以 `expected_store_id` 独立比较。

### 7.2 只读新鲜上下文复核

确定性测试完成后，由未参与产品代码修改的只读复核者在新鲜上下文中核对冻结哈希、只读重放契约、权限重检、声明/证据二次校验和 004 独立开放集。复核结论如下：

- `DEF-REAL-AI02-004` 可关闭；三个冻结核心文件哈希与本报告一致，004 独立开放集 20/20 通过，原误判根因已消除。
- 未发现新增 P0/P1/P2/P3；版本缺失或未知、额外敏感字段、写工具借用只读契约、权限撤销、跨店铺、未知状态和未保存事实授权均已覆盖。
- `REAL-AI-02` 当前确定性工程范围可判定为有条件通过，但不等于真实模型或生产放行。
- 复核定位：`backend/app/tools/contracts.py:91`、`:130`、`:206`、`:285`；`backend/app/tools/executor.py:106`、`:126`、`:143`、`:213`；`backend/app/agent/reply_rendering.py:95`、`:116`、`:145`、`:301`。
- 项目不是 Git 仓库，只能绑定当前可变 SHA-256 工作区快照；真实 DeepSeek、真实平台、公开 SSE、五日稳定性和不可变发布候选未完成前，生产结论必须保持 `INCONCLUSIVE`。

### 7.3 残余生产风险

- 真实 DeepSeek 对结构化声明的输出服从率尚未执行 `REAL-AI-05` 正式开放集评测。
- `DEF-P4-AI-008/009`、真实回复/翻译/营销、公开 SSE 性能和五日稳定性仍按 `REAL-AI-03～05` 独立验收。
- 项目不是 Git 仓库，不具备不可变发布候选；本报告不能给出生产 `PASS`。

## 8. 主要执行命令

```text
$env:PYTHONPATH='backend'; uv run --project backend pytest ../测试工程师/evidence/REAL-AI-02-002/test_real_ai02_retest.py -q
$env:PYTHONPATH='backend'; uv run --project backend pytest ../测试工程师/evidence/REAL-AI-02-003/test_real_ai02_third_retest.py -q
$env:PYTHONPATH='backend'; uv run --project backend pytest ../测试工程师/evidence/REAL-AI-02-004/test_real_ai02_fourth_retest.py -q
uv run pytest tests/test_tool_executor.py tests/test_agent_business_claims.py tests/test_agent_repository.py tests/test_agent_tool_execution.py tests/test_agent_workflow.py tests/test_agent_phase4.py -q
uv run pytest -q --basetemp .pytest-tmp-real-ai02-004
uv run python scripts/evaluate_phase4.py --dataset evals/agent-phase4-v1.0.0.jsonl --output ../../测试工程师/evidence/REAL-AI-02-004/agent-phase4-retest.json
uv run ruff check app tests scripts migrations
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

## 9. 验收建议与后续门禁

1. `DEF-REAL-AI02-004` 更新为 Closed；`DEF-REAL-AI02-001～003` 保持 Closed。
2. `REAL-AI-02` 当前确定性工程范围更新为有条件通过，无本任务未关闭 P0/P1/P2/P3。
3. 只读 v1 快照不得扩展为未保存事实；需要更完整数据时启动新 Agent Run 查询。
4. 进入 `REAL-AI-03～05` 前继续保持公开回复、生产翻译、AI 营销、自动回复和高风险平台写操作关闭。
5. 后续必须完成真实 DeepSeek 声明服从率评测、`DEF-P4-AI-008/009` 独立复测、SSE 50 客户端、P99 和五日稳定性。
6. 最终生产验收必须绑定不可变发布候选，并由架构师和产品负责人完成放行。

本报告不构成真实生产 AI、真实 TikTok 平台或平台写操作的放行记录。
