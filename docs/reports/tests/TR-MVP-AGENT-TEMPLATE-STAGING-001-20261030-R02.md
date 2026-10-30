---
record_id: TR-MVP-AGENT-TEMPLATE-STAGING-001-20261030-R02
record_type: test
revision: R02
status: PASS
task_id: MVP-AGENT-TEMPLATE-STAGING-001
created_at: 2026-10-30T17:31:53.744724+00:00
updated_at: 2026-10-30T23:36:30.080453+00:00
tested_sha: a0d9938e0441fb5848a51635a33dbbb27bd776a4
implementation_record: docs/records/implementation/IR-MVP-AGENT-TEMPLATE-STAGING-001-20261030-R02.md
requirement_ids: [MVP-AGENT-TEMPLATE-STAGING-001]
acceptance_ids: [AC-STG-01, AC-STG-02, AC-STG-03, AC-STG-04, AC-STG-05, AC-STG-06, AC-STG-07, AC-STG-08, AC-STG-09]
environment: authorized staging; rootless Docker; Codex in-app browser; real DeepSeek and BGE-M3
supersedes: TR-MVP-AGENT-TEMPLATE-STAGING-001-20261030-R01
---

# 验收结果与本次来源

TEST_LAYOUT: centralized；临时日志/截图位于已忽略测试输出根。R01最终本地代码dcf5621e的77契约、210 production浏览器（0skip）、lint/type/build和独立复审通过；合并后a0d9938e的前端及测试逐树相同。后端复用当前d67078db精确镜像，不能描述成a0d9938e重建后端。完整[低敏证据](../../../release/evidence/staging/crm-staging-agent-template-batch-20261030.json)记录摘要、哈希与trace，不含买家正文、订单号、密钥和Token。

| AC | 实际结果 |
|---|---|
| STG-01 手动部署 | 新旧ValidateOnly、共享锁Deploy exit0；046；12服务；固定出口；8路径200；11个资源与新容器哈希相同 |
| STG-02 文件入口 | 两份合成Markdown真实解析/清洗/分块/BGE-M3向量写入，各ready/v1/1块；由Agent知识页批准内部建议 |
| STG-03 两店创建 | 已确认v1批次两项成功，各有本店文件映射，默认停用草稿 |
| STG-04 差异更新 | US职责冲突拦截；保留本店职责、更新两店格式；XBM采用新模板职责；历史模板和Agent发布快照不变 |
| STG-05 后台/幂等 | 自有行110秒锁延迟，仅用于观察；处理中离页、释放后完成，重开4项各attempt1；未暂停全局处理器 |
| STG-06 最终中英文 | 新前端上各一次真实问答；中文trace30312d55、英文cb70639b；4个root/agent运行全succeeded/human_review/review_ready；6个持久工具调用全succeeded且mocked=false；两次均search_customer_orders/query_logistics/search_knowledge及本店文件引用 |
| STG-07 第二店隔离 | XBM问题仅检索其缺件指南，输出型号/缺件照片/外包装照片，未使用US配送指南；该后端实现未在最终前端切换中改变 |
| STG-08 UI修复 | 真staging显示未确认预览及中文成功2；本店映射文件仍存在，误列解绑候选count=0；未确认离页保护正常 |
| STG-09 清理 | 2Agent/2文件软删除、1模板归档；其他Agent/文件行哈希不变；DB活动自有对象均0；两店知识列表均0，US只保留原有Agent |

首轮业务矩阵先在fbacb372及测试期间切入的d67078db运行；最终中英文与UI回归明确在a0前端/d670后端组合重跑。每次结果来源分开记录，不把旧结果当作新版本现场执行。

# 失败、CI和限制

一次预览通用失败发生在另一次发布切换邻近，重试通过，未猜改后端。一次清理ORM注册缺失导致事务回滚，补集中导入后重跑成功。前端红绿与审查边界均在最终210中通过。PR679精确head的两个必需CI作业runner0/steps0，按持续批准本地替代；CI未运行，不算通过。

未执行真实平台发送、自动回复、production、48小时观察或备份恢复演练；未重复无改动后端/PG/eval。业务和合成数据清理PASS；本机3146服务已停止；临时registry副本清理被自动审批拒绝，仍等待精确授权；本记录仅确认业务发布及合成数据清理，不声称任务DONE。

本次继续核对：现场仍为a0前端/d670后端且healthy，共享锁空闲；两条最终trace的6项工具记录仍为succeeded/mock=false，活动自有Agent/文件/模板均0。本地认证文件只继承已保护的当前用户独占目录；服务器目录700/文件600，仅核对元数据未读凭证正文；本地3146已无监听。认证副本未删除，精确授权问题未答复，不重试被拒绝操作。

# 用户授权与延期决定补录（2026-10-31）

用户明确批准只删除两份本轮registry认证副本并停止本地测试服务。服务器副本已通过原精确路径脚本删除并确认不存在；本机删除在明确授权后仍被自动审批拒绝，只返回blocked by policy，未通过其他执行方式绕过。用户随后选择稍后处理，按该新决定保留本机副本于当前用户独占目录，不记作已删除，不再作为本轮已验收业务的阻断。真实密钥、全局Docker/GitHub凭证和备份保留。3146已停止；临时验收凭证虽获授权，但因真实验收已经完成而未签发。证据PR原e6头两个CI已终止、均runner0/steps0；主线富消息发布证据冲突保留双方事实解决，待最终head门禁与合并后才DONE。上述补录不追改此前观察时授权未答的事实。
