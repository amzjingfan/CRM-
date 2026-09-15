# AUTH-TK-US-001 `tkw api` 授权证据包

## 1. 证据包信息

| 项目 | 内容 |
| --- | --- |
| 证据编号 | `AUTH-TK-US-001` |
| 证据级别 | 公司内部低敏；不得对外传播 |
| 目标平台 | TikTok Shop |
| 目标市场 | 美国（US） |
| 目标应用 | `tkw api` |
| 取证时间 | 2026-09-15 09:03（UTC+08:00） |
| 取证方式 | 在用户已登录的 Seller Center 与 Partner Center 中只读查看；未触发重新授权、取消、Scope 开关或发布 |
| 技术复核人 | 架构师Agent（依据项目负责人在当前会话中的授权） |
| 结论状态 | 店铺侧与应用侧授权存在性通过；令牌、CRM 绑定和知识使用权待复核 |

## 2. 脱敏证据

### 2.1 店铺侧授权

证据来源：Seller Center `我的应用和事件`，页面路径 `/services/authorizations?shop_region=US`。

| 字段 | 核验值 |
| --- | --- |
| 应用名称 | `tkw api` |
| 服务状态 | 生效中 |
| 服务类型 | 非公开 |
| 开始日期 | 2026-07-24 18:45（平台页面未展示时区） |
| 结束日期 | 无限期 |
| 店铺地区 | 美国（US） |

同一页面中的旧 `CRM` 应用显示为已取消，因此不作为本项目当前授权依据。

### 2.2 开发者侧应用

证据来源：Partner Center `应用和服务`及 `tkw api` 管理页。

| 字段 | 核验值 |
| --- | --- |
| 应用状态 | 开启 |
| 应用类型 | 自定义 TikTok Shop 商家应用 |
| 目标卖家 | 美国本地商家；跨境商家（中国） |
| OAuth 回调 | 与项目 staging 回调契约 `https://staging.overselfx.com/v1/integrations/tiktok/oauth/callback` 一致 |

应用 ID、应用密钥和应用密码属于敏感凭据或受限标识，已在本证据包中删除。

### 2.3 应用级 API Scope

证据来源：Partner Center `管理 API` 页面。

- 页面显示共 27 项 Scope，其中 26 项生效、1 项未生效。
- 首批三类场景相关且在应用侧显示生效的 Scope：
  - 客服：`seller.customer_service`；
  - 订单信息：`seller.order.info`；
  - 物流与履约：`seller.logistics`、`seller.fulfillment.basic`；
  - 商品信息：`seller.product.basic`、`seller.global_product.info`；
  - 店铺信息：`seller.shop.info`。
- 唯一显示未生效的 Scope 为 `seller.redeem_info.write`，不属于首批三类试点的必要权限。
- `seller.customer_service` 与 `seller.order.info` 在平台页面标记为敏感数据范围，调用结果不得直接进入公司共享知识空间。

应用侧 Scope 状态不等同于具体店铺令牌的 `granted_scopes`。本项只能证明应用具备申请/承载相应权限的条件。

## 3. 脱敏与保管说明

以下内容未写入 Git，也不得补录到本文件：真实店铺 ID、应用 ID、应用密钥、应用密码、Access Token、Refresh Token、OAuth 授权码、买家信息、订单号和 API 原始响应。

会话中生成的裁剪图只展示 `tkw api` 名称和店铺侧生效状态，不作为长期原件。长期审计以本低敏记录、平台审计日志和受控运行环境的验证结果相互印证；若归档原始截图，必须存入公司受控存储并先遮盖上述字段，仅在本文件补不可公开的受控引用编号。

## 4. 复核与签署结论

| 复核项 | 结论 | 说明 |
| --- | --- | --- |
| 当前 US 店铺存在 `tkw api` 授权 | 通过 | Seller Center 显示生效中、非公开、美国（US）、无限期 |
| `tkw api` 应用处于可用状态 | 通过 | Partner Center 显示开启，目标卖家范围包含当前试点类型 |
| 首批三类场景的应用级 Scope | 通过 | 相关 Scope 在应用管理页显示生效 |
| 具体店铺令牌实际 Scope | 待复核 | 尚未读取受控令牌的 `granted_scopes` |
| Get Authorized Shops 只读调用 | 待复核 | 当前 TTS Open Toolkit 未登录，且未取得受控 CRM 运行时令牌 |
| CRM `channel_accounts` 店铺绑定 | 待复核 | 平台页面不能证明 CRM 内部映射 |
| 店铺数据保存、向量化与跨系统使用权 | 未批准 | 平台授权不自动等同于公司共享 RAG 使用许可 |

架构技术复核签署：**部分通过 / 门禁延期**。

本签署确认平台页面上可观察到的授权状态和最小技术范围，不替代产品负责人对实际业务店铺的确认、全栈工程师的令牌与 CRM 绑定核验、测试工程师的独立测试，也不替代平台协议、隐私或法务审批。在后四项完成前，不得启用 `shop_private` 数据摄取，不得将订单、客服或其他店铺私有数据写入公司共享 RAG。
