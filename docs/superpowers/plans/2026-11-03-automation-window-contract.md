# 自动发送窗口契约修复实施计划

任务 MVP-AGENT-AUTOMATION-WINDOW-001；基线7fe0788ff9c97ec0e5ed6ffc80f2946c4f89cfed；目标origin/main。用户已批准修复、测试、沿用手动staging发布及测试数据清理。保留两店当前自动化配置、真实买家不试发、不重放已取消投递。

## 已确认设计

202601会话详情只负责可信买家身份；202309会话列表负责明确可发送状态，二者不能共用缺字段默认为false的语义。分离响应模型；只在同渠道同会话、同买家且列表明确true时通过。列表分页到目标，重复游标/畸形响应/缺状态/关闭/找不到/整体超时仍失败关闭。使用现有request_timeout_seconds约束完整查找，不增加配置、服务或任意页数上限。

## 实施

1. 先在src/tests/backend/platform/test_tiktok_read.py新增真实HTTP契约形状的缺字段、分页、未知/关闭、畸形、重复游标和超时测试；在agent/test_logistics_notification_integration.py新增详情缺字段+列表true及身份不一致测试。运行并记录RED。
2. 修改app/integrations/tiktok_read.py的响应模型和窗口查找方法；app/agents/tools/logistics_updates/authorization.py统一组合身份/窗口。更新现有fixture的两个接口，保留撤权/时效/失败关闭断言。跑定向GREEN。
3. 增加或更新隔离PostgreSQL投递契约测试：真实HTTP返回形状驱动共享校验，捕获平台适配器验证Agent/欢迎/超时落账；物流订单发现通过同一校验。平台发送仅为本地捕获，绝不真实发送。静态、全后端、独立审查与适用CI一次收口。
4. 手动部署受审精确后端镜像，保留当前前端及customer automation profile、两店allowlist和策略。现场只读调用实际窗口来源及投递前复核，确认物流订单发现恢复；旧取消记录不补发。清理自有隔离测试数据，保留真实订单、审计与备份。IR/TR/RR和低敏证据准确区分模拟投递与真实收件。

## 安全负例

跨会话/买家不匹配、窗口false或缺失、未命中、分页循环/畸形、超时、令牌失效、撤权/版本变化均不得到达平台适配器；缺字段不得改为默认允许。
