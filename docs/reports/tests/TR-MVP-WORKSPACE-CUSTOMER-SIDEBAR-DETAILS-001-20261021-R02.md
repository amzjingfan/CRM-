---
record_id: TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-DETAILS-001-20261021-R02
record_type: test
revision: R02
status: PARTIAL
task_id: MVP-WORKSPACE-CUSTOMER-SIDEBAR-DETAILS-001
tested_sha: 3e01d7fc752e46c3105946ca3f3165b44c5c8aba
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-DETAILS-001-20261021-R02.md
requirement_ids: [MVP-WORKSPACE-CUSTOMER-SIDEBAR-DETAILS-001]
acceptance_ids: [AC-01, AC-02, AC-03]
environment: staging Rootless Docker; official TikTok read-only API; deployed HTTPS with synthetic browser responses
created_at: 2026-10-20T19:01:47Z
updated_at: 2026-10-20T19:08:58Z
supersedes: docs/reports/tests/TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-DETAILS-001-20261021-R01.md
---

# 范围与逐项结果

`TEST_LAYOUT=centralized`。源码本地后端 2212 passed/29 skipped、前端 47/47 和生产模式浏览器 44/44 的原始结果见 [R01](TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-DETAILS-001-20261021-R01.md)。本轮只验证合并主线的 staging 发布与真实只读数据，未用 GitHub Actions 作为门禁。

| 检查 | 本次结果 |
|---|---|
| GitHub main SHA、持久 Git checkout、旧运行镜像和受限备份 | `3e01d7fc752e46c3105946ca3f3165b44c5c8aba` 精确匹配；备份 SHA-256 见 IR，未复制客户数据到仓库 |
| 六项不可变镜像预取 | `passed`，`service_mutation=false`；[原样证据](../../../release/evidence/staging/crm-staging-sidebar-detail-prefetch-20261021.json) SHA-256 `0b604dda978419df3e26f9d6fcee92ed51ad3196c8e94e95e8f18f1ecba45287` |
| 手动 staging validate | `validated`；[原样证据](../../../release/evidence/staging/crm-staging-sidebar-detail-validate-20261021.json) SHA-256 `62e0cc10fc3a68d9a832c789754fab88dd1c2883d4f0a6e1d5cc1eafae95f924` |
| 手动 staging deploy | `passed`、`production_release=false`；[原样证据](../../../release/evidence/staging/crm-staging-sidebar-detail-deploy-20261021.json) SHA-256 `1301969976d839ff26ed064099ecbced7e7b549a71d0e03539d2ef7130f6ceb7` |
| 运行态与公网 | 11 个 Rootless 容器；后端/前端/检索 RepoDigest 精确等于候选；`025_workspace_actions (head)`，`/healthz`、`/v1/health`、`/v1/health/ready` 和 `/workspace` 均 HTTP 200；固定出口 configured/observed 同为预期 IP |
| 官方真实只读订单详情 | 当前授权会话返回付款方式、承运商、最新物流描述和时间，四项均存在；另一买家会话请求该订单返回 404；探针只输出布尔值与状态码，不保存正文和标识符 |
| 官方真实只读客户侧栏目录 | 当前授权会话订单 1/总 1，真实详情可用；店铺商品第一页 20/总 27，优惠券第一页 15/总 19。仅输出数量，不保存买家、商品或券明细 |
| 已部署页面合成浏览器 | 订单详情、订单状态/物流搜索与金额明细、商品 SKU/优惠券草稿 3/3 通过；发送调用 0。截图只在忽略的测试临时目录，全部 `/v1/` 响应为合成数据 |

# REQ/AC 映射

- AC-01：本地隔离测试覆盖授权与平台失败关闭；staging 真实跨买家只读探针返回 404。
- AC-02：真实详情四类字段存在，已部署页面合成交互可见；没有自动发送。
- AC-03：手动 staging 发布和官方只读服务核对通过；Codex 内置浏览器虽列出已登录工作台标签，读取连续超时，标记 `UI_UNAVAILABLE`。真实登录态客户侧栏视觉与点击验收尚缺。

# 残余风险与结论

整体为 `PARTIAL`：已部署服务和合成 UI 通过，真实登录态页面未核对。取得真实页面连接或截图后，再核对订单、商品和优惠券侧栏与店铺隔离并更新状态。无买家外发、退款、发券或 production 发布；既有公网间歇超时风险未由本轮消除。
