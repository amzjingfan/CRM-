---
record_id: TR-MVP-DEPARTMENT-RECEPTION-COPY-STAGING-001-20261030-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-DEPARTMENT-RECEPTION-COPY-STAGING-001
tested_sha: b5d4985b42fc2daac677a16805bfa18126b6439e
implementation_record: docs/records/implementation/IR-MVP-DEPARTMENT-RECEPTION-COPY-STAGING-001-20261030-R01.md
requirement_ids: [MVP-DEPARTMENT-RECEPTION-COPY-STAGING-001]
acceptance_ids: [AC-01, AC-02, AC-03]
environment: staging crmdeploy Rootless Docker, authenticated in-app browser, HTTPS staging.overselfx.com
created_at: 2026-10-30T12:34:25Z
updated_at: 2026-10-30T12:34:25Z
supersedes: null
---

# 现场结果

TEST_LAYOUT: centralized。原功能候选的浏览器红绿、55 项前端契约、静态检查与构建见[功能 TR](TR-MVP-DEPARTMENT-RECEPTION-COPY-001-20261030-R01.md)，本轮不冒充重跑。

- AC-01：已合并主线 `b5d4985b` 干净 checkout；前端 linux/amd64 OCI revision、远端 RepoDigest、镜像 tar 与 Git bundle SHA-256 通过。后端保持 `sha256:1e42a829…e3a2`。
- AC-02：私有 PostgreSQL 自定义格式转储、MinIO 压缩包和环境备份可读且为 0700/0600；旧版和候选 ValidateOnly、候选 Deploy 均通过；045 仍为迁移头，12 个服务运行或健康，五个公开路径 HTTP 200。
- AC-03：已登录 staging 部门页刷新后切换到部门店铺咨询分配，原长段落消失，负责店铺标题、派单开关、待领取原因和客服表格可见。后端运行开关及人工发送两店范围保持；临时 GHCR 凭据已注销，零真实买家测试外发，production 未部署。

门禁原件、备份和摘要见[低敏 JSON](../../../release/evidence/staging/crm-staging-department-reception-copy-20261030.json)。未以主管独立登录或真实 TikTok 入站演练本轮 UI 文案变更；当前派单没有参与者，不能把开关开启解释为已自动接待。
