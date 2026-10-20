---
record_id: RR-MVP-WORKSPACE-SEARCH-TRANSLATION-DEPLOY-001-20261020-R01
record_type: review
revision: R01
status: APPROVE
task_id: MVP-WORKSPACE-SEARCH-TRANSLATION-DEPLOY-001
reviewed_sha: a48f7447dfb905dcea5b30028544c1b0c04e1014
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-SEARCH-TRANSLATION-DEPLOY-001-20261020-R01.md
test_record: docs/reports/tests/TR-MVP-WORKSPACE-SEARCH-TRANSLATION-DEPLOY-001-20261020-R01.md
review_focus: [search-correctness, tenant-scope, staging-boundary, credential-handling, rollback]
created_at: 2026-10-20T10:11:07Z
updated_at: 2026-10-20T10:11:07Z
supersedes: null
---

# 审查范围、依据与重点风险

审查单项搜索空批量词修复、修复后不可变镜像与 staging 现场门禁。重点是查询是否仍限制在授权店铺/平台、是否意外扩大真实发送范围、临时凭据残留，以及数据库恢复会否覆盖部署后真实消息。

# 发现、级别、位置和证据

- 已解决：原 `get_session_list` 在 `terms=[]` 时忽略 `q`，导致单项搜索无过滤；合成回归先红后绿，真实会话搜索由 230 个降为 1 个。批量 OR 路径仍用非空 `terms`；已有跨店、分页和通配符隔离测试未改。
- 已解决：初始 Git archive 与 Linux checkout 的五个 CRLF 文件字节不同；最终门禁采用干净的同 SHA Git checkout、受审 origin 和当前 GitHub main 核对，未把失败的归档校验写成通过。镜像按 OCI revision、摘要、架构及 Rootless RepoDigest 独立核验。
- 已核对：人工真实发送仍只允许原一个店铺，Webhook 读取与翻译开关保持，通用 LLM/自动回复/高风险写入关闭。预览按钮出现并不等于调用模型或外发；现场均未执行。
- 已核对：本机与 staging 的临时 GHCR Docker 登录均注销，认证项为 0；低敏证据不含 Token、客户昵称、正文或店铺 UUID。
- 保留风险：旧镜像和受限备份可定位，但本轮未演练切回；恢复前必须保存新消息增量，不得直接用备份覆盖实时会话。公网既有间歇故障与 production G8 No-Go 仍在。

# 已验证与未验证内容

已验证精确主线源码、后端/前端不可变镜像、六摘要、手动 validate/deploy、11 容器、三个公网健康 200、原单店安全边界、真实搜索结果和六语言 UI。全量 PostgreSQL 回归在同一修复逻辑上通过，最终主线有定向 4/4 与静态检查；未在最终主线重跑完整 2223 项。未调用真实 DeepSeek、未发送 TikTok 消息、未验译文质量或 production。

# 结论和返修条件

**APPROVE，仅限当前 staging 部署及所观察的只读功能。** 若出现跨店搜索结果、未经人工审阅的外发、权限范围扩大或恢复目标改变，应停止继续放量并重新评审。
