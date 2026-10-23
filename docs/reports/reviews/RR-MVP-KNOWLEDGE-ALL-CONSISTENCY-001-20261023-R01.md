---
record_id: RR-MVP-KNOWLEDGE-ALL-CONSISTENCY-001-20261023-R01
record_type: review
revision: R01
status: APPROVE
task_id: MVP-KNOWLEDGE-ALL-CONSISTENCY-001
reviewed_sha: 662da11e4bad0785c7b1338bc7de0c8f22dd47d5
implementation_record: docs/records/implementation/IR-MVP-KNOWLEDGE-ALL-CONSISTENCY-001-20261023-R01.md
test_record: docs/reports/tests/TR-MVP-KNOWLEDGE-ALL-CONSISTENCY-001-20261023-R01.md
review_focus: [correctness, tenant-isolation, public-api-compatibility, pagination, historical-data, staging-boundary]
created_at: 2026-10-23T09:38:00Z
updated_at: 2026-10-23T09:38:00Z
supersedes: null
---

# 审查范围、依据与重点风险

审查“全部知识”定义、FAQ 和通用文件的查询筛选、同店有效分类约束、计数与分页、旧接口兼容、前端新增入口及 staging 数据安全。依据用户截图、现场只读 SQL、源码差异、回归和部署证据。

# 发现、级别、位置和证据

- 原因已定位：现场 11 个文件均无分类，旧合并列表显示文件，而五个预置分类与自定义分类角标按分类关联计数，所以出现 11 对 0。没有发现类别计数本身错误。
- 新过滤条件放在数据查询层并早于 `COUNT` 和 `LIMIT/OFFSET`；前端列表与角标统一请求该口径，避免只在展示层移除导致分页和总数不一致。
- 同店、有效分类子查询防止其他店铺分类 ID 或停用分类进入“全部知识”；服务层先执行原店铺授权。默认参数为 false，现有 API 调用和历史详情不变。
- 手工写入要求明确分类，避免新未分类文件继续进入不可见状态。旧 FAQ 表格路径保持既有 `category_code` 语义。
- staging 无数据写入、无迁移、无外部消息；源代码与合并主线树一致，前后端按摘要部署。未发现未关闭的高优先级缺陷。

# 已验证与未验证内容

已核对隔离 PostgreSQL、完整后端/前端回归、构建、staging 门禁与带认证只读 API。真实页面视觉点击及创建分类后的现场上传未执行；本审查不将其记为已验证。GitHub Actions 零步骤失败未作为通过证据。保留原 11 文件和默认 API 是有意兼容，后续若需归类必须另定操作与验收。

# 结论和返修条件

对本任务限定范围给出 `APPROVE`；production 仍需独立 G8 放行。若页面与真实 API 结果不一致、跨店铺数据出现、分页漏项或新增入口可写出无分类文件，应返修并修订 RR。
