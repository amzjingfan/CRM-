---
record_id: TR-MVP-STAGING-PROXY-PERSIST-001-20261008-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-STAGING-PROXY-PERSIST-001
tested_sha: dcddb26cbb6ecc92db30a11a2f504d034e6ec048
implementation_record: docs/records/implementation/IR-MVP-STAGING-PROXY-PERSIST-001-20261008-R01.md
requirement_ids: [MVP-STAGING-PROXY-PERSIST-001, G0, G6]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: local Windows PowerShell; GitHub CI; staging Rootless Docker on 192.168.110.210; public staging.overselfx.com
created_at: 2026-10-08T10:18:00+08:00
updated_at: 2026-10-08T10:18:00+08:00
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT: centralized`；新增回归用例位于 `src/tests/backend/runtime_infrastructure/`，普通下载 artifact 位于已忽略的 `src/tests/.artifacts/`。测试只验证 staging 工作流和代理挂载持久性；不触发真实 TikTok 授权或消息写入。

# 命令和逐项结果

| 验收 | 本次结果 |
|---|---|
| 旧缺陷复现 | 旧 proxy 重启返回 OCI bind 类型错误，`/etc/nginx/nginx.conf` 来源在 Runner 临时目录且已被清理；公网 ready 短暂为 502。新增回归用例在修改前因缺少 `OPERATION` 而失败。 |
| AC-01 工作流 | `uv run pytest -c pyproject.toml ../tests/backend/runtime_infrastructure/test_staging_image_prefetch.py -q`：13 passed；`uv run ruff check` 和 `ruff format --check` 对该文件均通过。PR #89 的 Backend/Frontend quality gates 均通过，合入 `main=dcddb26...`。 |
| AC-01 真实预检与部署 | `validate` [37716193186](https://github.com/CP11-gh/CRM/actions/runs/37716193186) 为 `validated`；`deploy` [37716402745](https://github.com/CP11-gh/CRM/actions/runs/37716402745) 为 `passed`，迁移头核对、三个公网健康接口 200，固定出口 `38.55.145.52`。两个 artifact SHA-256 分别为 `b55bce01f83c883d924bd2a13f18ff88b126c8582c8ab2dbeae73f645b3a870e` 和 `7a53f985a8b5ae3bade85021e6d569d23b352f29de58eb40f3978f043c7f86d7`。 |
| AC-02 持久来源 | Rootless `docker inspect` 显示 proxy 唯一 Nginx bind 指向 `/home/crmdeploy/src/crm-reviewed-source-37716402745-1/src/deploy/nginx/nginx-tunnel.conf`，`RW=false`；源码目录为 `crmdeploy:0750`，配置为普通文件，SHA-256 与仓库相同：`faba4cccfe7c6368ee6853fa95106e5bcb017f16668bff4b622b2bd2dde92c73`。 |
| AC-03 再次重启 | 工作流结束后显式 `docker restart --timeout 30 crm-staging-proxy-1` 成功；同一容器 ID `ee4da0d0bba3...` 在 `2026-10-08T02:14:03Z` 启动，最终 `running/healthy`；公网首页 307、`/login` 200、`/healthz`、`/v1/health`、`/v1/health/ready` 均 200，TLS 验证结果 0。 |
| AC-04 隔离 | 重启前后系统 Docker 的 12 个其他业务容器名称和 ID 相同；Rootless CRM 11 个常驻容器运行，固定出口复测配置与实际均为 `38.55.145.52`。production 未部署。 |

# REQ/AC 或门禁与证据映射

低敏机器证据为 [`crm-staging-proxy-persistent-source-20261008.json`](../../../release/evidence/staging/crm-staging-proxy-persistent-source-20261008.json)。正式工作流保留原始 artifact；本文件记录的 hash 可用于复核下载文件。现有三个镜像的 OCI revision 与本次 `main` 的构建输入零差异，没有新镜像发布。

# 缺陷、未执行项与残余风险

最初直接从非项目 pytest 配置运行单文件时 `_support` 导入失败；改用项目 `-c pyproject.toml` 后 13/13 通过，未改阈值。未重新执行完整后端业务回归或前端浏览器流程：本次没有修改应用源码、前端源码或镜像构建输入，适用的两项 PR CI 已运行。运行中的持久源码目录需保留；未来清理须先核对容器挂载并另立维护批次。TikTok 商家中心授权页“连接失败”的原因、G1 callback 重放和 G6 五日稳定性未在本任务内验证。

# 结论和复测条件

本任务的 staging 代理挂载持久化、再启动和业务隔离 AC-01～AC-04 通过。若下次工作流切换代理来源、清理活动源码目录或重启出现挂载错误，须重新执行相同 inspect、SHA-256、重启和公网健康验证；本结论不代表 production 放行。
