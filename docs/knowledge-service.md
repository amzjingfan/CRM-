# 公司级独立知识服务

## 定位与当前状态

公司级知识服务为多个内部系统提供“可授权、有效、可追溯”的知识证据，不负责生成回复、执行业务动作或直接向买家发送内容。CRM 是首个计划消费系统；第二个实际内部系统尚未选定。

K1 来源治理与 K2 独立服务底座已有工程交付。K2 可以独立启动，但 K3 索引与检索、K4 TikTok Shop 静态资料同步、CRM 切流、K5 第二系统复用和生产放行均未完成。当前默认检索器在没有活跃索引代次时返回 `unavailable/INDEX_GENERATION_UNAVAILABLE`，不能据此声称已有可检索内容。

## 数据与运行隔离

- 独立 FastAPI 入口：`app.knowledge_service.main:create_configured_app`。
- 独立数据库：`company_knowledge`，使用单独 SQLAlchemy metadata、Alembic 历史以及 migration/runtime 最小权限角色。
- 当前知识迁移头：`005_kb_governance_constraints`，不引用 CRM 的 `stores`、`users`、`knowledge_documents` 或 `knowledge_chunks` 外键。
- 独立对象桶：`company-knowledge`，使用专用服务账号和前缀受限策略。
- Compose 叠加：`CRM智能聊天系统/docker-compose.knowledge.yml`。

项目 PRD、代码、接口说明、测试、日志和实施历史只能作为建设依据，不得进入 RAG 语料。客户当前订单、物流、退款等实例事实继续来自可信业务 API。

## 身份与授权

应用身份和店铺委托身份使用 ES256/EdDSA 非对称 JWT，分别校验 `typ`、`kid`、issuer、audience、token type、有效期和撤销 JTI。授权结果取以下范围的交集：

1. 应用 Token 允许的空间；
2. 店铺委托 Token 的主体与空间；
3. 服务端应用/空间/店铺 grant；
4. 内容版本自身的平台、市场、语言、读者和店铺策略。

`company_shared` 不允许携带 `shop_ref`；`shop_private` 必须同时通过应用身份、委托身份和服务端授权。请求正文中的店铺标识不能提权。无效身份返回 401，已认证但超范围返回 403，授权权威或强制审计不可用返回 503。

## 内部证据 API

- `POST /internal/v1/evidence:search`：返回 `ok`、`no_evidence`、`conflict`、`unavailable` 四态及稳定 reason code。
- 应用凭证使用 Bearer Token；店铺委托凭证使用 `X-Shop-Delegation`。
- 响应出口再次校验授权范围；元数据损坏、索引不可用、超时或范围不一致时失败关闭。
- 响应与审计共享 `trace_id`。日志和审计只保存低敏标识与 JTI 哈希，不记录 Token、查询正文、知识正文、客户信息或真实店铺 ID。

## 内容治理

覆盖单元由领域、平台、市场、语言、读者、空间及条件性店铺范围组成。一级领域固定为平台运营、商品选品、定价营销、支付订单、仓储物流、售后争议、客服流程、税务合规。

来源与内容版本分开登记。内容只有在来源许可、适用范围、当前版本审批、复核有效期和独立 QA 全部满足时才可生效。来源冲突不能靠向量分数选赢家；过期、撤销、未审批、高风险未复核或权限不可判定时不返回正式证据。

首批 TK US 内容只覆盖已批准的公司自编物流、售后和商品说明，机器版本位于 `release/knowledge-content/TK-US/`。这些内容仍不授予 CRM 公开自动回复或自动发送权限。

## 后续门禁

- K3：受控采集、解析、切片、索引、混合召回、引用及分域真实阈值/容量评测。
- K4：确认真实 TK 店铺、市场、Scope 和官方契约后进行静态资料同步及 CRM 人工建议影子/双读。
- K5：由已命名的第二内部系统使用独立身份完成授权、检索、拒绝、审计和撤销验证。
- 切流前必须保留旧 FAQ，逐步进行影子、双读、小范围灰度和回滚演练。
