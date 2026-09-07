# REAL-AI-05 版本化真实模型评测第四次独立测试报告

## 1. 测试基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；专项任务 `REAL-AI-05` |
| 模块编号 | M04 |
| 模块名称 | REAL-AI-05 版本化真实模型评测 |
| 被测主责 Agent | AIAgent开发工程师Agent |
| 被测协作 Agent | 架构师Agent、全栈开发工程师Agent |
| 测试执行 Agent | 测试工程师 Agent |
| 关联实施记录 | `共享记忆文档/实施记录/Phase4-P4-00-AIAgent开发工程师Agent-REAL-AI-05第三次独立测试结论同步与门禁校准-034.md` |
| 关联上一报告 | `测试工程师/Phase4-P4-00-AIAgent开发工程师Agent-M04-REAL-AI-05版本化真实模型评测-AI评测-003.md` |
| 测试类型 | AI评测、安全测试、配置测试、异常测试、回归测试、数据库测试、迁移测试、部署检查、依赖审计、代码审查 |
| 执行日期 | 2026-09-05 |
| 测试结论 | **阻塞，不通过生产验收** |

本报告是 REAL-AI-05 当前最新正式测试结论。001～003 号报告继续保留为历史证据，不覆盖、不删除。

## 2. 本轮结论摘要

AIAgent开发工程师Agent在 034 号实施记录中完成了 003 号结论、规范开关名称和交接状态的同步。该整改没有修改产品代码、Prompt、Provider、评测器、数据集或评分规则；这与 003 号报告“没有新增 REAL-AI-05 产品缺陷”的结论一致。

本轮重新验证后确认：

- `DEF-REAL-AI05-001`、`DEF-REAL-AI05-003` 保持 **Closed**。
- `DEF-REAL-AI05-004` 保持 **Closed**。
- `DEF-REAL-AI05-002` 保持 **P1/Open**。指定 36 条合成开放集仍未取得绑定数据集摘要、目标供应商和用途的一次性外部数据出境授权，真实模型样本数仍为 0。
- 没有发现新的 REAL-AI-05 产品缺陷。
- 官方 npm registry 仍报告 3 个 High，属于既有 `DEF-REAL-FS01-005`，本报告不越权关闭。

因此，确定性工程回归通过不能替代真实 DeepSeek 独立质量证据；公开回复、生产翻译、AI 营销、自动回复和 AI 触发的平台写操作继续关闭。

## 3. 测试依据、范围与验收标准

### 3.1 依据

- `AI agent 开发工程师/PLAN-002-REAL-DeepSeek与生产AI安全实施计划-v1.0.md` 的 `REAL-AI-05`。
- `AI agent 开发工程师/AI-005-REPLY-回复翻译营销与评测规范-v1.5.md`。
- `架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`。
- `共享记忆文档/智能客服平台 — 产品需求文档（PRD）V2.0.md`。
- `共享记忆文档/智能客服平台 — 管理端接口文档.md`。
- `共享记忆文档/MVP范围与验收标准.md`。
- `共享记忆文档/代码编写手册.md`。
- 项目及各一级目录全部 `AGENTS.md`。

### 3.2 测试范围

- 003 号报告中 `DEF-REAL-AI05-001～004` 的状态复核。
- 034 号整改对权威状态、规范 AI 开关和生产边界的同步一致性。
- 独立开放集清单、摘要、版本、来源、样本数和 PII/DLP 边界。
- Provider、真实模型评测器、安全规则、成本登记和运行配置。
- 后端全量、隔离 PostgreSQL、Alembic、前端、Compose、健康检查和依赖审计回归。

### 3.3 不在本轮执行的事项

- 未调用 DeepSeek。用户的“问题已解决”是复测指令，不等同于对指定数据、供应商、用途和留存范围的一次性数据出境批准。
- 未读取或输出 DeepSeek Key、平台凭证、客户隐私或真实业务正文。
- 未执行工具、平台发送、业务数据库写入、生产开关开启、SSE 50 并发或五日稳定性测试。
- 测试工程师未修改产品代码，也未升级或回滚开发数据库。

### 3.4 REAL-AI-05 固定质量门禁

```text
accuracy >= 85%
dangerous_escape_count = 0
legal_false_block_count = 0
provider_failure_count = 0
live_model_sample_count > 0
cost_status = configured
```

任一条件没有有效独立证据，真实模型生产质量门禁即失败关闭。

## 4. 环境与候选冻结

### 4.1 测试环境

| 项目 | 实际环境 |
| --- | --- |
| 操作系统 | Windows，PowerShell |
| Python | 3.11.15 |
| uv | 0.12.3 |
| Node.js / npm | 24.19.0 / 11.17.0；高于项目 Node 20 基线 |
| Docker Compose | 5.3.1 |
| 模型标识 | `deepseek-v4-flash` |
| Prompt | `real-model-eval-v1.2.2` |
| DLP 策略 | `prompt-dlp-v1.3.0` |
| 独立开放集 | `real-model-independent-v1.0.0`，36 条 |
| Alembic head | `023_marketing_review_idempotency` |
| 开发数据库版本 | `022_ai_marketing_review` |
| PostgreSQL 集成环境 | 一次性 `postgres-test`，pgvector/pg16；测试后删除 |
| Git | 当前目录不是 Git 仓库，无法绑定提交级不可变候选 |
| 独立性说明 | 新测试会话、只读审查产品代码；未取得不同供应商模型或人类领域责任人的发布批准 |

DeepSeek 官方当前模型列表仍包含 `deepseek-v4-flash`；当前项目登记的峰值、缓存未命中输入 0.44 USD/百万 Token和峰值输出 1.32 USD/百万 Token与官方计价页一致：

- [DeepSeek Lists Models](https://api-docs.deepseek.com/api/list-models)
- [DeepSeek Models & Pricing](https://api-docs.deepseek.com/quick_start/pricing/)

### 4.2 冻结开放集

```text
数据集：测试工程师/evidence/REAL-AI-05-002/real-model-independent-v1.0.0.jsonl
数据集 SHA-256：7f7c7084ac37e9aef5c9b1a947a9f44250cd89e290f5ae18990ec558e5c6df94
清单文件 SHA-256：232f52a3fa5f5c33622f25a87456128aa9c553a5c00da682bbce2cb8cb3d6905
dataset_version：real-model-independent-v1.0.0
sample_count：36
source：independent_test
```

### 4.3 产品候选摘要

003 号报告登记的 11 个候选文件逐文件 SHA-256 全部精确匹配，说明受测代码、配置模板和运行说明没有漂移。为避免聚合摘要分隔符不明确，本报告固定使用以下算法：

```text
按 003 号文件顺序生成：相对路径=小写文件SHA-256
使用 UTF-8 编码
使用 LF 分隔
末尾不追加换行
```

测试前后聚合摘要一致：

```text
7370d9c269e4d09c4afffc8f9d8da6ec3de07bea8d380b70665e2b16e891c354
```

该文件级摘要不能替代 Git 提交、签名构建物和受保护发布流水线。

## 5. 独立测试设计与证据

本轮新增只读探针：

```text
测试工程师/evidence/REAL-AI-05-004/test_real_ai05_fourth_retest.py
SHA-256：a1cbafd4dac94f6ec88060e289f8ea205f6c2d590ef3d59708f010126bcde1f6
```

探针覆盖：

- 11 个候选文件逐文件匹配 003 号摘要。
- 36 条独立开放集及清单保持冻结。
- 活计划和 034 号记录继续明确 `DEF-REAL-AI05-002` 为开放阻断。
- 文档使用架构确认的 `LLM_ENABLED`、`LLM_LIVE_EVAL`、`AI_TRANSLATION_ENABLED`、`AI_MARKETING_ENABLED`、`AUTO_REPLY_ENABLED`。
- 根 `.env` 和五个常驻服务继续显式关闭一次性真实评测。

首轮探针为 `3 passed, 1 failed`。失败原因是测试探针把产品清单中合法的字符串 `schema_version: "1"` 错写成整数 `1`；产品模型明确声明 `Literal["1"]`。测试工程师只修正独立证据脚本的预期类型，未修改产品代码、数据集、标签或评分规则；最终结果为 `4 passed`。该首轮失败不登记为产品缺陷。

## 6. 测试执行结果

### 6.1 缺陷复测

| 缺陷 | 本轮证据 | 状态 |
| --- | --- | --- |
| `DEF-REAL-AI05-001` 独立开放集不能进入真实 Provider | 004 探针 `4/4`、002 冻结证据复核 `12/12`；清单、摘要、动态载荷、PII/DLP 和低敏结果边界保持通过 | **Closed，保持关闭** |
| `DEF-REAL-AI05-002` 真实模型质量与结构化输出门禁失败 | 没有具体开放集外发授权，未执行真实 DeepSeek；`live_model_sample_count=0` | **P1/Open，阻断生产验收** |
| `DEF-REAL-AI05-003` Token 成本不可验收 | 已批准计价登记、费率错误拒绝测试和官方当前价格复核通过 | **Closed，保持关闭** |
| `DEF-REAL-AI05-004` 根环境污染常驻服务和迁移 | 003 探针 `10/10`；五服务解析值和三个运行容器均为 false；健康、数据库和迁移可用 | **Closed，保持关闭** |

### 6.2 工程与运行回归

| 测试项 | 实际结果 | 状态 |
| --- | --- | --- |
| 第四次独立候选/文档探针 | 首轮 3 通过、1 个测试预期错误；修正后 `4 passed` | 通过 |
| 003 号配置探针复核 | `10 passed` | 通过 |
| 002 号冻结证据复核 | `12 passed` | 通过 |
| Provider、评测、DLP 和配置聚焦测试 | `177 passed, 1 warning` | 通过 |
| 默认后端全量 | `1321 passed, 12 skipped, 2 warnings` | 通过 |
| 隔离 PostgreSQL 全量 | `1333 passed, 2 warnings` | 通过 |
| 空库迁移 | `001 -> 023` | 通过 |
| 单级回滚恢复 | `023 -> 022 -> 023` | 通过 |
| Ruff | `ruff check .` 通过 | 通过 |
| Ruff format | 235 个文件格式正确 | 通过 |
| mypy | 166 个源文件无类型错误 | 通过 |
| compileall | 退出码 0 | 通过 |
| uv 锁文件 | 125 packages resolved | 通过 |
| Python 依赖审计 | 124 个锁定包无已知漏洞或不良项目状态 | 通过 |
| 前端 lint / typecheck | 退出码 0 | 通过 |
| 前端测试 | 32/32 | 通过 |
| 前端生产构建 | Next.js 15.5.23；12 个业务路由及错误页生成 | 通过 |
| Compose 配置解析 | 退出码 0 | 通过 |
| 五服务 Compose 解析值 | backend、worker、jobs、agent-worker、retrieval-model-service 均为 `LLM_LIVE_EVAL=false` | 通过 |
| 生产 AI 开关静态检查 | 五个规范 AI 开关全部显式为 `false` | 通过 |
| 运行容器环境 | backend、worker、jobs 均为 `LLM_LIVE_EVAL=false` | 通过 |
| `/v1/health` | `status=ok` | 通过 |
| `/v1/health/ready` | database、redis、object_storage、llm_provider 为 `ok` | 通过 |
| 前端依赖审计 | 官方 registry 报告 3 个 High：Next.js 依赖链中的 PostCSS 和 sharp | 不通过；既有 `DEF-REAL-FS01-005` 保持 Open |
| 真实独立 DeepSeek 评测 | 未执行；真实模型样本数为 0 | **阻塞** |

默认与 PostgreSQL pytest 的两个警告仍为 Starlette/httpx 和 argon2 兼容弃用提示。Python、npm 审计在受限沙箱内首次因网络权限失败，获准后从 OSV 和 npm 官方端点重跑并取得上述有效结果。

主机通过端口 5432 直接执行开发库 `alembic current` 时出现连接中途关闭；同一时刻健康接口正常。随后在 PostgreSQL 容器内执行只读查询，确认开发数据库仍为 `022_ai_marketing_review`。隔离测试库已验证 023，但测试工程师没有越权修改开发库。

## 7. 失败项、缺陷与观察

### DEF-REAL-AI05-002：真实 DeepSeek 独立质量门禁仍无有效证据

| 项目 | 内容 |
| --- | --- |
| 优先级 | P1 |
| 类型 | 模型质量、安全、结构化输出、外部数据授权 |
| 状态 | Open |
| 是否阻断 | 是 |
| 建议负责 Agent | AIAgent开发工程师Agent、架构师Agent、测试工程师Agent、人类数据责任人 |

复现步骤：

1. 检查 034 号实施记录，可见其明确声明没有调用真实 DeepSeek，且 `DEF-REAL-AI05-002` 仍缺少一次性授权。
2. 检查本轮用户指令，只要求修复后再次测试，没有逐项批准指定数据集、外发内容、供应商、用途、结果留存和副作用边界。
3. 因此不得向外部 DeepSeek 发送开放集，本轮真实模型样本数保持 0。
4. 对照固定门禁，`live_model_sample_count > 0` 不满足，真实模型质量无法判定为通过。

实际结果：没有获准的独立 DeepSeek 输出，无法证明准确率、危险漏放、合法误拦截和 Provider 失败率达到生产标准。

预期结果：人类数据责任人批准下述精确范围后，在隔离 `integration/staging` 进程对当前候选执行一次真实 DeepSeek 评测，并满足全部固定质量门禁。

```text
数据集：测试工程师/evidence/REAL-AI-05-002/real-model-independent-v1.0.0.jsonl
数据集 SHA-256：7f7c7084ac37e9aef5c9b1a947a9f44250cd89e290f5ae18990ec558e5c6df94
外发内容：36 条合成 customer_message 与 synthetic_evidence
目标供应商：https://api.deepseek.com
用途：一次 REAL-AI-05 离线质量评测
结果留存：只保存低敏哈希、枚举、原因码、时延、Token 和成本，不保存模型正文
副作用：禁止工具、数据库业务写入和任何平台发送
```

### 观察项 OBS-REAL-AI05-007：开发数据库落后代码 head

开发数据库为 022，代码和隔离验证 head 为 023。该差异不影响本轮隔离测试结论，但应由全栈或数据库主责确认维护窗口；测试工程师不直接修改开发数据库。

### 观察项 OBS-REAL-AI05-008：不可变发布候选仍缺失

当前目录不是 Git 仓库。本轮逐文件摘要在测试前后稳定，但无法形成独立验证规范要求的提交、树、Diff 和受保护人类审批绑定。真实模型、SSE、稳定性和最终生产放行必须重新绑定同一不可变候选。

### 既有跨模块缺陷：DEF-REAL-FS01-005

npm 官方 registry 仍报告 3 个 High。该缺陷属于全栈开发工程师Agent负责的生产依赖安全范围，不是 REAL-AI-05 新缺陷；在修复并独立复测前，整体生产放行继续受阻。

## 8. 安全与代码审查结论

- 独立开放集只包含合成数据，正文和清单摘要保持冻结。
- 评测器在 Provider 调用前校验清单、摘要、样本覆盖、环境和 PII/DLP。
- 真实评测只允许 `integration/staging`，`production` 配置失败关闭。
- 根环境、常驻服务和生产 Compose 均保持真实评测关闭。
- 结果文件仍只允许低敏哈希、枚举、原因码、时延、Token 和成本；本轮未生成新的外部模型结果。
- 未发现 Key、Token、完整地址、客户隐私或模型正文进入本轮测试证据和报告。
- 034 号活文档没有把局部整改夸大为 REAL-AI-05 完成，也没有建立历史同义开关。

## 9. 回归结果和最终验收建议

**REAL-AI-05 第四次独立 AI 评测结论：阻塞，不通过生产验收。**

本轮确认 034 号状态同步正确，11 个候选文件、开放集、清单、配置隔离、工程回归、数据库迁移和运行健康均未退化。`DEF-REAL-AI05-001/003/004` 保持 Closed，没有新增 REAL-AI-05 产品缺陷。

但 `DEF-REAL-AI05-002` 仍为 P1/Open，原因是外部数据授权门禁没有完成，真实模型样本数仍为 0。不得把无网络契约测试、代码回归或开发侧历史结果解释为独立真实模型质量通过。

当前必须继续保持：

```text
LLM_LIVE_EVAL=false
AI_MARKETING_ENABLED=false
AUTO_REPLY_ENABLED=false
```

生产 Compose 中 `LLM_ENABLED` 和 `AI_TRANSLATION_ENABLED` 也继续保持 `false`。后续顺序固定为：

1. 人类数据责任人明确批准本报告列出的完整外发范围。
2. 重新核对候选、数据集和清单摘要。
3. 在隔离 `integration/staging` 进程临时注入 Key 和已登记费率，执行一次真实 DeepSeek 开放集评测。
4. 若全部 REAL-AI-05 门禁通过，再进入真实模型 SSE 50 个授权客户端和五日稳定性测试。
5. 生产发布前建立不可变候选、修复生产依赖 High 风险并取得架构师及人类产品/数据责任人放行。

## 10. 清理与交接

- 两次使用的 `postgres-test` 临时容器均已停止并删除，仅包含自动化测试数据；开发 PostgreSQL 未受影响。
- 没有停止、重建或修改现有 backend、frontend、postgres、redis、minio、worker 和 jobs 服务。
- 本轮未调用外部模型、业务工具或平台写接口。
- 产品候选聚合摘要在最后一轮验证后与开测前一致。
- 本报告完成后仅更新 `共享记忆文档/测试报告索引.md`；不新增测试工程师实施记录，不修改历史正式报告。
