# 项目状态与恢复入口

2026-11-03 Agent全链路验收与两店自动化已完成：源码PR #719已合并；手动部署subject `20c9103cac541ed43c164a68e7ed2abe03430370`、050及三健康通过。两店各5永久Agent，auto、欢迎24小时咨询段、60分钟超时及60分钟物流轮询external已正式API回读；10测试Agent/8文件软删、139临时消息/12协作清理，原草稿/发布版本及会话记忆保留。88个功能组合中83自动新执行通过、5独立人工事实裁定，原始自动矩阵非全绿；物流为实际模型/BGE的双语模拟，未向真实买家测试发送。长复杂输入仍可被DLP拒绝、模型错误参数失败关闭；现场浏览器UI_UNAVAILABLE；production继续No-Go。见[TR R02](../reports/tests/TR-MVP-AGENT-AUTOMATION-FULL-001-20261103-R02.md)和[低敏证据](../../release/evidence/staging/crm-staging-agent-automation-20261103.json)。

- 治理：STANDARD；单仓库模块化单体；产品和API/AI当前入口见 docs/README.md。生产G8仍No-Go。
- 仓库：CP11-gh/CRM；产品源subject `20c9103cac541ed43c164a68e7ed2abe03430370`，已由PR #719合并 `f71fca80703d1abab0d735a4a28e9c1f5061aca3`；最终证据分支 docs/agent-automation-live-closeout-20261102；EVIDENCE_HEAD_SHA=READ_AT_GATE。
- 记录：本任务IR/TR/RR 20261103-R02；三索引内容从全部源记录重建为CANDIDATE_VIEW，合并后只读逐项核对。没有额外产品部署待执行。
- 自动化：只限现有两店，新店默认off。无合成知识绑定，缺政策依据时澄清/人工；不使用旧FAQ路径。旧重叠接待策略已先停用，启用不回填历史；审计与私有备份保留。
- 残余：原始自动矩阵失败未改写；83个新执行变体与5条人工事实复核完成场景覆盖。复杂输入保守DLP、模型无效参数和供应商失败会失败关闭；现场UI绑定超时，未验证真实买家收件。
- 其他任务：承运商自动回显已由并行主线PR #720/#721的TR R05完成两店真实侧栏视觉核对，任务DONE；保留该独立证据。本次Agent页面仍单独记录UI_UNAVAILABLE，不覆盖其他任务结论。
- Workspace hygiene: ATTENTION。未知Next生成AGENTS.md、主checkout和其他活动worktree/旧凭证副本均保留。仅本任务自有测试业务数据精确清理；不删除未知文件、卷或备份。

下一动作：①合并本次最终证据并复核远端；②观察用户自然业务中的失败关闭记录，改进复杂输入体验；③production维持No-Go。
