---
record_id: IR-MVP-AGENT-DYNAMIC-REWRITE-001-20261028-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-AGENT-DYNAMIC-REWRITE-001
base_sha: 0e4100b2b83012692ac2fb368707946687c9cde8
final_sha: 7594a1a53ede8e0b65f8987e352d78662bb04c41
test_record: docs/reports/tests/TR-MVP-AGENT-DYNAMIC-REWRITE-001-20261028-R01.md
review_record: docs/reports/reviews/RR-MVP-AGENT-DYNAMIC-REWRITE-001-20261028-R01.md
requirement_ids: [MVP-AGENT-DYNAMIC-REWRITE-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
created_at: 2026-10-28T16:00:24+08:00
updated_at: 2026-10-28T16:08:00+08:00
supersedes: null
---

# 实际实施与边界
本次完成本地动态 Agent 重写，尚未部署。配置由店铺人员创建并发布，模型/七段系统提示词/全部配置工具/显式文件绑定以不可变版本保存；同店可启用多个 Agent。七段内容是身份职责、服务范围、工具读写、可观察升级条件、语言格式、合规、澄清兜底。旧版本 1 使用保守投影，后续由管理员发布替代。
编排由项目 asyncio 协调器和状态机承担，langchain-core 提供 @tool；DeepSeek/OpenAI/Anthropic 使用原生 function calling。所有启用候选按容量分批，全部配置工具可被模型选择，没有固定 Agent/工具次数截断；循环仍受模型窗口、统一截止时间和重复无效调用收敛约束。没有 LangGraph checkpoint 或服务重启后续跑承诺。
正式建议与预览共用 runtime.execution；各子 Agent 独立数据会话，汇总成一段回答。最终独立复核直接对照低敏工具事实/知识原文，返回前重查审批/版本；高风险无依据事实、冲突、超时、撤权或协议异常不展示候选。所有输出均供人工复核，平台发送为零。
快照冻结配置、文件、消息水位和记忆 revision；近期消息/摘要进入路由与专家，路由目录包含 service_scope。会话内摘要和工具事实按店铺/会话/客户隔离，关闭冻结、重开恢复；工具记忆还要求当前配置与操作者权限，旧事实过期。关键事实保留值与来源，预算不足不截断事实。模型输入按来源标记和脱敏。
# 删除与共享代码
所有 Agent 源码收敛到 app.agents。旧 FAQ 工作流、正则工具路由、固定答案渲染、旧调试、专属 Prompt/Schema 与仅服务退役实现的测试在独立 CLEANUP-20261028-002 中移除；共享 DLP、声明安全、营销、翻译、知识库 FAQ 管理/数据继续保留。无引用 LangGraph 及 4 个传递包退役。manifest 保留精确路径、摘要和 Git 恢复点。
# 数据、配置和依赖
迁移 035–039 增加多 Agent 发布版本、七段草稿、快照、会话记忆和主子运行；空测试库完成 034↔039 升降级。AGENT_V2_DEBUG_ENABLED/AGENT_V2_FORMAL_ENABLED 默认关闭；关闭时明确不可用，无旧 FAQ 回落。主/备用模型分别有保守窗口配置，默认8192；每次 SDK 前检查完整消息与工具 Schema。依赖审计修复 certifi、dnspython、PyJWT 和 urllib3，最终审计无已知漏洞。
# 审查修复与偏差
两轴审查发现并修复最终依据缺失、汇总期间撤权、历史/服务范围未接路由、草稿并发覆盖。另补权限变化后的记忆过滤和目录/历史联合预算。Windows fake-Docker 测试隔离 TEMP/TMP，生产部署锁不变；浏览器样例改为预取前固定三条轨迹，断言未降低。
当前实现采用轻量项目编排而非 LangGraph，已向用户说明；真实模型语义可靠性、TikTok只读现场、50并发和P99门禁待用户批准部署后验收。普通 eval 输出在 src/tests/.artifacts 留存，定稿TR记录摘要，不新增发布证据冒充现场。
# 恢复
不在服务器执行迁移或部署。部署获批前先备份私有数据库/对象/配置并核对镜像；故障先关闭新入口，保留人工工作台，再恢复上一受审应用。已有多个启用 Agent 时禁止盲目降级重建旧唯一索引，保护配置/记忆和业务增量。
