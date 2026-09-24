---
record_id: IR-MVP-OAUTH-REDIRECT-001-20260924-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-OAUTH-REDIRECT-001
base_sha: 7adb26927a717b3fca04056e779bd09bd05d9c75
final_sha: 8a1b81f44478f2c71c4f275873cb68d0b8f4528f
requirement_ids: [MVP-OAUTH-REDIRECT-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
test_record: docs/reports/tests/TR-MVP-OAUTH-REDIRECT-001-20260924-R01.md
review_record: docs/reports/reviews/RR-MVP-OAUTH-REDIRECT-001-20260924-R01.md
created_at: 2026-09-24T16:18:00+08:00
updated_at: 2026-09-24T16:23:00+08:00
supersedes: null
---

# 实施目标与范围

修复真实 TikTok 授权回调在同步交换 Token 与读取店铺期间，浏览器提前断开、未收到 CRM 303 的缺陷。仅实现 staging 可验的代码候选；不部署 production，不开启真实写入、Webhook、LLM 或自动回复。现场部署与 TikTok 真实回跳属独立任务。

# 实际变更及原因

callback 成功路径只验证一次性 state 的用户/店铺绑定，将 state/code 加密写入按 state 摘要去重的短期任务后立即 303 回固定渠道页。现有 jobs worker 领取任务后 GETDEL 消费 state、校验卖家 Token/Scope 和唯一店铺。新增同用户且有当前店铺权限的低敏状态查询与前端轮询反馈。重复回调先查询既有任务，state 已消费时再查一次以覆盖并发提交窗口。加密参数超列长时返回受控 400。

初审发现成功结果和任务状态分别提交、双 worker 超时误判及失败路径释放行锁的问题；最终以 `FOR UPDATE SKIP LOCKED` 持锁贯穿平台调用，保存点只回滚失败的渠道侧写入，渠道成功审计与任务终态原子提交，失败终态、密文清除和低敏审计也在持锁事务中提交。崩溃回滚为 pending；Redis 已消费时再次领取失败关闭而不重复兑换 code。

# 关键决定与偏差

`processing` 为前端回跳语义，任务行的 processing 状态不独立提交；轮询可能先看到 pending，再看到 connected/failed。此取舍保留已批准的快速回跳与现有 worker 架构，同时消除长平台请求被固定超时误判的竞态。拒绝/无 code 的现有即时回跳保持不变。

# 数据、配置、接口、迁移或 Prompt 影响

可逆迁移 `024_tiktok_oauth_jobs` 新建短期任务表，无现有表数据改写。README 与部署说明区分当前代码迁移头 `024` 和尚未升级的 staging 运行头 `023`，固定 2026-09-07 历史基线不改。新增受权限和店铺隔离约束的状态接口；callback URL 固定路径不变，仅成功回跳增加低敏任务 UUID。使用现有凭证主密钥认证加密暂存材料，终态清除，一日后清理收据。未更改生产配置、Prompt 或 TikTok 请求签名。

# 验证交接

提交后本机全量后端、隔离 PostgreSQL 并发/崩溃、迁移升降级、前端生产构建与合成数据浏览器结果见 TR；独立只读复审见 RR。合并后另按 staging 部署门禁验证迁移、健康、回跳耗时和恢复点。

# 限制、风险与回滚

普通 Chrome 新授权目前被 TikTok 官方卖家类型门禁拒绝，尚未进入 callback；这与本代码问题独立。目标卖家设置需由用户在 Partner Center 核对，不能将本机测试冒充真实回跳。回滚须使用已验证的上一镜像与迁移兼容性检查；production 不在此次授权内。
