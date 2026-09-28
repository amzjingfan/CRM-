---
record_id: TR-MVP-OAUTH-REAUTH-001-20260928-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-OAUTH-REAUTH-001
tested_sha: fd750c15b6c2970b250de4f7218a4d456a3257aa
implementation_record: docs/records/implementation/IR-MVP-OAUTH-REAUTH-001-20260928-R01.md
requirement_ids: [MVP-002, G1]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
environment: staging Rootless CRM on 192.168.110.210 behind staging.overselfx.com; local Windows Python 3.11; production unchanged
created_at: 2026-09-28T16:51:56+08:00
updated_at: 2026-09-28T17:05:12+08:00
supersedes: null
---

# 范围、环境与 TEST_LAYOUT

`PASS` 只覆盖本任务四项重新授权现场核对，不关闭 `MVP-002`、`MVP-OAUTH-REDIRECT-DEPLOY-001` 或 G1。机器证据为 [`crm-staging-oauth-reauth-20260928.json`](../../../release/evidence/staging/crm-staging-oauth-reauth-20260928.json)。测试源码仍按 `TEST_LAYOUT: centralized` 位于 `src/tests/`。本机 `fd750c1` 对比 staging 后端源 `c99df14` 的 `src/backend`、Compose 与 Rootless 部署资产无差异；因此本轮针对相同产品源码的确定性 OAuth 测试可与现场结果分开解释。

| 验收 | 本次实际方式 | 结果 |
|---|---|---|
| AC-01 浏览器回跳与终态 | 用户亲自在官方页面重新授权并确认自动回到 CRM、美国测试店铺显示“已连接”；业务机只读查询 `TikTokOAuthJob` 最近任务及 `ChannelAccount`，只输出状态/时间/布尔值 | 08:00Z 初次盘点后仅 1 个新 job，创建时间 08:18:47Z；最近 job `connected`、完成时间存在，渠道 connected；浏览器结论来源于用户现场确认 |
| AC-02 一次性材料及审计 | SQLAlchemy 只选取 `state_cipher IS NULL`、`code_cipher IS NULL`；用 `ENCRYPTED_PREFIX` 比较引用前缀，不输出引用；按 job 发起用户、内部店铺、渠道和完成时间窗口统计 `channel.authorize/succeeded` | state/code 均已清空；access/refresh 引用符合加密格式且 access 尚有效；匹配成功审计恰好 1 条，job 无错误码 |
| AC-03 任务读取权限 | 在现有后端容器调用 `get_tiktok_oauth_job_status(session, owner, job_id)` 两次；未提交事务创建同店铺的合成 `agent` 用户调用同一服务，`rollback()` 后新会话核对不存在，并比较审计总数 | 原发起用户两次均为 connected，同店异人 404；审计数不变，合成用户未持久化，job 仍 connected 且密文已清空 |
| AC-04 staging 运行健康 | 容器 SQL 查询 `SELECT version_num FROM alembic_version`，Rootless `docker ps` 检查 backend/jobs，`curl.exe --silent --show-error --output NUL --write-out ... https://staging.overselfx.com/v1/health/ready` | 迁移头 `024_tiktok_oauth_jobs`；backend healthy、jobs running；公网 ready HTTP 200、TLS 验证结果 0 |
| 确定性 OAuth 回归 | 在 `src/backend/` 执行 `uv run pytest -c pyproject.toml ../tests/backend/platform/test_tiktok_oauth_redirect.py ../tests/backend/platform/test_tiktok_oauth.py` | 基线 `fd750c1` 上 36 passed，退出 0；不冒充真实 callback 重放 |

# 命令溯源、失败与限制

现场 SQL 探针经已验证主机密钥进入业务机，以 `runuser -u crmdeploy -- docker -H unix:///run/user/1004/docker.sock exec -i crm-staging-backend-1 python -` 从标准输入执行，不将 SSH 私钥、内部 UUID、平台响应或凭证写入仓库或结果。任务相关低敏事件名为 `tiktok_oauth_reauth_readonly_check`、`tiktok_oauth_reauth_correlation_check` 和 `tiktok_oauth_job_access_probe`。SQLAlchemy 查询只输出任务数量、状态、临时字段是否为空、匹配审计条数、加密格式和到期布尔值；`Store.name` 仅用于限定美国测试店铺，不输出店铺或客户数据。

第一次 AC-03 一次性脚本在已完成 `rollback()` 后访问 detached `Store.id`，退出 1；没有形成可用的测试结论。修正为事务内保存 `store_id` 后重新执行，退出 0 并由独立会话确认合成用户未持久化。此失败及修正均不涉及产品代码或权限放宽。

没有抓取或重放真实 callback 的 code/state；重复轮询 job 不等于重复 callback。自然刷新窗口尚未到，未强迫真实 Token 旋转。增强物流 `202604` 曾返回平台业务码 `11007009`，本轮未重试；Webhook 真实投递与普通消息发送也未执行。以上均保留在对应门禁，不能因本任务 `PASS` 改为通过。
