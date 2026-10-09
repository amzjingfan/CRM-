# 系统架构

## 仓库与运行边界

`src/` 是唯一工程根，包含 Next.js 前端、FastAPI 后端、数据库迁移、部署资产、构建配置和测试。仓库根保留 Git/GitHub 元数据、`docs/` 当前契约与 `release/` 发布基线及低敏机器证据。仓库不再用人员角色划分代码或文档。

## 核心组件

- Next.js 管理端：登录、看板、客服工作台、知识库、营销、Agent 和团队配置。
- FastAPI API：认证、授权、协议校验、业务服务编排和 OpenAPI。
- Worker：Webhook、同步、检索、模型和可重试的异步任务。
- PostgreSQL + pgvector：业务事实、审计、幂等、知识版本和 1024 维向量。
- Redis：会话/限流、OAuth state、短期状态和任务协调。
- MinIO：受控对象存储。
- 模型服务：本地 BGE-M3 Embedding、bge-reranker-large 和受控 DeepSeek Provider。

当前数据库迁移头为 `024_tiktok_oauth_jobs`。迁移顺序是部署契约的一部分，禁止跳过或手工修改生产结构。

## 请求与消息流

1. 浏览器进入 API，认证中间件恢复用户和店铺授权范围。
2. 路由验证协议，服务层执行状态机、权限、幂等和审计。
3. 平台适配器负责 TikTok 等外部契约；Agent 不直接调用平台 SDK。
4. Webhook 先验证原始签名并落入内部事件，再由 Worker 幂等消费。
5. AI 请求先做字段允许列表和 DLP，检索已审批知识，必要时调用只读/受控工具。
6. 生成结果经过结构和安全校验后成为坐席建议；人工确认后才允许普通文本平台发送。

## 店铺隔离与权限

用户的店铺范围由服务端会话和授权关系计算。所有业务表查询、缓存键、审计和外部渠道映射必须包含内部店铺边界；客户端提供的标识只能用于定位，不能扩大授权。跨店铺访问、未知权限、失效 OAuth 和缺少幂等键均失败关闭。

## Agent 与工具边界

Agent 只能调用注册的白名单工具。工具层承担参数模型、店铺范围、角色权限、风险分级、幂等、超时、审计和输出字段过滤。订单、物流、优惠和政策事实以工具或已审批知识为准，模型不能生成或改写为事实。高风险工具与真实写入由独立配置关闭。

## 数据与知识

- 核心实体包括用户、店铺、渠道、会话、消息、订单投影、知识分类/条目/版本、Agent 配置、营销任务、工具调用、审计和幂等记录。
- 知识使用 `statement_type`、`customer_scope`、`document_version` 和逐版本审批；正文或语义范围变化会撤销审批。
- RAG 使用 BGE-M3 的 1024 维向量，Dense Top-20 后由 bge-reranker-large 取 Top-5，Dense 门槛为 `0.52`。
- DeepSeek 不是业务事实来源，模型输入仅包含固定允许字段和已过滤工具结果。

## 真实平台与失败关闭

TikTok OAuth Token 加密保存，state 哈希绑定并由现有 jobs worker 原子消费。公开 callback 将 state/code 认证加密到短期任务并快速站内回跳；任务按 state 摘要去重，终态清除密文，过期和崩溃不重用一次性 code。状态查询同时核对原发起用户与店铺权限。Webhook 在真实模式只按官方签名验证。消息写入只允许人工确认的普通文本；真实发送在持久化 `processing` 前锁定店铺行，同店铺已有 `processing` 或 `unknown` 出站消息时阻断新发送。平台超时或结果不确定时记录 `unknown`，随后按消息标识对账，禁止自动重复发送；进程中断留下的 `processing` 同样保持阻断，待人工核对事实后走受审恢复流程。

`AUTO_REPLY_ENABLED=false` 与 `REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED=false` 是当前安全基线。Shopee/Amazon 真实适配、公开自动回复、自动营销和高风险写入不属于 v0.1。

## 可观测与恢复

请求、任务、模型、检索、工具和平台调用使用可关联的 request/trace 标识，但日志不含密钥、Token、客户正文或完整 Prompt。备份、恢复、迁移和回滚必须使用发布基线中的版本与哈希，并通过真实演练后才可用于生产签署。

## Staging 运行拓扑

当前 staging 是入口与业务运行分离的双服务器部署：

```text
staging.overselfx.com:443
  → 38.55.145.52 宝塔 Nginx / TLS
  → 127.0.0.1:18080
  → 受限 SSH 反向隧道
  → 192.168.110.210:127.0.0.1:18081
  → crmdeploy Rootless proxy:80
  → frontend / backend / worker / jobs / agent-worker / data / retrieval model
```

公网服务器只保存站点 Nginx 与宝塔管理的证书，不运行 CRM、数据库或模型。业务服务器只通过 UID 1004 的 Rootless Docker 运行 `crm-staging`，其宿主机入口固定为 `127.0.0.1:18081:80`；系统 Docker 和 GitLab 的 `10080/10443` 不属于 CRM 操作范围。隧道账号无交互 shell，只能创建新服务器回环 `127.0.0.1:18080`，目标固定为旧服务器回环 `18081`。

TLS 只在公网宝塔 Nginx 终止，内层代理使用明文 HTTP 并覆盖 `X-Forwarded-Proto=https`。隧道、应用或证书未就绪时入口必须返回明确 `502/503`，不得回退到 GitLab、默认站点或其他 vhost。历史同机 systemd `80/443 → 10080/10443` 资产已从活动树移除，只能通过 Git 历史查看。

production 仅复用 `www.overselfx.com`、固定 HTTPS、不可变镜像和安全开关等公共契约；是否采用相同双服务器拓扑仍需独立架构与发布批准。

## TikTok 固定出站拓扑

TikTok 出站与上述公网入口是两条独立、最小权限的 SSH 链路，不复用账号、密钥、转发方向或允许目标：

```text
backend / worker / jobs
  → socks5h://tiktok-egress:1080
  → Rootless Compose tiktok-egress helper
  → crm-egress@38.55.145.52:22（独立 SSH 动态转发）
  → auth.tiktok-shops.com:443 / open-api.tiktokglobalshop.com:443
```

helper 只加入独立 `tiktok-egress` 网络，不发布宿主机端口；backend、worker、jobs 同时加入默认网络与该网络。TikTok HTTP 客户端统一显式设置代理并使用 `trust_env=False`，隧道不可用时连接失败，禁止回退到业务服务器的随机直连出口。`checkip.amazonaws.com:443` 只允许发布门禁验证实际出口，不用于业务请求。

staging 的 helper 使用与候选 backend 相同的不可变镜像，并在 Rootless Docker 内显式以容器 `0:0` 运行；该 root 只映射到宿主机 `crmdeploy`，用于读取其所有的 `0600` 私钥，不获得宿主机 root。密钥目录只读挂载给 helper，应用容器继续使用镜像默认非 root 用户且不得取得私钥。production 只继承相同的配置与失败关闭契约，实际拓扑、出口、账号和密钥尚未部署或放行。
