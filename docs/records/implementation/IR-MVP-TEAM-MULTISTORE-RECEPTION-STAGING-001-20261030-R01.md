---
record_id: IR-MVP-TEAM-MULTISTORE-RECEPTION-STAGING-001-20261030-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-TEAM-MULTISTORE-RECEPTION-STAGING-001
base_sha: 4483ec9b512f698721d2db6500d54e0bbfd95b8e
final_sha: 4483ec9b512f698721d2db6500d54e0bbfd95b8e
requirement_ids: [MVP-TEAM-MULTISTORE-RECEPTION-STAGING-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
test_record: docs/reports/tests/TR-MVP-TEAM-MULTISTORE-RECEPTION-STAGING-001-20261030-R01.md
review_record: docs/reports/reviews/RR-MVP-TEAM-MULTISTORE-RECEPTION-STAGING-001-20261030-R01.md
created_at: 2026-10-30T09:17:21Z
updated_at: 2026-10-30T09:17:21Z
supersedes: null
---

# 实施目标与范围

将已合并的账号多店授权、角色显示及部门派单说明修复单独发布到 staging。仅替换前端，维持当前后端、人工发送范围和所有安全开关。

# 实施事实

- 干净 Git 主线 checkout 固定在 `4483ec9b`，与上一运行版相比只有四个前端文件变化；backend、Dockerfile、Compose 和门禁脚本不变。Windows Git 归档解包的一处 Unicode 文件名编码不同，因此最终门禁采用远端干净 Git checkout，前端 tree SHA 双端一致。
- linux/amd64 前端镜像按 OCI revision 和 RepoDigest 核对为 `sha256:fd2dab24…b1422`；后端、检索和解析镜像维持原摘要。远端拉取 GHCR 一度停滞，改传双端哈希一致的 Docker archive 并按摘要装载。
- 切换前保存 PostgreSQL 自定义格式转储、MinIO 归档和环境文件到私有目录，分别验证可列举、SHA 与 0700/0600 权限。
- 原版与候选 ValidateOnly 通过。首次 Deploy 因临时 GHCR 配置缺失在切换前失败，修正后重跑 Candidate Validate 和 Deploy，门禁最终通过；没有将第一次失败写成成功。
- 运行前端摘要、12 服务、044 迁移头、三个健康端点以及已登录账号和部门派单页面均复核。精确证据见 `release/evidence/staging/crm-staging-team-multistore-reception-20261030.json`。

# 影响与边界

没有新增接口、迁移或配置。没有改动真实店铺授权、自动发送、Agent 开关和生产环境；没有向买家发送消息。回退使用上一前端摘要 `sha256:903acf1a…174860`，保留部署后业务增量，不直接用旧数据库覆盖。
