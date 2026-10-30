---
record_id: TR-MVP-AGENT-TEMPLATE-BATCH-001-20261030-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-AGENT-TEMPLATE-BATCH-001
tested_sha: 831abbcc1510ca71e6ed572408884f789a7ce506
implementation_record: docs/records/implementation/IR-MVP-AGENT-TEMPLATE-BATCH-001-20261030-R01.md
requirement_ids: [MVP-AGENT-TEMPLATE-BATCH-001]
acceptance_ids: [AC-01, AC-02, AC-03, AC-04, AC-05, AC-06, AC-07, AC-08, AC-09, AC-10]
environment: Windows; locked Python environment; isolated PostgreSQL/pgvector; Next.js 16.4.2 standalone production; Chrome
created_at: 2026-10-30T12:22:19.880339+00:00
updated_at: 2026-10-30T13:56:53.688132+00:00
supersedes: null
---

# 范围与环境

TEST_LAYOUT: centralized。测试源码均在 src/tests；临时原始日志/截图在忽略的 src/tests/.artifacts/agent-template-batch-20261030，正式记录汇总真实命令、来源和限制。使用本任务独占 full_test 与 migration_test 两库（loopback56874），不使用旧 crm_test，不连接 staging 数据库。早期前端由用户手动启动 standalone3146；用户授权后根任务通过正常工具独立启动并停止最终构建。真实 app.main 与受限模型协议端口仅在联合测试运行，JWT/角色/CSRF未绕过。

# 最终候选门禁

| 验证 | 来源与真实结果 |
|---|---|
| 完整 backend + PostgreSQL | 325c15f8，`python -m pytest -c pyproject.toml`：2970通过/5跳过/2旧warning，261.37s；finally已精确恢复同fixture。3跳过为Windows无POSIX条件，2为已另跑的专库迁移opt-in |
| 专库迁移往返与非空保护 | 325c15f8，显式 migration_test+opt-in，046→044→046、旧独立Agent保留、登录表重建、非空模板拒绝降级：2通过/2未选，5.97s |
| 后端静态/锁 | 325c15f8，Ruff通过，566文件format通过，mypy302源文件通过，uv lock --check通过 |
| 确定性 AI 协议/安全评测 | 325c15f8，16动态/237安全样本 passed=true；不代表真实模型回答质量 |
| 前端契约/类型/lint | 831abbcc，74通过，类型通过，lint0错误（8项原有warning） |
| production 构建和完整浏览器 | 831abbcc，build exit0；production完整209通过/0失败/0跳过，61.04s；小屏聚焦另1通过。包含immutable断言，新增异步等待后验证保存前后四按钮全显并提交正确PATCH |
| 版本/资源来源绑定 | 最终831与325的src/backend、src/tests/backend、src/tests/integration/postgres三树逐项相同，故明确复用325的2970回归、2迁移、静态及评测；831只增加CSS/浏览器用例及已接受主线文案/文档。新构建25MeumsWIKSA80C1Rdujy，页面200且11个引用JS/CSS逐个哈希一致 |
| 真实HTTP/浏览器V3后台 | 325实际V3向导/已有草稿确认/6ms关页/独立后台完成/同任务重开attempt1及旧历史哈希通过；831的后端与Agent TSX/API业务逻辑未变，831重建后真实GET四按钮全显/无横滚、来源11/1/0、同批次结果及旧哈希全部复核通过；业务请求写入0，未重跑V4 |

# 行为覆盖与回归

AC-01～10由集中纯函数、API、真实PG、生产浏览器和联合场景组合验证。覆盖三方差异、模型成对、工具集合、部分覆盖、同店文件、已有草稿显式包含、归档/解除、权限/CSRF/隔离、原子失败、真实锁等待、幂等、取消、租约重认领与迟到拒绝；既有运行器、工具/RAG、记忆和工作台保留在完整回归中。

I1权限回归使用实际JWT/HTTP/PG及6种角色组合，qualified RED24失败/40通过：6项读取泄漏，18项实际配置/版本/运行/审计变化；修复后67新增用例与相关合跑109通过/2破坏性迁移预期跳过，detach相关7通过。模型与限流协议使用明确的本地测试替身，认证和逐店查询没有替换；不是平台或模型质量验收。

旧候选084（src等于6467）的真实联合已通过：两店映射各自文件，A发布且保持停用、B仅草稿；V1确认后9ms关闭context，关页GET仍running，后台自行完成2项；V2确认后5ms关闭，后台完成1项。重开同batch不重跑，真实SQL3执行项attempt=1，A历史[1,2]、B无发布；来源11一致/1本店覆盖/0待处理，桌面/390小屏已目视检查。这是旧候选历史，最终整合源另测V3，不冒充最终重跑。

# 失败、修正和限制

保留fea完整回归2968通过/2失败/5跳过：管理-only角色读取夹具及并发包装器漏传权限参数；只改两处测试，新增先拒绝后显式授权及manage参数断言，原来源/并发断言保留。另保留错误环境导致的早期Node契约失败（清除构建专用API环境后74通过）、Windows跨盘cwd重复拼接的启动错误（使用正式standalone入口后页面和脚本200）、新迁移测试误将046→045父头当作删除模板分支的两条失败（改用真实044边界而不改变产品迁移）、合成fixture的长度/角色错误及Windows子进程编码错误。它们不计为行为RED，也未通过删除测试或降低断言制造通过。

不运行真实TikTok/付费模型、真实外发、staging部署、production、48小时稳定性或生产备份恢复。本轮只证明本地功能、持久后台、权限和协议边界；部署须另获用户批准。小屏几何RED真实复现裁切后改CSS，异步模板按钮等待的静态P2已独立闭合；新前端聚焦与全量GREEN。原合成API进程曾退出（原因未确认），根任务已复核端口并以同fixture正常工具重启，旧capability失效，私有URL异常已抑制；不重建业务数据。最终只读新样式截图已目视确认。清理前完整合成行备份的ACL与原私有状态文件完整SDDL一致、哈希读回验证，通过精确PK事务清除55条自有记录；247条非自有审计保留，原/派生PK提交后独立复查均不存在。备份e062cbb1af663067ea3610c99eb7c01f4607da9119cc84593b67265a6f61c822保留，未做恢复演练。第一次备份因PowerShell5继承PS7模块路径而在权限复制前失败，删除尚未执行且行数未变；显式加载宿主原生Security模块修正，未改执行策略、未降低完整SDDL门禁，首个空失败文件保留。根自有前后端临时服务均已停止。

# AC逐项证据映射

| AC | 实际覆盖入口与结论 |
|---|---|
| AC-01 | test_agent_template_application_postgres.py、test_agent_template_batches.py及批量浏览器；多店选择/幂等/冲突与实际V1两店创建通过 |
| AC-02 | test_agent_template_diff.py、test_agent_templates_api.py、agent-templates.test.mjs；七段/模型对/工具集合/版本来源通过 |
| AC-03 | PG application/batches及真实A发布停用、B仅草稿；无变化发布文案与旧运行快照通过 |
| AC-04 | 纯diff及PG application、真实V2/V3向导；本店描述applied1/reviewed3、身份applied3、已有草稿显式包含通过 |
| AC-05 | test_agent_template_selection_postgres.py、application；本店文件候选/绑定、审批归档撤销、额外文件引用通过，真实两店各映射自有文件 |
| AC-06 | test_agent_template_batches.py、test_agent_template_final_authorization_lock_wait.py；原子失败、现时授权、实际锁等待、token/lease迟到拒绝通过 |
| AC-07 | processor/batches及三次真实context关闭；V3确认6ms后关闭、GET仍running、后台completed、重开attempt1；恢复/重试/取消组件PG通过 |
| AC-08 | 完整2970、test_agent_template_runtime_postgres.py及209 production浏览器；实际内部路由/工具/pgvector/汇总协议和既有工作台回归通过，外部模型合成 |
| AC-09 | 67项真实JWT/HTTP/PG权限矩阵及template API/锁等待；跨店/管理只读区分、CSRF、审计无写负例通过 |
| AC-10 | PG models专库2项、templates/application/source及浏览器；不可变历史/归档/解除/逆向来源与046往返通过 |

依赖验证明确复用31165ab3当次固定清单pip-audit未发现已知漏洞、官方npm audit450依赖总数/漏洞0；package.json/package-lock/pyproject/uv.lock四blob与831逐项相同。保留pip --no-deps/哈希提示和首次镜像registry不支持audit的失败，不称为831重新审计全部环境。有限新增行强密钥特征扫描0，不代表全面DLP。
