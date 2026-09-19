# 双服务器 Split-Ingress Staging 部署设计

日期：2026-09-19
状态：对话设计已批准，待书面规格复核
目标环境：`staging`
公共域名：`staging.overselfx.com`

## 1. 目标与成功标准

把 CRM staging 部署为入口与业务运行分离的双服务器拓扑：

- `38.55.145.52` 只承担 DNS 目标、公信 TLS、宝塔 Nginx 和受限 SSH 反向监听；
- `192.168.110.210` 以 `crmdeploy` 的 Rootless Docker 运行完整 CRM；
- 旧服务器主动连接新服务器，公网服务器不需要访问旧服务器内网地址；
- CRM 与旧服务器现有系统 Docker、GitLab 和其他公司负载保持隔离；
- 首次上线只形成全部真实能力关闭的失败关闭部署和 G0 证据，不提前宣称 G1～G6、MVP 或 production 放行。

部署成功必须同时满足：域名和证书正确、隧道仅监听回环、CRM 健康端点通过、数据库迁移到当前头、容器健康、公司系统 Docker 前后无漂移、入口不再返回 GitLab，以及所有真实 TikTok/LLM/自动化能力仍关闭。

## 2. 用户已确认的决定

1. staging 使用双服务器入口分离方案，并要求实际登录两台服务器完成部署。
2. 反向隧道由旧服务器主动建立；HTTPS 只在新服务器终止，隧道内转发明文 HTTP。
3. 沿用已经准备好的 `/home/crmdeploy`，不创建 `/home/crmstaging`。
4. 旧服务器 `10080/10443` 已被公司 GitLab 占用，不修改 GitLab；CRM 改用当前空闲的回环端口 `18081`。
5. 新服务器反向监听继续使用 `127.0.0.1:18080`。

## 3. 现场已核实事实

### 3.1 新服务器 `38.55.145.52`

- Ubuntu 24.04.1 LTS、宝塔、Nginx 1.30.4 已运行；其他站点不属于本任务。
- DNS A 记录已经是 `staging.overselfx.com → 38.55.145.52`。
- Nginx 正监听 `80/443`，`127.0.0.1:18080` 已由 `crm-tunnel` 的 SSH 会话监听。
- `crm-tunnel` 为无登录 shell 的专用账号，授权键限制为回环 `permitlisten="127.0.0.1:18080"`。
- 当前 staging vhost 的 HTTP 主路径主动返回 `503 staging TLS is not ready`。
- 当前 443 证书不包含 `staging.overselfx.com`，公网证书校验失败。

### 3.2 旧服务器 `192.168.110.210`

- Ubuntu 26.04 LTS，系统 Docker 正运行 GitLab、数据库及其他公司容器。
- 系统 Docker 的 GitLab 已占用 `0.0.0.0:10080` 和 `0.0.0.0:10443`；这些端口和容器不得修改。
- `crmdeploy`、UID 1004、Rootless Docker socket、专用 Runner、模型六文件、受限隧道密钥和 `crm-staging.env` 已存在。
- Rootless Docker 数据根为 `/home/crmdeploy/.local/share/docker`，安全选项包含 `rootless`，当前没有 CRM 容器或镜像。
- `crm-staging.env` 权限为 `0600`；基础数据库、对象存储、JWT、检索服务及镜像变量已设置，TikTok 应用身份和 DeepSeek Key 留空，符合首次失败关闭部署。
- 当前隧道服务错误地把新服务器 `18080` 转到旧服务器 `10080`，因此隧道上游实际是 GitLab。
- 旧服务器 `127.0.0.1:18081` 当前空闲。

### 3.3 仓库现状

- 当前运行文档和 Rootless overlay 仍描述同机 `10080/10443` 入口，和本设计冲突。
- Git 历史提交 `960e62afcee40160f15a4aaf0f31e803f6c0a2ea` 曾实现并审查相同的 split-ingress 架构；服务器现有隧道来自该版本。
- 本次只把历史方案中仍适用的安全边界移植到当前 `src/` 布局，并把旧服务器目标端口从冲突的 `10080` 改为 `18081`；不得整体回退仓库或恢复已经废弃的目录结构。

## 4. 方案选择

采用“宝塔 Nginx + 受限反向 SSH 隧道 + Rootless CRM”的最小恢复方案：

```text
浏览器 / TikTok
    │ HTTPS :443
    ▼
38.55.145.52 宝塔 Nginx
    │ HTTP → 127.0.0.1:18080
    ▼
受限 SSH 反向隧道
    │ 38.55.145.52:127.0.0.1:18080
    │       → 192.168.110.210:127.0.0.1:18081
    ▼
crmdeploy Rootless CRM proxy :80
    ├── frontend
    ├── backend / workers / jobs
    ├── retrieval-model-service
    ├── PostgreSQL + pgvector
    ├── Redis
    └── MinIO
```

不采用：

- 调整或停止 GitLab 以腾出 `10080/10443`：会影响任务范围外的公司负载；
- 在旧服务器增加额外宿主机端口代理：没有必要，并增加故障与审计面；
- 在新服务器运行完整 CRM：资源与职责不匹配；
- 临时在服务器源码构建或使用浮动镜像标签：不可追溯，无法满足回滚和供应链门禁。

## 5. 端口与信任边界

| 节点 | 监听 | 用途 | 约束 |
|---|---|---|---|
| 新服务器 | `0.0.0.0/[::]:80` | ACME 与 HTTPS 跳转 | 仅 staging vhost；不影响其他站点 |
| 新服务器 | `0.0.0.0/[::]:443` | TLS 终止与公网入口 | 公信证书 SAN 必须包含 staging 域名 |
| 新服务器 | `127.0.0.1:18080` | SSH 反向监听 | 仅 `crm-tunnel` 可创建；禁止 GatewayPorts |
| 旧服务器 | `127.0.0.1:18081` | Rootless CRM proxy HTTP | 不发布到 LAN 或公网 |
| 旧服务器 | `0.0.0.0:10080/10443` | 现有 GitLab | 任务范围外，必须保持不变 |

公网 Nginx 是唯一可信代理。它必须覆盖而不是透传客户端伪造的 `Host`、`X-Real-IP`、`X-Forwarded-For` 和 `X-Forwarded-Proto`。旧服务器的 proxy 只接受回环连接，应用继续使用现有受控代理头配置。

## 6. 仓库改造范围

实施阶段应在单主题分支完成以下最小变更：

1. `src/compose/docker-compose.rootless-staging.yml`
   - proxy 只发布 `127.0.0.1:18081:80`；
   - 不发布 staging `10443`；
   - 所有真实平台、LLM、自动回复和营销能力继续被 overlay 固定为 `false`。
2. `src/deploy/staging/rootless/`
   - 恢复适配当前目录结构的反向隧道安装器和用户级 systemd 单元；
   - `ssh -R` 固定为 `127.0.0.1:18080:127.0.0.1:18081`；
   - 保持独立密钥、固定主机指纹、`ExitOnForwardFailure`、ServerAlive 和自动重启；
   - 不恢复同机 80/443 systemd 入口作为活动 staging 路径。
3. 新服务器入口资产
   - 提供只针对 `staging.overselfx.com` 的宝塔 Nginx 配置片段与验证脚本；
   - 包含 ACME、HTTPS 跳转、TLS、SSE/WebSocket、健康检查和安全日志约束；
   - 不管理宝塔面板账号、其他 vhost 或全局证书。
4. 门禁脚本、测试与当前文档
   - 更新 Rootless 端口契约、split-ingress 健康验证和低敏证据字段；
   - 同步 `SYSTEM.md`、`DEPLOYMENT.md`、`RELEASE-GATES.md`、运行手册、任务状态和项目恢复摘要；
   - 历史规格和计划保留为历史，不批量重写。

## 7. 镜像、配置与数据

- backend、frontend、retrieval-model-service 必须使用与最终候选 SHA 对应的 `repository@sha256:<64-hex>`；外部 PostgreSQL、Redis、MinIO 和 Nginx 也保持固定摘要。
- 部署前验证环境文件中的三个应用镜像可拉取、摘要匹配候选，且不输出环境正文或 registry 凭据。
- 不在服务器构建镜像，不使用 `latest`，不把 PAT、`.env`、私钥、模型或备份复制到仓库。
- 模型继续从 `/home/crmdeploy/assets/models` 只读挂载并按清单校验。
- PostgreSQL、MinIO 和 Rootless Docker 数据只落在 `/home/crmdeploy`；不得写入系统 Docker data-root。
- 首次部署没有兼容的上一版 CRM 运行实例，因此入口回滚应恢复失败关闭 `503`，应用回滚应停止候选容器并保留卷，而不是删除数据或切回 GitLab。

## 8. Nginx 与 TLS

只修改 `/www/server/panel/vhost/nginx/staging.overselfx.com.conf` 及该站点专属证书材料：

- 修改前记录文件元数据和 SHA-256，并保存权限受限的精确备份；
- 证书通过宝塔现有 ACME/证书流程签发，SAN 必须包含 `staging.overselfx.com`；
- 证书链、私钥匹配和有效期通过后才启用 443；
- `80` 保留 `/.well-known/acme-challenge/`，其余请求重定向到 HTTPS；
- `443` 的默认上游为 `http://127.0.0.1:18080`；
- `/v1/chat/query` 关闭 buffering，读取超时不少于 120 秒，并保留 SSE 心跳；
- OAuth callback 与 Webhook 日志不得记录 query、authorization、Token、`code` 或 `state`；
- 每次变更先执行宝塔 Nginx 的配置测试，成功后仅 reload，不 restart；失败时不得加载；
- 隧道或上游不可用时返回明确 `502/503`，不得 fallback 到默认站点或 GitLab。

## 9. 部署顺序与恢复点

1. 完成仓库实现、测试、审查和当前事实文档同步，形成候选 SHA。
2. 验证三个不可变应用镜像与候选 SHA；缺少候选镜像时停止，不临时改用标签或服务器 build。
3. 记录两台服务器端口、服务、磁盘、vhost、隧道和公司系统 Docker 五字段基线。
4. 在旧服务器把 Rootless proxy 端口和隧道目标切为 `18081`，验证远端 `18080` 仍只监听回环。
5. 在新服务器申请并验证 staging 公信证书；先保留公网 `503`，不提前切正常流量。
6. 使用当前门禁脚本执行 validate；不得把 validate 当作部署通过。
7. 以全部真实能力关闭的配置拉取并启动 Rootless Compose，等待全部健康检查。
8. 执行数据库迁移并验证迁移头、应用存活、依赖就绪和首页。
9. 更新 staging vhost 为 HTTPS 代理，`nginx -t` 成功后 reload。
10. 从外部验证 DNS、证书、首页、`/healthz`、`/v1/health`、`/v1/health/ready` 和 SSE；响应不得含 GitLab 标头或登录重定向。
11. 主动重启隧道服务一次验证自动恢复，再复核外部健康。
12. 比较公司系统 Docker 与其他站点的前后基线；任一漂移均停止并恢复 staging 入口到 `503`。

任何一步失败都停在最近恢复点，不串行尝试多个补救。不会自动删除容器、卷、备份、证书、账号、密钥或服务器目录。

## 10. 验证与证据

### 10.1 仓库验证

- Rootless overlay 的唯一宿主机发布是 `127.0.0.1:18081:80`；
- 隧道单元只允许新服务器回环 `18080` 到旧服务器回环 `18081`；
- Nginx 模板不含默认站点 fallback、明文凭据或 query 日志；
- Compose 合并配置、PowerShell 门禁、Shell/systemd 语法、静态检查和完整后端回归通过；
- secret scan 不包含真实配置、私钥、Token、证书私钥或生产数据。

### 10.2 现场验证

- DNS A 记录精确等于 `38.55.145.52`；
- 证书链可信，SAN 包含 staging 域名，HTTP 正确跳转 HTTPS；
- 新服务器 `18080` 和旧服务器 `18081` 仅监听 `127.0.0.1`；
- Rootless socket、安全选项、data-root、Compose 项目名和镜像摘要符合基线；
- CRM 容器健康，数据库迁移头正确，三个健康端点和首页通过；
- 公网响应不再出现 `X-Gitlab-*`、GitLab 登录重定向或其他站点内容；
- 隧道断开时失败关闭，重连后自动恢复；
- 系统 Docker 容器 ID、名称、镜像 ID、StartedAt、运行状态和端口前后无变化；
- 低敏证据记录候选 SHA、镜像摘要、配置摘要、时间、健康结果和回滚状态，不记录秘密。

## 11. 验收标准

- AC-01：仓库与运行文档统一描述双服务器 split-ingress，旧的同机 staging 入口不再是当前方案。
- AC-02：GitLab 的 `10080/10443` 和全部公司系统 Docker 负载零变化。
- AC-03：CRM Rootless proxy 只绑定旧服务器 `127.0.0.1:18081`。
- AC-04：反向隧道只绑定新服务器 `127.0.0.1:18080`，账号权限不扩大。
- AC-05：`staging.overselfx.com` 的 DNS、TLS SAN、证书链和 HTTP→HTTPS 通过。
- AC-06：公网入口只返回 CRM 或明确 `502/503`，永不返回 GitLab/其他站点。
- AC-07：所有 CRM 容器健康，当前数据库迁移头和三个健康端点通过。
- AC-08：首次部署的真实 TikTok、LLM、自动回复、营销和高风险能力全部关闭。
- AC-09：隧道重连、入口失败关闭和无数据删除的首次部署回退路径通过。
- AC-10：仓库测试、现场证据、IR/TR/RR、任务状态、当前架构和发布门禁结论一致。

## 12. 边界与后续阶段

本设计只完成 staging 基础设施和失败关闭部署。TikTok OAuth/读取、Webhook、人工消息、DeepSeek/RAG、50 客户端 SSE、五日稳定性、备份恢复和兼容版本回滚仍按 G1～G6/G0 的独立任务取得真实证据。production 继续使用 `www.overselfx.com` 的公共契约，但生产运行拓扑、服务器、证书和放行不由本 staging 设计自动决定。
