# 本地检索模型资产

本目录保存 CRM 智能聊天系统 M04 RAG 使用的本地模型资产。大体积权重不进入版本库，仓库只保存本说明和 `model-manifest.json`。

## 当前状态

| 模型 | 用途 | 状态 | 本地目录 |
| --- | --- | --- | --- |
| `BAAI/bge-m3` | 1024 维 Dense 向量生成，预留 Sparse 和 ColBERT 能力 | 已接入，默认关闭 | `deploy/models/bge-m3` |
| `BAAI/bge-reranker-large` | 混合召回后的中英文 Cross-Encoder 重排序 | 已接入，默认关闭 | `deploy/models/bge-reranker-large` |

产品代码已通过内部单实例模型服务接入两个固定版本模型；迁移 `014_bge_hybrid` 已把知识向量切换到 1024 维，并创建 `pg_trgm` 词法索引。运行链路为 BGE-M3 Dense Top 20 + trigram Top 20，经 RRF 融合候选 Top 20，再由 Reranker 产出最终 Top 5。AI 功能仍默认关闭，正式启用前必须完成全量重新向量化、阈值标定以及测试工程师的质量和容量评测。

## 安全规则

- 只允许使用 `model-manifest.json` 固定的官方 `BAAI` 仓库和 Revision。
- BGE-M3 使用官方 `pytorch_model.bin`。该格式具有传统 PyTorch Pickle 供应链风险，禁止替换为来源不明的文件。
- Reranker 只保留 `model.safetensors`，不保存重复的 `pytorch_model.bin` 或 ONNX 文件。
- 模型目录只读挂载给 `retrieval-model-service`，backend 和 jobs 只调用内部 HTTP 契约，不得各自重复加载模型。
- `.cache/huggingface` 用于断点续传元数据，不进入版本库。

## 运行方式

模型服务位于 Compose 的 `ai` Profile。启动前必须在 `.env` 中设置随机 `RETRIEVAL_MODEL_SERVICE_TOKEN`，并先升级数据库迁移：

```powershell
docker-compose exec backend alembic upgrade head
docker-compose -f docker-compose.yml -f docker-compose.ai.yml --profile ai up -d --build
# GPU 环境追加：-f docker-compose.gpu.yml
```

`docker-compose.ai.yml` 启用本地模型并让 backend/jobs 等待模型健康；`docker-compose.gpu.yml` 只启用 NVIDIA GPU。模型服务使用只读模型挂载、离线加载、单 Worker 和非 root 用户，健康接口不返回路径、密钥或模型正文。

开发环境真实权重冒烟已验证 1024 维有限向量和重排序顺序，但该结果不等同于正式质量或性能结论。

生产或 staging 不直接挂载本仓库目录。服务器使用仓库外 `RETRIEVAL_MODEL_ASSET_DIR`
（推荐 `/srv/crm/models`）保存相同的两个模型目录，生产 Compose 只读挂载到 `/models`，
并在启动时强制执行六个运行文件的固定 SHA-256 校验。目录准备和门禁说明见
`deploy/production/README.md`。

2026-08-21 的 OSV 审计对锁定的 PyTorch/Transformers 报告已知漏洞。生产启用前必须完成安全版本兼容评估与测试工程师复核；固定 Revision、哈希、离线模式和非 root 运行不能替代依赖修复。

## 校验

配置、分词器、权重、固定提交、大小和 SHA-256 见 `model-manifest.json`。两个分词器摘要由固定 Revision 的官方 Xet 指针复核；两个配置文件先以下载元数据中的 Git blob SHA-1 核验官方固定 Revision 字节，再登记本地 SHA-256。下载与复核流程见项目 AI 工程师目录中的 `AI-003-MODEL-BGE本地模型下载与校验指南-v1.0.md`。
