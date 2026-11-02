---
record_id: IR-MVP-AGENT-AUTOMATION-FULL-001-20261102-R01
record_type: implementation
revision: R01
status: FINAL
base_sha: 81e22445cd9dcf756af41e94f3c68924d623b759
final_sha: c76e046de745bef6c18b475fe203664de378df54
test_record: docs/reports/tests/TR-MVP-AGENT-AUTOMATION-FULL-001-20261102-R01.md
review_record: docs/reports/reviews/RR-MVP-AGENT-AUTOMATION-FULL-001-20261102-R01.md
task_id: MVP-AGENT-AUTOMATION-FULL-001
requirement_ids: [USER-AGENT-FULL-CHAIN]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05, AC-06]
created_at: 2026-11-02T10:25:00Z
updated_at: 2026-11-02T10:25:00Z
supersedes: null
---

# 实施范围与实际变更

用户已授权两家现有 TikTok 店铺在完整验收后开启 Agent、欢迎、60 分钟超时及物流更新自动通知；新店和 production 默认关闭。测试不向真实买家发送消息。

- AC-01 普通 Agent 增加逐店 off/preview/auto、会话暂停、持久投递证明和同会话 FIFO。复核正文、发布版本、知识审批、权限与策略在最终适配器前重新校验；unknown 不自动重发，不伪造人工确认。
- AC-02 欢迎按 24 小时咨询段，超时从最早未答消息计时且每段一次。欢迎、已读、草稿不能取消超时，成功人工或 Agent 非欢迎答复可以取消；关闭期间不回填历史任务。
- AC-03 物流事件使用已绑定 @tool function calling 和文件 RAG；模型可自行补齐缺失前提。文本仅最新节点，文本后接详情卡片，事件基线、去重、乱序和独立复核保留。移除模型草稿错误复用的自由输入地址启发式，保留统一语义隐私过滤、重写后再复核和最终正文证明。
- AC-04 独立物流预演和第三轮固定双语兜底真实返回工具记录；调试内部协作仅预演，不产生业务写入。
- AC-05 050 迁移创建投递表、接待状态和物流证明字段。新增客户回复知识审批用途；内部审批不自动升级。REAL 与 AUTO 两开关共同授权，四个进程配置和固定出口由 staging 门禁校验。
- AC-06 增加两店正式认证验收入口、22 个版本化场景及隔离实际模型物流组件入口。部署先关外发，完成正式 API 验收及精确测试清理后再开启已授权策略。

# 决定、接口及回滚

保持模块化单体、现有 Worker、发送执行器、店铺隔离、CSRF、幂等和审计；不新增外部消息通道。生产仍为 No-Go。超时作用域已经过期时，即使模型 SDK 吞掉取消并返回 safe，也必须拒绝提示词批准。

当前 PRODUCT/API/AI/SYSTEM/DEPLOYMENT 与测试入口已同步。050 只在无新状态事实时可降级，不能为回滚删除投递事实；优先关闭全局/逐店自动化并恢复受审镜像。部署前数据库与运行配置私有备份已生成；现场验收与开启结果另行登记，不以本地测试代替。
