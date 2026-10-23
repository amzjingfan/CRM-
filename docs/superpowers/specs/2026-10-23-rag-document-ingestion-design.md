# RAG 文档导入设计（2026-10-23）

## 决定与范围

本设计依据用户关于 MinerU、CPU 降级、重复文件、清洗、分块、字段和知识库 UI 的讨论。原先“合格页先入库、问题页单独待复核”的建议已撤回：**只要文件中存在关键内容无法可靠识别，整个新版本停在“待复核”；该新版本不写入任何向量，也不成为当前有效版本。** 管理员修正或确认全部问题单元后，才对整个新版本分块、向量化并一次性切换。若是替换文件，旧有效版本在此之前保持原样。问题页仍逐页列出，供定位和修正，但不单独提前入库。

本期交付从上传到 PostgreSQL `pgvector` 入库的闭环：格式校验、私有 MinIO 原文件保存、MinerU 本地解析、可追溯清洗、质量判定、分块、BGE-M3 1024 维向量化、版本化保存、前端状态与待复核处理。**本期不接通 Agent 检索、Rerank 召回或自动回复。** 既有 CSV/XLSX FAQ 导入、逐版本审批、`knowledge_chunks` 检索边界保持不变。检索 Top-K、相似度阈值和 Rerank 控件须明确显示“检索未接入，当前不生效”，不得伪称本期已保存并用于检索。

## 外部能力与运行边界

- MinerU 精确锁定 `4.0.12`（镜像摘要随部署记录），在**本地受控进程**使用 `mineru.parser.parse` / `ParseResult`，不上传官方云服务。PDF 先用 Flash 读取原生文本；若存在无文本页，整个文件以 Basic（ONNX CPU 可运行）重解析。JPG/PNG 在自动模式使用 Basic OCR；DOC/DOCX、PPT/PPTX、XLS/XLSX、CSV/TSV 用 Flash；TXT/MD 直接读取。首期不使用 Standard/Advanced VLM，也不接收带宏格式。所有格式以解析结果的真实 `schema`/`schema_version`、`page_idx` 与 block 为准；Office 是整本解析，不能臆造可靠的 PDF 页码。参见 [MinerU 档位](https://opendatalab.github.io/MinerU/usage/tiers/)、[SDK](https://opendatalab.github.io/MinerU/usage/sdk_api/) 与 [结果格式](https://opendatalab.github.io/MinerU/reference/output_files/)。
- 使用与 FastAPI 后端隔离的 CPU 优先解析 Worker/镜像，串行消费并设置文件、页数、像素、耗时、解压和产物上限。后台 `jobs` 不加载 MinerU 重依赖。BGE-M3 复用内部检索模型服务的 Embeddings 端点；Rerank 模型不参与导入。模型服务 `auto` 在启动时无 CUDA 则使用 CPU；运行中 GPU 故障使任务可重试，运维以 CPU 配置重启后续跑，不在进程里无控制热切换。任何降级不跳过质量复核。
- 原文件、解析 JSON 与清洗预览属于私有数据，只在当前店铺授权范围读取，密钥由环境注入。日志和低敏证据只记 ID 摘要、数量、阶段、稳定错误码，不记正文、原始文件名或秘钥。MinerU 在线服务应在产品界面或公开文档显著标识“文档解析使用 MinerU”；上线前复核其[许可证](https://github.com/opendatalab/MinerU/blob/master/LICENSE.md)的商业门槛与署名义务。

## 版本与状态

`knowledge_files` 保存同店文件身份、分类与 `active_version`；`knowledge_file_versions` 保存不可变原文件 SHA-256、配置快照、解析器版本、对象键、状态、重试/租约与审计字段；`knowledge_file_units` 保存页/幻灯片/工作表或图像单元、定位符、原始/清洗文本、质量问题码和人工修订；`knowledge_file_chunks` 单独保存新文档向量，绝不混入现有 FAQ 表。每个 chunk 至少保存 `store_id,file_id,version_id,unit_index,chunk_index,content,token_count,content_hash,strategy,heading_path,source_locator,parser_version,cleaning_version,embedding_model,embedding_revision,embedding(1024),created_at`。可检索标识默认关闭；本期 Agent 查询完全不读取该表。

新版本状态：`queued → parsing → review_required | indexing → ready`，可恢复错误进 `failed_retryable`，确定性拒绝进 `failed_final`。`review_required` 没有该版本向量；审核接口按单元提交修订并保留操作者、时间和修订摘要，全部问题单元解除后重新排队，最终整版本向量写入事务成功才把 `active_version` 切到新版本。任何失败都不得把部分新版本标为 ready。旧版本和旧向量不在新版本处理中提前删除。取消/归档只影响所选文件，不跨店铺。

同店同文件名且内容不同时，上传者必须在 UI 明确选择“替换旧文件”及目标文件；否则提示冲突，不能悄悄覆盖。相同内容 SHA-256 与相同解析/分块/模型配置重复提交，返回现有任务或版本，不重复入库。不同配置可显式重处理成新版本。服务端再次核对 `replace_file_id` 与店铺、分类，不信任前端展示。上传要求 `knowledge.manage`、CSRF、`Idempotency-Key`；列表/详情要求 `knowledge.view`；重试/修订/删除写审计。分类非空判定也包含文档文件。

## 清洗、质量与分块

清洗规则版本固定：统一 Unicode 与换行；去掉重复空白、明显重复页眉页脚和独立页码；保留标题层级、列表顺序、表格标题与列头、金额/币种、SKU、日期、否定词和原始定位符；不靠正则推断或改写商品/政策事实。每个单元保留清洗前后预览，空白/乱码/异常替换字符、缺失的表格单元、截断/解析失败、OCR 不能可靠证实的关键内容均记稳定问题码。扫描 PDF 和图片的 OCR 单元首期默认待人工复核；非 OCR 单元只有通过完整性检查才自动通过。无可识别文本的单元不能默默忽略。

所有大小/重叠由后端验证、随版本冻结，前端所选策略与参数必须真实进入 Worker；改默认参数只影响未来任务，已有文件需显式重处理。Token 策略使用 BGE-M3 对应 tokenizer 计数，字符策略用 Unicode 字符计数；除表格/FAQ 外默认 `500/50` Token，固定字符默认 `1000/100` 字符；`overlap < size`，块不得跨文件版本或越过源定位边界。支持如下策略，格式不适用时前后端都禁用并说明原因：

| 策略 | 适用输入 | 默认与边界 |
|---|---|---|
| 按语义/结构递归（默认） | PDF、Office、TXT/MD、图片 OCR | 500/50 Token，先标题/段落，再句子，最后 Token 截断 |
| 按标题与段落 | 带标题/段落的 PDF、DOC(X)、PPT(X)、TXT/MD | 500/50 Token；无标题时退化为段落 |
| 按句子 | 散文/政策/说明文本 | 500/50 Token；中英句读，长句再切 |
| 固定 Token | 所有可提取文本 | 500/50 Token，保留定位符 |
| 固定字符 | 所有可提取文本 | 1000/100 字符，保留定位符 |
| 语义相似度 | 非表格长文本 | 500/50 Token；BGE 句向量切换主题，短文本回退句子 |
| 按页/幻灯片 | PDF、PPT(X) | 500/50 Token；一个来源单元内再按大小切 |
| OCR 版面 | 扫描 PDF、JPG/PNG | 500/50 Token；阅读顺序与版面块，不跨页 |
| 表格行组 | XLS(X)、CSV/TSV、有结构化表格的 PDF/Office | 500/0 Token；每组重复表头，单行超限标记待复核 |
| FAQ 问答 | FAQ CSV/XLSX | 既有 800/80 Token，沿用现有 FAQ 导入与审批，不混入通用文档流水线 |

## 验收与上线口径

硬门禁是**不静默丢失关键内容、错误版本无向量、跨店失败关闭、替换不提前切换、策略/大小实际生效、可恢复且数据可追溯**。解析质量采用固定样本逐项对照；文字识别百分比只作为诊断指标，不以单个 OCR 百分比阻断合理的人工修订流程，也不为了通过而降低已执行测试阈值。样本包括原生/扫描 PDF、含表格 Office、TXT/MD、图片、同名替换、坏页、GPU 不可用与重启重试。若缺可分发样本，优先自行生成脱敏样本，再从官方或许可明确的公开源取得并记录 URL、许可证、SHA-256。真实样本的关键字段必须正确或进入待复核，绝不自动 ready。

先在隔离本地环境完成单元、迁移、PostgreSQL/MinIO、前端契约与浏览器验证，再以当前受审镜像**手动直接部署 staging**，不使用 GitHub Actions；保留原 staging 运行模式、备份和回滚入口。部署前后核对不可变镜像、迁移头、健康、权限与一次真实文件全链路，保存低敏 IR/TR/RR 和发布证据。production 与 Agent 检索另作放行。
