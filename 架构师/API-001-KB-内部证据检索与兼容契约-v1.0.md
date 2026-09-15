# 内部证据检索与兼容契约

| 项目 | 内容 |
| --- | --- |
| 文档编号 | API-001-KB |
| 状态 | 已确认；经 `验收-001-KB` 纳入 KB-G0 架构基线 |
| 日期 | 2026-09-15 |
| 适用范围 | K2 独立知识服务内部 API、K3 检索、CRM 与后续内部系统适配 |

## 1. 契约边界

知识服务只返回获准的公司自编证据，不生成最终答复、不执行平台动作、不返回实时订单/SKU/退款事实。认证和授权在检索前完成；请求正文中的应用名、空间或 `shop_ref` 只用于缩小查询，不能授予权限。

业务结果四态固定为 `ok | no_evidence | conflict | unavailable`。认证失败用 HTTP 401，主体已认证但无权访问请求级空间/店铺/市场/读者用 HTTP 403，两者不进入业务四态；请求格式错误用 400/422。授权权威本身不可用时返回 HTTP 503、`AUTHORITY_UNAVAILABLE`，不生成业务四态信封。已知且在已授权请求范围内的冲突必须为 `conflict`，不得降成 `no_evidence`。只有请求级授权、权威元数据、索引、Embedding、召回和重排均正常完成但无合格证据时才允许 `no_evidence`；通过请求级授权后发生的数据库、模型、索引代际或内容元数据故障返回业务 `unavailable`，禁止退化为单路检索或自由生成。若服务崩溃到无法形成合法业务信封，则由网关返回普通 HTTP 503，不伪造四态结果。

## 2. 内部查询 DTO

`POST /internal/v1/evidence:search`

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `request_id` | 是 | 调用方生成的低敏追踪 ID |
| `query` | 是 | 查询文本；日志不得保存全文 |
| `platform_code/market_code/language_tag/audience_code` | 是 | 完整适用范围，不允许未知市场回退 |
| `requested_space_codes` | 是 | 只能是已认证主体获准空间的子集 |
| `shop_ref` | 条件 | 请求 `shop_private` 时必填，但授权取自可信委托和服务端登记的交集 |
| `top_k` | 否 | 默认 5，上限由 K3 配置冻结 |

服务端从认证上下文取得 `application_ref`、委托主体、允许空间和允许店铺，不接受正文覆盖。幂等性按 `request_id + application_ref` 只保证审计关联，不缓存跨授权结果。

## 3. 响应 DTO

| 字段 | 说明 |
| --- | --- |
| `status` | `ok/no_evidence/conflict/unavailable` |
| `request_id` / `trace_id` | 调用与服务追踪 |
| `index_generation_id` | 完整激活的索引代际；无可用代际时不得返回 `ok` |
| `retrieval_profile_version` | 切片、Dense/Lexical/RRF、重排与门槛组合版本 |
| `evidence[]` | 仅 `ok` 返回已批准公司自编片段及机器可执行用途策略 |
| `conflicts[]` | 仅 `conflict` 返回低敏冲突组和人工处理引用，不返回胜者 |
| `reason_code` | `no_evidence/unavailable` 的稳定低敏原因码 |
| `retryable` | 只对技术性 `unavailable` 表达是否可重试 |

每条 `evidence` 必须包含：`content_version_id`、`content_sha256`、`chunk_id`、`source_id`、官方 `source_url`、平台/市场/语言/读者/空间、条件性 `shop_ref`、`approval_ref`、有效期、`index_generation_id`、Dense/词法/RRF/重排分数及各分数类型。还必须携带 `usage_policy={rights_basis_ref,allowed_app_refs,allowed_space_codes,external_model_allowed,automatic_delivery_allowed,forbidden_uses}`，消费端必须执行而非忽略。重排 logit 只能用于排序，不标为概率或置信度。`RGT-TK-US-PUBLIC-001` 范围内 `external_model_allowed=false`、`automatic_delivery_allowed=false`，不得返回官方原文或官方片段，只返回获批公司自编内容和官方链接。

稳定原因码首版固定为：`NO_CURRENT_APPROVED_EVIDENCE`、`NO_SCOPE_MATCH`、`NO_ELIGIBLE_EVIDENCE`、`ACTIVE_SOURCE_CONFLICT`、`INDEX_GENERATION_UNAVAILABLE`、`INDEX_VERSION_DRIFT`、`CONTENT_METADATA_INVALID`、`EMBEDDING_UNAVAILABLE`、`RERANKER_UNAVAILABLE`、`DATABASE_UNAVAILABLE`。来源撤销/过期、版本未批、内容级 `allowed_app_refs` 不含当前应用或内容适用范围不匹配时，健康检索结束后统一返回 `no_evidence` 与不泄露具体存在性的通用原因；请求级越权仍为 403。只有已授权范围内登记的冲突可返回 `conflict/ACTIVE_SOURCE_CONFLICT`。技术原因码不得包含 Token、店铺平台 ID、查询全文或未授权来源标题。

## 4. 语义、形态和状态映射

安全语义沿用 ADR-005 的唯一枚举：`policy | technical_artifact | customer_instance_fact | non_assertive_proposition | unknown`。`knowledge_shape=A/B/C/D` 与 `content_kind=rule/guide/faq/case` 仅描述内容形态，不参与提升权限。当前三类政策内容均为 `statement_type=policy`、`knowledge_shape=B`。

新服务使用彼此独立的状态机：`content_status=draft|reviewed|approved|revoked`，`approval_status=pending|approved|rejected|revoked`，`index_state=not_indexed|building|ready|failed|stale`。`service_eligibility` 不是可人工写入的状态，而是由当前内容与审批、来源许可、应用/空间/店铺授权、市场/语言/读者、时效、冲突和当前激活 `ready` 代际共同推导。撤销、过期、冲突、授权失效是即时不可服务条件；`index_state=ready` 只表示候选代际技术完整，不能单独使内容可服务。CRM 的 `published + ready + approved_for_internal_review` 仅用于旧记录映射，不直接成为新服务批准事实。

为避免审批—索引—测试循环：内容负责人、来源权利和必要专业复核均接受且绑定精确哈希后，可把候选版本置为 `content_status=approved`、`approval_status=approved`，仅在隔离评测命名空间构建 `ready` 候选索引；此时生产 `service_eligibility=false`。测试工程师独立验收通过、发布记录完成后，才原子激活该代际并重新推导服务资格。测试失败时将候选代际标为 `failed/stale`，内容批准事实可以保留，但不能对正式查询服务。

## 5. CRM 与第二系统适配

- CRM 通过服务端适配器调用，不让浏览器直接调用知识服务。
- `ok` 映射为内部建议所用证据；`no_evidence` 进入安全无知识路径；`conflict` 与 `unavailable` 强制人工复核/转人工，不能继续自由生成。
- CRM 适配器必须检查每条证据的 `usage_policy`；当 `external_model_allowed=false` 时，不得把证据正文、摘要或可逆派生内容加入 DeepSeek/OpenAI/Claude 等外部模型 Prompt，只能在获准内部界面展示或交给另行获批的本地处理链路。
- 401/403 不自动重试；技术 `unavailable` 最多一次有界重试，仍失败则转人工。
- 第二系统必须注册不同 `application_ref`、audience 凭据和权限；不得复用 CRM 前端 JWT 或共享全能密钥。
- 现有公开 API 与 ADR-005 的 `automatic_delivery_allowed=false` 不因适配而改变。

## 6. 版本与索引代际

内容、审批和索引分别版本化：`content_version_id/content_sha256`、`approval_ref`、`index_generation_id`。索引代际还要记录 Embedding/Tokenizer revision、parser/chunker version、Dense/Lexical/RRF 配置、Reranker revision、构建时间和状态。新代际完整构建并通过校验后原子切换；部分索引、版本漂移或损坏元数据返回 `unavailable`。正文、范围、许可或审批改变时，旧索引立即失去服务资格，不等待物理删除。

## 7. K2/K3 验收

- K2：OpenAPI/Pydantic 契约、401/403、四态、错误码、超时与审计测试完成。
- K3：四态、错误市场/语言、冲突、撤销、过期、索引代际、引用字段、外部模型禁止传递和依赖故障测试完成。
- 任一契约字段变化必须升版本并重新执行 CRM 和第二系统契约测试。
