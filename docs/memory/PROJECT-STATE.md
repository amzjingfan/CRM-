# 项目状态与恢复入口

2026-10-28，治理档位 STANDARD，产品仍为 TikTok 人工辅助 v0.1。当前任务以[任务表](../tasks/TASKS.md)为准；产品、架构和治理见 [PRODUCT](../product/PRODUCT.md)、[AI](../architecture/AI.md)、[GOVERNANCE](../governance/GOVERNANCE.md)。

本地 worktree 整合 `MAINT-CLEANUP-20261028-003 DOING`：批次见[清理索引](../operations/cleanup/CLEANUP-INDEX.md)。截至本次合流前已归档并移除 62 个旧工作树和 71 条本地分支，另有批次 004 的 470 条原分支名已归档移除；截至本轮核验有 14 个工作树、14 条本地分支，活动会话仍可能切换分支，三个指定会话的最新工作保留。本地 `main=e2eba1bcaadd62c34e320d09e16660c61e90e87c` 已合流 Agent PR #582–#584 和多店授权迁移，`040_merge_agent_multishop` 为唯一迁移 head，详细[IR](../records/implementation/IR-MAINT-CLEANUP-20261028-003-20261028-R01.md)、[TR](../reports/tests/TR-MAINT-CLEANUP-20261028-003-20261028-R01.md)、[RR](../reports/reviews/RR-MAINT-CLEANUP-20261028-003-20261028-R01.md)。本地合流 PR #585 的 staging 证据；开放 PR、独有提交和其他现场资料待逐项验收。旧 OCI 缓存及整合工作树临时依赖 junction 的精确删除均被自动审批审查以 `blocked by policy` 拒绝，原位保留。根 checkout 五个未知条目未触碰。Workspace hygiene: ATTENTION。

`MVP-TIKTOK-MULTISHOP-AUTH-001 DONE`：卖家级多店授权已合入本地主线，未部署 staging 或 production；与动态 Agent 的两条迁移链在 040 合流。正式[IR](../records/implementation/IR-MVP-TIKTOK-MULTISHOP-AUTH-001-20261028-R01.md)、[TR](../reports/tests/TR-MVP-TIKTOK-MULTISHOP-AUTH-001-20261028-R01.md)、[RR](../reports/reviews/RR-MVP-TIKTOK-MULTISHOP-AUTH-001-20261028-R01.md)保留。部署须另行验证备份和迁移门禁。

`MVP-STAGING-LATENCY-001 VERIFYING`：性能源码 PR #584 已合入远端主线；用户选择的性能专用 release `e64ef52c9702540a5c5eb3a151cd19afce97b0e0` 已单独部署 staging，动态 Agent 重写未部署。私有备份、摘要、ValidateOnly/Deploy、固定出口、12 容器、网关缓存与已登录订单只读 UI 验收见[IR R02](../records/implementation/IR-MVP-STAGING-LATENCY-001-20261028-R02.md)、[TR R02](../reports/tests/TR-MVP-STAGING-LATENCY-001-20261028-R02.md)、[RR R02](../reports/reviews/RR-MVP-STAGING-LATENCY-001-20261028-R02.md)及[低敏证据](../../release/evidence/staging/crm-staging-latency-performance-only-20261028.json)。公网/隧道仍有秒级抖动，20 次样本未控制并发和冷热，AC-01/AC-06 待网络修复与同批受控复测；production G8 No-Go。

`MVP-AGENT-DYNAMIC-REWRITE-001` 与 `MAINT-CLEANUP-20261028-002` 已完成源码与旧代码清理，本地和远端主线含七段 Prompt、模型工具路由、绑定文件 RAG、最终依据复核、展示前撤权及会话记忆。现场旧 Agent 链路和安全开关仍在使用，新 Agent 功能默认关闭，未部署；正式[IR](../records/implementation/IR-MVP-AGENT-DYNAMIC-REWRITE-001-20261028-R01.md)、[TR](../reports/tests/TR-MVP-AGENT-DYNAMIC-REWRITE-001-20261028-R01.md)、[RR](../reports/reviews/RR-MVP-AGENT-DYNAMIC-REWRITE-001-20261028-R01.md)。旧 Agent 代码清理批次在本地合流时重编号为 `CLEANUP-20261028-049`。整合后本地完整后端 2304 passed/4 skipped，前端契约 49/49、生产浏览器 119/119，通过类型、静态和 Webpack 构建；这些结果不代表现场新 Agent 验收。

下一动作：①逐支验收开放 PR 和独有提交，再合入本地 main 清理旧副本；②处理自动审批阻断的两个原位保留项目；③性能任务完成网络与公网受控复测，动态 Agent 部署单独决策。
