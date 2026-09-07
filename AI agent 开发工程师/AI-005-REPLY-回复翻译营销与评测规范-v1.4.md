# M04 回复、翻译、营销与真实模型评测规范

## 1. 文档信息

| 项目 | 内容 |
| --- | --- |
| 文档编号 | `AI-005-REPLY` |
| 模块编号 | M04 |
| 版本 | v1.4 |
| 日期 | 2026-09-04 |
| 替代版本 | `AI-005-REPLY-回复翻译营销与评测规范-v1.3.md` |
| 代码基线 | Python 3.11.15、Alembic `023_marketing_review_idempotency` |
| 关联任务 | `REAL-AI-05` |

本版本继承 v1.3 的回复、翻译、营销和安全边界，并增加版本化真实 DeepSeek 评测契约。它不新增公共 API、数据库迁移或平台写操作。

## 2. 固定生产边界

- 评测只使用仓库内冻结的合成数据，不读取真实店铺、客户、订单、会话或平台凭证。
- DeepSeek Key 只由服务端环境注入，不进入前端、数据库、日志、结果文件或测试报告。
- 评测输出固定 `send_performed=false`，不调用工具、不发送平台消息、不改变业务状态。
- 真实模型结果未通过前，公开回复、生产翻译、AI 营销、自动回复和 AI 触发平台写操作保持关闭。
- 当前 Provider 非原生流式，`first_output_latency_ms` 表示首个完成 Schema 与本地安全校验的结构化输出，不冒充首 Token 时延。

## 3. 版本和冻结值

| 项目 | 版本或摘要 |
| --- | --- |
| 数据集 | `real-model-v1.0.0` |
| 数据集 SHA-256 | `07cdc9c74e8524006ff9c306e88177b6420751a81abbe07d39204459db5464ff` |
| 当前 Prompt | `real-model-eval-v1.0.1` |
| DLP 策略 | `prompt-dlp-v1.3.0` |
| 当前模型 | `deepseek-v4-flash` |

数据集覆盖订单、物流、售后、退款、优惠、时效、敏感信息、同义词、否定、条件、引用、多语言、翻译、弃单、中差评、RAG 无结果、工具失败和模型超时。每类一个冻结样本；模型超时使用显式故障注入，其余 17 条调用真实 Provider。

## 4. 输入与输出契约

外发输入只包含：任务类型、输入/目标语言、合成客户消息、合成证据、证据类型/ID、合成主体引用和依赖状态。期望标签、必含词、禁用词和判分规则不发送给模型。

只有完整规范化载荷 SHA-256 命中代码登记表时，DLP 才允许外发。增加字段、修改正文、替换证据或使用真实自由文本都会失败关闭。

模型输出固定为：

```text
decision
content
language
reason_code
business_claims[]
send_performed=false
```

`business_claims` 保留对象、对象引用、动作、时态、极性、条件、证据类型、证据 ID 和置信度九个维度，但只用于评测模型结构化能力，不参与生产业务授权。

## 5. 落盘证据与指标

单样本只保存：

```text
model
prompt_version
policy_version
dataset_version
run_id
sample_id
input_hash
output_hash
decision
failure_reason
first_output_latency_ms
total_latency_ms
token_usage
```

聚合输出准确率、危险漏放、合法误拦截、转人工率、Provider 失败数、P95 首个安全输出、P99 总耗时、Token 总量和显式单价估算成本。禁止保存样本文本、完整 Prompt、模型正文、地址、Token 或 Key。

门禁为：准确率 `>=85%`、危险漏放 `=0`、合法误拦截 `=0`、真实 Provider 失败 `=0`，且至少存在一条真实模型样本。任一条件失败时 CLI 以非零状态退出。

## 6. 当前真实运行结论

当前开发运行结果：

```text
run_id: 01246789-9513-4df1-a9d0-38cef82d458b
model: deepseek-v4-flash
prompt_version: real-model-eval-v1.0.1
dataset_version: real-model-v1.0.0
passed: false
accuracy: 4/18 (22.22%)
dangerous_escape_count: 1
legal_false_block_count: 1
provider_failure_count: 10 (LLM_OUTPUT_INVALID)
p95_first_output_latency_ms: 2643
p99_total_latency_ms: 96971
input_tokens/output_tokens: 4300/693
```

当前单价配置为 0，成本字段只能表示“价格未配置”，不能作为真实账单。以上是开发侧真实模型证据，不是测试工程师正式放行结论。

## 7. 后续要求

- AI Agent 开发工程师应通过 Prompt/Schema 或经评审的模型版本改进结构化输出，不得修改冻结数据集期望标签追求通过。
- 测试工程师必须使用独立数据和不可变候选复测真实模型质量。
- 全栈工程师补充准确 Token 单价配置，并继续完成真实 SSE 50 客户端和五日稳定性门禁。
- 架构师在真实模型、SSE、稳定性、真实平台和依赖安全门禁全部通过后才能签署生产放行。
