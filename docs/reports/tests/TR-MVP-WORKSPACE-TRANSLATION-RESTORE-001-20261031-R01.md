---
record_id: TR-MVP-WORKSPACE-TRANSLATION-RESTORE-001-20261031-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-WORKSPACE-TRANSLATION-RESTORE-001
tested_sha: 1e7e15fba356877876e71f7d70cafcd1235d571e
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-TRANSLATION-RESTORE-001-20261031-R01.md
requirement_ids: [MVP-WORKSPACE-TRANSLATION-RESTORE-001]
acceptance_ids: [AC-01, AC-02, AC-03]
environment: staging Rootless Docker, existing backend d67078db and frontend a0d9938e, migration 046_merge_templates_dispatch
created_at: 2026-10-31T00:07:06Z
updated_at: 2026-10-31T00:07:06Z
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

TEST_LAYOUT: centralized。本次无产品源码或测试源码变更；现场只验证翻译配置恢复、部署门禁、运行边界与登录态工作台入口。未发送买家消息、未操作退款或 production。

# 命令和逐项结果

- 源码检查：受审 staging checkout 干净，HEAD d67078db；手动门禁脚本 SHA-256 6ff59aef…a7388e6，翻译 overlay fc1e4a40…8797a。后端/前端运行镜像摘要在切换前后相同。
- 切换前容器 WORKSPACE_MESSAGE_TRANSLATION_ENABLED=false，源码 workspace/service.py 以该开关计算 translation_enabled；MessageBubble.tsx 因此隐藏英文文字消息的“译成中文”按钮。
- 私有备份：环境 SHA 0621a122…b5cb0，PostgreSQL custom dump f3641563…a1ae 且 pg_restore -l 可读，MinIO 63024efd…e443 且 tar -tzf 可读；目录 0700、文件 0600。备份脚本末尾通配符校验受 CRLF 干扰返回 1，随后逐文件校验和读取通过，没有把该退出码冒充成功。
- 当前配置 ValidateOnly 与带 -EnableWorkspaceTranslation 候选 ValidateOnly 均通过；原件 SHA 分别 6e2a0970…406e、90ab0fb1…5839。初次 Deploy 因 PowerShell 参数传递错误未切换；下次被 GHCR 拒绝也未切换。完成临时镜像仓库认证后按同一摘要重试，Deploy 通过，原件 SHA 9e186e76…89c8；已退出临时 GHCR 登录。
- 部署后运行容器开关为 true，三公网健康 /healthz、/v1/health、/v1/health/ready 均 200，迁移仍为 046，固定出口 38.55.145.52。人工发送允许列表仍为两店；自动回复、营销、高风险写入、G5 SSE 仍关闭。
- 已登录 staging 工作台 AX 树中，英文买家与客服文字消息可见“译成中文”按钮；系统消息无翻译按钮。没有点击按钮或发送操作。

# REQ/AC 或门禁与证据映射

AC-01 根因：源码链路和切换前运行开关；AC-02 恢复：双预检、Deploy、运行开关与已登录 UI；AC-03 边界：精确镜像、私有备份、迁移、健康及安全开关。低敏机器证据见 release/evidence/staging/crm-staging-workspace-translation-restore-20261031.json，门禁原件保存在 staging 私有目录。

# 缺陷、未执行项与残余风险

未执行真实 DeepSeek 翻译请求，因而未验证供应商响应、时延和译文质量。没有触发外部消息、退款或 production 操作。首次失败部署的参数和认证问题已修正，不影响最终门禁通过。

# 结论和复测条件

staging 翻译入口恢复且安全边界保持。后续若验证译文质量，须另行做坐席显式单条请求并记录供应商结果；后续每次 staging 切换按部署说明保留翻译 overlay 并核对运行态。
