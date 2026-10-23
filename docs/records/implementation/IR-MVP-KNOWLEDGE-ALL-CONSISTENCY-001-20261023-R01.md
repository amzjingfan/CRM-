---
record_id: IR-MVP-KNOWLEDGE-ALL-CONSISTENCY-001-20261023-R01
record_type: implementation
revision: R01
status: FINAL
task_id: MVP-KNOWLEDGE-ALL-CONSISTENCY-001
base_sha: 323bbf73054c6a5719d7a20e87211a51206cb8bb
final_sha: 662da11e4bad0785c7b1338bc7de0c8f22dd47d5
requirement_ids: [MVP-KNOWLEDGE-ALL-CONSISTENCY-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04]
test_record: docs/reports/tests/TR-MVP-KNOWLEDGE-ALL-CONSISTENCY-001-20261023-R01.md
review_record: docs/reports/reviews/RR-MVP-KNOWLEDGE-ALL-CONSISTENCY-001-20261023-R01.md
created_at: 2026-10-23T09:38:00Z
updated_at: 2026-10-23T09:38:00Z
supersedes: null
---

# 实施目标与范围

修复用户在 staging 发现的“全部知识”显示 11 篇，而所有可见分类均显示 0 的不一致。全部知识定义为当前店铺有效分类内 FAQ 与通用文件的并集。原有 11 个未分类文档保留，未自动归类或删除；Agent、检索与 production 不在本次范围。

# 实际变更及原因

- 只读现场查询确认 staging 的 11 个未删除通用文件全部 `category_id IS NULL`，有效分类 0；旧文件列表计入这些记录，侧栏分类计数则不计入。
- FAQ 与通用文件列表新增可选 `categorized_only=true`。服务层在店铺授权查询之后，只纳入同店铺有效分类内的记录；在数据库查询层完成筛选，再计算总数和分页。省略参数保持旧 API 行为，以免影响其他调用者及历史文件详情。
- 知识库页面的列表、搜索与分类角标使用相同筛选口径；手工新建 FAQ 和通用文件上传先要求选定分类。旧 FAQ 表格按已有 `category_code` 逻辑处理。
- 隔离工作分支的源码 subject 经 [PR #546](https://github.com/CP11-gh/CRM/pull/546) squash 合入 `main=c7f601fdf27655235449deb66e634a4e2ad27245`；subject 与合并主线树一致。由该干净主线构建、发布并部署 staging 前后端精确摘要。[低敏部署证据](../../../release/evidence/staging/crm-staging-knowledge-all-category-20261023.json)保留现场聚合结果。

# 关键决定与偏差

历史未分类文件不出现在“全部知识”，但保留默认文件 API 和现有详情读取，以便后续明确归类或处理。未执行自动数据迁移。GitHub Actions 两项检查在零步骤失败，无法计为 CI 通过；使用本地全量测试和现有 staging 手动门禁验证。

# 数据、配置、接口、迁移或 Prompt 影响

新增两个只读列表的可选查询参数，不变更默认响应、权限边界、数据模型、迁移、Prompt、模型或运行开关。当前迁移头仍为 `030_merge_rag_reception`。现有单店人工发送、Webhook 只读和工作台翻译模式保持；production 未发布。

# 验证交接

[TR R01](../../reports/tests/TR-MVP-KNOWLEDGE-ALL-CONSISTENCY-001-20261023-R01.md)记录先红后绿、完整本地测试、构建、staging 门禁及带认证的只读 API 结果。真实已登录页面没有通过 UI 工具直接点击；用户可刷新 staging 知识库确认“全部知识”空态及后续新分类数据。

# 限制、风险与回滚

这 11 个历史文档仍在数据库和文件详情 API 中，不会因本次修复而自动归类。部署前私有 PostgreSQL 备份已创建且 `pg_restore -l` 可读，原前后端镜像摘要已冻结。若需回滚，使用既有 staging 门禁切回前后端旧摘要并核对健康与运行模式；本次无新迁移，优先保留部署后新数据。production G8 继续 No-Go。
