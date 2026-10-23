---
record_id: IR-MVP-MARKETING-BASIC-RECEPTION-001-20261023-R02
record_type: implementation
revision: R02
status: FINAL
task_id: MVP-MARKETING-BASIC-RECEPTION-001
base_sha: bc542e7b34d7eac3ac97db0bb97b43ef74772cdb
final_sha: 439c50c926240e34e85d543629dab9cd03bdaea4
requirement_ids: [MVP-MARKETING-BASIC-RECEPTION-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05]
test_record: docs/reports/tests/TR-MVP-MARKETING-BASIC-RECEPTION-001-20261023-R02.md
review_record: docs/reports/reviews/RR-MVP-MARKETING-BASIC-RECEPTION-001-20261023-R01.md
created_at: 2026-10-23T03:29:56Z
updated_at: 2026-10-23T03:43:37Z
supersedes: docs/records/implementation/IR-MVP-MARKETING-BASIC-RECEPTION-001-20261023-R01.md
---

# 现场部署补记

[R01](IR-MVP-MARKETING-BASIC-RECEPTION-001-20261023-R01.md) 的基础接待源码与人工发送边界不变。源码 [PR #539](https://github.com/CP11-gh/CRM/pull/539) 已合入 `main=d19f683558c1d186478fb4f4a0682d8af95f5a15`；本记录绑定原 subject `439c50c926240e34e85d543629dab9cd03bdaea4`，不把主线合并 SHA 冒充 subject。

# 合并与部署

- 合并主线 `d19f683558c1d186478fb4f4a0682d8af95f5a15` 的构建源已核对为干净；后端和前端候选镜像为 `sha256:2049c745befffe969d01313e4b557190f596dea72909be9d8fc648f578cd1f94` 和 `sha256:0b34a7182eb09741ccd32afa8618515bb88df2218017e2d0a18f8eee34edf311`，OCI amd64 与 revision 核对通过。
- 部署前后端和前端旧摘要分别为 `sha256:b3598ebf39c1982937528d1b834008764add6886c4f7347733b849f7aabeebf0`、`sha256:a867f62455c02a3d918cc9526d326ae92e003db8d50d28cad88ec101b3defa39`；现有检索镜像摘要为 `sha256:feeee5a3327bc7d18e49bf534dad431adcb12a3089b025bb068a687662523059`。六角色预取和 `ValidateOnly` 均通过。
- 部署前私有 PostgreSQL 备份大小 389366 字节，权限 `0600`，`pg_restore -l` 可读，备份哈希两端一致（低敏证据只记录前缀 `625d792b42bf`）。
- 精确摘要 `Deploy` 通过，后端、前端按上述候选摘要运行，检索维持 `sha256:feeee5a3327bc7d18e49bf534dad431adcb12a3089b025bb068a687662523059`。迁移头为 `028_basic_reception_config`，CRM 11 容器运行；固定出口及既有单店人工发送、TikTok 读取/Webhook、工作台翻译范围核对通过，自动回复、高风险写入、AI 营销、LLM 和 SSE 保持关闭，查询上限 10。
- 公网 `/healthz`、`/v1/health`、`/v1/health/ready` 及 `/marketing/reception/quick-replies`、`/marketing/reception/timeout`、`/marketing/reception/welcome` 均返回 HTTP 200。已登录 staging 页面经浏览器现场核对：智能营销侧栏显示“基础接待”及三个子入口；快捷回复页有个人/团队、分组/搜索和空态；超时自动回复、进店欢迎语页正常加载且明确提示自动发送关闭。

命令门禁与页面结果见[低敏现场证据](../../../release/evidence/staging/crm-staging-basic-reception-20261023.json)。

# 限制、风险与回滚

本次未创建或更改真实策略配置，未向买家发送消息；现场 UI 与运行模式核对不等于买家发送验收。production 未发布，仍须独立 G8 放行。任何回退须核对旧镜像和迁移 028 后新增的配置数据；不能盲目降级并丢失新数据。证据不写入店铺 ID、账号、Token、客户正文或私有备份路径。
