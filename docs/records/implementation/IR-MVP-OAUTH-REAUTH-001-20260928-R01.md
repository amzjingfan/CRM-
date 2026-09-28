---
record_id: IR-MVP-OAUTH-REAUTH-001-20260928-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-OAUTH-REAUTH-001
base_sha: fd750c15b6c2970b250de4f7218a4d456a3257aa
final_sha: fd750c15b6c2970b250de4f7218a4d456a3257aa
requirement_ids: [MVP-002, G1]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
test_record: docs/reports/tests/TR-MVP-OAUTH-REAUTH-001-20260928-R01.md
review_record: docs/reports/reviews/RR-MVP-OAUTH-REAUTH-001-20260928-R01.md
created_at: 2026-09-28T16:51:56+08:00
updated_at: 2026-09-28T17:05:12+08:00
supersedes: null
---

# 目标与范围

仅将本次 staging 美国测试店铺重新授权的浏览器回跳、OAuth job 终态、一次性材料清除、授权审计、任务读取权限及运行健康固定为低敏证据。它是 `MVP-002` / G1 的一个独立子集，不修改或降低 `MVP-OAUTH-REDIRECT-DEPLOY-001` 对真实重复 callback 的现场验收要求。

# 实际实施与边界

用户在官方页面自行授权，确认自动返回 CRM 并显示“已连接”；Codex 未接收、读取或输出 callback URL、code、state、Token 或验证码。业务机只读核对 08:00Z 盘点后唯一的新 OAuth job 已进入 `connected` 终态，任务密文清空；与同一任务发起用户、内部店铺和渠道关联的成功审计恰好一条，渠道维持连接、凭证引用为受支持加密格式且未到期。

在真实 staging 数据库的未提交事务中构造同店铺、不同用户的合成身份，仅调用任务状态服务两次原发起用户查询及一次异人查询；异人得到 404，回滚后合成用户不存在，授权审计未增加。首次探针已执行回滚，但在随后复核时误读了脱离事务的 ORM Store 对象而退出 1；修正为回滚前保存店铺 ID 后重跑退出 0。该错误属于一次性探针，不改变产品状态或把失败冒充通过。

没有代码、镜像、环境文件、权限、迁移、真实平台消息或 production 变更。此任务仅提交低敏现场记录和当前状态文档，撤销方式是正常 Git revert 文档提交，不需要业务回滚。

# 未完成范围

复用同一真实 callback 的现场重放未执行：job 终态已清除 code/state，不能从审计或重复状态轮询推断“重复 callback 未二次兑换”。确定性回归覆盖代码路径，但不替代现场重放。真实 Token 成功刷新、增强物流 `202604`、G2/G3 和 G1 最终签署也不在本次结论内。
