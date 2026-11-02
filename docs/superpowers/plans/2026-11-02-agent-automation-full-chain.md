# 完整 Agent 验收与自动投递实施计划

Spec: ../specs/2026-11-02-agent-automation-full-chain.md
Parent task: MVP-AGENT-AUTOMATION-FULL-001
BASE_SHA: 81e22445cd9dcf756af41e94f3c68924d623b759
MERGE_TARGET: origin/main

## Global Constraints

- 全部测试与临时资产在 src/tests；不向真实买家发送测试消息。
- 当前两家已授权 TikTok 店铺的实际开启已由用户决定；新店及 production 默认不开放。
- 60 分钟超时、24 小时欢迎新段、60 分钟物流补查；既定固定第三轮话术。
- 模型选择已绑定工具和文件，不用正则路由，不以非空正文伪装安全通过。
- 自动发送不能伪造 human_confirmed；权限/店铺/身份/CSRF/幂等/审计/unknown 不能绕过。
- 共享接口由任务 1 定义；任务 2/3 不改迁移、公共发送契约或任务状态文件。

## Task 1: 自动投递基础与 Agent 运行

在 app/agents/automation 增加普通消息账本、策略、投递与运行，接入 chat Worker 和可信入站；新全局 REAL_TIKTOK_AUTOMATION_ENABLED 与逐店 off/preview/auto 共同授权。保持人工发送，sender_role 正确，服务端持久证明核对正文与目标，重复/撤权/关闭/unknown 失败关闭。添加 UI 控制、会话暂停/恢复。现有只有 human_review 的正式结果须保留复核依据并产生显式自动资格，不准按正文存在放行。客户回复文件审批独立于内部建议。

Shared contract: automation.models.AutomationDelivery 提供 id/store_id/conversation_id/trigger_message_id/source_kind/source_key/part_index/content/message_type/card_order_id/card_package_id/agent_run_id/authorized_by/policy_revision/payload_hash/mode/status/not_before/authorization_json/remote_message_id/error_code/attempt_count/claim_token/claimed_until/processed_at 与时间戳。source_kind 为 agent/welcome/timeout；source_key 是来源消息或咨询段唯一标识。automation.service.enqueue_delivery(session, *, store_id, conversation_id, source_kind, source_key, content, authorized_by, policy_revision, mode, trigger_message_id=None, agent_run_id=None, part_index=0, message_type='text', card_order_id=None, card_package_id=None, not_before=None, authorization_json=None) 返回 AutomationDelivery，幂等不提交事务。

Task 1 owns app/agents/automation、chat、tools/executor.py、tools/contracts.py、integrations/tiktok_write.py、integrations/adapters.py、shared/config/settings.py、agents/runtime 与 safety、管理/工作台自动化入口及对应 UI/API。不改 reception、物流模块或迁移；需要的迁移字段交给 controller 汇总。

## Task 2: 接待自动化

reception 模块增加策略字段和基于可信入站的欢迎/超时调度；沿用现有权限/有效期/时区，旧策略 preview。提供 on_reception_inbound(session, conversation, trigger, settings)、collect_due_reception_deliveries(session, settings, now=None) 及 authorize_reception_delivery(session, row, settings)。通过 Task 1 enqueue_delivery 入账，authorization_json 绑定 policy_id。成功的非欢迎出站取消计时，最早未答计时不因后续消息延后，关闭/撤权/人工回复竞态重新检查。添加完整行为/数据库测试和现有策略 UI。

Allowed paths: app/reception/**、components/ReceptionPolicyManager.tsx、lib/reception.ts、对应 src/tests/backend/domain、src/tests/integration/postgres/test_reception_automation.py 及前端接待测试。不修改共享迁移、chat Worker、发送层；报告所需调用点。

## Task 3: 物流事件工具与 RAG

替换 NativeNotificationModel tools=() 的路径，使用 Agent 已配置 @tool 工具及绑定知识进行生成/复核，保留事件账本、窗口验证和基线去重。同步可核实会话关联订单，首次建立基线，补查 60 分钟；已完结且无新事件不重复。提供可测试的依赖注入和独立事件预演，生产不可注入伪造事件。模拟双语事件验证每工具、RAG引用、最新文字、幂等及失败。发送仍共用原 SqlAlchemyToolExecutor，由 controller 接入新 ROBOT 身份。

Allowed paths: app/agents/tools/logistics_updates/**、对应 src/tests/backend/agent 与 test_logistics_notifications.py、新增 test_logistics_event_agent.py。不改 runtime、settings、发送契约、迁移或 task docs；新增执行协作点在报告列清。

## Task 4: 集成、迁移、验收与上线

汇总 050 迁移和模型注册；接入任务 2 的入站/扫描/投递授权，验证三任务共享状态。生成可复用合成知识与五类场景，普通正式 API + 有认证浏览器进入两入口，真实 DeepSeek/BGE，平台事实按真实/模拟标记。逐项修复后全量静态/类型/后端 PG/前端契约与生产浏览器/安全评测。完成任务级及整分支审查，一次产品 PR 合并并手动部署 staging，外发关闭时现场复验并清理测试 manifest；最后应用两店正式配置和新 cutoff，开启四类自动化并核对。IR/TR/RR、索引和恢复摘要定稿后才能 DONE。
