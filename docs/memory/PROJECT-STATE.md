# 项目状态与恢复入口

2026-11-03 最新真实接口验收：在用户明确指定的US测试买家发送1条标记虚拟的消息，正式接口sent/real，平台同ID可见；US查单空结果及Agent搜索回答通过。XBM只读增强物流200、1包裹15节点及Agent两工具回答通过。US增强样本11007009仍保留为失败；未强制自动欢迎/超时/物流事件，未证明买家已读。无合成订单/临时Agent/文件，真实消息与审计保留。见[本次TR](../reports/tests/TR-MVP-AGENT-REALSHOP-API-001-20261103-R01.md)和[低敏证据](../../release/evidence/staging/crm-real-shop-api-20261103.json)。本次不改产品或部署；证据分支docs/real-shop-api-20261103。

2026-11-03 自动发送共享窗口缺陷已修复并手动部署 staging：详情仅核身份，202309列表提供当前窗口；两店真实grant/identity/window均true。旧取消记录保留，未补发；没有真实买家试发或新送达回执证明。当前产品/架构入口见docs/README.md；治理STANDARD，production G8 No-Go。

- 仓库CP11-gh/CRM；产品subject `fc5d0c70e3d508b9ba78949a5d609f28ee234559`，PR#723合并 `85a2214e1c1618fbb07103f6b6c9fd8316e3ad04`；当前证据分支docs/automation-window-evidence-20261103，EVIDENCE_HEAD_SHA=READ_AT_GATE。
- 本次任务MVP-AGENT-AUTOMATION-WINDOW-001实现已合并，最终IR/TR/RR为20261103-R01。固定subject隔离PG3678通过/5跳过，静态、类型、锁及实际前后端CI通过，独立审查APPROVE。见[TR](../reports/tests/TR-MVP-AGENT-AUTOMATION-WINDOW-001-20261103-R01.md)和[机器证据](../../release/evidence/staging/crm-staging-automation-window-20261103.json)。三索引从全部源记录重建CANDIDATE_VIEW，合并后只读核对。
- staging后端及四工作进程/egress为ac640ba7…2efc，前端仍2e6fb84d…2651、检索feeee5a3…2059；050、三健康200。现有两店各5永久Agent和auto/欢迎24小时咨询段/60分钟超时/物流external3600秒配置保留，现权、审批、DLP及unknown边界未放宽。
- 现场只读：两店身份与发送窗口通过；US所选样本0订单，XBM1订单；核验当时已持久订单/物流基线仍0，下一自然扫描未在本轮强制触发。自动化账本当时没有新成功投递回执；本轮后来定向人工测试的sent回执见顶部，不能据此推断自动调度通过。凭证仅在进程内存，进程结束；staging没有新测试业务数据。
- 清理：本次fixture自有店铺/策略剩余0，隔离PG容器停止并清除tmpfs；私有环境/数据库及旧验收恢复资料备份保留。旧完整验收的10Agent/8文件、139临时消息/12协作已按原记录清理，不重复创建或删除。
- 其他证据：承运商自动回显两店视觉核对仍以TR-MVP-WORKSPACE-ORDER-TRACKING-CONSISTENCY-001-20261102-R05为准。本次无UI变化，未重复浏览器/付费模型矩阵。
- Workspace hygiene: ATTENTION。未知前端AGENTS.md、其他活动worktree、原旧凭证副本均保留；没有自动删除未知资产，无活动文件清理批次。仅清理本任务可识别的测试业务行。
- 风险：实时分页增加读取延迟，整体受现有请求预算控制；未知/关闭/撤权仍停止发送。自然新消息/物流事件及平台回执需与当前策略一起判断，旧账本不重放。

下一动作：①合并本次证据并只读核对三索引；②以自然新业务回执/下一物流周期确认实际送达，不试发或补发旧任务；③production维持No-Go。
