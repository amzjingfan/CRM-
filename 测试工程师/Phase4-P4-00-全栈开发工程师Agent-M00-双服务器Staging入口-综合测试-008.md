# 双服务器 Staging 入口综合测试记录

## 1. 测试基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-00；关联 P4-11、REAL-FS-01/G0 |
| 模块编号 | M00 |
| 模块名称 | 双服务器 Staging 入口 |
| 被测主责 Agent | 全栈开发工程师Agent |
| 被测协作 Agent | 架构师Agent、共享记忆文档Agent |
| 测试执行 Agent | 全栈开发工程师Agent工程自测；测试工程师独立复测待执行 |
| 关联实施记录 | `共享记忆文档/实施记录/PhaseX-PX-00-全栈开发工程师Agent-双服务器Staging入口-001.md` |
| 执行日期 | 2026-09-11 |
| 当前结论 | 仓库静态契约与脚本语法阶段通过；PR/CI、真实 DNS/TLS/隧道/部署/G0～G6 未执行，不构成 staging 或 production 放行 |

## 2. 范围与环境

本轮只验证 `38.55.145.52` 公网 Nginx/TLS → 公网回环 `127.0.0.1:18080` → 受限反向 SSH 隧道 → `192.168.110.210` 业务回环 `127.0.0.1:10080` → Rootless CRM 的仓库资产。产品/UI 继续保留三平台，但真实接入范围只含 TikTok 人工辅助首版。

工作树为 `.worktrees/split-ingress-staging`，分支为 `feature/split-ingress-staging`，基础为 `main@ed17ea55994764f954e50f9ad04dbe8f4ee5c5a3`。本地环境为 Windows PowerShell、Python 3.11/uv、Git for Windows Bash 和 Docker 29.7.2；本节结果不等同于目标 Ubuntu、宝塔 Nginx、OpenSSH、systemd 或 Rootless 现场结果。

## 3. 已执行命令与结果

| 场景 | 命令摘要 | 准确结果 |
| --- | --- | --- |
| 修改前聚焦基线 | split-ingress 邻接测试集 | 114 passed in 38.43s |
| Rootless 单端口 RED | `pytest test_split_ingress_staging_assets.py ...` | 旧 overlay 含 10443、缺少 tunnel Nginx、旧双端口夹具导致预期失败 |
| Rootless 单端口 GREEN | `pytest test_split_ingress_staging_assets.py test_rootless_staging_assets.py test_production_gate_scripts.py -q` | 116 passed in 30.03s |
| 隧道资产 RED | `pytest test_split_ingress_staging_assets.py -q` | 2 failed, 2 passed；三个目标资产缺失 |
| 隧道与既有 Rootless 回归 | `pytest test_split_ingress_staging_assets.py test_rootless_staging_assets.py -q` | 55 passed in 1.72s |
| 公网 vhost/验证脚本 RED | `pytest test_split_ingress_staging_assets.py -q` | 3 failed, 4 passed；三个目标资产缺失 |
| 公网入口与 Rootless 回归 | `pytest test_split_ingress_staging_assets.py test_rootless_staging_assets.py -q` | 58 passed in 1.93s |
| 文档全量聚焦首次回归 | 三个入口/Rootless/门禁测试模块 | 7 failed, 114 passed；重写手册误删既有 runner 安全转移章节 |
| runner 文档修复聚焦 | `pytest test_rootless_staging_assets.py -q -k runner_readme` | 6 passed, 45 deselected |
| 修复后三模块回归 | `pytest test_split_ingress_staging_assets.py test_rootless_staging_assets.py test_production_gate_scripts.py -q` | 121 passed in 31.31s |
| Shell 语法 | Git Bash `bash -n` 检查三个新增 `.sh` | exit 0，无输出 |
| 空白与行尾 | `git diff --check`；`.conf/.sh/.service` LF 属性 | exit 0；无空白错误 |

首次文档回归的根因是活动入口手册重写时删除了既有 runner 的逐 SSH 路径复验、Windows SCP 模式收紧、原子提升和 Token 同进程复验说明。修复从基础 main 完整恢复该安全章节，没有恢复旧 80/443 socket 的活动入口命令。完整后端、前端、Compose、PR CI 和目标 Nginx 语法将在后续验证阶段追加；未运行前不预填结果。

## 4. 已验证工程契约

- Rootless overlay 只发布 `127.0.0.1:10080:80`，挂载只读 `nginx-tunnel.conf`，不再发布 10443 或挂载活动 TLS。
- 内层 Nginx 只使用 HTTP，错误 Host 返回 444；对上游固定 `X-Forwarded-Proto https`，两层 SSE 关闭缓冲，日志只记录 `$uri`。
- 用户级隧道固定 `-R 127.0.0.1:18080:127.0.0.1:10080`、严格主机校验、独立私钥和断线重启。
- 公网 `crm-tunnel` 授权项锁定密码、nologin、forced command、`restrict,port-forwarding` 和单一 `permitlisten`。
- 公网 HTTP 引导 vhost 只开放 ACME、低敏健康和 503；正式 vhost 在公网终止 TLS 且唯一上游为 `127.0.0.1:18080`。
- 低敏验证脚本覆盖三个 DNS 解析器、证书 SAN/有效期、回环监听、HTTP 301、三个健康端点和 SSE Content-Type，不读取活动私钥、环境正文或容器环境。

## 5. 未执行与阻塞项

| 项目 | 状态 | 所需证据 |
| --- | --- | --- |
| PR/CI/squash merge | 未执行 | GitHub required checks、人工审阅和新 main SHA |
| 新不可变候选 | 未执行 | 三条应用 RepoDigest 与新 main 完整 SHA 关联 |
| 公网 Nginx 配置 | 未执行 | 其他 vhost 前后摘要、`nginx -t`、安全 reload |
| DNS | 未执行 | 三个公共解析器均返回 `38.55.145.52` |
| TLS | 未执行 | 公信证书 SAN、链、有效期、续期和私钥权限 |
| 受限隧道 | 未执行 | 主机指纹、账号边界、仅回环 18080 和断线恢复 |
| Rootless deploy/G0 | 未执行 | 摘要拉取、迁移 023、健康、模型六文件、备份恢复和兼容回滚 |
| TikTok G1～G6 | 未执行 | Partner Center、真实店铺、DeepSeek、50 个授权客户端和连续五日证据 |
| production | 阻塞 | 运行方案未决定，G8 未签署 |

## 6. 结论

当前只能写“仓库工程资产的聚焦测试通过”。不能写“双机入口已部署”“G0 通过”“TikTok 人工辅助 v0.1 可用”“完整 MVP 完成”或“production 放行”。测试工程师应在目标机现场按 ADR-008 和运行手册独立复核，并把真实结果追加到本报告和索引。
