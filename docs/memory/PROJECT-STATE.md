# 项目状态与恢复入口

2026-10-29；STANDARD；TikTok 人工辅助 v0.1；仓库 CP11-gh/CRM，目标 origin/main。MVP-STAGING-LATENCY-001 和 MVP-TIKTOK-MULTISHOP-AUTH-001 为 DONE，具体事实以 TASKS 及其最终记录为准。

活动任务 MVP-AGENT-STAGING-DEPLOY-001 为 VERIFYING。动态 Agent/十二工具和多店授权已从 main `45d872c060f9b632de340318f32bf9de2904efb5` 手动直部署 staging，状态收尾分支 docs/agent-staging-evidence-index-current-20261029；CANDIDATE_SUBJECT_SHA=45d872c060f9b632de340318f32bf9de2904efb5，EVIDENCE_HEAD_SHA=READ_AT_GATE。IR/TR/RR 为 MVP-AGENT-STAGING-DEPLOY-001-20261029-R03；TR=PARTIAL。低敏清单 release/evidence/staging/crm-staging-agent-multishop-20261029.json。

发布事实：私有双备份可读、精确源码与镜像/amd64/OCI、ValidateOnly/Deploy、041 合流 head、12 容器、固定出口和三健康/12公网项通过。本机和服务器临时 GHCR 登录已注销。v2 仅调试开启，正式建议/LLM/自动回复/营销/高危关闭，原单店人工发送白名单、读取/Webhook、翻译和文档摄取保持。

现场六类/16能力目录和原店铺/渠道/工作台只读兼容通过；旧 v1 Agent 两工具、0文件，真实两请求分别 no_verified_evidence 与 sensitive_agent_output/specialist_incomplete，尚无已接受业务回答。worker 早返回可能遗漏工具事件，不能从页面零调用断言没有平台请求。本次没有改业务 Prompt、放宽 DLP、创建新知识/客户/店铺授权或发送平台消息，工具加 RAG 全链路未验收。041 后新增运行和派生记忆须保留，不能盲目恢复旧库。production G8 No-Go，WAN 抖动风险仍在。

本地受影响180项和组合2394/3、前端52/134的精确受测源与复用见R02；本次新事实为构建、部署及现场请求。发布证据 PR #632 已合入 main 83b6fe7a；从该权威主线逐项核对296/321/279条源记录，三索引CURRENT。任务仍VERIFYING，业务回答未验收。

Workspace hygiene: ATTENTION。根checkout未共享历史、未知需求/私有文件、其他活动worktree和生成的未跟踪src/frontend/AGENTS.md保留。临时日志、截图和镜像包位于src/tests/.artifacts；既往入口临时密钥副本由原授权清理范围处理，不自动删除。

下一动作：①定位并保留真实工具调用的低敏轨迹及输出拒绝原因；②完成普通问题、已绑定文件、多Agent汇总的现场验收；③网络条件改善后补公网/401/429及独立生产门禁。
