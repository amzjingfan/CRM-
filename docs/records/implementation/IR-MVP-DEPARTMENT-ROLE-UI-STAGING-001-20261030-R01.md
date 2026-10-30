---
record_id: IR-MVP-DEPARTMENT-ROLE-UI-STAGING-001-20261030-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-DEPARTMENT-ROLE-UI-STAGING-001
base_sha: eb76837823f9e200f47db4a7786d4e91a94f9997
final_sha: eb76837823f9e200f47db4a7786d4e91a94f9997
requirement_ids: [MVP-DEPARTMENT-ROLE-UI-STAGING-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
test_record: docs/reports/tests/TR-MVP-DEPARTMENT-ROLE-UI-STAGING-001-20261030-R01.md
review_record: docs/reports/reviews/RR-MVP-DEPARTMENT-ROLE-UI-STAGING-001-20261030-R01.md
created_at: 2026-10-30T07:00:55Z
updated_at: 2026-10-30T07:00:55Z
supersedes: null
---

# 实施范围

从已合并主线 `eb768378` 单独发布部门角色、逐店派单摘要、账号部门选择和账号“更多”菜单修复到 staging；保留现行 Agent、TikTok 人工发送范围及全部安全开关，不触及 production。

# 实施事实

- 对比原运行源码 `18a0d7bb`，产品差异仅为 5 个已批准前端文件；后端、Dockerfile、Compose 和门禁脚本无差异。构建输入与已通过 56 项浏览器回归的源码 subject `0fb8202f` 一致。
- 在干净主线 linux/amd64 构建并推送前端不可变镜像 `sha256:903acf1a…74860`；后端、检索及文档解析镜像保持原摘要。Git 归档两端 SHA-256 一致，远端源码校验通过。
- 切换前生成 PostgreSQL、MinIO 和环境备份；远端分别验证 `pg_restore -l`、归档清单、权限与 SHA-256。当前模式 ValidateOnly、候选模式 ValidateOnly 和 Deploy 均通过。
- 首次远端 GHCR 拉取及预取停滞，未切换服务；改用相同不可变摘要的本地 Docker 归档，双方哈希一致，远端 `docker load` 后按摘要 `docker pull` 并核对 RepoDigest、平台及 OCI revision，随后才部署。
- 部署后独立复核 12 服务、044 迁移头、前后端摘要、原有开关、公网健康和已登录账号页菜单。低敏精确证据见 `release/evidence/staging/crm-staging-department-role-ui-20261030.json`。

# 边界与恢复

没有触发真实买家发送、退款、真实 TikTok 入站或 production 发布。若需回退，使用原前端不可变摘要 `sha256:45fbdee0…dd1bb` 并保留部署后业务增量，不直接用旧整库覆盖。备份尚未做整库恢复演练。
