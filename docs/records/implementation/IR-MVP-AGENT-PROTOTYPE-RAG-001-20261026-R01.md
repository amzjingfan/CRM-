---
record_id: IR-MVP-AGENT-PROTOTYPE-RAG-001-20261026-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-AGENT-PROTOTYPE-RAG-001
base_sha: c755716e8efeb99538c366a185747df2dc836216
final_sha: 09455b510f1e8f2281d1ad4f0fb8911fc8ae6ae0
requirement_ids: [MVP-AGENT-PROTOTYPE-RAG-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05, AC-06]
test_record: docs/reports/tests/TR-MVP-AGENT-PROTOTYPE-RAG-001-20261026-R01.md
review_record: docs/reports/reviews/RR-MVP-AGENT-PROTOTYPE-RAG-001-20261026-R01.md
created_at: 2026-10-26T02:34:46Z
updated_at: 2026-10-26T02:34:46Z
supersedes: null
---

# 实施目标与范围

依照用户提供的 Agent 管理 v3 HTML 原型完成五个配置页签、新建、店铺切换、运行记录及本地预览；将知识库导入文件真实绑定到 Agent 检索，并为 Embedding、SQL 和重排设置单次总超时。服务范围仍为 TikTok 人工辅助建议。

# 实际变更及原因

- Agent 配置新增服务/经营类型和店铺内文件 ID 绑定；绑定时校验文件可用性和 `knowledge.view`。经营类不能启用客服运行。页面配置保存后从真实 API 回读，店铺切换清除旧文件、日志和临时选择。
- 文件版本新增内部建议审批语义、审批人和时间，配套审批/撤销 API、权限、CSRF、幂等与审计。替换文件生成的新版本默认未审批；解析复核与建议使用审批分开。
- 文件向量检索使用同店铺显式绑定、当前有效版本、索引就绪、人工审批、未归档/删除和相同 Embedding 模型门禁；Dense 与词法候选融合后沿用现有重排、安全引用和结构化生成。无文件绑定的 Agent 仍走 FAQ 路径。
- Agent 调用 RAG 的查询向量化、连接获取、Dense/词法 SQL、融合和重排共享 12 秒预算；超时记 `RAG_RETRIEVAL_TIMEOUT` 失败终态，不继续生成答复。
- 前端按原型组织布局、弹窗、工具和知识列表。模型下拉与自动发送开关只演示页面状态，生产 Prompt 仅展示只读摘要；预览不调用模型或平台。

# 关键决定与偏差

模型切换、任意 Prompt 编辑和真实自动发送超出当前获批的人工辅助产品边界，页面明确标为演示。文件审批要求人明确选择语义类型；技术资料仅允许无客户范围，客户实例事实拒绝进入通用建议。预览不能被误认作真实 Agent 回答。

# 数据、配置、接口、迁移或 Prompt 影响

迁移 033 为文件版本增加审批字段，并为文件分块增加向量 HNSW 和词法 trigram 索引；已批准数据存在时降级拒绝丢失审批状态。Agent 绑定保存在既有 `knowledge_scope` JSON。新增文件版本审批/撤销接口、Agent 配置字段和运行时可用模型只读列表；生产 Prompt 文本和模型发布配置不变。

# 验证交接

完整命令与结果见 [TR](../../reports/tests/TR-MVP-AGENT-PROTOTYPE-RAG-001-20261026-R01.md)，权限、租户、迁移及超时审查见 [RR](../../reports/reviews/RR-MVP-AGENT-PROTOTYPE-RAG-001-20261026-R01.md)。本次未部署 staging 或 production，也未调用真实模型或 TikTok。

# 限制、风险与回滚

文件审批是人工内容判断，自动化只验证门禁和路由；真实质量须以受控样本另验。迁移建索引可能在大库耗时，发布前需按数据量评估窗口。回滚优先恢复应用镜像并保留新增列；如已有审批记录，不能直接降级 033。
