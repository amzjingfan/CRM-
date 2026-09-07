# TikTok 本地真实店铺联调配置实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；关联 REAL-FS-01、REAL-FS-02、REAL-FS-03 |
| 模块编号 | M00、M01 |
| 主责 Agent | 全栈开发工程师Agent |
| 协作 Agent | 架构师Agent、测试工程师Agent |
| 实施状态 | 部分完成 |
| 开始日期 | 2026-09-01 |
| 完成日期 | 未完成 |
| 代码位置 | `CRM智能聊天系统/` |

## 2. 需求与依据

- 产品需求：真实 TikTok 店铺优先用于本地 MVP 联调和演示。
- 接口依据：`共享记忆文档/管理端接口文档.md` 及现有 TikTok OAuth、渠道和店铺管理接口。
- 架构依据：`架构师/ADR-004-REAL-真实平台与DeepSeek生产接入边界-v1.0.md`。
- 任务依据：`全栈开发工程师/PLAN-002-REAL-真实TikTok与DeepSeek运行面实施计划-v1.0.md` 中 REAL-FS-01～REAL-FS-03。
- 验收依据：`架构师/PLAN-001-REAL-真实平台与AI生产环境接入实施计划-v1.0.md`。
- 代码规范：`共享记忆文档/代码编写手册.md`。

## 3. 目标、范围与非目标

### 3.1 实施目标

- 将当前 Quick Tunnel、公网 OAuth 回调和本机出口 IP 注入本地运行环境。
- 创建真实 TikTok 店铺对应的 CRM 店铺隔离边界。
- 为 TikTok Partner Center 回调地址、IP 白名单和 OAuth 联调做好本地准备。

### 3.2 实施范围

- 本地 `.env` 的临时公网地址、CORS、OAuth 市场、OAuth 回调和出口 IP。
- Backend、Worker、Jobs 配置重载。
- CRM 本地真实店铺记录。
- Quick Tunnel 公网登录页和健康检查验证。

### 3.3 非目标

- 本记录不放行真实读写开关、自动回复、主动营销、发券或修改地址。
- 不在文档中记录 App Secret、DeepSeek Key、OAuth Token、完整回调临时主机名或出口 IP。
- 不将临时 Quick Tunnel 地址视为生产固定域名。

## 4. 实施前确认

- [x] 已读取共享记忆文档文件清单。
- [x] 已读取相关 PRD、接口、任务拆解和验收标准。
- [x] 涉及配置修改时已读取代码编写手册和适用 Skill。
- [x] 已确认 Phase、任务编号、模块编号和主责 Agent。
- [x] 已确认依赖、风险和验收方式。

## 5. 实施方案

### 5.1 方案说明

保持现有真实平台功能开关关闭，只更新本地联调所需的运行时地址和网络信息。CRM 内部先创建一个美国 TikTok 真实店铺记录，随后在 TikTok Partner Center 配置同一 OAuth 回调和出口 IP，完成授权后再按门禁逐项开启只读能力。

### 5.2 依赖关系

- 前置依赖：本地 Docker Compose、Quick Tunnel、真实 TikTok 应用凭证和 Partner Center 开发者账号。
- 后续依赖：Partner Center 登录、回调/IP 白名单保存、真实店铺 OAuth、只读 API 和 Webhook 冒烟。

### 5.3 风险控制

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| Quick Tunnel 地址重启后变化 | OAuth 回调失效 | 每次重启 Tunnel 后同步本地 `.env` 和 Partner Center |
| 本机公网 IP 变化 | TikTok API 请求被白名单拒绝 | 联调前重新查询出口 IP 并同步白名单 |
| Partner Center 未登录 | 无法保存应用设置 | 保留登录页，等待账号持有人完成登录 |
| 真实开关误开启 | 可能触发真实平台动作 | 本次保持全部真实读写开关为 `false` |

## 6. 实际变更

### 6.1 文件变更

| 文件路径 | 变更类型 | 变更说明 | 负责 Agent |
| --- | --- | --- | --- |
| `CRM智能聊天系统/.env` | 修改 | 更新临时公网入口、CORS、OAuth 回调、美国市场和本机出口 IP；未修改或输出密钥 | 全栈开发工程师Agent |
| `CRM智能聊天系统/backend/app/integrations/oauth_router.py` | 修改 | OAuth 回调不再依赖发起浏览器的 CRM Cookie | 全栈开发工程师Agent |
| `CRM智能聊天系统/backend/app/integrations/oauth_service.py` | 修改 | 从一次性 state 恢复发起用户，并重新校验用户状态和店铺权限 | 全栈开发工程师Agent |
| `CRM智能聊天系统/backend/tests/test_tiktok_oauth.py` | 修改 | 增加跨浏览器回调契约并更新 state 用户恢复测试 | 全栈开发工程师Agent |
| `共享记忆文档/实施记录/Phase4-P4-00-全栈开发工程师Agent-TikTok本地真实店铺联调配置-013.md` | 新增 | 记录本轮本地联调配置、验证和阻塞项 | 全栈开发工程师Agent |
| `共享记忆文档/实施记录索引.md` | 修改 | 登记本实施记录 | 全栈开发工程师Agent |

### 6.2 接口、数据和配置变更

- API：无接口契约变更。
- 数据库：通过现有店铺管理接口新增 `HopHorseFit TikTok US`，编码 `hophorsefit-tiktok-us`，时区 `America/Los_Angeles`，币种 `USD`。
- 配置项：更新 `PUBLIC_BASE_URL`、`CORS_ORIGINS`、`TIKTOK_OAUTH_REDIRECT_URI`、`TIKTOK_OAUTH_MARKET` 和 `TIKTOK_EGRESS_IP`；真实平台读写开关保持关闭。
- AI：不适用。

### 6.3 关键实现说明

本轮没有增加依赖、脚本或抽象。真实密钥仍只存在本地 `.env`；实施记录不复制敏感值。Quick Tunnel 同时代理前端登录页和 `/v1` API，因此 OAuth 固定回调可通过前端代理转发到后端。TikTok 店铺常在独立指纹浏览器中授权，公开回调改为依赖 Redis 一次性 state 恢复发起用户；恢复后仍重新校验用户状态、店铺权限、唯一店铺、Scope 和凭证加密边界。

## 7. 验证记录

| 验证项 | 命令或方法 | 预期结果 | 实际结果 | 状态 |
| --- | --- | --- | --- | --- |
| 出口 IP | `Invoke-RestMethod https://api.ipify.org` | 返回当前公网 IPv4 | 与用户确认值一致 | 通过 |
| Quick Tunnel 主机 | 读取 cloudflared 本机指标 | 获取精确临时主机名 | 已获取并写入本地配置 | 通过 |
| 公网健康检查 | `Invoke-WebRequest {PUBLIC_BASE_URL}/v1/health` | HTTP 200 | HTTP 200 | 通过 |
| 公网登录页 | `Invoke-WebRequest {PUBLIC_BASE_URL}/login` | HTTP 200 | HTTP 200 | 通过 |
| Compose 服务 | `docker-compose.exe ps --format json` | 核心服务运行 | Backend、Frontend、PostgreSQL、Redis、MinIO、Worker、Jobs 均运行；带健康检查的服务为 healthy | 通过 |
| 店铺创建 | 本地店铺管理页面 | 新店铺可见且 active | `HopHorseFit TikTok US` 已创建并显示 active | 通过 |
| OAuth 专项回归 | `uv run pytest tests/test_tiktok_oauth.py -q` | 跨浏览器回调、state、凭证和隔离通过 | 27 passed | 通过 |
| OAuth 静态检查 | Ruff、format、mypy | 无格式、Lint 和类型错误 | 全部通过 | 通过 |
| 修复后公网健康检查 | `Invoke-WebRequest {PUBLIC_BASE_URL}/v1/health` | HTTP 200 | HTTP 200 | 通过 |
| Partner Center 配置 | TikTok Partner Center | 保存回调地址和 IP 白名单 | 用户截图确认已保存正确 | 通过 |
| 真实 OAuth 授权 | 紫鸟浏览器人工确认 | 返回 callback 并建立渠道 | 待用户在已登录紫鸟中点击授权 | 未执行 |

## 8. 实施结果

- 完成项：本地 `.env` 更新、服务重载、真实店铺记录创建、Partner Center 回调/IP 白名单、公网验证及跨浏览器 OAuth 回调修复。
- 未完成项：紫鸟中的真实店铺 OAuth 最终确认和只读冒烟。
- 与原方案差异：浏览器代理不能访问包含一次性 OAuth state 的外部跳转，最终授权必须由已登录紫鸟的账号持有人点击。
- 当前状态：部分完成；工程和平台配置已就绪，等待真实卖家授权确认。

## 9. 遗留问题与风险

| 编号 | 问题或风险 | 优先级 | 负责 Agent | 计划处理 Phase/任务 |
| --- | --- | --- | --- | --- |
| R-001 | 真实店铺 OAuth 最终确认必须由已登录紫鸟的账号持有人执行 | P1 | 用户、全栈开发工程师Agent | Phase4 / REAL-FS-02 |
| R-002 | Quick Tunnel 和本机出口 IP 均可能变化 | P1 | 全栈开发工程师Agent | 每次本地联调前 |
| R-003 | Customer Service Scope 仍在审核 | P1 | 用户、TikTok 平台 | Scope 审核完成后 |

## 10. 交接事项

- 交接给：用户、全栈开发工程师Agent、测试工程师Agent。
- 后续任务：在 TikTok Partner Center 登录后保存回调地址和 IP 白名单，执行单店铺 OAuth，再进行只读 API 与 Webhook 冒烟。
- 必须注意：Quick Tunnel 进程必须持续运行；真实写操作和自动化开关保持关闭，直到独立验证通过。

## 11. 文档同步

- [x] 已同步接口变化：无接口变化。
- [x] 已同步架构决策：沿用既有真实平台接入边界。
- [x] 已同步任务状态。
- [x] 已通知测试工程师需要覆盖的范围：后续需覆盖真实 OAuth、只读 API 和 Webhook。
- [ ] 测试报告索引将在正式测试完成后更新。
