---
record_id: IR-MVP-READONLY-LOG-001-20260928-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-READONLY-LOG-001
base_sha: c72406349c56f55f9e433b64523b3626682c4adb
final_sha: a2f4da8e12ae10efb27adea400f96b9e037cd6ea
requirement_ids: [MVP-READONLY-LOG-001]
acceptance_ids: [AC-01, AC-02, AC-03]
test_record: docs/reports/tests/TR-MVP-READONLY-LOG-001-20260928-R01.md
review_record: docs/reports/reviews/RR-MVP-READONLY-LOG-001-20260928-R01.md
created_at: 2026-09-28T09:20:00+08:00
updated_at: 2026-09-28T09:33:00+08:00
supersedes: null
---

# 实施目标与范围

修复真实 TikTok 只读冒烟入口使用普通文本 INFO 日志，导致第三方 HTTP 客户端把带签名的请求 URL、店铺与订单标识写入终端输出的缺陷。只改脚本日志出口和成功摘要格式，不改 TikTok API 请求、生产配置或真实能力开关。

# 实际变更及原因

脚本入口改用已有 `configure_logging("INFO")`。该出口只保留受控事件名和低敏白名单元数据，不复制 `httpx` 自由文本；成功时单独向标准输出写入六项纯整数聚合计数 JSON。复审指出异常 traceback 绕过日志出口后，入口也将任意运行异常压缩成固定低敏失败事件与异常类型，保持非零退出而不输出异常链。新增进程级回归分别验证合成签名 URL 和含订单/店铺哨兵的异常链均不进入输出；另验证成功计数仍可供门禁读取。

# 关键决定与偏差

不扩大全局日志元数据白名单。将计数以独立 JSON 输出，避免为单个验收脚本允许任意业务字段进入全应用日志。`202604` 物流接口的现场业务码 `11007009` 未获官方定义，本任务不增加臆测的重试或降级，也不将旧版 `202309` 的成功冒充增强接口成功。

# 数据、配置、接口、迁移或 Prompt 影响

无数据库、配置、公共 API、Prompt 或模型变化；脚本成功输出由普通文本日志变为低敏聚合 JSON。staging 现运行镜像尚未包含本提交，production 未部署。

# 验证交接

针对最终 subject 的红绿回归、全量后端与静态检查见 TR；初审 Important 已通过失败路径红绿测试返修，审查结论见 RR。需先合并并按独立 staging 部署门禁上线新脚本，才能在现场重复真实冒烟；不能把本机测试写成现场泄漏已消除。

# 限制、风险与回滚

先前一次性终端输出已出现签名 URL 与店铺/订单标识；本变更不追溯删除既有工具记录，记录访问应受限。未见 Access Token 或 App Secret 出现在该次输出。新版物流接口异常、OAuth 重复回调现场证据、Token 生命周期和店铺隔离仍属 G1 及前置部署的未完成项。回滚代码可恢复旧脚本，但会重新引入日志泄漏，故不应在真实冒烟中运行旧版本。
