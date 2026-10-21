---
record_id: IR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-DETAILS-001-20261021-R02
record_type: implementation
revision: R02
status: FINAL
task_id: MVP-WORKSPACE-CUSTOMER-SIDEBAR-DETAILS-001
base_sha: 26faf36d0570c4ce90f5875ce26618adb112558d
final_sha: 3e01d7fc752e46c3105946ca3f3165b44c5c8aba
requirement_ids: [MVP-WORKSPACE-CUSTOMER-SIDEBAR-DETAILS-001]
acceptance_ids: [AC-01, AC-02, AC-03]
test_record: docs/reports/tests/TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-DETAILS-001-20261021-R02.md
review_record: docs/reports/reviews/RR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-DETAILS-001-20261021-R02.md
created_at: 2026-10-20T19:01:47Z
updated_at: 2026-10-20T19:01:47Z
supersedes: null
---

# 实施目标与范围

将已合并的客户侧栏订单详情源码手动发布至 staging，维持已批准的单店人工发送、Webhook 读取与工作台翻译范围。本轮不发送买家消息、不退款、不发券、不发布 production；源码边界见 [R01](IR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-DETAILS-001-20261021-R01.md)。

# 实际变更及恢复点

- 从精确合并主线 `3e01d7fc752e46c3105946ca3f3165b44c5c8aba` 的相同前后端文件树，手动构建 linux/amd64 GHCR OCI index：后端 `ghcr.io/cp11-gh/crm-backend@sha256:fe2f0cf8ce2fe3ae6351226236efb9922c04909016cca0afbd8b4700063c9b40`，前端 `ghcr.io/cp11-gh/crm-frontend@sha256:5e4d9c0d2076c1c8346075cd0e32744288279c629dde0f498265343ca3990eab`。两者 OCI revision 均为上述 main SHA；检索镜像仍为 `sha256:feeee5a3…23059`。
- 从本地可验证 Git bundle 建立此前不存在的 staging 持久、干净 Git clone；手动入口向 GitHub 核对其 HEAD 仍为 main。旧后端 `sha256:67da479a…22281`、前端 `sha256:e3e286a8…5ee8606` 和检索摘要保留为恢复点。
- 切换前在 `crmdeploy` 私有目录保存受限 PostgreSQL 自定义格式备份，SHA-256 为 `d434b3af634cfe8c5b9aebe513f1bf14cf43a8241bf1cad415f658aed4d54982`；私有店铺限定值仅保存在服务器受限文件，不进入仓库或命令输出。六摘要预取不切服务，随后手动 validate/deploy。
- 部署中 TikTok 出口容器首次 Compose pull 返回非零，既有门禁在同一候选摘要上执行第 2 次受控尝试，最终部署、运行模式和健康检查通过。临时 GHCR 登录在本机与 staging 均已注销。

# 数据、配置、接口与安全边界

没有新增迁移或密钥，数据库头仍为 `025_workspace_actions`。Webhook 只读、单店人工发送和工作台翻译维持开启；自动回复、通用 LLM、真实高风险写入和 production 放行维持关闭。新增订单详情接口使用官方只读数据，不自动调用发送。

# 验证交接及限制

六摘要预取、预检和部署原样低敏文件见 [预取](../../../release/evidence/staging/crm-staging-sidebar-detail-prefetch-20261021.json)、[预检](../../../release/evidence/staging/crm-staging-sidebar-detail-validate-20261021.json)、[部署](../../../release/evidence/staging/crm-staging-sidebar-detail-deploy-20261021.json)；现场探针和已部署页面合成浏览器结果见关联 TR。真实登录态浏览器连接连续超时，尚未获得真实客户侧栏截图，任务保持 `VERIFYING`。

如需回滚，先保护部署后新增消息并核对当前容器摘要与私有备份；仅按受审手动门禁切回上述旧镜像，不用旧数据库备份覆盖新消息。
