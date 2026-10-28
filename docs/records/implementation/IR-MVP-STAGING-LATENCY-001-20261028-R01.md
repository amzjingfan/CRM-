---
record_id: IR-MVP-STAGING-LATENCY-001-20261028-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-STAGING-LATENCY-001
base_sha: 0b14b1d1be1a68e607d0665807048c81ca7fb01c
final_sha: 2c77b8d9a729e467d702c116ad7403e94660f979
requirement_ids: [MVP-STAGING-LATENCY-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05, AC-06]
test_record: docs/reports/tests/TR-MVP-STAGING-LATENCY-001-20261028-R01.md
review_record: docs/reports/reviews/RR-MVP-STAGING-LATENCY-001-20261028-R01.md
created_at: 2026-10-28T16:35:00+08:00
updated_at: 2026-10-28T16:35:00+08:00
supersedes: null
---

# 实施目标与范围

降低 staging 订单侧栏等待，建立浏览器、入口、应用与 TikTok 只读调用的低敏耗时观测。变更仅涉及只读路径和静态资源缓存；人工发送权限、固定出口及自动回复开关不变。

# 实际变更及原因

- TikTok 只读 HTTP 连接按事件循环、渠道、凭证版本和固定代理出口复用，限制池规模并在进程退出时关闭，避免每次请求重建连接。
- 订单侧栏先显示已同步摘要，详情与标准物流分开请求；限制并发和自动详情次数，并保留手动刷新与重试。
- 仅对已核验买家的订单摘要建立 20 秒进程内私有缓存，键覆盖店铺、会话、买家、渠道与凭证引用；错误不缓存，超大列表只复用买家身份；详情仍重新核验订单归属。
- 应用返回 Server-Timing，慢 API 在浏览器记录固定路由类别；入口配置新增上游耗时和 Trace ID。只有 `/_next/static/` 可使用现有 `cache_one`，HTML/API 不进入共享缓存。

# 关键决定与偏差

20 次分段复测仍显示公网及反向隧道的显著等待；本次代码不能修复物理线路。新主线 `ac7216d4` 含另需部署批准的动态 Agent 改写，性能提交已兼容合并但 staging 不得顺带发布该改写。

# 数据、配置、接口、迁移或 Prompt 影响

新增独立标准物流只读接口与订单详情 `include_tracking` 参数；无数据库迁移或 Prompt 变更。入口缓存配置安装前需核对现网 `cache_one`、额外路由及回滚配置。

# 验证交接

本地回归和实测见 TR R01。部署需对最终合并源码和不可变摘要另行完成私有备份、ValidateOnly、Deploy 与现场订单/静态缓存验收。

# 限制、风险与回滚

进程缓存仅 20 秒且不跨实例；无法消除公网 TCP 建连及隧道抖动。发生身份、授权、限流或异常时失败关闭。回滚到已审查前后端摘要与入口 vhost 私有备份，保护业务增量。
