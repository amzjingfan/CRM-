# 项目压缩历史

旧的实施记录、架构版本和测试报告全文仍保存在 Git 历史中。可从标签 `v0.1.0-mvp.20260907` 及其之前提交使用 `git log`、`git show` 检索；本文件只保存长期有用的结果、编号和遗留风险。

## 2026-08：Phase 1～3

- 建立 Next.js + FastAPI + PostgreSQL/pgvector + Redis + MinIO + Worker 的单仓工程，形成认证、看板、工作台、知识、营销、Agent 和团队基础能力。
- 建立店铺隔离、权限、CSRF、幂等、审计、统一错误和平台适配器边界。
- M04 明确为模型适配与意图/RAG 模块；Agent 通过受控工具访问业务，不能直接调用平台 SDK 或数据库。

## 2026-08-21：本地 BGE

- ADR-002/003 将检索切换到本地 BGE-M3 + bge-reranker-large，固定 1024 维、Dense Top-20、Rerank Top-5 和 0.52 阈值。
- RTX 4060 8GB 质量与 50 并发容量门禁通过；冻结聚合证据迁入 `release/evidence/retrieval/`。

## 2026-08-25 至 2026-09-03：真实 TikTok 与 DeepSeek 边界

- REAL-FS-02～05 实现 TikTok OAuth、真实只读、Webhook、人工确认普通文本、`unknown` 对账和 DeepSeek SSE 运行面。
- REAL-AI-01～03 建立正向字段协议、三态 DLP、完整信封、JSON Output、结构化业务声明、知识语义和逐版本审批。
- ADR-004/005/006 固定 v0.1 为 TikTok 人工辅助：AI 只给建议，公开自动回复、营销和高风险写入继续关闭。

## 2026-09-07：v0.1 工程基线

- 创建 `v0.1.0-mvp.20260907` 基线与冻结独立评测集，记录数据集和配置 SHA-256。
- 该标签证明工程基线可追溯，不代表真实生产门禁或最终放行。

## 2026-09：GitHub Flow 与 staging

- 仓库切换到短分支、PR、CI、审阅和 squash merge 的 GitHub Flow，并以根 `.worktrees/` 隔离并行开发。
- ADR-007 建立 Rootless staging；ADR-008 将公网 Nginx/TLS 与业务 Rootless 运行面分离，通过反向 SSH 隧道连接。
- 当前域名为 `staging.overselfx.com`；入口资产已实现，但真实部署、恢复、回滚和最终门禁仍未完成。

## 2026-09-15：仓库结构压缩

- 将 `全栈开发工程师/`、`AI agent 开发工程师/`、`共享记忆文档/`、`开发工具/`、`架构师/`、`测试工程师/` 六类角色目录中的 427 个跟踪文件压缩为用途型当前文档和最小机器证据。
- 产品代码继续位于 `CRM智能聊天系统/`；当前文档位于 `docs/`，发布资产位于 `release/`。
- 历史全文不复制、不原样迁移，由 Git 保留；本次不改变产品运行行为和生产放行状态。
