# 项目状态与恢复入口

2026-10-28，治理档位 STANDARD，产品范围 TikTok 人工辅助 v0.1；仓库 `CP11-gh/CRM`，权威目标 `origin/main`。当前源任务见[任务表](../tasks/TASKS.md)，产品、架构和治理入口分别为[PRODUCT](../product/PRODUCT.md)、[AI](../architecture/AI.md)、[GOVERNANCE](../governance/GOVERNANCE.md)。

当前活动任务 `MVP-STAGING-LATENCY-001 VERIFYING`。性能源码 [PR #584](https://github.com/CP11-gh/CRM/pull/584) 已合入 `main=9d6a9182ec7e9e29712e670654b757f8c767ef5d`；性能 subject `2c77b8d9a729e467d702c116ad7403e94660f979`。用户最终选择只部署当前性能修复；已从独立 release `e64ef52c9702540a5c5eb3a151cd19afce97b0e0` 手动直部署 staging，动态 Agent 改写仍未部署。当前证据分支 `docs/staging-latency-evidence-20261028`，`CANDIDATE_SUBJECT_SHA=e64ef52c9702540a5c5eb3a151cd19afce97b0e0`（独立 release 分支），`EVIDENCE_HEAD_SHA=READ_AT_GATE`；索引 `CANDIDATE_VIEW`，待证据合并后从 main 重建 `CURRENT`。

[IR R02](../records/implementation/IR-MVP-STAGING-LATENCY-001-20261028-R02.md)、[TR R02](../reports/tests/TR-MVP-STAGING-LATENCY-001-20261028-R02.md) 与[RR R02](../reports/reviews/RR-MVP-STAGING-LATENCY-001-20261028-R02.md)记录 release、验证与审查。私有备份、精确前后端摘要、六角色预取、ValidateOnly/Deploy、固定出口、12 容器、健康、网关静态 MISS/HIT 和已登录订单只读 UI 通过，详见[低敏部署证据](../../release/evidence/staging/crm-staging-latency-performance-only-20261028.json)。原单店人工发送、Agent 调试、翻译与安全开关保持；未向真实买家发送、退款或部署 production，G8 仍 No-Go。

性能残余风险：业务机 `/healthz` 毫秒级，隧道和公网仍有秒级抖动；20 次前后样本未控制并发及缓存冷热，不能证明公网改善。AC-01/AC-06 尚待网络修复与足量同批次复测；不得把本任务标记 `DONE`。动态 Agent 主线源码仅在本地通过，现场开关未启用。Workspace hygiene: ATTENTION（活动 worktree、未知文件及根 checkout 未共享历史保留；本次没有清理）。

下一动作：①定位反向隧道重启、连接重传和网关高耗时；②按同请求分段日志完成订单与店铺页冷/热、p50/p95 受控复测；③验收达到目标后关闭性能任务，动态 Agent 单独决定部署。
