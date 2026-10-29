# Agent 回复交付实施计划

父任务 MVP-AGENT-REPLY-DELIVERY-001。基线为已合入R10的main；旧MVP-AGENT-STAGING-DEPLOY-001先按真实证据收尾。设计见同日spec，用户当前聊天的明确要求与澄清构成授权；本轮不真实发送。

## 文件与接口

- providers/tool_calling.py、anthropic_tool_calling.py、budget.py：原生complete_streaming，返回最终ToolTurn并回调类型化增量；不改变原complete接口。SDK真流，取消关闭连接，同预算/计量，不把reasoning或工具JSON直接显示。
- orchestration/aggregator.py、runtime/formal.py、execution.py、chat/router.py：显式审阅计划模式、原问题绑定、结构化有序文本段；编译和独立复核后才形成可发送计划。普通旧接口维持兼容。
- agents/delivery/：有序文字/物流卡片计划、状态、幂等、部分失败/unknown恢复；工作台路由只负责协议和授权依赖。复用现有真实发送校验，不模拟human_confirmed。
- agents/tools/logistics_updates/：新节点观察/去重/通知计划、tool描述和受控投递入口；不把通知调度混入模型语义路由。持久化和jobs接线由主任务统一集成，默认关闭。
- frontend/lib/api与独立reply-review模块、workspace/page：草稿流与已复核计划分开，逐条/分段预览和物流卡片，旧草稿/跨会话/迟到结果不覆盖，不能使用未复核内容。
- src/tests/backend/agent、domain、integration/postgres和frontend/contract/browser：唯一测试根，临时输出仅src/tests/.artifacts/agent-reply-delivery-20261029。

## 实施顺序

1. 编写可失败行为测试：第一增量早于最终Turn、上下文预算/取消/SDK错误、分段顺序、消息绑定、最新物流摘要+卡片、文字失败阻断卡片和部分成功重试、通知重复/乱序/撤权/未知结果。
2. 在相互独立路径并行实现原生Provider流与物流更新深模块；主任务负责计划/审阅栏/运行接线。每个子任务记录允许路径和交付物，不触碰Git/共享文档/密钥/真实发送。
3. 集成服务端有序交付和模型分段，保留@tool、全部配置工具和Agent候选、原绝对deadline。完成真实草稿事件通路，复核前仅内部审阅，失败清空并显示原因。
4. 实现审阅栏文字、分段和卡片序列，复用当前TrackingCard；发送计划仅在人工明确确认或单独启用的物流策略授权下执行。当前仅本地替身演练。
5. 回归原手工文本/译文/卡片、调试、绑定RAG、取消、店铺切换、队列/幂等和通知关闭。全量隔离PG/迁移回退、静态、前端契约/生产构建浏览器、动态与安全评测和独立审查。
6. 同步PRODUCT/API/AI/DEPLOYMENT/TESTS、IR/TR/RR和机器证据。完成即合并到main；本期新增真实发送/通知默认关闭，部署或自动发送实际开启另行按批准执行。

## 并行职责

- stream-provider：允许src/backend/app/agents/providers/{tool_calling.py,anthropic_tool_calling.py,budget.py,text_streaming.py}及src/tests/backend/agent/test_native_text_streaming.py；交付可单独行为验证的流式端口，无其他接线。
- logistics-updates：允许src/backend/app/agents/tools/logistics_updates/**及src/tests/backend/agent/test_logistics_updates.py；交付有类型状态/去重/授权/通知计划接口及替身测试。不能改模型注册、迁移、jobs或前端，接线由主任务完成。
- 主任务拥有其余路径；审查者只读最终候选。共享契约先沟通，不能同时改相同文件。
