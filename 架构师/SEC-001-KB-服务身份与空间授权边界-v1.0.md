# 知识服务身份与空间授权边界

| 项目 | 内容 |
| --- | --- |
| 文档编号 | SEC-001-KB |
| 状态 | 已确认；经 `验收-001-KB` 纳入 KB-G0 架构基线 |
| 日期 | 2026-09-15 |
| 决策目标 | 固定 K2 可实现的内部应用身份、委托上下文、撤销与失败关闭边界 |

## 1. 身份模型

每个内部消费系统登记唯一 `application_ref` 和独立非对称签名凭据。首批签发者为公司内部服务身份签发组件，知识服务只接受精确 `issuer=company-service-identity`、`audience=company-knowledge-service` 的短时 JWT；算法限定 ES256 或 EdDSA，必须带 `kid`，公钥通过受控配置/密钥服务分发。禁止 HS256 共享全能密钥、CRM 前端 JWT 和 `RETRIEVAL_MODEL_SERVICE_TOKEN` 作为消费系统身份。

应用 JWT 最长 TTL 5 分钟，JWT Header `typ=service_access+jwt`，Claims 必须含 `token_type=service_access`、`iss/aud/sub/application_ref/iat/nbf/exp/jti`，且 `sub` 必须与 `application_ref` 完全相等。知识服务对该 Token 使用独立校验配置，校验类型、算法白名单、签发者、受众、时间、`kid`、应用启用状态和 `jti` 撤销状态；时钟偏差最多 30 秒。`jti` 在每次签发时唯一，用于撤销和异常重复使用审计，但短时 Bearer Token 在有效期内不是一次性 Token；幂等重试可复用，不能靠单次消费防重放。私钥只保留在签发服务，Git 和日志不得记录。

## 2. 店铺委托与授权求交集

`company_shared` 不需要店铺委托，但仍受应用、市场、语言和读者许可限制。`shop_private` 查询必须同时满足：有效应用主体、可信业务后端签发的短时委托、服务端 `application_ref ↔ shop_ref ↔ space` 授权登记、来源/内容版本自身许可。最终权限是这些集合的交集。

委托 JWT 最长 TTL 2 分钟，JWT Header `typ=shop_delegation+jwt`，由公司内部业务委托签发组件签发，精确 `issuer=company-business-delegation`、`audience=company-knowledge-service`，算法同样限定 ES256 或 EdDSA，并强制 `kid`。它至少含 `token_type=shop_delegation`、`sub=delegated_subject_ref`、`application_ref/shop_ref/allowed_space_codes/iat/nbf/exp/jti`；知识服务使用与应用 Token 分离的校验配置，禁止两类 Token 互换。其中 `application_ref` 必须与同一请求的已验证应用 JWT 完全相等，否则 403。正文 `shop_ref` 只能与已验证委托相等，不能扩大委托；稳定 `shop_ref` 由公司店铺授权权威映射，不能使用店铺名称、平台 Token 或用户输入的平台 ID。委托 `jti` 规则与应用 JWT 相同：每次签发唯一、支持撤销和异常审计，但在两分钟有效期内允许同一授权上下文的有界幂等重试。

## 3. 生命周期与撤销

| 事件 | 最长生效时限 | 行为 |
| --- | --- | --- |
| 应用禁用/密钥撤销 | 5 分钟，紧急拒绝清单 1 分钟 | 密钥、`kid` 或具体凭据撤销返回 401；已认证应用主体被禁用返回 403；缓存不得超过凭据剩余 TTL |
| 用户/委托主体禁用 | 2 分钟 | 私有查询拒绝；共享查询按应用权限重新判断 |
| 店铺撤权或绑定移除 | 2 分钟 | `shop_private` 立即 403，旧索引不得继续服务 |
| 来源许可/内容版本撤销 | 权威状态提交后立即 | 返回非 `ok`，物理索引清理异步 |
| 授权权威不可用 | 即时 | 失败关闭为 503/`unavailable`，不使用过期授权缓存 |

公钥轮换采用新旧 `kid` 短时重叠，重叠期不超过最长 Token TTL；旧 `kid` 到期后拒绝。紧急泄露时直接加入拒绝清单并审计。日志只记录不可逆主体引用、`application_ref`、`shop_ref`、决定、原因码、`jti` 哈希和时间，不记录 JWT、查询全文或平台 ID。

## 4. 错误边界

- 无凭据、签名/issuer/audience/时间/算法/Token 类型不合法，或密钥、`kid`、具体凭据已撤销：401。
- 主体已认证但应用被禁用，或应用对空间、店铺、市场、读者无权：403。
- 授权权威或密钥配置不可用：HTTP 503、`AUTHORITY_UNAVAILABLE`，不生成业务四态信封，不回退到缓存的扩大权限。
- 已认证授权后才进入 `ok/no_evidence/conflict/unavailable` 业务四态。

## 5. K2 强制测试

覆盖无 Token、过期、未来生效、错 issuer/audience、错误算法、未知/撤销 `kid`、重放 `jti`、应用禁用、委托主体禁用、跨应用、跨店、正文伪造 `shop_ref`、撤权传播、授权权威故障和日志脱敏。第二消费系统必须用不同 `application_ref` 与密钥完成同一组契约测试。上述测试未通过前，`shop_private` 与 API Data 开关保持关闭。
