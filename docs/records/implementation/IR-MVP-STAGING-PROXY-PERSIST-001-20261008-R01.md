---
record_id: IR-MVP-STAGING-PROXY-PERSIST-001-20261008-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-STAGING-PROXY-PERSIST-001
base_sha: 87acfd643720ec2a120ee78b5e57ecaebff8e93d
final_sha: dcddb26cbb6ecc92db30a11a2f504d034e6ec048
requirement_ids: [MVP-STAGING-PROXY-PERSIST-001, G0, G6]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
test_record: docs/reports/tests/TR-MVP-STAGING-PROXY-PERSIST-001-20261008-R01.md
review_record: docs/reports/reviews/RR-MVP-STAGING-PROXY-PERSIST-001-20261008-R01.md
created_at: 2026-10-08T10:18:00+08:00
updated_at: 2026-10-08T10:18:00+08:00
supersedes: null
---

# 实施目标与范围

修复 staging Rootless proxy 在 Runner 临时源码目录清理后无法重启的缺陷；仅变更 staging 部署工作流的受审源码解包位置，并在真实 staging 复测。用户已要求将临时路径改为持久路径；production 不部署，TikTok 授权页错误另行定位。

# 实际变更及原因

`2026-10-08` 的现有容器重启中，proxy 的 `/etc/nginx/nginx.conf` bind 来源仍指向 `crm-reviewed-source-36702556391-1` 所在的 Runner 临时目录，目标文件被清理后 Docker 将其路径建成目录，代理重启以 OCI bind 类型错误退出，公网 ready 短暂为 502。已从持久受审源码复制 SHA-256 相同的配置恢复原容器，公网恢复 200；这只是临时恢复点。

PR #89 将 `Staging production gates` 的 `deploy`/`rollback` 已验证源码解包到 `/home/crmdeploy/src/crm-reviewed-source-<run-id>-<attempt>/`，目录模式 `0750`，存在即失败；`validate` 仍在 Runner 临时目录。后续 Compose gate 使用前一步输出的精确解包路径，代理相对只读挂载因此由持久目录解析。镜像摘要、应用、数据库模式、生产入口和其他公司服务未改。

# 关键决定与偏差

保留原有 `git archive` SHA-256 校验、唯一运行目录、四个 Compose 文件顺序和固定能力关闭门禁。运行中的代理引用该持久目录时禁止清理。三个现有运行镜像的 OCI revision 均为 `33d80bd4acc1dfb9c93ec687086ee466d99682c6`；该修复合入后的 `main=dcddb26cbb6ecc92db30a11a2f504d034e6ec048` 与该 revision 的 backend、frontend 和三份 Dockerfile 构建输入无差异，现场沿用原不可变摘要，未发布新镜像。

# 数据、配置、接口、迁移或 Prompt 影响

只改变 staging 部署工作流的主机源码路径。正式部署按既有门禁执行一次 `alembic upgrade head` 并核对 `current --check-heads`，无新迁移；活动数据卷、公共 API、生产配置和 Prompt 未变。持久源码目录由 `crmdeploy` 持有，配置文件作为只读 bind 挂载；不提交真实环境文件或凭证。

# 验证交接、限制与回滚

PR #89 的两项 CI 通过；staging `validate` 运行 `37716193186` 和 `deploy` 运行 `37716402745` 通过。代理新 bind 来源、配置 SHA-256、再次显式重启、健康、公网接口、固定出口及公司容器不变见对应 TR 和 [低敏现场证据](../../../release/evidence/staging/crm-staging-proxy-persistent-source-20261008.json)。如后续配置或部署异常，保留当前活动目录和容器，使用既有 staging 回滚工作流；不删除活动数据卷、不触及系统 Docker。该任务不关闭 TikTok G1、五日稳定性 G6 或 production 门禁。
