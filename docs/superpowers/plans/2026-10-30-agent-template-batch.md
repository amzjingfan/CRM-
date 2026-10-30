# Agent 模板与持久后台批量应用实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 模板复用、逐字段三方差异、本店知识映射及关闭页面后持续执行的多店批量创建/更新，在本地完成全部功能、回归和统一修复后交付，部署另等批准。

**Architecture:** 在现有 app.agents.management 下新增 templates 配置管理模块，运行时继续读取每店不可变 AgentConfigVersion。预览冻结配置，后台以确认人当前权限执行；模型复核在事务外，最终配置/发布/关联/项目结果在同一短事务写入，SQL 租约与 token 拒绝迟到执行。现有后端 lifespan 启停处理器，不新增运行服务。

**Tech Stack:** Python 3.11 / FastAPI / SQLAlchemy async / PostgreSQL JSONB / Alembic；Next.js / React / TypeScript，沿用现有依赖。

**Spec:** ../specs/2026-10-30-agent-templates-batch-design.md

## Global Constraints

- 父任务 MVP-AGENT-TEMPLATE-BATCH-001；BASE_SHA=1eb6dbd1fa44688660fb2809ae3df8ee19108027；MERGE_TARGET=origin/main。
- 只写本任务现有隔离 worktree；不改主 checkout、未知 src/frontend/AGENTS.md、其他任务文件或全局配置。
- 用户明确要求制定计划后直接实施；无需再次请求计划批准。仅本地开发/测试，全部问题统一修复，全部验收后一个最终 PR；不部署、不真实发送、不调用真实付费模型。
- 所有测试和临时 SDD 台账/brief/report 位于 src/tests/，临时根 src/tests/.artifacts/agent-template-batch-20261030/；项目规则覆盖 Skill 默认 .superpowers 输出路径。
- 七段键为 identity/service_scope/tool_rules/escalation/language_format/compliance/clarification；模型成对更新，工具集合比较，名称/编码仅创建用，reply_profile 保持本店。
- 一模板一店一有效关联；旧 Agent template_id 为空。实际文件 ID/审批/客户/记忆/凭证不入模板；知识槽只映射同店文件。
- 模板版本不可变；发布模板不改店铺；草稿不改运行。新 Agent 默认停用，发布后启用必须明确确认；已有未发布草稿须完整差异确认。
- 背景批次在关闭页面后继续；后台用户授权重新核验、短事务、幂等、取消、租约重认领和迟到 fencing 均须有行为证据。

## Review Focus

1. 本店修改后模板未变/两边相同/两边冲突/部分未选字段：基线与审阅版本不虚假推进（T1/T3）。
2. 手工解绑、同文件多槽引用、槽移除、审批撤销：不静默恢复文件、不删文件、不保留失效发布资格（T3）。
3. 发布前已有草稿及预览后并发修改：完整目标确认且 revision/权限/依赖重新核验（T3/T4）。
4. 页面关闭、后端取消或重启、租约过期且旧执行迟到：后台继续或恢复且只提交一次（T4）。
5. 多店部分失败、权限中途撤销、模板归档、修改快照后重试：成功不重跑，变化进入新预览续接批次（T4/T6）。

## Task 1: 类型、三方差异与持久结构（AC-01/02/04/10）

**Files:** 新增 src/backend/app/agents/management/templates/{__init__,schemas,diff,models}.py；修改 management/{config_models,models}.py、shared/database/models.py；新增 migrations/versions/045_agent_templates.py；测试 src/tests/backend/agent/test_agent_template_diff.py、src/tests/integration/postgres/test_agent_template_models.py。

**Interfaces:** schemas.TemplateConfig 使用 default_agent_name/suggested_code/agent_type/description/model_provider/model_name/prompt_sections/tool_names/knowledge_slots。KnowledgeSlot 为 key/name/purpose/required，stable key 唯一。纯函数 config_fields(TemplateConfig) -> dict[str, JsonValue]；three_way_diff(baseline, local, target) -> list[FieldDiff]。字段 key 为 agent_type/description/model/tool_names/knowledge_slots 及 prompt_sections.<七段key>；model 值为 provider/name 对；FieldDiff 含 field/baseline/local/target/status/default_choice，状态 unchanged/template_changed/local_changed/converged/conflict，建议 skip/template/local/resolve。

持久对象 AgentTemplate、AgentTemplateVersion、AgentTemplateBatch、AgentTemplateBatchItem；模板草稿 revision、版本 JSON/hash、preview 快照与确认/幂等、逐店 expected revision/目标JSON/token/lease/status/result；AgentConfig 增可空 template_id/template_state_json，AgentConfigVersion 增 template_source_json；(store_id,template_id) 有效部分唯一。

- [x] 写纯比较及 Pydantic 边界测试：五种状态、模型原子、工具顺序等价、草稿允许未完整七段但拒绝未知段键/未知工具/重复槽 key；先运行见 RED，再实现。
- [x] 实现上述类型/纯函数和带可逆迁移的四表及索引；旧数据无自动关联。
- [x] 实际 PostgreSQL 验证同店重复关联拒绝、独立 Agent 兼容、版本约束、升级/降级往返；聚焦测试和 ruff/mypy。
- [x] 本地小步提交并独立任务审查，记录实际命令，不创建 PR/部署。

## Task 2: 模板生命周期与已发布库（AC-02/03/09/10）

**Files:** templates/{service,router}.py；management/router.py；测试 backend/agent/test_agent_templates_api.py、integration/postgres/test_agent_templates.py。
**Interfaces:** GET /v1/agents/templates/catalog 返回无店铺依赖的已配置模型/七段标题/全部工具元数据；GET/POST /v1/agents/templates，GET/PATCH /{template_id}，GET /{template_id}/versions，POST /publish、/archive、/restore，POST /templates/from-agent。静态 router 优先于 /{agent_id}。TemplateConfig 仅复用 T1 DTO。管理员修改、agent.view 读已发布，非管理员不读草稿。from-agent 指定 source_agent_id 及 source_version 或 source_draft_revision 二选一。

- [x] RED：非管理员写拒绝、无权源店拒绝、发布后版本不可变/草稿继续编辑、归档恢复、源版本选择及不提取文件 ID/reply_profile。
- [x] 实现生命周期、revision 乐观锁、审计、模型/提示词/工具校验，发布模型复核使用现有 review_configured_prompt（测试注入假 provider）。模板校验不要求实际文件。
- [x] GREEN：API CSRF/权限/隔离、不可变版本与旧 Agent 回归；任务审查并提交。

## Task 3: 冻结预览、映射与原子应用（AC-01/03/04/05/06）

**Files:** templates/{preview,application,knowledge,state}.py；重用并最小提取 management/service.py 内不 commit 的发布辅助；config_service.py、schemas.py 增来源读字段及正常发布来源冻结；集中测试 backend/agent/test_agent_template_application.py、integration/postgres/test_agent_template_application_postgres.py。
**Interfaces:** POST /templates/{id}/application-previews，输入 template_version、items[{store_id, action:create|adopt|update, agent_id?, expected_revision?, fields:dict[field,{choice:template|local|manual,value?}], knowledge_mappings:dict[key,list[uuid]], unbind_removed_file_ids, name?, code?, include_existing_draft, publish, enable_after_publish}]。服务端生成完整冻结目标、A/B/C差异、阻断原因、依赖 hash、preview ID。创建不接收客户端 template_state_json。

- [x] RED：新建/关联/更新目标、代码冲突、部分字段基线不推进、显式冲突解析、模型 pair、未发布草稿完整确认、无变化不重复发布。
- [x] RED：必需槽缺失/审批/跨店、同文件多来源、手工额外绑定、手工解绑、槽移除默认留存、显式解绑只移除引用。
- [x] 实现配置与模板逐字段状态、预览 hash、知识依赖校验；提取复用写入/发布函数，外层事务拥有唯一 commit。
- [x] 发布前模型复核在事务外；短事务锁定 item/config、核验 token/revision/hash/权限/知识后一次提交版本+关联+审计+成功台账。普通接口回归并冻结真实模板来源。
- [x] GREEN 聚焦与 PostgreSQL 原子失败/并发/旧运行版本不变；任务审查并提交。

## Task 4: 后台处理、恢复和批次 API（AC-06/07/09）

**Files:** templates/{batch,processor}.py、router.py；main.py lifespan；shared/config/settings.py（只需后台轮询/租约配置时新增）；集中 backend/agent/test_agent_template_processor.py、integration/postgres/test_agent_template_batches.py。
**Interfaces:** POST /v1/agents/template-batches 确认持久 preview（Idempotency-Key、preview_id、confirmation）；GET 列表/详情（分页 items）；POST /{id}/cancel、/retry-failed。重新预览可带 parent_batch_id，只含未成功店铺。processor.run_once() 可在隔离会话测试；start/stop 在现有 lifespan 调用，数据库 token/lease fencing。

- [x] RED：重复确认不复制，key 内容冲突，预览失效；确认返回后无浏览器请求也处理；终止重启/过期恢复，迟到旧 token 不提交；同店并发只创建一次。
- [x] RED：权限撤销/用户停用、模板归档、文件撤销、模型目录改变、超时、取消与部分成功；原 hash 失败可重试，改变配置须新预览。
- [x] 实现 SQL SKIP LOCKED 认领、有限租约、独立 session、退出取消、固定低敏错误码、当前确认人权限重读。应用和成功记录保持同事务，错误另事务持久；不运行 Agent、不启用 LLM/自动回复。
- [x] GREEN 真实 DB 多处理器与崩溃恢复、main lifespan 启停；任务审查并提交。

## Task 5: 模板中心和复用编辑 UI（AC-02/03/09/10）

**Files:** frontend/app/agents/templates/page.tsx、components/agents/templates/*、lib/agent-templates.ts（复用 api.ts 请求出口），agents/page.tsx 导航与保存模板入口；集中 frontend/contract/agent-templates.test.mjs、browser/agent-templates.test.mjs。
**Interfaces:** 消费 T2 API及全局catalog（不借第一店授权冒充全局可用性），对已发布库和管理员草稿区分，模型/七段/工具分类复用现有控件；槽定义不绑定文件 ID。保留原 Agent 编辑/调试/日志行为。

- [x] RED 浏览器：创建/源版本提取、保存发布、编辑不覆盖发布版、归档恢复、无权按钮和私有草稿不泄露。
- [x] 实现模板中心、版本选择、七段与工具编辑、知识需求定义、从 Agent 提取；统一加载/错误/焦点反馈。
- [x] GREEN 前端 contract、lint、typecheck、浏览器；任务审查并提交。

## Task 6: 批量向导、差异审阅、任务中心和来源（AC-01/04/05/07/10）

**Files:** components/agents/templates/{application-wizard,diff-review,batch-progress}*.tsx；app/agents/template-batches/page.tsx；agents/page.tsx 来源/覆盖/解除关联；templates router/service detach 端点；集中 browser/agent-template-batch.test.mjs。
**Interfaces:** 消费 T3/T4 快照 API；预览必须由完整选择产生，确认只提交 ID 不夹带新配置。批次页面仅轮询，不发送推进请求。detach-template 带 expected_revision 保留原配置和历史。

**执行拆分：** T6A 先完成向导所需的精确逐店权限选项、按有效版本显示的本店知识候选、来源摘要和解除关联后端接口及真实 HTTP/PostgreSQL 测试；T6B 消费已审查的 T6A/T3/T4 接口实现完整 UI。候选接口位于现有 templates 模块，复用逐店权限与知识资格判断，不扩展权限框架，不改既有运行或批次状态机。T6A/T6B 都完成并独立审查后才关闭本任务。

执行进展：T6A 已在 bfacd4ae 实现并以 a5e7d732 修复锁等待期间用户/店铺停用边界，95 相关测试、提交后 7 项及修复后 4 个真实锁等待场景通过，独立审查和定点复审闭合。T6B 已在 e03111be 实现，并由 25e72a60 集中修复四项独立审查发现；修复前 RED 1+4、受影响 GREEN 2+7、提交后 4 项定点通过，独立定点复审全部闭合。最终生产/真实HTTP联合与全量仍由 T7 执行。

T6E 消费合同补充已在 009ee882 闭合：批次逐店结果返回冻结的 old_published_version，沿用当前逐店权限隐藏。新增真实HTTP/SQL验证create空旧版本、V1→V2及之后V3不改旧批次、撤权隐藏；2项提交复验和独立审查通过。它不改变执行状态机或迁移，T6B消费该字段完成准确历史展示。

- [x] RED：跨页店铺选择、同名冲突/明确关联、逐店知识、字段三方冲突、完整草稿确认、默认停用、发布启用分离。
- [x] RED：关闭/重开任务页面继续后台、失败行重试/改映射续接、取消、权限缩减、迟到预览不显示、部分升级标识、选择旧版本逆向应用。
- [x] 实现向导与后台进度、来源详情/本店覆盖/恢复跟随/脱离；禁用已确认配置编辑，修改回到新预览。
- [x] GREEN 浏览器与旧 Agent UI 回归；任务审查并提交。

## Task 7: 全量本地验收、统一修复及证据（全部 AC）

最新检查点：最终source831abbcc；backend/全部backend+PG测试树与325相同，完整2970pass/5预期skip、专库另2pass、Ruff566/mypy302/锁/16动态/237安全通过。831前端74contract/类型/lint0error8旧warning/build及209 production浏览器0skip通过。真实V1/V2/V3关context后台、同任务重开attempt1、旧历史哈希与部分来源通过；最终小屏四按钮全显且实际mock PATCH通过，真实GET新样式也通过。统一源/集成/测试兼容及小屏复审全闭合。55自有合成行在完整SDDL私有备份后清理，247非自有审计保留，临时API/前端停止。记录已定稿；尚未PR/合并/部署，进入T8。旧阻断只作历史，不再重跑已闭合任务。

历史过程（已解除）：2026-10-30 整分支源总审 e86a3cdd 收齐 2 Important（生命周期/源店等锁后现时授权、批次最后锁后归属）及 2 Minor（no-op发布文案、action离页尾随GET）。统一 final-fix wave已完成且定点源复审闭合，最终UI仍待合法本机服务；旧候选结果保留追溯，不能据后端通过标整体完成。服务启动策略拒绝与源码缺陷分开记录。

**Files:** docs/architecture/{API,SYSTEM,AI}.md、product/PRODUCT.md、operations/DEPLOYMENT.md、src/tests/README.md；IR/TR/RR 与机器证据、任务/恢复索引。

- [x] T7A：结构破坏性往返只在本任务专属 migration_test 库显式运行；真实升级/降级往返及有数据拒绝降级 2 项通过，独立审查闭合。
- [x] T7C：非破坏性模板 PostgreSQL 测试精确支持项目正式临时库入口，禁止旧 fixture 库；86 项相关回归及静态检查通过，独立审查闭合。
- [x] T7B 准备：新增批次实例进入实际路由/工具/绑定 pgvector/汇总复核的集成覆盖，七段/正文依据/低敏日志计数断言已补强并独立复审闭合；最终 subject 全量仍按下列门禁另行执行。
- [x] T7D：完整 UI 与真实本地 HTTP/PostgreSQL/lifespan 处理器联合探针，关页后完成并重新打开查到准确结果；外部模型仅合成协议端口。
- [x] backend：uv lock --check；ruff check/format；mypy app scripts；隔离 PostgreSQL 完整 pytest（当前唯一合流头046，绝不使用其他任务DB）。
历史结果（不是当前门禁）：后端候选4db20374完整PG为2870 passed/5 skipped（3 Windows/POSIX，2迁移opt-in另在专库2 passed）。31165ab3完整静态与前端生产build/类型/57contract/lint0error通过，src/frontend、backend/app/scripts/uv.lock与4db逐树/逐blob完全一致；T7E只同步迁移链测试并将本轮五缓存可恢复隔离。首次无DB两失败保持记录。前端生产服务启动被工具自动批准审查两次拒绝blocked by policy，尚未完成生产UI/真实HTTP关页联合，不标父任务验收。

- [x] frontend：npm run lint/typecheck/test/build；本地生产 Next 服务执行 npm run test:ui，合成请求与数据，必要时 Codex 浏览器实际交互。
- [x] 覆盖 spec AC-01～10 的逐项证据表、依赖/secret scan、迁移往返、断开浏览器与后台恢复真实 DB 验证；全分支独立审查，统一修复发现后重跑受影响验证。
- [x] 冻结最终 subject，针对其完整验证并记录 IR/TR/RR；文档不得称 staging 上线或真实模型/买家验收。

## Task 8: 单一最终 PR、合并和等待部署批准

- [x] 全部验收之后才推送一个本功能 PR，关联父任务，附回滚与未运行现场项；不为测试发现逐个创建PR。
- [x] 核验精确 head 的 CI；仅 runner/steps=0 可依持续授权用本地替代，已运行失败继续阻断；按当前 AGENTS 完成即合并门禁执行。
- [x] 合并后才更新任务 DONE、核验索引/恢复摘要和证据尾区间；保留部署等待批准，最终按要求逐项报告本地结果。

## 计划自查

AC-01→T1/T3/T4/T6；02→T1/T2/T5；03→T2/T3/T5；04→T1/T3/T6；05→T3/T6；06→T3/T4；07→T4/T6；08→T7全量回归；09→T2/T3/T4/T5/T6；10→T1/T2/T6/T7。接口先定义后消费，frontend 不承担执行语义，后台不依赖客服运行开关。余下实现细节在测试台账记录可逆裁定，不缩减设计范围。

## 主线整合决定（2026-10-30）

完成旧候选的207项production浏览器和真实关页后台联合后，核验主线已到0fc2b50b，新增045_dept_dispatch_login。保留模板045历史，通过046_merge_templates_dispatch合流；单头测试先证明双头失败，再验证046唯一head。Alembic实际证明046降至单个045只拆开合流、不移除模板父分支；专库改测046→044→046，验证旧独立Agent保留、登录表随父迁移正确重建，有模板数据时拒绝降级并保留046。整合后的受影响测试、构建和同fixture认证/来源浏览器另行留证，不把旧候选结果当新主线重跑。

## 最终主线整合核对

PR #674前因主线#673推进产生共享测试导入/文档冲突，保留双方内容后候选a8重新完成2970/5条件skip、迁移2、前端74及209 production浏览器和静态/确定性评测；新前端已由工具独立启停。原Agent/迁移实现相同，真实V3与已清理fixture证据明确复用。R02追加而不改写R01历史；仅待精确PR head门禁与合并，不部署。

## 合并后的状态收尾

产品PR #674已于2026-10-30 squash合入d62981d7。精确head6f84aa4b的run41070184354，后端job124111920290及前端job124111920831均终止failure、runner_id=0、steps=0；CI未运行，按已持续批准本地验证替代。合并源码树与6f84候选一致。任务和隔离子任务在实际合并后标DONE；三索引按权威主线d629全部源记录重建CURRENT。此收尾只修改状态/索引，不新增产品PR或部署。
