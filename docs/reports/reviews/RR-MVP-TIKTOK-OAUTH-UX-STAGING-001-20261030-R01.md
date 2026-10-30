---
record_id: RR-MVP-TIKTOK-OAUTH-UX-STAGING-001-20261030-R01
record_type: review
revision: R01
status: APPROVE
task_id: MVP-TIKTOK-OAUTH-UX-STAGING-001
reviewed_sha: 18a0d7bb0b0ca6b2bb601de32af7128d1a41a9ec
implementation_record: docs/records/implementation/IR-MVP-TIKTOK-OAUTH-UX-STAGING-001-20261030-R01.md
test_record: docs/reports/tests/TR-MVP-TIKTOK-OAUTH-UX-STAGING-001-20261030-R01.md
review_focus: [release_source, authorization_scope, store_isolation, backup, rollback, runtime_mode, no_external_send]
created_at: 2026-10-30T04:04:03Z
updated_at: 2026-10-30T04:04:03Z
supersedes: null
---

# 审查范围、依据与重点风险

审阅本轮 staging 发布源码、原运行镜像、五文件差异、固定模式、恢复点和现场门禁。重点检查错误镜像覆盖正在运行的部门/Agent 功能、扩大 TikTok 真实发送范围、丢失代理持久挂载、泄露凭据及将部署健康误判为真实 OAuth 成功。

# 发现、级别、位置和证据

- 远端主线构建期间新增两次部门发布文档提交；前后端、Dockerfile、Compose 和门禁 Git 对象完全一致。最终镜像 OCI revision、部署归档与当前主线统一为 18a0d7bb；无新增产品差异。
- 当前后台仅 1 家店铺可人工真实发送。候选门禁参数从现场后端只读提取该 allowlist，不将店铺 ID 写入发布证据；部署后仍为 1，自动回复、营销、高风险写入关闭。
- 前后端旧摘要在 Rootless Docker 中可用，PostgreSQL/MinIO/环境备份可读。回滚须保留当前业务增量，不以旧整库覆盖。没有执行不必要的降级或真实平台写入。
- 代理配置来自本次持久源码且只读；源码文件与运行挂载 SHA-256 相同。12 服务及健康、044 迁移头、检索与解析器不变。
- GHCR 临时授权仅用于镜像发布和拉取，使用独立 Docker 配置；本机与服务器登出后核对无授权项。未把密钥、Token、平台原始响应、客户正文或店铺 ID 写入仓库证据。

# 已验证与未验证内容

发布/预检/切换/健康与页面 JS 资源已经现场核对，原授权实现的安全审查见 RR-MVP-TIKTOK-OAUTH-UX-001-20261030-R01。未在已登录真实店铺上再次进行 OAuth，也未演练备份整库恢复；本审查只批准本轮 staging 发布记录，不扩展 G1 或 G8 结论。

# 结论和返修条件

APPROVE：本轮 staging 版本、运行模式与恢复点满足限定部署门禁。若后续要触发真实 OAuth 或扩大店铺人工发送 allowlist，应使用相应任务的独立授权和现场证据。
