---
record_id: IR-MVP-AGENT-TEMPLATE-UI-STAGING-001-20261031-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-AGENT-TEMPLATE-UI-STAGING-001
final_sha: d6de3be766d6656eadfe8e410dff6981c01fea4a
requirement_ids:
- MVP-AGENT-TEMPLATE-UI-STAGING-001
acceptance_ids:
- AC-01
- AC-02
- AC-03
- AC-04
created_at: '2026-10-31T08:22:48.825247+00:00'
updated_at: '2026-10-31T08:22:48.825247+00:00'
supersedes: null
base_sha: 6074c4b001aa37e1653db3a3a7f226dd3e2077e3
test_record: docs/reports/tests/TR-MVP-AGENT-TEMPLATE-UI-STAGING-001-20261031-R01.md
review_record: docs/reports/reviews/RR-MVP-AGENT-TEMPLATE-UI-STAGING-001-20261031-R01.md
deployed_source_sha: 6074c4b001aa37e1653db3a3a7f226dd3e2077e3
integration_base_sha: 743eb782904e39065c1a9d8779749f4af613198c
---

文档交付候选 subject 为 `d6de3be766d6656eadfe8e410dff6981c01fea4a`；该SHA仅绑定本轮发布说明与静态校验，实际构建/运行/模型测试对象单列 `deployed_source_sha=6074c4b001aa37e1653db3a3a7f226dd3e2077e3`。不能将文档候选误认为运行镜像，也不将后合入工作台源码算作部署验证。


# 实施目标与实际结果

用户批准将已合并 Agent 模板 UI 和回复偏好修复手动部署 staging，并测试后清理本轮合成数据。冻结发布来源 `6074c4b001aa37e1653db3a3a7f226dd3e2077e3`，来自源码/收尾 PR #696/#697；没有将发布期间另一任务合入的工作台目录/侧栏变更追加进本次镜像。集成文档时主线为 `743eb782904e39065c1a9d8779749f4af613198c`，证据分支相对该主线仅有文档和低敏证据，不把其额外源码冒充已部署或已验收。

官方 Dockerfile 干净 Git archive 构建 backend/frontend，核对 OCI linux/amd64、源码 revision、原始 blob 与 GHCR manifest。镜像摘要见[低敏证据](../../../release/evidence/staging/crm-staging-agent-template-ui-20261031.json)。私有 env/PostgreSQL/MinIO 备份及可读目录检查完成；原版/候选 ValidateOnly 均通过，锁内 Deploy 完成，048、12 服务、固定出口和三个公网健康通过。

服务器 GHCR 拉取首次 TLS 超时且尚未切换；只停止本轮门禁及其拉取子进程，使用已校验内网 OCI 传输/导入，再次经过同一门禁成功。没有放宽镜像、认证或运行校验。

# 验收和清理

正式 API 保留 Cookie 身份、有效登录会话、CSRF、权限和店铺隔离。用户批准的临时凭证仅在内存使用；首轮10分钟窗口过期后按精确补充批准仅5分钟清理，不续期模型测试。8项最终实际模型/RAG/原生流式参数链路结果通过（语气未作本轮独立语义评分）；两店预览与后台批次完成，回复参数和文件不跨店复制。浏览器真实模板布局、两店多选/搜索保留、无可见分页已核对并截图。

7个合成 Agent、4份合成文件软删除，2个合成模板归档；0分类创建，2个完成批次与审计保留。清理 API 404 与独立只读数据库盘点均通过，既有4个 Agent 与原模板不变，零买家外发。未知工作树、旧凭据副本、备份与用户资料均保留。

# 恢复边界

回退使用证据中的原完整前后端摘要及原开关/两店人工发送范围，保留048可空字段和部署后业务增量；没有实际回滚/恢复演练。production 未发布。
