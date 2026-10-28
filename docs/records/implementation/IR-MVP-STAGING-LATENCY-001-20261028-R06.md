---
record_id: IR-MVP-STAGING-LATENCY-001-20261028-R06
record_type: implementation
revision: R06
status: FINAL
task_id: MVP-STAGING-LATENCY-001
base_sha: dd427267094a17f46f33d8d961e967c66d4e879d
final_sha: ef4beff3bb0d26b86195b7b36b590eb5153cfd2e
requirement_ids: [MVP-STAGING-LATENCY-001]
acceptance_ids: [AC-05, AC-06]
test_record: docs/reports/tests/TR-MVP-STAGING-LATENCY-001-20261028-R06.md
review_record: docs/reports/reviews/RR-MVP-STAGING-LATENCY-001-20261028-R06.md
created_at: 2026-10-28T22:45:00+08:00
updated_at: 2026-10-28T22:45:00+08:00
supersedes: docs/records/implementation/IR-MVP-STAGING-LATENCY-001-20261028-R05.md
---

# 实施目标与实际变更

基础接待的快捷回复、超时自动回复与进店欢迎语初次加载原先先等 `currentUser()`，再请求 `listStores()`，使两个公网往返串行。`ef4beff3` 让店铺名称请求与身份请求同时开始，身份仍决定授权店铺 ID，店铺列表仅补名称；名称失败仍显示授权 ID 和既有提示，身份失败仍失败关闭。新增浏览器行为回归：阻塞身份响应时，三个页面共用的两类管理器均先发起店铺请求；测试在旧实现失败、修改后通过。

# 源码和发布边界

主线候选只改两个前端管理器和一个集中式浏览器测试。按用户只部署当前性能修复的要求，staging 从已运行的性能专用 `9d6ccc20` 摘取相同代码形成 `97ac71ef`；两个实现及测试文件与主线候选逐文件同树。发布差异只有这三个文件，后端、Agent 动态改写、部署配置及人工发送开关均未随最新 main 部署。新前端 linux/amd64 单清单摘要 `sha256:7bfce9ae5bd2ccc9b83b4c43beccad76bbf39b3fd3b16bf2b527c35ce22ba74c`。

# 验证、偏差与恢复

私有环境、PostgreSQL 和 MinIO 备份及可读性、源提交、OCI revision 和 RepoDigest、`ValidateOnly` 均通过。第一次 `Deploy` 因临时 GHCR 凭据目录为空停在镜像拉取，前端未切换；保留失败日志，补入一次性凭据后同一候选的 `Deploy` 通过并注销凭据。12 个容器运行，前后端摘要、单店人工发送范围及原安全开关复核通过。已登录只读检查三个基础接待页面；未发送平台消息、退款或发布 production。详见 [TR R06](../../reports/tests/TR-MVP-STAGING-LATENCY-001-20261028-R06.md) 和 [低敏发布证据](../../../release/evidence/staging/crm-staging-reception-bootstrap-20261028.json)。

用户将网络故障期间的公网 p50/p95 改为诊断指标，不设应用修复的绝对通过阈值；应用正确性、权限与失败处理仍须验证。本轮仅证明串行请求消除及页面可用，不能宣称公网整体提速。恢复只切回前端旧摘要 `sha256:ba138da355d1e51b33e15c389004f16c238ca55787201466778c70b7c472f98c`，保留业务数据和后端现状。
