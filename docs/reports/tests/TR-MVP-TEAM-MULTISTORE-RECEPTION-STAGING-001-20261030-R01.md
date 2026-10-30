---
record_id: TR-MVP-TEAM-MULTISTORE-RECEPTION-STAGING-001-20261030-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-TEAM-MULTISTORE-RECEPTION-STAGING-001
tested_sha: 4483ec9b512f698721d2db6500d54e0bbfd95b8e
implementation_record: docs/records/implementation/IR-MVP-TEAM-MULTISTORE-RECEPTION-STAGING-001-20261030-R01.md
requirement_ids: [MVP-TEAM-MULTISTORE-RECEPTION-STAGING-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: Windows Docker linux/amd64; staging Rootless Docker; authenticated staging browser; HTTPS staging.overselfx.com
created_at: 2026-10-30T09:17:21Z
updated_at: 2026-10-30T09:17:21Z
supersedes: null
---

# 测试结果

TEST_LAYOUT: centralized。源码行为验证见 [功能 TR R01](TR-MVP-TEAM-MULTISTORE-RECEPTION-UI-001-20261030-R01.md)：55/55 前端契约、58/58 浏览器回归、typecheck、build 通过，lint 无错误。这些是原 subject 的验证，不冒充本轮重新运行。

- AC-01：发布版与前一运行版产品差异仅四个前端文件，远端干净 Git checkout 与主线 `4483ec9b` 和本地前端 tree 一致；前端 OCI revision、linux/amd64 平台、RepoDigest 绑定新摘要，其他镜像不变。
- AC-02：私有备份校验、原版 ValidateOnly、候选 ValidateOnly、最终 Deploy 均通过。第一次 Deploy 因注册表临时认证缺失在服务切换前失败；修正后候选预检与部署重新通过。原件 SHA-256 及恢复点在[低敏证据](../../../release/evidence/staging/crm-staging-team-multistore-reception-20261030.json)。
- AC-03：迁移头 `044_reception_assignment`、12 服务，公网 `/healthz`、`/v1/health`、`/v1/health/ready`、账号和部门页面全部 HTTP 200。新开已登录浏览器标签的账号页显示“系统管理员（全部店铺）”和“客服主管（1 店）”；部门派单页显示开关状态、无合格客服原因、禁用的参与派单选项及 60 秒工作台心跳说明。
- AC-04：运行后端仍只有 2 个已授权人工发送店铺，Webhook 读取和人工发送保留，Agent 调试与人工建议保留；自动回复、自动营销、高风险写入关闭；`production_release=false`。未对真实账号执行写入，也未向买家发送消息。
- 证据 PR #666 的 CI run 41032869320：后端 job 123986565930 和前端 job 123986566293 均显示 failure，但 runner 为空、steps=0，测试未执行。按项目持续批准的本地替代门禁，使用上述发布证据、原 subject 验证及本轮 JSON/链接/敏感信息/diff 核对；不称 CI 通过。

# 未执行与限制

浏览器编辑抽屉操作曾因连接超时中断；新开标签后账号列表及部门派单页只读现场回显成功，编辑表单的线上读操作未完成。多选店铺及角色修改由源码行为测试覆盖，未在 staging 真实账号上提交更改。未演练真实 TikTok 入站派单、数据库整库恢复或 production 发布。此限定 staging 发布验收为 PASS。
