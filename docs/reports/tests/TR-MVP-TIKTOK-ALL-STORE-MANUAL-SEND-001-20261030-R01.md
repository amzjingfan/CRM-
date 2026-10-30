---
record_id: TR-MVP-TIKTOK-ALL-STORE-MANUAL-SEND-001-20261030-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-TIKTOK-ALL-STORE-MANUAL-SEND-001
tested_sha: 18a0d7bb0b0ca6b2bb601de32af7128d1a41a9ec
implementation_record: docs/records/implementation/IR-MVP-TIKTOK-ALL-STORE-MANUAL-SEND-001-20261030-R01.md
requirement_ids: [REQ-01]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: staging Rootless Docker; PostgreSQL 044; TEST_LAYOUT=centralized
created_at: 2026-10-30T04:10:46+00:00
updated_at: 2026-10-30T04:17:25+00:00
supersedes: null
---

# 测试范围、环境与 TEST_LAYOUT

从干净 `18a0d7bb` 合并主线导出 Git bundle 并在 staging 建立干净 detached checkout；前后端 OCI revision 与运行摘要匹配。测试覆盖已接入两店的授权和发送模式、未接入店的失败关闭、安全开关、部署门禁，以及用户要求的临时派单测试。

# 命令和逐项结果

- 只读 SQL 核对三家店铺、TikTok 渠道、Scope、Token 时效和未结清出站；只读 Python 对两家已接入店解密 Token，并分别调用 TikTok `get_conversations(page_size=1)`，均成功。没有记录或输出 Token、买家正文。
- 备份目录 `0700`，环境、PostgreSQL custom dump、MinIO archive 均 `0600`；在数据库容器用 `pg_restore --list`、在主机用 `tar -tzf` 核验可读。首次主机端 `pg_restore` 因未安装而返回非零，改用容器内工具完成核验，未重做或覆盖备份。
- Git bundle 校验、远端 checkout HEAD/干净状态、当前镜像 RepoDigest/OCI revision 一致。门禁 `-ValidateOnly` 状态 `validated`；同一组镜像用 `-Deploy` 状态 `passed`。迁移头 044、固定出口 `38.55.145.52`、12 服务和公网 `/healthz`、`/v1/health`、`/v1/health/ready` 均通过。
- 运行 backend 的人工发送名单恰好为两家店；各抽样两条活动会话，`_message_send_mode` 及现存管理员权限下的 `get_session_messages` 均为 `real`。「测试店铺」0 渠道、0 会话，不在 allowlist；对未持久化的该店活动会话调用同一运行判定为 `disabled`。Worker、Jobs、Agent Worker 的真实写入开关均为 false。
- 全部进程的 `AUTO_REPLY_ENABLED=false`、`AI_MARKETING_ENABLED=false`、`REAL_TIKTOK_HIGH_RISK_WRITE_ENABLED=false`。部署后 1 个管理员、3 家保留店铺、0 条派单店铺配置、0 条未结清出站。
- 在「测试店铺」短暂建立合成两坐席、各容量 1 和两条入站待回复会话，两个独立数据库会话并发运行 `dispatch_conversation`：分别分给不同坐席；重复调用保持原归属；产生两条派单审计。最后精确删除合成账号、客户、会话、资格、店铺配置/关联及审计，逐表复查 0 残留。

# REQ/AC 或门禁与证据映射

AC-01：逐店渠道和 Token 只读核对；AC-02：backend 两店名单、现有服务层校验与其他进程写入关闭；AC-03：全部自动/高风险开关关闭；AC-04：干净源码、私有备份、ValidateOnly/Deploy、健康、发送模式及零真实买家测试外发。[机器证据](../../../release/evidence/staging/crm-staging-all-store-manual-send-20261030.json)记录摘要。

# 缺陷、未执行项与残余风险

未向真实买家发送测试消息；真实 TikTok 入站派单、真人多坐席 UI 和 XBM 实际平台收件均未演练。「测试店铺」未接入 TikTok，无法用它验证真实平台入站。未运行 GitHub Actions 部署、全量后端及前端回归；本次只变更部署配置，现有源码与镜像未变。

# 结论和复测条件

当前 staging 两家已授权店铺的人工发送配置及只读发送模式通过，自动发送关闭；合成派单并发与清理通过。将来新增或重授权店铺须重新审查并调整 allowlist，production 仍需单独批准。
