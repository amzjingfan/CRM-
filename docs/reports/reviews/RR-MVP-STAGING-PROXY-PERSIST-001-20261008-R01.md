---
record_id: RR-MVP-STAGING-PROXY-PERSIST-001-20261008-R01
record_type: review
revision: R01
status: APPROVE
task_id: MVP-STAGING-PROXY-PERSIST-001
reviewed_sha: dcddb26cbb6ecc92db30a11a2f504d034e6ec048
implementation_record: docs/records/implementation/IR-MVP-STAGING-PROXY-PERSIST-001-20261008-R01.md
test_record: docs/reports/tests/TR-MVP-STAGING-PROXY-PERSIST-001-20261008-R01.md
review_focus: [staging-path-persistence, archive-integrity, rootless-isolation, restart-recovery, secret-exposure]
created_at: 2026-10-08T10:18:00+08:00
updated_at: 2026-10-08T10:18:00+08:00
supersedes: null
---

# 审查范围、依据与重点风险

复核 PR #89 对工作流路径选择及测试的差异、当前部署/回滚脚本的相对 bind 解析、两项 CI、两次 staging 工作流 artifact 和现场代理再启动。重点是受审源码是否先校验再持久化、持久目录是否唯一且权限受限、`validate` 是否仍不改变活动容器、代理是否仍只读绑定以及是否误触公司系统 Docker、凭据和 production。

# 发现、级别、位置和证据

根因是临时解包目录成为运行中 proxy 的 bind 来源，Runner 清理与容器启动不是原子事务。新工作流先比较源码包 SHA-256，再将 `deploy`/`rollback` 解包到唯一持久目录，目标已存在即失败；`validate` 继续在临时目录。现场 proxy 的 bind 来源精确落在该持久目录，`RW=false`，源文件与受审配置哈希相同；工作流完成后显式重启成功。无新增外部网络权限、密钥输出或 production 操作。本次审查未发现阻断本任务的 Critical/Important 问题。

# 已验证与未验证内容

已验证本次 staging 部署、迁移头、公网健康、固定出口和同机系统 Docker 容器 ID 无变化。未模拟宿主机重启或整个 Runner 清理策略变化；持久目录位于 Runner 临时根之外且已在作业完成后用于成功再启动，但未来仍必须保护活动挂载路径。TikTok 平台授权失败与 G1/G6 验收独立，未据此签署。

# 结论和返修条件

批准 `MVP-STAGING-PROXY-PERSIST-001` 的 staging 代理持久挂载实现和现场复测。证据 PR 合入 `main` 并复核索引后才将任务标为 `DONE`。若后续将源码目录重新放回临时根、放宽只读挂载或清理活动目录，应返修并重做现场再启动门禁。
