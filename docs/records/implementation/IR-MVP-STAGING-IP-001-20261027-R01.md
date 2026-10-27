---
record_id: IR-MVP-STAGING-IP-001-20261027-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-STAGING-IP-001
base_sha: 8ee98830026990ad1b0ee1c382eb309a4aeb4ea0
final_sha: f384863122af30b93d3b362c11c43c3019124a18
requirement_ids: [MVP-STAGING-IP-001, G0]
acceptance_ids: [AC-01, AC-02, AC-03]
test_record: docs/reports/tests/TR-MVP-STAGING-IP-001-20261027-R01.md
review_record: docs/reports/reviews/RR-MVP-STAGING-IP-001-20261027-R01.md
created_at: 2026-10-27T11:41:00+08:00
updated_at: 2026-10-27T11:41:00+08:00
supersedes: null
---

# 实施目标与范围

业务服务器搬迁后，确认 `192.168.1.173` 是原 staging 业务主机，并将现行仓库部署说明和公网 SSH 出口账号安装器中的旧业务 IP 改为该地址。范围仅为 staging 地址事实和安装器校验上下文；不重新部署应用、修改公网入口、迁移数据或发布 production。

# 实际变更及原因

以远端 `main=8ee98830` 建立隔离分支。更新根 README、架构图、活动部署文档、staging 运行手册、production 对 staging 的当前说明，以及 `install-public-egress-account.sh` 中 `sshd -T -C` 的业务客户端地址。`PROJECT-STATE.md` 和任务表记录本次恢复点。历史设计、计划、清理清单与原始证据保留当时的 `192.168.110.210`，不改写历史现场值。

# 关键决定与偏差

业务机 `/home/crmdeploy`、UID 1004 Rootless Docker、反向 SSH 隧道和 `127.0.0.1:18081` 无旧 IP 引用。隧道由业务机主动连到 `38.55.145.52`，所以不需要重启服务或更改容器网络。GitHub staging Environment 只有公开 Base URL 变量和环境文件路径 secret，没有主机 IP 配置项；工作流通过 `crm-staging` 自托管 Runner 标签调度。本次没有修改 GitHub 设置或真实密钥。

# 数据、配置、接口或迁移影响

安装器仅将 `sshd -T -C` 的模拟来源地址从旧业务 IP 换为新地址，原有账号限制、`PermitOpen`、密钥、监听端口和失败关闭检查均未放宽。未执行该安装器，公网 sshd 配置与运行中的 egress 隧道不变。数据库、对象、模型、镜像、接口、迁移及生产配置均未改动。

# 验证交接、限制与回滚

本次验证见对应 TR；安全边界审查见 RR。服务器 `enp2s0` 当前为 DHCP 分配的 `192.168.1.173/23`，地址保留尚未核实；应由网络管理员设置 DHCP 保留或批准静态配置。若地址再次变化，先通过控制台确认主机身份，再更新现行部署资料与安装器校验上下文，不能沿用旧地址盲连。
