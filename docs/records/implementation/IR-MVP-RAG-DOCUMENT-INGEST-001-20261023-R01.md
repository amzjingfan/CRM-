---
record_id: IR-MVP-RAG-DOCUMENT-INGEST-001-20261023-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-RAG-DOCUMENT-INGEST-001
base_sha: 5adaf0be9371e2a866d1e7848858aa5a41bae686
final_sha: 5ae37c54ec4abfe49a65b11525f08214bb182f65
requirement_ids: [MVP-RAG-DOCUMENT-INGEST-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
test_record: docs/reports/tests/TR-MVP-RAG-DOCUMENT-INGEST-001-20261023-R01.md
review_record: docs/reports/reviews/RR-MVP-RAG-DOCUMENT-INGEST-001-20261023-R01.md
created_at: 2026-10-23T08:05:00Z
updated_at: 2026-10-23T08:05:00Z
supersedes: null
---

# 实施目标与范围

按[设计](../../superpowers/specs/2026-10-23-rag-document-ingestion-design.md)和[实施计划](../../superpowers/plans/2026-10-23-RAG知识库模块实施计划.md)，交付知识库通用文件从上传、MinerU 本地解析、保守清洗、整版质量判定、真实分块、BGE-M3 向量化到 PostgreSQL pgvector 的闭环。本期只建立文档入口及管理交互；Agent 检索、Rerank 召回、自动回复和 production 发布未接入。

# 实际变更及原因

- 新增独立文档文件、不可变版本、解析单元、向量块、导入回执和店铺设置模型；原件和解析产物存放在私有 MinIO，FAQ CSV/XLSX 导入及既有 `knowledge_chunks` 路径保留。
- 解析 Worker 独立运行 MinerU 4.0.12；本地受控解析和 CPU ONNX 路径支持 PDF、Office、表格、文本和图片。无可靠文本、OCR 或关键表格结构问题按单元标记，但**整份新版本**保持 `review_required` 且不写任何向量。人工确认或修订全部问题单元后才继续整版入库。
- 九种策略、大小、重叠、解析模式和模型配置经过前后端校验并冻结在版本中。BGE-M3 生成 1024 维向量；版本块保留店铺、文件、版本、单元、定位、标题、策略、清洗及模型修订等溯源字段。新旧版本在同一事务中切换，待复核和失败期间旧有效版本保持不变。
- 新增店铺隔离的列表、详情、设置、导入、复核和重试接口，以及知识库上传与进度界面。改内容的同名文件要求上传者明确选择替换目标；写操作沿用权限、CSRF、幂等及审计边界。检索参数界面明确标识本期不生效。
- 主线同时出现独立的基础接待 `029` 迁移，新增 `030_merge_rag_reception` 合流两条迁移头；分别验证从已部署 RAG `029` 和接待 `029` 进入 `030`。最终前端将 Next.js 从 16.3.8 升至修复版 16.4.2，官方 npm 生产依赖审计为 0 项漏洞。

# 数据、配置、接口、迁移或 Prompt 影响

新增 `/v1/knowledge/files` 及 `/v1/knowledge/file-settings` 契约和 `029_knowledge_file_ingestion`、`030_merge_rag_reception` 迁移。文档解析容器使用已冻结的 MinerU 模型资产、只读根文件系统和资源上限；向量写入现有 PostgreSQL 的独立 `knowledge_file_chunks` 表。运行时 GPU 不可用可在 CPU 配置下继续处理或重试，不热切换、不绕过复核。对应当前事实已同步至架构、AI、API、部署与测试文档。

# 验证交接

本地全量后端、真实 PostgreSQL/pgvector、前端契约、生产浏览器、类型、lint、构建和生产依赖安全审计，以及 staging 手动精确摘要部署和真实合成文件全链路见 [TR](../../reports/tests/TR-MVP-RAG-DOCUMENT-INGEST-001-20261023-R01.md)。低敏现场事实见[发布证据](../../../release/evidence/staging/crm-staging-rag-document-ingestion-20261023.json)。后端和解析器镜像的源码修订为 `69f32427395baeef310f37c78455efdd60ecc456`；该提交到最终 subject 的后端及两份镜像 Dockerfile 差异为空。前端镜像 OCI revision 为最终 subject。

# 限制、风险与回滚

staging 有合成测试文件和版本，不接入 Agent 检索，也未对真实店铺执行导入或外发消息。备份可读性已核对，整库恢复未实演。回滚优先切回部署前后端、前端、解析器精确摘要，保留新增版本、原件及向量；不得以部署前 PostgreSQL/MinIO 快照直接覆盖之后的业务增量。MinerU 商用许可证义务、真实复杂文档样本和生产门禁须在生产放行前另行复核。
