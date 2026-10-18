---
record_id: IR-MVP-TIKTOK-STORE-SEND-001-20261018-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-TIKTOK-STORE-SEND-001
base_sha: ad91efadb92f04e7b96656b7f039edef107c02aa
final_sha: 6394282897abdb89349dee7399bb05629220ca2e
requirement_ids: [MVP-TIKTOK-STORE-SEND-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
test_record: docs/reports/tests/TR-MVP-TIKTOK-STORE-SEND-001-20261018-R01.md
review_record: docs/reports/reviews/RR-MVP-TIKTOK-STORE-SEND-001-20261018-R01.md
created_at: 2026-10-18T12:14:00+08:00
updated_at: 2026-10-18T12:14:00+08:00
supersedes: null
---

# 实施目标与范围

把 staging 已审核 TikTok 店铺的现有会话，从单个受控会话范围扩展为同店铺人工确认普通文本范围。真实写入仍需坐席权限、人工确认、有效渠道授权、店铺隔离、幂等与审计；其他店铺、自动回复、高风险写入和 production 不在此次放行范围。

# 实际变更及原因

- [PR #348](https://github.com/CP11-gh/CRM/pull/348) 将真实发送目标限定为互斥的单会话 ID 或已审核标准 UUID 店铺列表；空范围和混用配置失败关闭。工作台只有对活动店铺、已连接且具备客服权限与有效凭证的 TikTok 渠道才显示 `send_mode=real`。
- 同一范围检查在工作台服务、工具执行层和 TikTok 写客户端重复执行；工具层锁定活动店铺，保留未结清 `processing/unknown` 的店铺级阻断、人工确认、幂等、审计和单次平台调用。
- staging Compose 与手动部署门禁接受精确的店铺列表，并核对部署前后运行环境；G5 快照和恢复脚本保留原店铺范围，兼容旧版单会话快照。
- [PR #350](https://github.com/CP11-gh/CRM/pull/350) 修复未启用真实发送时空会话目标变量的解析，使默认关闭配置可启动，开启时仍强制目标范围。

# 关键决定与偏差

店铺列表只经 staging 受审部署参数注入，仓库和低敏证据仅保存目标类型与数量，不保存店铺 UUID。真实消息发送不由本任务自动触发；既有受控买家双向发送由 `MVP-004` 的独立 [R04 测试报告](../../reports/tests/TR-MVP-004-20261017-R04.md)证明。此次扩范围只对一个已审核店铺生效。

# 数据、配置、接口、迁移或 Prompt 影响

新增 `TIKTOK_MESSAGE_WRITE_ALLOWED_STORE_IDS` 配置和手动门禁参数，且与原单会话目标互斥。工作台现有详情接口的 `send_mode` 根据店铺与渠道实时判断；无 API 路由或数据库迁移变化。生产 Compose 保持真实写入关闭。

# 验证交接

最终 subject 为 `6394282897abdb89349dee7399bb05629220ca2e`。手动 staging validate/deploy、低敏运行检查、本地定向回归与安全审查见对应 TR/RR；之后独立 G5 窗口的恢复与模式核对见 [R70](../../reports/tests/TR-MVP-006-20261018-R70.md)。

# 限制、风险与回滚

`send_mode=real` 表示项目允许人工提交，不能保证 TikTok 对过期或受限会话接受每条消息。平台返回不确定结果时保持 `unknown` 并人工对账，不盲重发。回退时通过受审 staging 门禁恢复此前单会话范围或关闭写入；production 另行放行。
