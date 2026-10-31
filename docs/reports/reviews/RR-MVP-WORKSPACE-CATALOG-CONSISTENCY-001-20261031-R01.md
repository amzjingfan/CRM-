---
record_id: RR-MVP-WORKSPACE-CATALOG-CONSISTENCY-001-20261031-R01
record_type: review
revision: R01
status: APPROVE
task_id: MVP-WORKSPACE-CATALOG-CONSISTENCY-001
reviewed_sha: a1be18c4c266293b8fdc6c6f88514f990cfd1d19
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-CATALOG-CONSISTENCY-001-20261031-R01.md
test_record: docs/reports/tests/TR-MVP-WORKSPACE-CATALOG-CONSISTENCY-001-20261031-R01.md
review_focus: [catalog_correctness, agent_tool_semantics, order_fields, send_safety, tenant_scope]
created_at: 2026-10-31T07:50:35Z
updated_at: 2026-10-31T07:50:35Z
supersedes: null
---

# 审查范围、依据与重点风险

按用户截图和补充复核共用目录服务、工作台各状态订单卡、Agent 工具调用、全站侧栏及草稿发送边界。重点是平台目录缺字段、搜索与详情之间状态变化、分页空页、不同店铺订单字段和误把摘要预览当成原生卡片发送。

# 发现、级别、位置和证据

- 共用商品服务过滤 `ACTIVATE` 和正库存，按 ID 与详情同样执行；详情在状态变化后拒绝不可用商品，专用后端测试覆盖。未扩大店铺查询权限，原 `_tiktok_client` 与会话访问校验保留。
- 共用优惠券服务只返回 `ONGOING` 且处于平台领取窗口的券。买家专属资格没有平台确证，工具结果仍标记未验证，工作台卡片也提示核对。
- 平台分页可能出现过滤后空页；工作台保留 `next_page_token`、自动继续加载且有明确加载更多入口，浏览器空页回归通过。
- 订单字段缺值用占位，不根据订单状态推导付款/物流时间；预览仅对应可编辑文本，实际发送仍走原审阅与安全开关，合成测试发送计数 0。
- 未发现需阻断合并的新增权限、外发或数据迁移风险。

# 已验证与未验证内容

相关后端 1795/1795、1 条件跳过；生产构建浏览器 138/138；契约 78/78；类型、lint 0 错误、Ruff、mypy、构建通过。未连接真实 TikTok 商店或验证买家独享券资格，未发布 staging。

# 结论和返修条件

同意合并本地候选。真实店铺目录或券状态字段与平台响应不一致时应回到同任务诊断；不得为凑展示而把未知库存、过期券或无资格券当作可推荐。
