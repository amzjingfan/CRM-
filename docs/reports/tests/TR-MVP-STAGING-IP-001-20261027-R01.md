---
record_id: TR-MVP-STAGING-IP-001-20261027-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-STAGING-IP-001
tested_sha: f384863122af30b93d3b362c11c43c3019124a18
implementation_record: docs/records/implementation/IR-MVP-STAGING-IP-001-20261027-R01.md
requirement_ids: [MVP-STAGING-IP-001, G0]
acceptance_ids: [AC-01, AC-02, AC-03]
environment: Windows PowerShell local worktree; Ubuntu business host 192.168.1.173; staging.overselfx.com
created_at: 2026-10-27T11:41:00+08:00
updated_at: 2026-10-27T11:41:00+08:00
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT: centralized`。本次只改 staging 部署地址资料和一处安装器校验上下文；定向运行既有基础设施测试、脚本语法检查、SSH 身份与运行健康检查。没有修改业务应用或执行部署。

# 命令和逐项结果

| 验收 | 本次结果 |
|---|---|
| AC-01 主机身份和位置 | `ping -n 2 192.168.1.173` 为 2/2；TCP 22 可达。使用新地址对应私钥、`StrictHostKeyChecking=yes` 和原服务器 `HostKeyAlias` 登录成功，证明当前主机密钥与原记录匹配；`root` 登录后 `/home/crmdeploy`、`config`、`src`、`assets/models` 均存在且归 `crmdeploy`。主机 `ad-H610` 的 `enp2s0` 为 `192.168.1.173/23`。私钥 ACL 在命令结束后恢复。 |
| AC-02 现行文件 | 对根 README、`docs/architecture/SYSTEM.md`、`docs/operations/DEPLOYMENT.md`、两份活动部署 README 和 `install-public-egress-account.sh` 查找旧地址，结果为 0；六处当前地址均为 `192.168.1.173`。旧地址只保留在历史资料、原始证据及既有负向测试中。`git diff --check origin/main...HEAD` 通过。 |
| AC-02 安装器 | 将候选脚本送入业务机 `bash -n`，退出码 0，未执行安装器。以 `f384863122af30b93d3b362c11c43c3019124a18` 在 `src/backend` 使用既有 Python 3.11 虚拟环境运行 `python -m pytest -c pyproject.toml ../tests/backend/runtime_infrastructure/test_split_ingress_staging_assets.py -q`：37 passed、3 skipped。 |
| AC-03 当前链路 | `crm-staging-tunnel.service` 为 active，Rootless `crm-staging` 12 个容器运行。本机 `127.0.0.1:18081` 和 `https://staging.overselfx.com` 的 `/healthz`、`/v1/health`、`/v1/health/ready` 各返回 200。业务机活动配置及用户级 unit 未找到旧 IP。 |
| AC-03 地址来源 | `ip -4 route show default` 显示 `default via 192.168.1.1 dev enp2s0 proto dhcp src 192.168.1.173`；长期地址保留无法从主机确认。 |

# REQ/AC 与证据映射

AC-01 由 SSH 主机密钥匹配、目录及网卡现场检查覆盖；AC-02 由当前资料搜索、脚本语法和定向 pytest 覆盖；AC-03 由隧道、容器和六个 HTTP 状态覆盖。命令均为只读，除本地 Git 记录外没有服务器变更。

# 未执行项与残余风险

未执行完整后端或前端回归：本次不改变应用业务代码、镜像或运行配置。未在公网服务器重跑安装器或重载 sshd；安装器仅作静态与契约验证。DHCP 地址可能在租约变更后漂移，需网络管理员确认地址保留。

# 结论和复测条件

当前 `192.168.1.173` 业务主机和 staging 链路通过本任务验收；地址保留属于后续网络维护风险。若重新分配地址或改动公网 SSH 账号策略，重新核对主机身份、安装器、隧道和三个公网健康端点。
