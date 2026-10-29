---
record_id: TR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R03
record_type: test
revision: R03
status: PARTIAL
task_id: MVP-AGENT-STAGING-DEPLOY-001
tested_sha: 45d872c060f9b632de340318f32bf9de2904efb5
implementation_record: docs/records/implementation/IR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R03.md
requirement_ids: [MVP-AGENT-STAGING-DEPLOY-001]
acceptance_ids: [AC-01, AC-02, AC-03]
environment: authorized Rootless staging / actual immutable images / authenticated Codex browser
created_at: 2026-10-29T10:35:46+08:00
updated_at: 2026-10-29T10:35:46+08:00
supersedes: docs/reports/tests/TR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R02.md
---

# 结果分界

**发布门禁通过，Agent 业务回答验收未通过。** 机器事实见[发布清单](../../../release/evidence/staging/crm-staging-agent-multishop-20261029.json)。没有用本地 Mock 或供应商合成协议探针代替实际 Agent 链路。

| 范围 | 本次事实 | 结论 |
|---|---|---|
| 精确源和构建 | main 45d872c0，干净持久 Git 源；两镜像本机构建、GHCR 清单/amd64/OCI revision 和远端 RepoDigest 核对 | PASS |
| 备份 | 最新私有 PG 744419 字节且 pg_restore -l 成功；MinIO 132764 字节且 gzip -t 成功；环境及原容器快照 | PASS（可读性） |
| 受审部署 | ValidateOnly、Deploy、041 唯一合流 head、固定出口一致、12 活动容器与运行模式 | PASS |
| 公网 | 三健康、七页面 200；根 307→/dashboard；页面 no-store；指纹 JS 200/immutable，共 12 项 | PASS |
| 新 Agent 页面 | 六分类、三操作标签、十二业务工具加四项确认提议；旧物流 Agent v1 与原两项工具保留 | PASS |
| 原店铺兼容 | 另一授权会话在已登录店铺/渠道各见一条生效/connected，工作台原会话及历史消息可见 | PASS（只读 UI） |
| 普通物流问题 | 真实模型父运行 succeeded/review_required，4484 ms，no_verified_evidence；没有业务回答/引用 | 未验收 |
| 显式只读工具请求 | 11920 ms，父 specialist_incomplete；子运行 failed/sensitive_agent_output；无业务回答/引用 | 未验收 |
| 绑定文件 RAG、新店 OAuth | 当前测试 Agent 0 绑定文件；未发起新授权或增加权限 | NOT EXECUTED |
| 实际恢复、生产发布 | 未执行；保护部署后增量 | NOT EXECUTED / No-Go |

# 诊断与证据限制

两条真实请求使用此前获用户授权的买家上下文及现有 DeepSeek。没有改变工具白名单、Prompt、DLP、知识审批或自动发送。父子运行元数据与页面结果一致，第二条明确为输出安全检查失败，不能解释为模型连接失败。

页面两条均显示零工具，但 worker 在无回答、超时或敏感输出等早返回分支不携带 loop 已有事件；本次没有记录模型原文或重跑带原文日志，故无法仅凭零事件断言 TikTok API 未被调用。后续需先保留低敏调用轨迹并定位具体拒绝字段，再完成普通问句、工具事实、文件引用和多 Agent 汇总联测，不得为通过而关闭安全规则。

浏览器自动 AX/多动作调用曾超时；通过同一 IAB 的文档化 DOM API恢复，先只读对账无新运行，再单步提交，最终确认恰有两条父运行及其子运行。截图仅保存在忽略的 src/tests/.artifacts，未上传买家资料。首次 PowerShell 操作从 /root 启动而被权限拒绝，在执行受审门禁前切换到已审核目录后成功。一次只读诊断导入了错误的会话工厂名，修正后才取得有效运行数据；未以该失败输出充当证据。

本地 180 受影响回归与组合 2394/3、前端 52/134 的确切测试源和复用边界保持 R02；本次新事实是镜像构建和实际发布/页面/模型请求，没有声称重跑产品全量。PR #631 两 CI 作业均 runner 0、steps 0，CI 未运行，依据持续批准使用本地替代。网络耗时只作诊断，不宣称公网整体提速。

# 结论

AC-01 发布与 AC-03 目录/原店铺 UI 已验证；AC-02 的实际业务回答仍待定位和复测。任务保持 VERIFYING，不能标 DONE 或宣称工具加 RAG 全链路通过。
