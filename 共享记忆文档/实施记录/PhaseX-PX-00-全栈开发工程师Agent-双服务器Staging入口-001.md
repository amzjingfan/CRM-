# 双服务器 Staging 入口实施记录

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | PhaseX |
| 任务编号 | PX-00；关联 P4-11、REAL-FS-01/G0 |
| 模块编号 | M00 |
| 主责 Agent | 全栈开发工程师Agent |
| 协作 Agent | 架构师Agent、共享记忆文档Agent、测试工程师Agent |
| 实施状态 | 实施中；仓库工程完成到文档同步，PR/CI/服务器现场待执行 |
| 开始日期 | 2026-09-11 |
| 完成日期 | 未完成 |
| 分支/工作树 | `feature/split-ingress-staging` / `.worktrees/split-ingress-staging` |
| 基础提交 | `ed17ea55994764f954e50f9ad04dbe8f4ee5c5a3` |

## 2. 需求与依据

- 产品边界：TikTok OAuth、读取、Webhook、人工发送、AI 建议、RAG、工作台、知识库和看板；Shopee/Amazon UI 保留但不实现真实接入。
- 架构依据：用户批准的双服务器设计、`docs/superpowers/specs/2026-09-11-split-ingress-rootless-staging-design.md` 和 ADR-008。
- 任务依据：`docs/superpowers/plans/2026-09-11-split-ingress-rootless-staging.md`。
- 规范依据：产品需求、管理端接口、开发任务拆解、团队职责、MVP 验收、代码编写手册和实施记录规范。

## 3. 目标、边界、依赖与验收

目标是把公网域名/TLS 与业务 Rootless 计算分离：`38.55.145.52` 只运行公网 Nginx 和受限隧道账号，`192.168.110.210` 只运行 Rootless CRM。固定链路为公网回环 18080 到业务回环 10080。

不修改 API、数据库迁移、AI Prompt/RAG 算法或三平台 UI；不决定 production 拓扑；不操作公司系统 Docker。依赖新 main 三条不可变应用摘要、公网 DNS/证书、两台服务器 SSH、既有 Rootless/runner 和六文件模型。

仓库验收要求包括：单端口 Compose、HTTP 内层代理、受限 SSH 账号/unit、正式/引导 vhost、低敏验证脚本、门禁回归、Shell/Compose/前后端验证、PR/CI/人工审阅。现场验收另要求 DNS/TLS/隧道/健康/恢复/回滚和公司负载不变。

## 4. 实施前确认

- [x] 已读取共享记忆文档清单以及最新 PRD、接口、任务拆解、团队职责和 MVP 标准。
- [x] 已读取代码编写手册、实施记录规范、相关 ADR、运行手册和既有测试结论。
- [x] 已明确目标模块、需求边界、依赖、验收标准和公司容器/其他 vhost 风险。
- [x] 用户已逐段批准设计，并明确要求生成计划后直接实施。
- [x] 已从 `origin/main` 创建隔离工作树和 `feature/split-ingress-staging` 分支。

## 5. 实施方案

1. 用 TDD 把 Rootless proxy 改为唯一回环 HTTP 10080，并同步部署/回滚门禁。
2. 创建仅允许单一 remote listen 的 SSH 用户 unit、业务安装器和公网受限账号安装器。
3. 创建 ACME 引导 vhost、正式 TLS vhost 和低敏端到端验证脚本。
4. 用 ADR-008 取代 ADR-007 的旧入口部分，同步运行手册、检查表、README、报告和索引。
5. 全量验证后通过 GitHub Flow PR、人工审阅和 squash merge，发布新 main 候选。
6. 两台服务器失败关闭实施 G0，再按 G1～G6 逐级验证真实 TikTok 人工辅助首版。

## 6. 实际变更

| 路径 | 说明 |
| --- | --- |
| `CRM智能聊天系统/deploy/nginx/nginx-tunnel.conf` | 新增业务服务器 HTTP-only 内层代理 |
| `CRM智能聊天系统/docker-compose.rootless-staging.yml` | 改为唯一 `127.0.0.1:10080:80` 和只读 tunnel 配置 |
| `CRM智能聊天系统/scripts/Test-StagingProductionGates.ps1` | 部署门禁固定单端口、单挂载 |
| `CRM智能聊天系统/scripts/Invoke-StagingRollbackDrill.ps1` | 回滚门禁固定同一入口契约 |
| `CRM智能聊天系统/deploy/staging/rootless/systemd/user/crm-staging-tunnel.service` | 新增用户级反向隧道 |
| `CRM智能聊天系统/deploy/staging/rootless/install-reverse-tunnel.sh` | 新增业务端身份/权限/指纹/unit 安装门禁 |
| `CRM智能聊天系统/deploy/staging/rootless/install-public-tunnel-account.sh` | 新增公网受限账号和 authorized_keys 安装门禁；拒绝附加组和 group/other 可写目录 |
| `CRM智能聊天系统/deploy/staging/rootless/public-nginx/*` | 新增 HTTP 引导和正式 TLS vhost |
| `CRM智能聊天系统/deploy/staging/rootless/verify-split-ingress.sh` | 新增低敏全链路验证；精确约束 DNS 唯一值、单一回环监听、Cookie 属主和 HTTP 重定向目标 |
| `CRM智能聊天系统/backend/tests/test_split_ingress_staging_assets.py` | 新增双机入口契约测试 |
| `CRM智能聊天系统/backend/tests/test_production_gate_scripts.py` | 更新单端口门禁夹具 |
| `CRM智能聊天系统/backend/tests/test_real_runtime_config.py` | 把旧 10443 契约更新为单端口和只读 tunnel 配置 |
| `CRM智能聊天系统/frontend/package-lock.json` | 将 ESLint 传递 `js-yaml` 从 4.3.1 最小升级到安全的 4.3.2 |
| `.gitattributes` | 固定 `.conf` 为 LF |
| `架构师/ADR-007...`、`ADR-008...` | 追加取代勘误并登记新决策 |
| Rootless/production/项目 README、放行检查表 | 同步唯一活动操作和真实状态 |
| 008 测试报告及两个索引 | 登记工程证据与未执行项 |

提交链截至合并前安全复核：`338400c`、`6954d71`、`3ee7314`、`1de02c8`、`557f13c`、`bddd9d2`、`1d2ab21`、`2fdbeb7`、`7403ac5`、`93e82d1`、`d026c93`。最终 squash SHA 和镜像摘要待 PR 合并后追加，禁止预填。

## 7. 验证结果

| 验证 | 结果 |
| --- | --- |
| 修改前邻接基线 | 114 passed |
| Rootless proxy/门禁聚焦 | 116 passed |
| 隧道和既有 Rootless 回归 | 55 passed |
| 公网入口和既有 Rootless 回归 | 58 passed |
| 合并前安全复核 | RED 为 2 failed/5 passed；补齐约束后 7 passed，邻接回归 191 passed |
| 文档回归与修复 | 首次 7 failed, 114 passed；恢复既有 runner 安全章节后 121 passed |
| 后端全量 | 正确 `backend/` 工作目录最终 1565 passed, 12 skipped, 2 warnings in 46.17s；Ruff check/format 通过 |
| 前端 | lint 0 error/2 warning、类型通过、40 passed、生产构建通过 |
| 前端安全 | 发现 1 High 后最小升级 `js-yaml 4.3.2`；生产与完整官方审计均 0 vulnerability |
| Compose/Nginx/Shell | 单端口/单只读挂载通过；三个 Nginx 配置语法通过；三个 Shell 脚本语法通过 |
| PR CI | 未执行，后续追加 |
| 服务器/DNS/TLS/部署/G0～G6 | 未执行 |

详细命令和限制见 008 测试报告。上述工程结果不替代目标 Ubuntu/Nginx/OpenSSH/systemd、真实平台或生产证据。

## 8. 遗留风险与下一步

- 必须完成全量仓库验证、人工审阅、CI 和 squash merge，再发布与新 main 关联的三条 RepoDigest。
- 公网 vhost 必须在现有宝塔环境执行 `nginx -t` 并复核其他站点前后不变。
- DNS 当前尚未证明指向 `38.55.145.52`；证书不得提前宣称签发成功。
- 公网受限账号、主机指纹、隧道断线恢复和回环监听须现场独立复核。
- G0 的环境、迁移、模型、健康、备份恢复和兼容回滚，以及 G1～G6 均未执行。
- production 方案仍阻塞，不得从 staging 拓扑推导。

## 9. 文档与状态同步

本次新增 ADR-008、008 测试报告和本实施记录，并同步放行检查表、三个 README、测试报告索引和实施记录索引。服务器真实实施完成后必须把低敏结果、完整 main SHA、RepoDigest 和 run ID 追加到同一报告/记录，不另建竞争结论。
