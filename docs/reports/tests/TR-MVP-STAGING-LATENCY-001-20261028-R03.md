---
record_id: TR-MVP-STAGING-LATENCY-001-20261028-R03
record_type: test
revision: R03
status: PARTIAL
task_id: MVP-STAGING-LATENCY-001
tested_sha: 81c851bf53b7216ef6f5bf4ee8d125aefacb0eaa
implementation_record: docs/records/implementation/IR-MVP-STAGING-LATENCY-001-20261028-R03.md
requirement_ids: [MVP-STAGING-LATENCY-001]
acceptance_ids: [AC-01, AC-05, AC-06]
environment: staging public Nginx gateway, reverse SSH tunnel, business host, public HTTPS
created_at: 2026-10-28T18:52:00+08:00
updated_at: 2026-10-28T18:52:00+08:00
supersedes: docs/reports/tests/TR-MVP-STAGING-LATENCY-001-20261028-R02.md
---

# 测试范围、环境与 TEST_LAYOUT

`TEST_LAYOUT=centralized`；本次无新增测试源码，使用只读 `curl`、`mtr`、`ss` 与 Nginx 语法检查，低敏聚合见发布证据。现场未使用真实客户消息、退款或 production。

# 命令和逐项结果

- `nginx -t` 使用含候选 vhost 的独立主配置通过；候选源码 SHA-256 `5e733a1dcd8b7a09323093b5a26634fe53f91c3b44349f55ee1a796d401229d2` 与传输文件、活动 vhost 一致。私有原配置备份 SHA-256 `82669bd7aab93e6986ba3d81f17fa1959e981e6236b528569a6da76a3329da9d`，目录 `0700`、文件 `0600`。安装后 `nginx -t`、reload、复核 `nginx -t` 均通过。
- 独立回环 Nginx 交替对照 20 组，40 次 `/healthz` 均 200：每次新建上游连接 TTFB p50/p95 `0.491/1.416` 秒，复用连接 `0.314/0.687` 秒；独立监听与临时文件已清理。
- 活动入口配置前后，各 30 次同路径回环 HTTPS `/healthz` 均 200：TTFB p50/p95 `1.042/2.061` → `0.400/1.161` 秒。公网各 30 次均 200：`1.564/4.002` → `1.742/4.028` 秒；公网样本未显示改善。
- 公网 `/v1/health`、`/v1/health/ready`、`/settings/stores` 均 200，`/activate/test` 404、未授权 GET `/v1/chat/query` 405。指纹静态资源 200、网关 `HIT`，API 共享缓存状态为空，HTML `Cache-Control` 含 `no-store`；后端/前端容器仍健康且镜像前缀不变。

# REQ/AC 或门禁与证据映射

[低敏现场证据](../../../release/evidence/staging/crm-staging-nginx-keepalive-20261028.json)保存源/活动配置哈希、备份、样本数、分位数与安全边界。业务机本地网关 20 次 ICMP 探测 0% 丢包，公网入口 ICMP 20 次终点 30% 未回复但可能限速；TCP MTR 20 次终点 0% 未回复、最大 RTT 2266 ms。活动隧道连接同期 `bytes_sent` 从 10,328,806 到 12,555,478，`bytes_retrans` 从 1,488,396 到 1,860,984，重传增量约占发送增量 16.7%。隧道今日有超时重连，累计重启 969 次。

# 缺陷、未执行项与残余风险

两组 30 样本不控制公网共用线路负载，不能作为因果证明；公网 p50/p95 未改善。未对真实 SSE、Webhook、媒体上传或跨店铺业务内容做写入验证，只读状态码和不变配置证明的范围有限。外部线路/隧道仍有显著 RTT 波动和重传，不能靠共享缓存或连接复用消除。

# 结论和复测条件

入口回环等待下降、语法与只读安全回归通过；整体性能任务仍 **PARTIAL**。须修复广域网链路或替代传输后，对同一时段页面冷/热、不同店铺、错误/限流和公网 p50/p95 进行受控复测，达到 AC-01/06 才可关闭任务。
