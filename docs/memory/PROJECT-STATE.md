# 当前项目恢复摘要

项目ACTIVE，治理STANDARD；仓库CP11-gh/CRM、主分支main。产品/架构/治理入口以docs/README.md为准，production G8继续No-Go。

- 当前任务MVP-AGENT-LANGUAGE-QUEUE-UI-001的产品修复已由PR #728/#729合并，最后主线976aa94d；运行候选subject `70293cc68d803670345826cf2892d0ff209d0869`，本次证据分支docs/agent-language-queue-evidence-20261103，EVIDENCE_HEAD_SHA=READ_AT_GATE。
- 最新[IR](../records/implementation/IR-MVP-AGENT-LANGUAGE-QUEUE-UI-001-20261103-R01.md)、[TR](../reports/tests/TR-MVP-AGENT-LANGUAGE-QUEUE-UI-001-20261103-R01.md)、[RR](../reports/reviews/RR-MVP-AGENT-LANGUAGE-QUEUE-UI-001-20261103-R01.md)记录卡片语种、计时器队列、UI状态、人工发送完整等待、机器人不清未读、助手口吻及jobs跨买家持锁修复。最终后端3711通过/5条件跳过，实际前后端CI和独立审查通过。
- staging后端与工作进程/egress为20d03428…d4de，前端e3593a02…3700，051；检索/解析资产不变。三健康与模板页200，现场PG阻塞/闲置写事务0，精确镜像与模板Prompt hash见[机器证据](../../release/evidence/staging/crm-staging-agent-language-queue-20261103.json)。
- 五个共享模板已正式发布v2，旧快照保留；模型、工具、知识槽和店铺Agent配置未批量覆盖。统一运行表达策略1.1.1生效，10个中英文合成表达案例最终通过；两轮原始失败保留，不当作真实工具/RAG/发送链路证明。
- 用户当前US auto、XBM off。XBM最新任务因策略变化cancelled，不再误显生成；未覆盖该开关。欢迎24小时咨询段、60分钟超时和物流external保留。旧unknown/取消任务不重放，未向真实买家试发。
- 本轮staging创建测试业务行0；本地3148/3149测试前端停止，专用PG/tmpfs容器删除。临时管理员同权限身份仅内存且进程结束，私有数据库/环境/历史恢复资料备份保留。
- Workspace hygiene: ATTENTION。未知前端AGENTS.md、其他活动worktree及历史待处理凭证副本保留，不清理未知文件；无本轮文件永久删除批次。三索引保持CANDIDATE_VIEW，证据合并后只读核对全部源记录，不另开状态PR。
- 现场浏览器绑定超时UI_UNAVAILABLE；实际UI行为以本地90项生产浏览器回归为证，不能冒充线上视觉检查。自然新业务送达及用户关闭店铺的恢复开启需要按当前明确范围操作。

下一动作：①合并证据并只读核对索引；②按用户当前开关检查自然新消息回执，不补发历史记录；③production保持No-Go。
