# 最新测试状态

本文件只汇总当前仍有效的正式结论。历史报告用于追溯，不代表本分支重新运行。生产是否可放行以 `../operations/RELEASE-GATES.md` 为准。

## 模块状态

| 主题 | 已有结论 | 尚缺内容 |
|---|---|---|
| M00 基础设施 | Split-ingress Rootless staging 已通过真实 DNS/TLS、两台主机部署、迁移头、容器/公网健康、隧道恢复和公司负载零变化验收 | 密钥轮换、备份恢复、兼容镜像回滚和 production 放行 |
| M01 管理端/工作台 | 认证、权限、看板、会话、知识、团队、Agent 和人工消息主流程有自动化覆盖 | 真实浏览器/网络下的完整 staging 回归 |
| M02 数据与任务 | PostgreSQL/pgvector、Redis、Worker、幂等、审计和店铺隔离有模块/综合测试 | 真实负载、长稳和灾难恢复 |
| M03 平台集成 | TikTok OAuth、只读、Webhook、人工消息、`unknown` 对账实现并通过确定性检查 | 真实店铺 OAuth/Scope/投递/消息/对账；Shopee/Amazon 真实接入未做 |
| M04 AI 与 RAG | Provider、DLP、结构化声明、知识审批、工具边界和本地 BGE 已覆盖；固定综合集为 32/36（88.89%） | 真实 DeepSeek 质量、50 客户端 SSE、5 日稳定性；公开自动回复/营销未放行 |

## BGE 正式基线

- 质量：Dense Recall@20 = 100%，Rerank Recall@5 = 100%，MRR = 1，nDCG = 1，引用合法率 = 100%，无答案拒判率 = 100%。
- 接受阈值：Dense 相似度 `0.52`。
- RTX 4060 8GB 单实例容量：50 并发零失败；Embedding P99 = 375.22 ms；Reranker P99 = 1966.59 ms；显存峰值 = 3697 MB；冷启动 = 24.256 s。
- 机器证据：`release/evidence/retrieval/bge-quality-threshold-052-20260821.json`、`bge-capacity-gpu-gate-20260821.json`、`bge-gpu-runtime-20260821.json`。

这些结果固定模型、硬件、数据集与当时配置，不自动外推到其他模型 Revision、GPU、并发模型或生产网络。

## 当前未关闭风险

- G4 的 4 个未通过用例尚未形成生产 AI 质量闭环；危险逃逸为 0、合法输入误拦截为 0，但综合正确率不能替代逐项关闭。
- 未执行真实 TikTok 店铺端到端验收，不能确认生产 Scope、回调、投递和消息行为。
- 未执行真实 DeepSeek 50 客户端 SSE 和连续 5 日 99.5% 稳定性。
- 未完成备份恢复、实际回滚及最终联合签署。

## 域名契约迁移验证

候选 `10428b4501fd470a5a671676edcdc00e75180844` 已将 staging/production 固定域名统一为 `staging.overselfx.com` / `www.overselfx.com`。完整后端回归为 `1538 passed, 12 skipped, 3 warnings`，Ruff、格式、mypy、锁文件和旧域名扫描通过。该候选当时只证明仓库内契约一致；后续 staging DNS/TLS 与部署结论见下节，Partner Center 与真实 OAuth/Webhook 仍未执行。

## Split-ingress staging 部署验证

最终候选 subject `c0f1e6f0a5c575190b71541be3f67b3163780d61` 已将域名契约落地为真实 staging；它与已部署运行配置 `98460796...` 的受审运行资产零差异。PR #25 CI 为 `1559 passed, 12 skipped, 3 warnings`，前端 40/40 测试及 production build 通过；staging-only deploy `35561109568` 完成不可变镜像、迁移头和三个公网健康端点验证。真实隧道恢复、端口隔离、Nginx/TLS 与公司系统 Docker 零变化详见 `TR-MVP-STAGING-001-20260919-R01`。该结论只关闭 staging 基础设施 AC-01～AC-10，不替代 G1～G6 真实业务与稳定性验收。

## 本次根目录迁移验证口径

本次将产品代码恢复到源提交 `77d9f8f` 并提升到仓库根，验证范围为 Git 历史、目录结构、活动路径引用、JSON 可解析和首版 Rootless Staging 关键资产。按用户要求不执行完整后端回归、前端安装/构建或真实平台门禁，且历史测试结果不得被描述为本分支重新运行结果。
