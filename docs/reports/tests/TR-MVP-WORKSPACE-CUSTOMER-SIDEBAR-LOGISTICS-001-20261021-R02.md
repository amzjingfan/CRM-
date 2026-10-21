---
record_id: TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-LOGISTICS-001-20261021-R02
record_type: test
revision: R02
status: PASS
task_id: MVP-WORKSPACE-CUSTOMER-SIDEBAR-LOGISTICS-001
tested_sha: 6e1f2489007b085b5a02d0aff2df6f4d2f86c44e
implementation_record: docs/records/implementation/IR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-LOGISTICS-001-20261021-R02.md
requirement_ids: [MVP-WORKSPACE-CUSTOMER-SIDEBAR-LOGISTICS-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: Windows production build and intercepted browser tests; staging Rootless Docker and authorized TikTok order read
created_at: 2026-10-21T03:39:47Z
updated_at: 2026-10-21T03:39:47Z
supersedes: docs/reports/tests/TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-LOGISTICS-001-20261021-R01.md
---

# 测试范围、环境与 TEST_LAYOUT

R01 记录集中式 `src/tests/` 合成浏览器先红后绿、静态检查及生产构建。R02 补充从精确合并主线手动发布 staging、运行核对及真实订单卡片可见性；低敏证据在 `release/evidence/staging/`。

# 命令和逐项结果

- `git diff --quiet 6e1f2489 4f32c04e -- src/frontend src/docker/Dockerfile.frontend.prod`：前端构建输入一致；运行前端 OCI revision 为完整合并 SHA `4f32c04e2cc2f92170f30c91b8a2ca4d1bf75266`。
- 已审核源码与运行模式 CheckOnly 通过；受限 `pg_dump` 模式 `0600`、SHA-256 `1340b926…b9524afecb`；六摘要预取通过。首次断点预取因单平台镜像格式被拒绝，改用受审脚本的 Docker pull 路径，精确摘要核对成功；此阶段未切换服务。
- 手动 `validate` 和 `deploy` 均通过；新前端 `sha256:7dbdd3ac…d543934`，原后端与检索摘要不变。运行前端 healthy、迁移头已应用、固定出口一致、单店人工发送范围保持；`GET /healthz`、`GET /v1/health`、`GET /v1/health/ready` 独立复核均为 200。
- 用户刷新已登录的真实 TikTok 订单卡并提供截图，直接看到“买家实付金额”“物流状态：已送达”、物流单号、USPS、最新物流描述和时间；详情按钮显示“刷新详情”。截图含订单标识，不纳入仓库。
- 内置浏览器绑定现有标签和新建标签均超时，记 `UI_UNAVAILABLE`；用户截图是现场 UI 证据，没有伪称自动化截图。
- 私有门禁原件 SHA-256：prefetch `4c787b75…36c009b3d`、validate `40101a91…7ada261b8`、deploy `dc616593…5cc779c7e5`；低敏摘要见本任务 JSON。未使用 GitHub Actions，没有由本次操作向买家发送消息或触发退款/发券。

# REQ/AC 或门禁与证据映射

- AC-01、AC-02：R01 合成浏览器覆盖自动只读详情、六项字段及缺失状态；R02 真实卡片截图显示六项信息，无需手动展开详情。
- AC-03：R01 静态、契约、构建及生产浏览器测试；本次部署输入与受测源码一致。
- AC-04：本次手动 staging 门禁、运行摘要、公网健康及用户可见页面确认。

# 缺陷、未执行项与残余风险

不同物流状态的真实订单未逐一制造或测试；合成浏览器已覆盖 `IN_TRANSIT`、`DELIVERED` 和未知状态。平台未返回结构化状态或轨迹字段时仍显示空值，不能据此推断“待派送”。后端/数据库未变，未重跑无关后端回归。production 发布不在范围。

# 结论和复测条件

AC-01～04 的源码、手动部署和已登录真实订单卡片证据齐备，R02 为 `PASS`。后续若实际物流状态与显示阶段不符，应先核对授权订单详情中的结构化物流状态与最新轨迹，不从描述文案猜测状态。
