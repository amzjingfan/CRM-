---
record_id: RR-MVP-WORKSPACE-EXPERIENCE-DEPLOY-001-20261020-R01
record_type: review
revision: R01
status: APPROVE
task_id: MVP-WORKSPACE-EXPERIENCE-DEPLOY-001
reviewed_sha: 4cd019c26f15bcbff2fb83f5175021e6a672a5cb
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-EXPERIENCE-DEPLOY-001-20261020-R01.md
test_record: docs/reports/tests/TR-MVP-WORKSPACE-EXPERIENCE-DEPLOY-001-20261020-R01.md
review_focus: [correctness, migration, staging-scope, credential-handling, rollback]
created_at: 2026-10-20T14:28:00+08:00
updated_at: 2026-10-20T14:37:25+08:00
supersedes: null
---

# 审查范围、依据与重点风险

审查已合并源码的 staging 手动部署组合、迁移 `025`、原 G3 单店发送边界、镜像/备份可恢复性及本轮 GitHub 凭据处理。对照 staging 专用门禁、独立运行核对和[低敏证据](../../../release/evidence/staging/crm-staging-workspace-experience-deploy-20261020.json)；不把浏览器按钮存在等同于真实写操作通过。

# 发现、级别、位置和证据

- 已解决：GHCR 原生直拉超时；改用同一镜像层的 OCI index 与分块 SHA-256 校验导入，六角色 RepoDigest 精确通过，没有以失败的直拉冒充通过。
- 已解决的安全事件：旧 GitHub CLI OAuth 凭据进入本地命令错误输出后，立即通过官方撤销接口撤销并验证失效；经用户授权重新登录，临时 Docker 认证目录在部署后清除。未在 Git 差异或低敏证据中包含凭据正文。
- 保留风险：迁移 `025` 增加列且旧版本 Alembic 头不包含此迁移；回滚前须保存部署后增量和新标记，不能直接恢复旧数据库备份覆盖真实消息。实际降级/回滚未演练，不能声称 G0 或 production 恢复能力因此通过。
- 保留风险：真实星标、转交、关闭及新未读事件未在 live 会话上写入验证；已合并源任务的隔离行为与权限测试支持功能，但本轮现场结论仅为只读可见性和打开定位末尾。

# 已验证与未验证内容

已验证后端/前端 OCI revision、Rootless 运行摘要、迁移头、单店开关、固定出口、11 容器、三健康 200 及只读 UI。未验证生产数据、production 发布、真实业务写操作、平台新增外发或真实回滚。PR #466 两项 Actions 检查虽显示 failure，Job API 确认均为零步骤、无 runner；未运行代码检查且未计为 CI 通过。

# 结论和返修条件

**APPROVE，仅限 staging 部署与当前只读验收。** 若目标改为扩大真实会话范围、生产部署或承诺可立即切回旧版，需要新的精确授权、迁移/恢复验证和门禁评审。
