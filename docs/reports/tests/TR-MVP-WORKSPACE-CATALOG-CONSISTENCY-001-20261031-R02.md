---
record_id: TR-MVP-WORKSPACE-CATALOG-CONSISTENCY-001-20261031-R02
record_type: test
revision: R02
status: PASS
task_id: MVP-WORKSPACE-CATALOG-CONSISTENCY-001
tested_sha: a1be18c4c266293b8fdc6c6f88514f990cfd1d19
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-CATALOG-CONSISTENCY-001-20261031-R01.md
requirement_ids: [MVP-WORKSPACE-CATALOG-CONSISTENCY-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
environment: merged-main Linux rootless staging; authenticated workspace read-only observation
created_at: 2026-10-31T09:09:12Z
updated_at: 2026-10-31T09:09:12Z
supersedes: docs/reports/tests/TR-MVP-WORKSPACE-CATALOG-CONSISTENCY-001-20261031-R01.md
---

# 测试范围、环境与 TEST_LAYOUT

R01 记录后端 1795 通过/1 条件跳过、生产构建浏览器 138/138、契约 78/78、类型/lint/构建通过，绑定实现 subject `a1be18c4`。PR #698 合入 `171c65ea`；本轮从干净主线 `743eb782` 直接构建前后端，仅发布 staging。测试布局仍为 centralized。

# 命令和逐项结果

- 本机 `docker buildx build --platform linux/amd64 --push` 两镜像成功；远端按不可变摘要核对 `linux/amd64`、OCI revision `743eb782`。业务机直拉后端层停滞，改为本机 `docker save`、SHA-256 校验、内网传输与 `docker load`，再由业务机向 GHCR 按摘要拉取并得到准确 RepoDigest。
- 发布前私有环境、运行快照、PostgreSQL 自定义格式 dump 与 MinIO 归档均已保存；`pg_restore -l` 与归档清单可读，权限为目录 `0700`、文件 `0600`。这不是备份恢复演练。
- 旧版及候选版 `Test-StagingProductionGates.ps1 -ValidateOnly` 均为 `validated`；候选 `-Deploy` 为 `passed`。迁移头 `048_published_reply_profile (head)`，12 个常驻服务运行或健康，固定出口 IP 与配置相同。精确 SHA 和摘要见[低敏机器证据](../../../release/evidence/staging/crm-staging-workspace-catalog-20261031.json)。
- 公网 `/healthz`、`/v1/health`、`/v1/health/ready`、`/workspace`、`/login`、`/marketing`、`/knowledge`、`/agents`、`/settings/stores` 返回 200；HTML 为 `no-store`，取样指纹 JS 为 `immutable`。
- 新建的已登录工作台标签可见统一侧栏及 XBM 已取消订单的支付、发货、物流等稳定基础字段。点击商品标签时浏览器工具超时，真实商品及优惠券列表验收记 `UI_UNAVAILABLE`，不冒充通过；R01 的合成测试仍覆盖筛选行为。
- 运行模式保留两店人工真实发送、Webhook 只读、翻译、Agent 调试/正式建议、文档解析；自动回复、营销、高风险 TikTok 写入关闭。未触发买家外发、退款或 production 发布。

# REQ/AC 或门禁与证据映射

AC-01/AC-03 的已登录导航及订单字段为本轮只读观察；AC-02/AC-04/AC-05 的行为回归来自 R01，本轮验证候选镜像、部署与安全配置。真实店铺库存及优惠券时窗回显尚待可用浏览器进一步复核。

# 缺陷、未执行项与残余风险

商品标签的浏览器操作超时，未取得真实商品/优惠券列表的端到端结果。未做数据库/MinIO 恢复演练，也未发送真实消息；这两项不由本次 staging 发布推出。若需回退，仅切回本轮证据中旧前后端完整摘要，保留部署后的业务增量，禁止直接覆盖整库。

# 结论和复测条件

staging 手动部署门禁和运行模式通过，代码行为沿用 R01 的本地验证结论；真实目录回显另行只读复核。production 保持 No-Go。
