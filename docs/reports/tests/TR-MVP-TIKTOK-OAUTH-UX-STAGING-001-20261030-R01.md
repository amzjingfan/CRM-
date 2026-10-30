---
record_id: TR-MVP-TIKTOK-OAUTH-UX-STAGING-001-20261030-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-TIKTOK-OAUTH-UX-STAGING-001
tested_sha: 18a0d7bb0b0ca6b2bb601de32af7128d1a41a9ec
implementation_record: docs/records/implementation/IR-MVP-TIKTOK-OAUTH-UX-STAGING-001-20261030-R01.md
requirement_ids: [MVP-TIKTOK-OAUTH-UX-STAGING-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: Windows local Docker linux/amd64; staging Rootless Docker crm-staging; HTTPS staging.overselfx.com
created_at: 2026-10-30T04:04:03Z
updated_at: 2026-10-30T04:04:03Z
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

TEST_LAYOUT: centralized。验证本轮镜像、备份、配置、staging 切换和公网资源；授权交互使用原任务合成测试及本轮源码/部署 bundle 对照，不发起真实 OAuth。

# 命令和逐项结果

- git diff b21f59a7..18a0d7bb -- src/backend src/frontend src/docker src/deploy：产品差异只有 5 个已批准 OAuth 文件；逐一比较 be936358 与 18a0d7bb 的 5 个 Git blob 均相同。1eb6dbd1 与 18a0d7bb 的构建输入和门禁文件 Git 对象一致。
- GitHub publish-backend-image.yml run 40998702571 与 publish-frontend-image.yml run 40998706414：均 failure、steps=0，未执行 CI；改用本地 Docker linux/amd64 构建并推送两个 GHCR 私有镜像。远端 OCI manifest 均为 application/vnd.oci.image.manifest.v1+json，Rootless Docker 的 RepoDigests、平台与 OCI revision 精确匹配。
- Git archive 18a0d7bb 的本地与 staging SHA-256 均为 3b42c65d…d9e9，verify_staging_source_archive.py 逐文件通过。旧/新前后端、检索与解析器六个 RepoDigest 在 staging 逐项通过；部署前 12 容器及 044 head 正常。
- 受限备份：PostgreSQL 自定义 dump SHA-256 e881a0d4…e630，pg_restore -l 返回 0；MinIO 归档 SHA-256 6217a54b…1ce5，归档可读；环境备份 SHA-256 0621a122…5cb0，文件模式 0600。
- Test-StagingProductionGates.ps1：原模式预检 validated，候选 ValidateOnly validated，候选 Deploy passed；门禁原件 SHA-256 分别 c2f61768…733c、c6499dc2…8fe5、50df5657…0d2f。部署检查三公网健康 200，固定出口 configured/observed 均为 38.55.145.52，production_release=false。
- 部署后独立 docker inspect：12 服务 healthy/running，5 个后端角色及前端新摘要准确，检索与文档解析镜像不变；Webhook 只读、单店人工发送、翻译、Agent 调试/正式建议及文档解析保持，自动回复、营销、高风险写入关闭。alembic current --check-heads 为 044_reception_assignment (head)。代理配置挂载来自本轮持久源码、只读，SHA-256 与仓库一致。
- 公网无查询参数 GET：/login、/marketing、/knowledge、/settings/stores、/settings/channels 及三个健康路径均 200。HTML Cache-Control 含 no-store；指纹 JS 200 且 immutable。实际部署的渠道 bundle 不含旧 TikTok Shop OAuth 标题，含行内重新授权文本；店铺 bundle 含添加店铺文本。
- node --test src/tests/frontend/contract/tiktok-oauth.test.mjs：4 passed、0 failed。原修复 TR R01 的相关浏览器 9、后端 OAuth 53、前端契约 55 与构建基于逐 blob 相同的源码，不伪称本轮重跑。临时 GHCR 凭据本机和服务器均已注销并核对无授权项。

# REQ/AC 或门禁与证据映射

AC-01 镜像发布与源码身份：PASS。AC-02 保持运行模式及恢复点：PASS。AC-03 staging 健康、页面资源与已批准单入口代码：PASS（实际登录点击和真实 OAuth 未执行）。AC-04 不外发、不扩权、production 不发布：PASS。完整低敏摘要见 release/evidence/staging/crm-staging-oauth-single-entry-20261030.json。

# 缺陷、未执行项与残余风险

首次候选模式预检因命令从 root 的不可访问工作目录启动而失败；从 crmdeploy 可访问目录重试后通过，服务未受影响。两个 GitHub 镜像发布作业零步骤失败，不计为验证；证据 PR #656 的 run 41001262146 两项质量作业也均 runner 为空、steps=0，按项目已持续批准的本地替代门禁使用本轮文档链接、JSON、索引、隐私、diff 检查及发布现场结果，不称 CI 通过。未执行真实 OAuth callback、真实多店选择、真实买家外发、整库恢复及 production 发布；这些不属于本次部署通过的证明范围。

# 结论和复测条件

本次 staging 发布及可见资源检查 PASS。若真实店铺授权仍要求二次操作，需按对应 OAuth job、store/channel 聚合状态和失败码另行现场诊断；不能仅凭本次部署声明真实授权成功。
