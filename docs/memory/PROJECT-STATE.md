# 项目状态与恢复入口

2026-10-28 `MVP-STAGING-LATENCY-001 VERIFYING`：性能源码从 `BASE_SHA=0b14b1d1` 重放到 `main=ac7216d4`，`CANDIDATE_SUBJECT_SHA=2c77b8d9a729e467d702c116ad7403e94660f979`、`EVIDENCE_HEAD_SHA=READ_AT_GATE`。只读 20 次复测业务机/隧道/公网健康 TTFB p50/p95 分别为 0.000833/0.004535、0.905597/3.727746、1.782162/9.107670 秒；公网 TCP connect p95 7.199228 秒，隧道累计重启 969 次且当天多次超时。后端 2289 passed/54 skipped、前端契约 48/48、生产构建与合成浏览器 118/118、Ruff/mypy/typecheck 通过；完整证据见 [TR R01](../reports/tests/TR-MVP-STAGING-LATENCY-001-20261028-R01.md)。最新主线的动态 Agent 改写仍需独立 staging 部署批准，不得随性能候选自动发布；现网保持原 Agent 调试、安全开关及单店人工发送，未向买家发送、退款或发布 production。Workspace hygiene: ATTENTION（活动 worktree 和未知文件保留）。下一步：①完成性能 PR 本地替代门禁与合并；②确定动态 Agent 部署边界；③满足发布门禁后进行 staging 性能部署和前后实测。

2026-10-28，治理档位 STANDARD，产品仍为TikTok人工辅助v0.1。仓库 CP11-gh/CRM；授权远端 origin，目标main。产品、架构、治理和任务事实源分别见 docs/product/PRODUCT.md、docs/architecture/AI.md、docs/governance/GOVERNANCE.md 和 docs/tasks/TASKS.md。

当前任务 `MVP-AGENT-DYNAMIC-REWRITE-001` 与 `MAINT-CLEANUP-20261028-002` 处于 DONE；源码PR #582已squash合入main `ac7216d42ec5b56fbda618ca95826b9b7d075600`，状态收尾分支 `docs/dynamic-agent-local-close-20261028`。CANDIDATE_SUBJECT_SHA=`7594a1a53ede8e0b65f8987e352d78662bb04c41`，EVIDENCE_HEAD_SHA=READ_AT_GATE；已从合并主线读取全部源记录并核对src树与受测subject一致；已包含主线订单详情文档0b14b1d1，根checkout已有未共享历史和未知文件，未改写。

本地动态Agent具备版本化七段Prompt、模型自主多Agent路由、配置工具的@tool/function calling、绑定文件RAG、独立最终依据复核、展示前撤权、会话内记忆/关闭重开/权限过滤和联合上下文预算。编排是项目asyncio与显式状态机，不使用LangGraph checkpoint或服务重启续跑。旧Agent FAQ/正则/固定答案/旧调试和专属Schema/Prompt已删除，共享知识库FAQ管理、翻译、营销与工作台保留；清理批次CLEANUP-20261028-002通过Git历史可恢复。

最终本地2335项通过、3项POSIX平台条件跳过；50项隔离数据库集成、48前端契约/114生产浏览器、类型/构建/静态、迁移034↔039、16动态协议/237安全样本、运行依赖审计通过。两轴复审无剩余阻断。[IR](../records/implementation/IR-MVP-AGENT-DYNAMIC-REWRITE-001-20261028-R01.md)、[TR](../reports/tests/TR-MVP-AGENT-DYNAMIC-REWRITE-001-20261028-R01.md)、[RR](../reports/reviews/RR-MVP-AGENT-DYNAMIC-REWRITE-001-20261028-R01.md)。派生索引CURRENT；从权威主线逐条核对IR/TR/RR为271/292/254条。

部署状态：本候选尚未部署。staging最新已批准的订单详情前端发布见TR-MVP-WORKSPACE-ORDER-DETAIL-UI-001-20261028-R02及对应staging证据；后端仍为旧Agent链路、迁移034。用户要求本次本地验收后等批准再统一部署。真实模型语义路由/依据复核可靠性、TikTok只读联合链路、50客户端P99和长期稳定性未由本次本地测试验证；production G8 No-Go。默认新调试/正式开关关闭，不恢复已删除FAQ路径。

Workspace hygiene: ATTENTION。仅本任务受跟踪源码按独立批次移动/删除；其他活动worktree、根checkout未知需求/私有文件和未共享历史保留，未清理服务器或密钥。没有平台消息发送。

源码PR的CI核对：run40655266642、Backend job122704652719/Frontend job122704652999，均runner_id=0、steps=[]；CI未运行，按持续授权使用本地验证，不计CI通过。

下一动作：①等待用户批准统一部署staging；②获批后核对备份、迁移039和精确应用产物；③验证真实模型、多Agent工具＋RAG、零平台发送和恢复/性能。
