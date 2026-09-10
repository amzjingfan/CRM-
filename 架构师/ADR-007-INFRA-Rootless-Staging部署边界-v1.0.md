# Rootless Staging 部署边界

状态：已确认（设计）；Tasks 8/9 基础设施已就绪，应用真实运行验收待执行
日期：2026-09-09；2026-09-10 更新 staging 域名

## 1. 决策摘要

staging 暂时使用 `/home` 下的 Rootless Docker，由 `crmdeploy`（UID/GID 1004，home `/home/crmdeploy`）管理。production 的运行方案尚未决定；staging 可行性不授权 production 采用 Rootless 或系统 Docker。

本决策落实已批准的 `docs/superpowers/specs/2026-09-09-rootless-staging-deployment-design.md`。运维操作统一以 `CRM智能聊天系统/deploy/staging/rootless/README.md` 为准，独立验收仍使用生产放行检查表，不以本 ADR 替代测试结论。

## 2. 背景与约束

- 已有公司系统 Docker 负载运行，用户无权停止现有容器或迁移 Docker data-root；根盘空间有限，`/home` 有独立容量。
- 既有检查登记 Ubuntu 26.04 x86_64、Docker 29.6.2、Compose 5.3.1、systemd 259；这些是设计输入，实施当日必须重新预检。
- 专用用户已存在；root 只负责最小主机依赖、linger 和标准端口入口，不将用户加入 docker/sudo 组。
- 独立 staging 域名获准；当前执行环境的系统解析器已将 `staging.overselfx.com` 解析到 `183.158.225.78`，上游 NAT 由用户确认已配置，但入口尚未监听，公网 TCP/TLS 仍待应用部署阶段复验。公信 TLS、服务器模型和环境配置尚未取得实际部署证据。
- 仅覆盖 ADR-006 的 TikTok 人工辅助首版运行面。产品/UI 三平台概念保持，Shopee/Amazon 真实接入不在本次范围。

## 3. 架构决策

### 3.1 运行隔离

Rootless socket 固定 `unix:///run/user/1004/docker.sock`，Compose 项目名固定 `crm-staging`。数据预期位于 `/home/crmdeploy/.local/share/docker`，真实路径须经 `realpath` 和 `docker info` 确认为 `/home/crmdeploy/` 内，security options 须含 `rootless`。配置、TLS、模型、证据、备份、runner 和工具链均位于 checkout 外的 `/home/crmdeploy` 子目录。

系统 Docker、公司容器、网络和数据卷在项目边界外，禁止停止、重启、重建、迁移、修复和接管。bootstrap 在退出时保留系统容器五字段快照；任何差异或无法取证均失败关闭，不自动修复公司工作负载。

### 3.2 公网入口和固定回调

唯一公网入口为 root 管理的 `crm-staging-http.socket/.service` 和 `crm-staging-https.socket/.service`，在 80/443 使用 systemd socket proxy 转发到 `127.0.0.1:10080/10443`。Rootless proxy 只发布这两个回环端口；不开放 Docker TCP API，也不发布数据库和应用内部端口。

| 环境 | 公共地址 | OAuth callback |
| --- | --- | --- |
| staging | `https://staging.overselfx.com` | `https://staging.overselfx.com/v1/integrations/tiktok/oauth/callback` |
| production（integration 保留相同回调契约） | `https://www.hophorsefit.com` | `https://www.hophorsefit.com/v1/integrations/tiktok/oauth/callback` |

回调必须按 APP_ENV 精确匹配，不接受其他 scheme、主机、路径、query 或 fragment。Partner Center 的 staging Webhook 为 `https://staging.overselfx.com/v1/webhooks/tiktok`，配置和真实投递仍待后续门禁。2026-09-10 起旧 `staging.hophorsefit.com` 失败关闭，production 契约保持不变。

### 3.3 供应链和能力边界

工程通过 GitHub Flow 合并后，为完整 main SHA 发布三个不可变应用镜像；机器可读清单/发布制品是摘要权威。runner 使用已校验的官方工具链归档和仓库短期 Token，GHCR 拉取使用工作流短期 GITHUB_TOKEN。基础部署、回滚脚本固定关闭 Mock、全部真实 TikTok、LLM/live eval、翻译、营销和自动回复。

`基础运行面就绪`、`失败关闭部署通过`、`G1～G6 真实门禁通过`、`production 放行` 是四个独立结论，前者不推导后者。真实能力逐项开启需要另行受控配置与测试批准。

### 3.4 Runner 离线可信缓存

当 staging 主机无法稳定下载 GitHub Release 归档时，允许操作人在受控本地环境中仅从 `toolchain-manifest.json` 登记的官方 GitHub HTTPS URL 下载，先按清单 SHA-256 校验，再通过受保护 SSH/SCP 通道传入 `/home/crmdeploy/.cache/crm-toolchain/sealed-<manifest filename>`。该方式是官方制品的经验证转运，不是第三方镜像。

安装器必须从同一已校验清单导出官方文件名，并在解压前重新校验 `/home/crmdeploy` 及安装路径遍历到的每一个既有目录均为 UID 1004 拥有、非符号链接的目录且不可被组/其他用户写入；新建目录继续受 `umask 077` 约束。缓存文件还必须是 UID 1004 拥有、不可被组/其他用户写入的非符号链接普通文件，并与清单 SHA-256 一致。路径存在但任一检查失败时必须硬停，禁止退回网络绕过；只有路径完全不存在时，才可使用原官方 URL 的直连下载流程。无论来源，都必须走“摘要通过 → 私有临时目录解压 → 原子提升”的唯一路径。

Runner 注册所用安装器、工具清单和用户 unit 必须来自干净 `main` 的同一 40 位合并 HEAD。三项资产先传入唯一临时目录，逐文件完成类型、链接、UID 1004、组/其他写权限、本地/远端 SHA-256 和 Bash 语法校验，再原子提升为带 HEAD 的版本目录。每个 bootstrap/cache 的 prepare、verify/promote SSH 调用都必须重新验证所依赖父路径和临时/目标路径，不依赖前一进程检查，也不得依赖 `install -d -m` 修正既有不安全权限。Token 阶段重新推导 HEAD、重算三项本地摘要，并在申请短期 Token 前完成一次同等强度的远端最终复验；携带 Token 的 SSH 还必须在同一个远端进程内先再次执行完整复验，全部成功后才从 stdin 规范化 Token 并调用该版本安装器。Token 不得进入命令参数、文件、环境或输出，且禁止依赖前一个 SSH 的检查结果。

## 4. 影响与后果

- 镜像和数据消耗 `/home`，系统 Docker 不承载 CRM；Rootless 自身的网络/cgroup、原生依赖和性能仍需 Ubuntu 现场验证。
- 入口增加四个可独立撤除的系统单元；socket active 仅说明监听，不代表后端或 TLS 健康。
- TLS 私钥由 root 管理且 crmdeploy 只读；轮换由域名/主机管理员负责，仓库不保存 CA/DNS 凭据。
- 模型清单目前只包含两份权重摘要，六文件中的其他四个 JSON 文件需要后续补齐可信摘要证据。
- 历史 `f7c0f9f9` 镜像不支持 staging 专用回调，不可未经兼容性确认作为成功回滚目标；不通过修改 production 回调解决此问题。

## 5. 未采用方案

- 迁移系统 Docker data-root 或给根分区重新分配 `/home` 容量：超出公司容器授权范围，不能在本项目实施。
- RootlessKit 增加低端口 capability：扩大权限边界且升级可能丢失 capability。
- 只暴露公网高端口：不满足本次标准 HTTPS OAuth/Webhook 入口约定。
- 直接决定 production 部署方案：尚无 staging 实测和容量/恢复证据。

## 6. 回滚边界

先关闭最小能力，使用已批准兼容的上一版 RepoDigest 回滚应用；保留数据库、对象和审计。入口撤除只针对四个精确 CRM unit，先校验归属再停用/删除，命令见唯一运行手册。系统 Docker 不变；runner 注销、Rootless 卸载、镜像/卷或 `/home/crmdeploy` 数据删除需要单独明确批准。

## 7. 验收与责任

- 全栈开发工程师Agent：主机资产、Rootless/Compose、runner、部署和恢复操作及低敏证据。
- 架构师Agent：隔离、兼容回滚、生产方案与逐级放行决策。
- 测试工程师Agent：Ubuntu 运行、失败路径、公司容器不变、健康、恢复/回滚及 G1～G6 独立复核。
- 共享记忆文档Agent：单一报告、实施记录和两个索引的一致性。

截至 2026-09-10，Tasks 8/9 的 Rootless 主机与 runner 已通过独立只读复核，DNS A 记录已解析到目标公网 IP；TLS、模型、配置、候选镜像、公开健康、恢复/回滚和 G1～G6 仍待验证。production 未放行。
