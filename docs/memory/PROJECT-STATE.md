# 项目状态与恢复入口

2026-10-28，治理档位 STANDARD，产品范围 TikTok 人工辅助 v0.1；仓库 `CP11-gh/CRM`，权威目标 `origin/main`。任务、产品、架构和治理事实入口分别为[任务表](../tasks/TASKS.md)、[PRODUCT](../product/PRODUCT.md)、[AI](../architecture/AI.md)及[GOVERNANCE](../governance/GOVERNANCE.md)。

当前任务 `MVP-STAGING-LATENCY-001 VERIFYING`。性能源码 [PR #584](https://github.com/CP11-gh/CRM/pull/584) 已合入；用户限定 staging 仅部署性能专用应用 release `e64ef52c9702540a5c5eb3a151cd19afce97b0e0`，动态 Agent 重写未部署。[R02 部署证据](../../release/evidence/staging/crm-staging-latency-performance-only-20261028.json)记录镜像、私有备份、门禁和只读订单 UI。

入口连接复用从 `BASE_SHA=5a4143062d37cdb811f33f9e2959d04df79f1415` 的独立 `fix/staging-nginx-upstream-keepalive-20261028` 实施，`CANDIDATE_SUBJECT_SHA=81c851bf53b7216ef6f5bf4ee8d125aefacb0eaa`，`EVIDENCE_HEAD_SHA=READ_AT_GATE`，索引 `CANDIDATE_VIEW`。[IR R03](../records/implementation/IR-MVP-STAGING-LATENCY-001-20261028-R03.md)、[TR R03](../reports/tests/TR-MVP-STAGING-LATENCY-001-20261028-R03.md)、[RR R03](../reports/reviews/RR-MVP-STAGING-LATENCY-001-20261028-R03.md)与[低敏证据](../../release/evidence/staging/crm-staging-nginx-keepalive-20261028.json)记录 Nginx 配置部署。入口回环各 30 次 p50/p95 `1.042/2.061` → `0.400/1.161` 秒；公网各 30 次 `1.564/4.002` → `1.742/4.028` 秒。公网没有可证明的改善，广域网重传/隧道超时仍是风险，AC-01/06 未完成。

当前单店人工发送、Agent 调试、翻译及全部安全开关保持；无真实买家外发、退款或 production 部署，G8 No-Go。Workspace hygiene: ATTENTION（根 checkout 未共享历史和未知文件、活动 worktree 原样保留；本次没有清理）。

下一动作：①完成入口变更证据 PR 与主线索引对账；②与网络/线路提供方处理两机广域网重传或评估更近入口/替代传输；③按页面分段日志对订单与店铺设置等路径做冷/热、跨店和公网 p50/p95 受控复测。
