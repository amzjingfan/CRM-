# BGE 本地模型下载、校验与启用指南

## 1. 文档信息

| 项目 | 内容 |
| --- | --- |
| 文档编号 | AI-003-MODEL |
| 版本 | v1.0 |
| 模块编号 | M04 |
| 主责 Agent | AIAgent开发工程师Agent |
| 状态 | 已生效 |
| 生效日期 | 2026-08-21 |

## 2. 目的与边界

本指南用于把固定版本的 BGE-M3 和 BGE Reranker 下载到项目部署目录，并生成可追溯的模型资产清单。

本指南最初只负责模型资产下载。2026-08-21 架构师确认后，产品已完成本地 Provider、单实例模型服务、`014_bge_hybrid` 结构迁移、`015_vector_ops` 运维索引、混合检索和重排序接入；测试工程师已完成正式质量、容量和依赖安全评测。

## 3. 固定模型

| 用途 | 模型 | Revision | 权重格式 | 本地目录 |
| --- | --- | --- | --- | --- |
| 向量生成 | `BAAI/bge-m3` | `5617a9f61b028005a4858fdac845db406aefb181` | `pytorch_model.bin` | `deploy/models/bge-m3` |
| 重排序 | `BAAI/bge-reranker-large` | `55611d7bca2a7133960a6d3b71e083071bbfc312` | `model.safetensors` | `deploy/models/bge-reranker-large` |

BGE-M3 输出 1024 维向量，最长支持 8192 Token。当前使用 Dense 向量，混合检索的词法通道由 PostgreSQL `pg_trgm` 提供；BGE Sparse 和 ColBERT 文件作为后续评估资产保留。Reranker 是中英文 Cross-Encoder，原始分数不应直接视为 0 到 1 的业务置信度。

## 4. 下载命令

Hugging Face Hub 0.x CLI 不支持本指南使用的 `--dry-run`。下载工具使用一次性 `huggingface_hub>=1,<2`，不加入项目 `pyproject.toml`。

```powershell
$modelRoot = "E:\develop\CRM智能聊天系统\CRM智能聊天系统\deploy\models"
$env:UV_CACHE_DIR = "E:\develop\CRM智能聊天系统\CRM智能聊天系统\.uv-cache\huggingface-cli-v1"

uvx --from "huggingface_hub>=1,<2" hf download BAAI/bge-m3 `
  --revision 5617a9f61b028005a4858fdac845db406aefb181 `
  --exclude "onnx/*" `
  --exclude "imgs/*" `
  --exclude "*.jpg" `
  --dry-run

uvx --from "huggingface_hub>=1,<2" hf download BAAI/bge-reranker-large `
  --revision 55611d7bca2a7133960a6d3b71e083071bbfc312 `
  --exclude "onnx/*" `
  --exclude "pytorch_model.bin" `
  --dry-run
```

移除 `--dry-run` 并增加相应 `--local-dir` 后执行正式下载。匿名下载不需要模型 API Key；如果触发公共仓库限流，只能使用专用 Hugging Face Token，不得复用 OpenAI 或 DeepSeek Key，也不得把 Token 写入命令、日志或文档。

## 5. 完整性校验

关键文件要求：

```text
bge-m3/
├─ config.json
├─ modules.json
├─ pytorch_model.bin
├─ sentencepiece.bpe.model
├─ tokenizer.json
├─ tokenizer_config.json
├─ colbert_linear.pt
└─ sparse_linear.pt

bge-reranker-large/
├─ config.json
├─ model.safetensors
├─ sentencepiece.bpe.model
├─ tokenizer.json
└─ tokenizer_config.json
```

当前已验证权重：

| 模型 | 文件大小 | SHA-256 |
| --- | ---: | --- |
| BGE-M3 | 2,271,145,830 字节 | `b5e0ce3470abf5ef3831aa1bd5553b486803e83251590ab7ff35a117cf6aad38` |
| BGE Reranker | 2,239,618,772 字节 | `c5ae4e262c60ed2fb507ec587358285377ec36ee0a2e6da029f0534272b06d36` |

本地 SHA-256 必须与 `deploy/models/model-manifest.json` 以及 Hugging Face 下载元数据一致。Reranker 目录不得出现 `pytorch_model.bin` 或 `onnx/`。

## 6. 供应链与运行安全

- 固定模型 ID、完整 Revision 和 SHA-256，禁止直接依赖可变的 `main`。
- BGE-M3 官方仓库当前使用传统 PyTorch 权重。仅允许加载清单登记的官方文件，并保持 `trust_remote_code=false`。
- 权重目录不提交版本库，不复制到测试报告，不通过 MinIO 或业务上传接口分发。
- 后续模型服务以只读方式挂载模型目录，启动时校验 Revision 清单和关键文件。
- RTX 4060 8 GB 只表示具备 CUDA 设备，不等于两模型并发常驻已经通过容量验收。后续必须验证 FP16、批大小、延迟、显存峰值和 OOM 降级。

## 7. 启用状态与剩余门禁

已完成：

1. 架构师确认单实例内部模型服务及回滚方式。
2. 新增 BGE Provider 和 Reranker 契约，backend 与 jobs 不重复加载模型。
3. 将 pgvector 从 1536 维迁移到 1024 维，并将已发布 FAQ 重置为待回填。
4. 使用 Dense/词法双路召回、RRF 候选 Top 20，再由 Reranker 产生最终 Top 5。
5. 在 RTX 4060 8 GB 上完成真实模型离线加载、1024 维和重排序冒烟；两模型常驻约 2922 MiB。

已完成的生产前门禁：

1. Dense Recall@20、Rerank Recall@5、nDCG/MRR、无答案转人工率和引用合法率评测均达到门禁。
2. 已完成 50 并发、P95/P99、吞吐、冷启动和 OOM 压力测试。
3. Dense 门禁已根据固定模型 Revision 和版本化评测集从临时值 0.45 校准为 0.52；模型、数据、切分、候选或 GPU 变化后必须重新评测。
