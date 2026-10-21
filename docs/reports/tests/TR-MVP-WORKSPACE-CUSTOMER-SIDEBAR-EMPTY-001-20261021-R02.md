---
record_id: TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-EMPTY-001-20261021-R02
record_type: test
revision: R02
status: PASS
task_id: MVP-WORKSPACE-CUSTOMER-SIDEBAR-EMPTY-001
tested_sha: 7cd8e43e27544036027f2b2d8be2a5fc411d97ca
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-EMPTY-001-20261021-R02.md
requirement_ids: [MVP-WORKSPACE-CUSTOMER-SIDEBAR-EMPTY-001]
acceptance_ids: [AC-01, AC-02, AC-03]
environment: Windows CPython 3.11.15; staging Rootless Docker, authorized TikTok read-only session
created_at: 2026-10-21T01:25:29Z
updated_at: 2026-10-21T01:25:29Z
supersedes: docs/reports/tests/TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-EMPTY-001-20261021-R01.md
---

# 测试范围、环境与 TEST_LAYOUT

R01 记录源码回归；R02 补充从合入主线构建的 staging 后端部署及真实只读验收。项目测试继续使用 `src/tests/` 集中布局；正式低敏机器证据位于 `release/evidence/staging/`。

# 命令和逐项结果

- `git diff --quiet <subject> <merge> -- src/backend src/docker/Dockerfile.backend`：构建输入完全一致。镜像 OCI revision 与合入主线 `f487ea1b6723e4fc1afbc2601e43ce64ac3db911` 一致。
- staging 手动 `CheckOnly`、私有 `pg_dump`、六摘要 `prefetch`、`validate`、`deploy` 全部返回成功；门禁原件见本任务三份 JSON。运行 backend 摘要为 `sha256:cd287496ab80ec4763319f9b761b98e2eb8d7af13d545ce542cdea00c686d764`，容器 healthy、迁移头应用、固定出口通过，三项公网健康接口均返回 200。
- 同一授权零订单会话的只读探针：部署前精确复现 `TikTok 返回数据结构异常`；部署后官方数据仍为 `total_count=0`、空翻页、无 `orders`，侧栏返回 `order_count=0` 且无异常。另一个真实非空会话仍返回 1 笔订单，商品页 20 项、优惠券页 15 项。
- 用户在已登录工作台刷新后直接确认订单栏显示“暂无订单”，不再出现原结构异常。内置浏览器自动化连接超时记 `UI_UNAVAILABLE`；没有把自动化截图作为证据。
- 独立公网 `GET /healthz`、`GET /v1/health`、`GET /v1/health/ready` 均为 200；无买家外发、退款或优惠券写入。
- 低敏证据 SHA-256：prefetch `727d209ed5f5305adfb5afdbaf5e5f95867e6f1f4978318eaa51dd2cd872a7c7`；validate `3f575e427ada3c6d45a5556555c48b040542d37c0f60431193dccdacfd0566ff`；deploy `3cbe156d7a96e906f9a88fb9883514d8e8190c02789d1c5cb44601a89940734e`；只读对账 `eb8a1b35c01261676cf284bba6c5ac493ec91562782d36221be2961869966ab9`。四份 JSON 均通过解析，未含 Bearer 或私钥正文。

# REQ/AC 或门禁与证据映射

- AC-01：零订单会话现场后端返回空结果，用户确认页面空态。
- AC-02：R01 四种失败关闭回归通过；非空真实会话仍返回原订单。
- AC-03：合入主线手动发布、受限备份、健康/出口、同会话只读复测通过。

# 缺陷、未执行项与残余风险

GitHub Actions 两个自动作业为零步骤失败，不作为本次通过证据；用户明确采用手动路径。未进行 production 发布或新真实买家消息测试，这些不在修复范围。将来上游零订单格式改变时仍可能失败关闭。

# 结论和复测条件

本次修复在 staging 的同一会话服务端与用户可见页面均已确认，任务 AC-01～03 通过。后续如再次出现结构异常，应只读记录安全字段路径与分页摘要后重新定位，不宽泛吞掉上游错误。
