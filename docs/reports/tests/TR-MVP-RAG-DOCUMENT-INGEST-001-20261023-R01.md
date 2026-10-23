---
record_id: TR-MVP-RAG-DOCUMENT-INGEST-001-20261023-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-RAG-DOCUMENT-INGEST-001
tested_sha: 5ae37c54ec4abfe49a65b11525f08214bb182f65
implementation_record: docs/records/implementation/IR-MVP-RAG-DOCUMENT-INGEST-001-20261023-R01.md
requirement_ids: [MVP-RAG-DOCUMENT-INGEST-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: isolated local PostgreSQL/pgvector and Windows Next.js production build; rootless Linux staging with CPU MinerU and BGE-M3
created_at: 2026-10-23T08:05:00Z
updated_at: 2026-10-23T08:05:00Z
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT: centralized`。本地测试使用 `src/tests/` 和隔离的 PostgreSQL/pgvector，staging 使用授权合成店铺、私有 MinIO 和真实解析/向量 Worker。所有网页请求均指向 staging；没有真实 TikTok 买家外发。

# 命令和逐项结果

| 验证 | 本次结果 |
|---|---|
| `uv run --frozen pytest -q -rs`，隔离 PostgreSQL 已迁移 | 2379 passed、3 skipped、2 个既有弃用提示；九种分块、质量门禁、权限/隔离/幂等、失败恢复和 pgvector 集成覆盖。后端源码和测试在该运行后至最终 subject 没有改变。 |
| `uv run ruff check`、`ruff format --check`、`uv run mypy app scripts` | 通过；mypy 覆盖 208 个源码文件。 |
| Alembic 双路径升级 | 从 `029_knowledge_file_ingestion` 及独立 `029_reception_group_enabled` 均升级到唯一头 `030_merge_rag_reception`；临时测试库已清理。 |
| `npm run test`、`npm run typecheck`、`npm run lint`、`npm run build` | 48/48，类型和生产构建通过；lint 0 error、5 条既有 warning。 |
| `UI_BASE_URL=http://127.0.0.1:3127`、`UI_CACHE_EXPECT_PRODUCTION=1`、`npm run test:ui` | 最终 Next.js 16.4.2 生产构建上 85/85；含导入配置、同名替换和整版复核交互。 |
| `npm audit --omit=dev --registry=https://registry.npmjs.org` | 生产依赖 0 漏洞。全依赖审计仍有 11 项开发依赖告警，未进入生产运行镜像。 |
| staging `ValidateOnly`、精确摘要 `Deploy` | 均通过；迁移头 `030`、12 容器、解析器重启 0/只读根、五个公网入口 HTTP 200，前端容器 Next.js 16.4.2。 |
| staging 真实文件 API、Worker、MinerU、BGE-M3、pgvector | 原生 PDF 与 Office 自动 ready；图片及混合页整版 review_required、0 向量；图片人工修订后 ready。同名变更未选替换为 409，选定后新版成为 active，旧版块仍保留；跨店读 404。 |
| staging 数据库核对 | 有效块均 1024 维，策略/模型/哈希/定位元数据存在；待复核混合 PDF 仍 0 块。长 PDF 用固定 Token `32/4` 实得 19 块，最大 32 Token。 |
| CPU 路径 | BGE 服务 `torch.cuda.is_available()` 为 false；解析器无 GPU 设备，ONNX `CPUExecutionProvider` 可用且完成图片解析。 |

# AC 与证据映射

- AC-01：图片及混合 PDF 在 staging 直接验证 `review_required`、数据库 0 新向量；修订后整版入库，旧有效版本保留。参见[低敏现场证据](../../../release/evidence/staging/crm-staging-rag-document-ingestion-20261023.json)。
- AC-02：九种策略、大小/重叠和格式适用性由后端/前端测试覆盖；staging 选用固定 Token、标题段落、OCR 布局、递归分块，并以长 PDF 实证 `32/4` 设置进入实际块。FAQ 原路径由回归测试保持。
- AC-03：权限、CSRF、幂等、审计、店铺隔离、重复提交/替换、重试和恢复由后端/集成测试覆盖；staging 跨店 404、同名 409/显式替换和旧版保留再次核对。
- AC-04：私有 PostgreSQL/MinIO 备份模式 `0600`，`pg_restore -l` 可读；双迁移路径、手动门禁、CPU、健康和不可变运行摘要见低敏证据。没有 GitHub Actions 部署。

# 缺陷、未执行项与残余风险

前端生产浏览器首次运行有一条既有会话筛选用例在异步选中完成前读取状态；改为等待选中状态后，定向和全部 85 项均通过，业务逻辑未变。独立 staging 镜像无法稳定直接远程下载时，经本机校验 SHA-256 后用受限目录传入 Docker 归档，远端加载并以仓库摘要再次核对；门禁最终通过。真实店铺文件、GPU 故障发生时的进程内热切换、整库恢复和 production 未测试或发布；CPU 已在无 CUDA 的 staging 真实执行。九种策略没有全部逐一在 staging 跑真实样本，完整策略行为由隔离本地测试覆盖。全依赖开发工具告警待独立维护，不将其计为生产镜像漏洞。

# 结论和复测条件

AC-01～04 在本期限定范围内 `PASS`，可作为 staging 文档入口使用。任何解析器、清洗规则、分块、模型、迁移或权限修改，需重新跑受影响策略样本、整版零向量、隔离和现场门禁；Agent 检索与 production 另行验收。
