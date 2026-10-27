---
record_id: RR-MVP-STAGING-IP-001-20261027-R01
record_type: review
revision: R01
status: APPROVE
task_id: MVP-STAGING-IP-001
reviewed_sha: f384863122af30b93d3b362c11c43c3019124a18
implementation_record: docs/records/implementation/IR-MVP-STAGING-IP-001-20261027-R01.md
test_record: docs/reports/tests/TR-MVP-STAGING-IP-001-20261027-R01.md
review_focus: [ssh-host-identity, ingress-egress-boundary, deployment-scope]
created_at: 2026-10-27T11:41:00+08:00
updated_at: 2026-10-27T11:41:00+08:00
supersedes: null
---

# 审查范围、依据与重点风险

审查 `origin/main..f3848631` 的现行部署资料、SSH 出口账号安装器和控制文档，重点核对身份未被自动接受、权限未放宽、活动服务未误改，以及历史证据未被改写。

# 发现、级别、位置和证据

- 无阻断发现。SSH 使用严格主机密钥验证并匹配原主机记录；没有关闭校验、写入密钥、修改用户级 SSH 配置或把私钥纳入 Git。
- 安装器只替换 `sshd -T -C` 的来源地址上下文；`PermitOpen` 白名单、密码禁用、禁止交互与端口转发边界及失败关闭检查无差异。安装器未在公网主机执行，因此现场策略未因本任务改变。
- 现行六处地址与新主机一致，历史设计、清理清单、测试和证据仍保留原地址。当前业务机地址来自 DHCP，未确认地址保留；已在活动部署说明及任务恢复点显式列为风险。

# 已验证与未验证内容

定向基础设施测试 37 passed、3 skipped；`bash -n`、本机及公网六个健康响应、12 容器和活动隧道均通过。未做生产发布、镜像部署、数据写入、SSH 服务重载或公网账号重新安装；不把这些未执行项视为通过。

# 结论和返修条件

对本次地址事实与安装器校验上下文变更予以 `APPROVE`。如网络管理员分配不同地址、SSH 主机密钥变化或公网账号策略变化，需停止沿用此结论并重新审查。
