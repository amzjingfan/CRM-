---
record_id: TR-MVP-DEPARTMENT-ROLE-UI-STAGING-001-20261030-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-DEPARTMENT-ROLE-UI-STAGING-001
tested_sha: eb76837823f9e200f47db4a7786d4e91a94f9997
implementation_record: docs/records/implementation/IR-MVP-DEPARTMENT-ROLE-UI-STAGING-001-20261030-R01.md
requirement_ids: [MVP-DEPARTMENT-ROLE-UI-STAGING-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: Windows Docker linux/amd64; staging Rootless Docker; authenticated staging browser; HTTPS staging.overselfx.com
created_at: 2026-10-30T07:00:55Z
updated_at: 2026-10-30T07:00:55Z
supersedes: null
---

# 测试结果

TEST_LAYOUT: centralized。本轮针对发布源码、备份、镜像、部署门禁和实际账号页回显。源码行为验证见 [功能 TR R01](TR-MVP-DEPARTMENT-ROLE-UI-002-20261030-R01.md)：生产构建浏览器回归 56/56，前端 55/55，后端 2658 通过、77 跳过；这些是原 subject 的验证，不冒充本轮重新运行。

- 本轮发布源码 `eb768378` 与已测 subject `0fb8202f` 的前端构建输入一致；原运行版到发布版的产品差异仅 5 个前端文件。前端 OCI revision、平台和远端 RepoDigest 与精确摘要匹配，后端及另外两镜像未变。
- Git 归档 SHA-256 `06328e2d…f32a` 双端一致；私有备份 PostgreSQL `a107d036…c968`、MinIO `053381a9…3576`、环境 `0621a122…5cb0`；清单可读，0700/0600 权限核对通过。
- 门禁 `CurrentValidate` validated、`CandidateValidate` validated、`Deploy` passed，原件 SHA-256 见发布 JSON；`production_release=false`。044 迁移头、12 服务和运行摘要通过，自动回复、营销及高风险写入仍关闭，人工发送仅原两家已授权店铺。
- 公网 `/healthz`、`/v1/health`、`/v1/health/ready`、`/settings/team`、`/settings/team/departments` 均为 200。已登录 staging 账号页只有 1 个启用管理员；点击该行“更多”后，修改密码、停用和删除账号三项全部显示在表格外，无需滚动；当前管理员的删除动作被禁用。
- 原功能 TR 已在连接 staging 的测试店铺用数据库事务回滚验证合成入站派单及角色权限，零平台外发、零残留；这不是 TikTok 真实 webhook 验收。
- 证据 PR #662 的 CI run 41018105080：后端 job 123938923830、前端 job 123938923382 均 failure，runner 为空且 steps=0，实际未执行 CI；依持续批准的本地替代门禁使用已记录的功能验证和本轮 JSON/链接/索引/敏感信息/diff 检查，不记为 CI 通过。

# 未执行与结论

本轮没有再次执行真实 TikTok webhook、外部消息、整库恢复或 production 发布。完整前端 `npm run test:ui` 中其他套件因缺各自服务端口未通过；受影响的 `ui-regressions.test.mjs` 已在生产构建服务上 56/56 通过。上述限定 staging 发布与菜单现场验收为 PASS；真实平台入站能力仍需独立证据。
