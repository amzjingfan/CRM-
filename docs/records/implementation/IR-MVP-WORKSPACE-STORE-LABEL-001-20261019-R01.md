---
record_id: IR-MVP-WORKSPACE-STORE-LABEL-001-20261019-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-WORKSPACE-STORE-LABEL-001
base_sha: aec80dc4878333b59dcab914d44e676f99660148
final_sha: 6a3c5abc7ca8e07fdb52c6006e290e2076c38d5b
requirement_ids: [MVP-WORKSPACE-STORE-LABEL-001]
acceptance_ids: [AC-01, AC-02, AC-03]
test_record: docs/reports/tests/TR-MVP-WORKSPACE-STORE-LABEL-001-20261019-R01.md
review_record: null
created_at: 2026-10-19T10:48:37+08:00
updated_at: 2026-10-19T11:43:27+08:00
supersedes: null
---

# 实施目标与范围

用户截图中的工作台店铺筛选项显示 UUID 前八位，无法识别店铺。staging 已登录页面只读检查复现 `全部店铺 / 74bd2ebb`；系统设置页同时能展示授权店铺的名称。

# 实际变更及原因

原因是工作台从当前会话列表提取 `store_id`，再以 `id.slice(0, 8)` 作为选项文字。筛选或空列表还会让可选店铺消失。改为独立调用既有 `/settings/stores` 只读接口，显示用户有权访问的店铺名称，筛选请求仍使用店铺 ID；接口失败显示明确错误，URL 中现有筛选 ID 仍可清除。新增合成浏览器行为回归，覆盖显示名称及空列表后保留选项。无后端、数据库、权限、真实发送或配置变更。

源码 PR [#417](https://github.com/CP11-gh/CRM/pull/417) 已 squash 合并为 `6a3c5abc7ca8e07fdb52c6006e290e2076c38d5b`。独立 G5 后端修复使构建时 `main` 前进到 `e82b8ddba4297cabbc443311bb852952bb61d765`；两个提交的 `src/frontend` 与前端 Dockerfile 构建输入完全相同。从该 main 构建、发布并部署的单平台前端私有镜像为 `ghcr.io/cp11-gh/crm-frontend@sha256:77a710880ea63a804de53f57b421c75ebed96a56c87c7efbd86a8e2877344051`，OCI revision 精确匹配构建源码。下载期间 G5 验收仅推动 main 文档至 `7d0a1312a2e4235ae2c875ff97b8f240dd9b3eed`；与构建 SHA 的前端构建输入再次核对相同。

# 关键决定与偏差

继续使用受权限约束的现有店铺接口，不增加新 API。GitHub PR 自动触发的 Actions 两个作业在没有执行步骤时失败；本任务不以其结果作为测试或部署证据，使用本地质量门禁和手动 staging 路径。

# 数据、配置、接口、迁移或 Prompt 影响

复用既有受用户权限约束的只读店铺接口；后端、数据结构、配置、Prompt 与真实发送能力均无变更。staging 门禁确认数据库仍为 `024_tiktok_oauth_jobs`，后端、检索镜像和 G3 单店人工发送范围保持原状。

# 验证交接

合并 SHA 的 lint、typecheck、47 条契约测试、生产构建及 31 条生产模式浏览器测试通过。staging 手动 validate/deploy、三个公网健康接口、运行摘要、固定出口及登录工作台真实选项名称均核对通过，见关联 TR 和[低敏部署证据](../../../release/evidence/staging/crm-staging-store-label-deploy-20261019.json)。

# 限制、风险与回滚

仅改变筛选项显示和选项来源；未发送买家消息。上一版前端不可变摘要 `sha256:1addb6c82f9a76d27ec59e999e8dea172bc49f06227808ecee00e28a892db795` 保留为回滚点；production 不在本任务范围。
