---
record_id: TR-MVP-AGENT-FIVE-TEMPLATES-AUTO-001-20261101-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-AGENT-FIVE-TEMPLATES-AUTO-001
tested_sha: ad9a9c9c1ea76970835fd255f768c30ebf5ba7c8
implementation_record: docs/records/implementation/IR-MVP-AGENT-FIVE-TEMPLATES-AUTO-001-20261101-R01.md
requirement_ids: [MVP-AGENT-FIVE-TEMPLATES-AUTO-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
environment: Windows local isolated PostgreSQL/pgvector and production Next browser; manual staging at 433715ec with 049 migration, DeepSeek and formal authenticated API; no buyer send
created_at: 2026-11-01T14:07:14Z
updated_at: 2026-11-01T14:07:14Z
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT: centralized`。产品 subject `ad9a9c9c` 的本地测试、已合并源码 `433715ec` 的 staging 发布，以及 2026-10-31～11-01 TikTok US 测试店真实只读工具/模型/RAG 验收。现场脚本仅使用当前管理员有效会话签发的短时身份，正式 API 继续执行认证、CSRF 与店铺权限；凭证不落盘。真实买家姓名、消息正文、订单号和模型输入不进入报告。

# 命令和逐项结果

| 检查 | 结果 |
|---|---|
| `./src/scripts/run-postgres-integration-tests.ps1` 最终 subject | 3169 passed、5 条件 skipped、2 第三方警告；含 049、模板、权限、预演、物流通知 ledger/幂等、固定兜底 |
| Ruff、mypy、`uv lock --check`、staging gate 154 项 | 全部通过 |
| 前端 lint、typecheck、78 契约、生产 build 与 236 浏览器用例 | 0 lint 错误、契约和浏览器全部通过；已有 lint 提示保留 |
| `Test-StagingProductionGates.ps1` ValidateOnly 当前/候选、Deploy | 三份校验摘要及镜像在低敏 JSON；049 为 head、12 服务健康、公网三健康 200、固定出口通过 |
| 已授权正式 API：4 个模板应用、双语 Agent 调试、真实会话建议 | 模板应用成功；中文和英文均生成非空待审阅正文，已绑定知识有引用；详情见下表 |
| 正式 API 删除及只读数据库核对 | 本轮 4 Agent、1 文件软删除；加上首轮共 8 Agent、2 文件；五模板仍发布、预演关闭、测试时段出站消息 0 |

# REQ/AC 或门禁与证据映射

| AC | 现场/隔离证据 |
|---|---|
| AC-01 | 五个共享模板均保留 v1；四个新模板曾应用到同一测试店，绑定的合成知识索引 ready 且审批。订单物流原模板未改写。 |
| AC-02 | 售前调试 `review_ready`，`search_products` 与 3 次 `query_product` 成功；售前工作台真实入站得非空 HUMAN_REVIEW。售后工作台真实入站得非空 HUMAN_REVIEW 与 1 条本店绑定知识引用，`query_order`、`search_customer_orders`、`query_aftersales` 两次及 `search_knowledge` 成功。订单物流工作台非空，订单搜索/详情成功；该样本 `query_logistics` 失败，另一个已授权调试样本成功。物流事件和兜底的专用入口见下段。 |
| AC-03 | 实时商品目录返回 5 项，均已上架且至少一 SKU 有正库存；仍有下一页。隔离测试覆盖零库存、未知库存、下架、混合 SKU 与分页。 |
| AC-04 | 本地多 Agent 预演覆盖入站幂等、授权、撤权、开关关闭、失败关闭与待审阅结果。现场店铺预演开关复原为关闭；全局 `AUTO_REPLY_ENABLED=false`，测试时段出站消息 0。 |
| AC-05 | 源码单次 PR #704 合并，手动 staging 部署、私有备份、双预检、健康和合成数据统一清理已完成；低敏发布细节见[机器证据](../../../release/evidence/staging/crm-staging-five-agents-20261031.json)。 |

# 缺陷、未执行项与残余风险

- 售后早期调试样本的 `query_aftersales` 曾失败；随后真实工作台两次成功。订单物流对一位买家的 `query_logistics` 仍失败，未把整轮工具链宣称全绿；该样本最终返回待审阅正文，但需要按失败原因继续观察具体店铺/API 数据。
- TikTok US 测试店无本地订单和已核实新物流节点，现场不能触发物流更新通知。隔离 PostgreSQL 测试覆盖节点事件、通知预演、账本幂等、零外发和撤权；这是 `无现场样本`，不是平台实测通过。
- 三条现有真实入站均由业务 Agent 回答，第三轮无解条件未成立；英中固定买家语言话术和成功后清零只在隔离行为测试通过，现场未触发。
- 已登录 Codex 浏览器标签读取/创建持续超时，标记 `UI_UNAVAILABLE`；236 项本地生产浏览器回归不能替代 staging 视觉观察。真实买家端自动发送/流式体验不在本轮放行范围。
- GitHub PR #704 的后端/前端 CI run `41193578774` 两作业均 0 步骤且未执行测试；按持续授权的本地替代门禁，未把 CI 写成通过。发布前私有备份未演练整库恢复。隔离 registry 认证副本的精确删除被自动审批拒绝，仍保留且未提交。

# 结论和复测条件

已批准范围内的功能、正式 API 只读模型/工具/RAG、清理与零外发 PASS。专用物流事件、第三轮无解、staging UI 仅有隔离/本地证据，待出现可核实现场样本或浏览器可用时补录，不因此开放真实自动发送。现有物流工具失败若在有对应平台轨迹的真实订单持续重现，按单独缺陷复查，不通过猜测物流状态补答。
