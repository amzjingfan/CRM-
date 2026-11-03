# 当前测试状态

2026-11-03 真实店铺接口与定向发送[TR](../reports/tests/TR-MVP-AGENT-REALSHOP-API-001-20261103-R01.md)通过：US指定买家查单200空结果、Agent实际搜索后回答；本店订单详情和通用物流8节点；1条标记虚拟的真实消息sent且官方历史可见。XBM真实买家增强物流200/1包裹15节点，Agent查单/查物流并回答，0外发。US增强样本11007009原失败保留；本次不证明买家已读或自动欢迎/超时/节点触发。没有创建假订单/临时Agent/知识文件，真实消息与审计保留；不改策略或部署。

2026-11-03 自动发送共享窗口缺陷已修复并部署：PR#723合并85a2214e，subject `fc5d0c70e3d508b9ba78949a5d609f28ee234559`；详情身份与202309列表窗口分离，保留未知/撤权失败关闭。全后端3678通过/5跳过、实际双CI和独立审查通过。两店线上grant/identity/window全true，XBM只读读到1订单；四项自动化仍开启。隔离测试行已清理、tmpfs停止，staging无新测试业务行、零买家试发；尚无新成功回执，物流仍60分钟扫描。见[本次TR](../reports/tests/TR-MVP-AGENT-AUTOMATION-WINDOW-001-20261103-R01.md)。

2026-11-03 Agent全链路验收与两店自动化已完成：源码PR #719已合并；手动部署subject `20c9103cac541ed43c164a68e7ed2abe03430370`、050及三健康通过。两店各5永久Agent，auto、欢迎24小时咨询段、60分钟超时及60分钟物流轮询external已正式API回读；10测试Agent/8文件软删、139临时消息/12协作清理，原草稿/发布版本及会话记忆保留。88个功能组合中83自动新执行通过、5独立人工事实裁定，原始自动矩阵非全绿；物流为实际模型/BGE的双语模拟，未向真实买家测试发送。长复杂输入仍可被DLP拒绝、模型错误参数失败关闭；现场浏览器UI_UNAVAILABLE；production继续No-Go。见[TR R02](../reports/tests/TR-MVP-AGENT-AUTOMATION-FULL-001-20261103-R02.md)和[低敏证据](../../release/evidence/staging/crm-staging-agent-automation-20261103.json)。

2026-11-02 订单与物流商自动回显[TR R05](../reports/tests/TR-MVP-WORKSPACE-ORDER-TRACKING-CONSISTENCY-001-20261102-R05.md) **PASS（两店已登录 staging 现场抽样）**：重新打开 Codex 内置浏览器标签并打开客户侧栏，TikTok US 订单卡在点详情前显示 USPS、已完成订单与已送达物流；XBM 订单卡显示 SwiftX、运送中订单及物流。两店详情与物流弹层承运商、最新轨迹一致，分别有 8/16 条节点，无错误横幅。关闭侧栏的旧可访问性节点不是可见缺陷。本次未重跑 R03 本地测试或 R04 镜像核验；零测试数据写入、买家外发、退款和 production 操作。

2026-11-02 CBT 增强物流修复 [TR R06](../reports/tests/TR-MVP-G1-LOG-202604-001-20261102-R06.md) **PASS（staging 已登录页面）**：从已部署 `d856760c` 只读检查两笔不同 XBM CBT 已送达订单，物流详情分别展开 19 和 16 条节点；另一家 TikTok US 店铺的 USPS 订单显示通用物流轨迹。R05 的独立真实增强响应含空节点单号且解析/投影成功，R04 回归确认保留该节点而不借用其他单号。没有新建测试数据、买家外发、退款或 production 操作。平台错误 `11007009` 的其他订单仍需按单诊断，不能外推全量成功。

2026-11-01 五类共享 Agent 模板与多 Agent 待审阅预演[TR R01](../reports/tests/TR-MVP-AGENT-FIVE-TEMPLATES-AUTO-001-20261101-R01.md)在批准范围内 PASS：本地隔离 PG/pgvector 3169 通过、5 条件跳过，前端契约 78 与生产浏览器 236 通过；staging 从已合并 `433715ec` 手动发布 049，12 服务及三健康通过。正式认证 API 已验证售前商品调试、售前/售后/订单物流真实会话待审阅建议、售后知识引用及只读工具；实时商品目录抽样 5 项均上架且有正库存。首轮和本轮累计 8 Agent、2 文件软删除，五模板保留，测试时段出站消息 0。物流新节点与连续三轮无解在测试店无现场触发条件，仅隔离测试通过；某物流工具调用样本失败，staging 浏览器 `UI_UNAVAILABLE`，均未冒称现场通过。自动真实发送仍关闭、production No-Go；见[低敏证据](../../release/evidence/staging/crm-staging-five-agents-20261031.json)。

2026-10-31 工作台目录与订单一致性修复已从主线 `743eb782` 手动部署 staging：[TR R02](../reports/tests/TR-MVP-WORKSPACE-CATALOG-CONSISTENCY-001-20261031-R02.md)记录私有备份可读、双 `ValidateOnly`、`Deploy`、048、12 服务、固定出口及九条公网只读路径通过；本地行为验证沿用同 subject 的 R01。已登录工作台可见统一导航和 XBM 已取消订单的稳定基础字段；真实商品与优惠券列表因浏览器工具超时为 `UI_UNAVAILABLE`，不能算现场验收通过。两店人工发送范围和自动发送关闭项保持，零真实消息与退款；精确摘要见[低敏证据](../../release/evidence/staging/crm-staging-workspace-catalog-20261031.json)，production No-Go。

2026-10-31 用户批准的 Agent 模板 UI/回复参数修复已从固定主线 `6074c4b001aa37e1653db3a3a7f226dd3e2077e3` 手动部署 staging，后端 `sha256:dc16ae47…19fa`、前端 `sha256:250d680d…75df`；检索与解析镜像保持。私有备份、原版/候选预检、Deploy、048、12服务、固定出口及三公网健康通过；原翻译/Agent及两店人工发送保持，自动回复/营销/高风险写入关闭。真实绑定合成文件的8项参数/流式验收最终通过（一次坐席译文不可用后重试），两店批次与搜索多选页面核对通过；7合成Agent/4文件软删、2模板归档，原配置保留，零外发。见[TR](../reports/tests/TR-MVP-AGENT-TEMPLATE-UI-STAGING-001-20261031-R01.md)与[完整摘要证据](../../release/evidence/staging/crm-staging-agent-template-ui-20261031.json)。后合入工作台变更不包含在该冻结发布；回退保留048与业务增量，不等同生产放行。

2026-10-31 Agent模板界面与回复偏好已在PR #696合并，未部署；本地候选 78e7069c9a0386d143c474ad9a6cd9a5fb903094：隔离PG3145通过/5条件跳过、生产前端230/230、契约78/78、Ruff/格式/类型305、048升级降级升级、16/237确定性评测与9/9真实模型合成参数测试通过；中间复核协议失败和语义评分分歧原件保留，最终未降低阈值。真实模型例只用合成物流事实，不等同真实TikTok或新RAG现场验收。临时库/自建UI服务清理、零外发，尚未部署；见 [TR](../reports/tests/TR-MVP-AGENT-TEMPLATE-UI-001-20261031-R01.md)。

2026-10-31 Agent调试流式与XBM全链路[TR R02](../reports/tests/TR-MVP-AGENT-DEBUG-STREAM-XBM-001-20261031-R02.md) PASS：候选本地3018/5条件跳过、生产浏览器214/214、78契约、16/237确定性评测；合并8bf的实际部署、中文/英文四工具+知识引用、126公网早片/终态和断连取消持久记录通过。模板与XBM Agent保留启用，合成指南已软删、有效文件/绑定0，清理后仅工具物流回答通过，零真实外发。未运行项及测量时间见R02，不等于production放行。

2026-10-31 客服主管店铺授权[TR R02](../reports/tests/TR-MVP-SUPERVISOR-STORE-AUTH-001-20261031-R02.md) **PASS（本地行为与 staging 部署门禁）**：PR #686 合入主线 `8d296227`，本地隔离 PostgreSQL 2984 通过/5 跳过、前端契约 77 通过；已按该主线直构建并部署前后端，私有备份、源码核验、不可变镜像、ValidateOnly/Deploy、047、12 服务和三健康通过。现场主管角色的新权限关联为 1 行；原两店人工发送及所有安全开关保持，零外发。已登录主管页面的浏览器工具两次超时，记 `UI_UNAVAILABLE`；真实 TikTok 新店授权未执行，不记现场 OAuth 验收。见[低敏证据](../../release/evidence/staging/crm-staging-supervisor-store-authorization-20261031.json)，production No-Go。

2026-10-31 Agent模板[TR R02](../reports/tests/TR-MVP-AGENT-TEMPLATE-STAGING-001-20261030-R02.md) **PASS（手动staging发布、业务与合成数据清理）**：统一产品PR #679合并并部署a0前端，后端沿用d670；新旧预检/046/12服务/固定出口/8路径200/11资源哈希通过。最终本地77契约及210生产浏览器、类型/lint/build与独立复审通过；真实两店创建/v2保留覆盖/离页后台（4项各attempt1）、最终中英文订单列表/物流/知识同轮回答及正确引用通过，6项持久工具mock=false。2测试Agent/2文件软删除、模板归档，非测试行哈希不变，两店知识列表0篇。用户已精确授权清理：服务器认证副本已删，本机仍受执行门禁阻止并按用户稍后处理的决定保留；不记作全部凭证已清理，任务待证据合并后收尾。production No-Go，零真实买家外发。[证据](../../release/evidence/staging/crm-staging-agent-template-batch-20261030.json)。

2026-10-31 TikTok 富消息修复 [TR R02](../reports/tests/TR-MVP-WORKSPACE-TIKTOK-RICH-MESSAGES-001-20261031-R02.md) **PASS（staging）**：合并主线 `d67078db` 的前后端精确镜像、私有备份、双 ValidateOnly/Deploy、046、12 服务和公网四条路径通过；已登录工作台实际看到买家图片、商品、订单、物流卡片和两个视频播放器。两家授权店原 4301 条旧类型占位经官方只读列表与单会话补录后均清零，定向旧会话处理没有新增本地消息或错误；完整数量见[机器证据](../../release/evidence/staging/crm-staging-tiktok-rich-messages-20261031.json)。人工发送范围未变、自动发送关闭、零真实买家测试外发，production No-Go。

2026-10-30 管理员接待资格与旧登录标识 [TR R02](../reports/tests/TR-MVP-DEPARTMENT-ADMIN-IDENTITY-001-20261030-R02.md) **PASS（staging 门禁与运行服务只读核对）**：合并主线 `476cc8d5` 精确镜像、私有备份、旧/新预检、Deploy、045、12 服务、固定出口和五个公开路径通过；主管目录可见旧管理员登录标识、联系方式仍隐藏，管理员在部门两店有回复资格且默认未参与派单。登录态视觉检查 `UI_UNAVAILABLE`，真实入站未演练；不把这些项记为通过。自动发送关闭，production No-Go。

2026-10-30 管理员派单资格与旧登录账号显示[TR R01](../reports/tests/TR-MVP-DEPARTMENT-ADMIN-IDENTITY-001-20261030-R01.md) **PASS（本地候选）**：`ae947878` 的隔离 PostgreSQL 权限/派单集成通过，后端 2730 passed/3 skipped、前端契约 55/55、生产构建浏览器 166/166、Ruff/格式/mypy、lint/typecheck/build 通过。主管账号目录显示旧邮箱登录标识，联系方式仍隐藏；管理员须部门成员、显式参与并在线才进入派单。staging 待从合并主线部署，真实入站未演练，production No-Go。

2026-10-30 部门派单冗余说明移除[发布 TR R01](../reports/tests/TR-MVP-DEPARTMENT-RECEPTION-COPY-STAGING-001-20261030-R01.md) **PASS（staging）**：主线 `b5d4985b` 的前端精确摘要、私有备份、双预检/部署、045、12 服务、五个公开路径及已登录页面文字消失通过；后端和人工发送范围不变，零真实买家测试外发。原源码 [TR](../reports/tests/TR-MVP-DEPARTMENT-RECEPTION-COPY-001-20261030-R01.md) 的红绿浏览器、55 契约、lint/typecheck/build 与本轮现场结果分开记录；production No-Go。[证据](../../release/evidence/staging/crm-staging-department-reception-copy-20261030.json)。

2026-10-30 部门派单冗余文案移除 [TR R01](../reports/tests/TR-MVP-DEPARTMENT-RECEPTION-COPY-001-20261030-R01.md) **PASS（本地候选）**：两条合成浏览器用例先红后绿，55 项前端契约、lint（0 error/8 既有 warning）、typecheck 和 build 通过；staging 尚待合并与部署。

2026-10-30 部门统一派单/账号目录[发布 TR R01](../reports/tests/TR-MVP-DEPARTMENT-UNIFIED-DISPATCH-STAGING-001-20261030-R01.md) **PASS（限定 staging 部署）**：主线 `0fc2b50b` 精确前后端、私有备份、双预检/部署、045、12 服务、固定出口、三公网健康和账号/部门页面通过；已登录部门目录回显管理员与主管，派单页进一步浏览器读取超时。源码 subject 的 2730 后端、55 契约、165 常规浏览器与 1 生产缓存项及隔离旧数据迁移见[功能 TR](../reports/tests/TR-MVP-DEPARTMENT-UNIFIED-DISPATCH-001-20261030-R01.md)。真实入站派单与主管独立 staging 登录未演练；原人工发送范围及安全开关保持，production No-Go。[低敏证据](../../release/evidence/staging/crm-staging-department-unified-dispatch-20261030.json)。

2026-10-30 部门角色 UI [staging 发布 TR R01](../reports/tests/TR-MVP-DEPARTMENT-ROLE-UI-STAGING-001-20261030-R01.md) **PASS**：精确前端镜像、私有备份、双预检/部署、044、12 服务和五个公网路径通过；已登录账号“更多”菜单三项直接可见，删除当前管理员禁用。原功能 subject 的浏览器 56/56、前端 55/55、后端 2658 通过/77 跳过；连接测试店合成入站事务回滚零外发零残留。真实 TikTok webhook 未演练，production No-Go。见[低敏证据](../../release/evidence/staging/crm-staging-department-role-ui-20261030.json)。

2026-10-30 全店人工发送 [TR R01](../reports/tests/TR-MVP-TIKTOK-ALL-STORE-MANUAL-SEND-001-20261030-R01.md) **PASS（staging 配置及只读发送模式）**：现存三店中两家已接入 TikTok 客服渠道，原运行 `18a0d7bb` 同版镜像以精确摘要经私有备份、ValidateOnly/Deploy 发布；各店抽样两条活动会话为 `real`，未接入店失败关闭。044、12 容器、固定出口、三健康通过，自动回复/营销/高风险写入及其他应用进程的平台写入均关闭。合成两坐席并发派单与清理通过；未测试真实买家发送或 TikTok 入站派单。见[低敏证据](../../release/evidence/staging/crm-staging-all-store-manual-send-20261030.json)。

2026-10-30 TikTok 授权单入口 [发布 TR R01](../reports/tests/TR-MVP-TIKTOK-OAUTH-UX-STAGING-001-20261030-R01.md) PASS（限定 staging 部署）：源码 `18a0d7bb`，两项镜像发布工作流零步骤失败后按既有本地替代门禁构建/推送；备份、精确摘要、ValidateOnly/Deploy、044、12 服务、模式开关、五个页面和三个公网健康、指纹 JS 均通过。新部署 bundle 无旧 OAuth 卡片标题，店铺页保留添加入口，4 项 OAuth 契约复测通过。真实 OAuth、已登录交互和生产发布未执行；见[低敏证据](../../release/evidence/staging/crm-staging-oauth-single-entry-20261030.json)。

2026-10-30 单客服部发布 [TR R02](../reports/tests/TR-MVP-DEPARTMENT-AUTO-ASSIGN-001-20261030-R02.md) **PASS（staging 发布与默认关闭状态）**：干净主线 `b21f59a7` 的精确前后端镜像、私有备份、ValidateOnly/Deploy、044 迁移、12 容器、固定出口与三健康通过；只读数据核对为 1 指定管理员、3 指定店铺、0 派单配置和 1 清理审计；已登录部门/角色/逐店派单关闭状态可见。现有单店人工真实发送未扩大，自动回复/营销/高危关闭，未向真实买家发送测试消息；真实入站自动分配与多坐席竞争未现场演练，production No-Go。见[低敏证据](../../release/evidence/staging/crm-staging-department-assignment-20261030.json)。

以下为部署前阶段记录；当前运行状态以本页首段和最新全店人工发送 TR 为准。

2026-10-30 本轮回复交付staging通过：冻结发布d111d164/043_logistics_updates，最终中英工具+绑定文件RAG、真实坐席草稿流、文字后卡片、正式审阅取消零发送及临时预演UI移除通过。发布源码2712/3、55/158；保留PR646的本地集成fe4cf4b8为2731/3、55/161。16条合成消息/测试记忆清理、文件软删解绑v13、原26条消息未改。失败重试及限制见[TR R01](../reports/tests/TR-MVP-AGENT-REPLY-STAGING-001-20261030-R01.md)；本次未部署044，真实外发/主动通知未验收。

2026-10-30 单客服部接待与派单候选 `dcc2ada1eb3290c64857b4b5e5e0328402f4281d` 本地 AC-01～04 通过：隔离 PostgreSQL 迁移 043→044→043→044；后端 2730 passed/3 skipped；前端 55/55、浏览器 161 passed/1 skipped；Ruff、格式、mypy、typecheck、lint 0 error/8 既有 warning、webpack build 通过。普通客服可转交本人同店会话；逐店自动派单默认关闭，零自动外发。CI 待 PR 创建后核验；staging 待用户单独批准，production 不变。见[TR R01](../reports/tests/TR-MVP-DEPARTMENT-AUTO-ASSIGN-001-20261030-R01.md)。

2026-10-29 回复交付源码已合入main 26782c2a（PR644），本地通过，subject `b3ce00a35bda8a1504f7f56cb4d910bc0fa0b865`：后端2711/3平台skip、前端55/159、构建/类型/静态/锁及动态16/安全237通过；独立审查关闭。043→041→043和新五表ORM一致；全库98项既有差异与基线完全相同，未伪报alembic check通过。CI run40904785085两个job均runner0/steps0未运行，按持续授权本地替代。新能力未部署、真实发送0；[TR R01](../reports/tests/TR-MVP-AGENT-REPLY-DELIVERY-001-20261029-R01.md)。


2026-10-29 [TR R10](../reports/tests/TR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R10.md)：staging精确手动更新、六类中英现场验收通过；工作台英文1668/中文834，四工具+RAG；一次CN复核格式失败后重试、EN超长改v7运营配置后恢复，均保留。统一恢复性清理、零真实发送。新流式/卡片顺序/主动物流通知待下一范围。
2026-10-29 [TR R09](../reports/tests/TR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R09.md)：精简与双语澄清本地2571/3、静态和独立审查通过；真实候选英文1875字及双语缺证通过。aa公开中英调试/工作台四正例通过，英文长稿和英文缺证旧兜底未满足新要求；本subject未部署，任务PARTIAL。


2026-10-29 第二批本地门禁通过，subject `ff4d5e262bed31f07d9ec04a7c021c1a2b7fa9ba`；新候选未部署。后端2514/3与新增统计8、前端52/105、真实候选5/5、输出语义14+1补测及配置16复用见[TR R05](../reports/tests/TR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R05.md)。用户要求等待明确批准才部署/发布v4，staging仍e3fc，production G8 No-Go。

2026-10-29 统一 Agent 与多店授权发布现场结论为 PARTIAL：精确 staging 发布、041、12 容器、固定出口与12项公网/缓存检查通过，已登录工具目录及原店铺/渠道/工作台只读回归通过；两个实际 Agent 请求仍无已接受业务回答，文件 RAG 未测。局部180项及组合2394/3、前端52/134的源身份和复用保持 R02，不冒充本轮重跑全量。详见[TR R03](../reports/tests/TR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R03.md)。

2026-10-29 [TikTok 多店 TR R02](../reports/tests/TR-MVP-TIKTOK-MULTISHOP-AUTH-001-20261029-R02.md) **PASS（远端主线功能集成本地门禁）**：PR #629 从 `origin/main=7cee8b4c` 合入，功能 subject `c289a9a0`；专属隔离 PostgreSQL/pgvector 全量后端 2394 passed/3 skipped，迁移 `034→041→034→041` 通过，前端契约 52/52、生产构建浏览器 134/134，Ruff、格式、mypy、类型及构建通过。两项 GitHub CI runner 空/0 步失败，记录为未运行并按持续授权使用本地替代。真实多店 OAuth、Webhook、逐店读取和 staging 部署尚未验收；production G8 No-Go。

2026-10-29 [TR R21](../reports/tests/TR-MVP-STAGING-LATENCY-001-20261029-R21.md) **PASS（修订后的 staging 应用侧验收）**：当前线上隔离 release 的订单私有缓存 19/19 后端测试覆盖冷/热、过期、跨店、凭证轮换、手动刷新与 429 不缓存；已登录看板两店切换后币种、咨询摘要、更新时间变化并恢复原店。连接复用、渐进回显、分段观测、401/503/429 合成恢复与发布安全门禁引用此前精确源码及 release 记录。用户放宽网络异常时的公网绝对阈值，WAN 重传/隧道抖动和秒级等待仍是风险；不宣称全站用户可见稳定提速、真实故障注入或 production 放行。

2026-10-29 [TR R20](../reports/tests/TR-MVP-STAGING-LATENCY-001-20261029-R20.md) **PARTIAL（看板局部发布通过）**：主线 [PR #623](https://github.com/CP11-gh/CRM/pull/623) 源码已从实际运行的性能专用 release 单独摘取并部署 staging，仅更新前端；隔离 release 的 129/129 生产浏览器、51/51 契约、类型/构建、私有备份、精确摘要、ValidateOnly/Deploy、12 容器、固定出口及安全开关通过。三健康和四页面公网 HTTP 200，已登录看板只读显示授权店铺名称与指标。两项 PR CI 作业均 0 steps，按已批准本地替代门禁记录；单次公网 TTFB、浏览器工具墙钟都不能证明提速，真实冷热、跨店、401、429/失败和全站对照仍待验。见[低敏证据](../../release/evidence/staging/crm-staging-dashboard-authorized-20261029.json)。

2026-10-29 [TR R19](../reports/tests/TR-MVP-STAGING-LATENCY-001-20261029-R19.md) **PARTIAL（看板授权店铺先回显源码）**：店铺名称延迟时指标先回显的合成用例先红后绿，生产浏览器 133/133、契约 51/51、类型/构建通过，lint 0 error/8 既有 warning。尚未发布到 staging，实际冷/热和跨店/故障耗时仍待测。

2026-10-29 [TR R18](../reports/tests/TR-MVP-STAGING-LATENCY-001-20261029-R18.md) **PARTIAL（欢迎语已登录补测）**：R17 首次浏览器工具超时后，重新绑定同一 staging 页面，完整页面状态显示既有欢迎语策略及“仅配置状态，不自动发送”。仅只读浏览，没有页面回显计时或平台写入；真实冷热、跨店与异常/限流及整体提速仍待验。

2026-10-29 [TR R17](../reports/tests/TR-MVP-STAGING-LATENCY-001-20261029-R17.md) **PARTIAL（基础接待局部发布通过）**：隔离 release `82e9fd83` 仅摘取两组件和浏览器测试，前端生产浏览器128/128、契约51/51、类型/构建通过；镜像精确摘要、私有备份、ValidateOnly/Deploy、12容器、迁移头、固定出口和原安全开关通过。公网三健康及三接待路由200；已登录快捷回复与超时页只读回显，欢迎语浏览器工具超时。整体用户可见提速、跨店与真实异常仍未验，见[低敏证据](../../release/evidence/staging/crm-staging-reception-progressive-20261029.json)。

2026-10-29 [TR R16](../reports/tests/TR-MVP-STAGING-LATENCY-001-20261029-R16.md) **PARTIAL（基础接待渐进回显源码验证）**：延迟店铺名称的浏览器用例先红后绿，最终 132/132 生产浏览器、51/51 契约、类型与构建通过，lint 0 error/8 既有 warning。只读 30 次健康分段显示业务机回环 p50/p95 约 0.6/1.1 毫秒、入口隧道 446/1170 毫秒、公网 787/1760 毫秒；非配对请求不可相减。源码尚未发布，真实用户回显与全站冷热/跨店/失败限流仍未验。

2026-10-29 [TR R15](../reports/tests/TR-MVP-STAGING-LATENCY-001-20261029-R15.md) **PARTIAL（已登录订单 UI 有限补测）**：性能专用 release `eb0eedc7` 下，一个已有已送达订单的会话只读回显“售后买家”及订单、物流、商品、付款详情；另一无订单会话显示“售前买家”和空订单提示。两会话属于同一测试店铺，详情已预先打开；浏览器绑定及截图接口耗时不能当作页面加载耗时。真实跨店、冷/热回显、并发 401、429/失败与可归因的整体提速仍待验。R14 发布门禁与合成回归结论不变。

2026-10-29 [TR R14](../reports/tests/TR-MVP-STAGING-LATENCY-001-20261029-R14.md) **PARTIAL（订单限流重试局部发布通过）**：主线 [PR #612](https://github.com/CP11-gh/CRM/pull/612) 已合并，性能专用 release `eb0eedc7` 仅改前端详情组件与浏览器测试，51/51 契约、50/50 生产工作台浏览器、类型及构建通过，lint 0 error/8 既有 warning。最终 PR head 的 GitHub 两作业 runner 空/0 steps 失败，CI 未运行，按已批准本地替代门禁；私有备份、精确镜像、`ValidateOnly/Deploy`、12 容器、四公网入口和原安全开关通过。详情与物流 429 恢复为合成响应验证，已登录 staging 订单 UI 工具超时记 `UI_UNAVAILABLE`；真实限流、全站冷热/跨店/并发 401 和整体提速仍待验。见[低敏证据](../../release/evidence/staging/crm-staging-order-detail-retry-20261029.json)。

2026-10-29 [TR R13](../reports/tests/TR-MVP-STAGING-LATENCY-001-20261029-R13.md) **PARTIAL（页面只读观察）**：性能专用 release `4edddffb` 下，已登录门店、看板、工作台、知识库与 Agent 管理显示对应内容；看板切换两店后币种与咨询摘要随店铺变化。入口安全日志同一窗口 134 条均 2xx；工作台会话 18 条入口 p50/p95 754/2363 ms、应用 16/124 ms，消息 17 条入口 500/1781 ms、应用 19/116 ms，相关 TikTok 分段为 0。样本非配对，不能证明用户可见提速；真实并发 401、全站冷热/跨店与买家身份、失败/429 仍待验。公网 p50/p95 在 WAN 抖动期间只作诊断。低敏聚合见[证据](../../release/evidence/staging/crm-staging-latency-readonly-pages-20261029.json)。

2026-10-29 浏览器并发认证刷新 [TR R12](../reports/tests/TR-MVP-STAGING-LATENCY-001-20261029-R12.md) **PARTIAL（隔离发布通过，全站验收未完成）**：源码候选 `eab7e2c2` 经 [PR #605](https://github.com/CP11-gh/CRM/pull/605) 合入 main `f8c3be74`；51 契约、129 生产浏览器、类型及构建通过，lint 0 error/8 既有 warning。GitHub CI run 40744490193 两作业均 runner 空/0 steps 失败，不计通过，采用项目已批准本地替代门禁。专用 staging release `4edddffb` 只更新前端，51/51 契约、125/125 生产浏览器、私有备份、精确镜像、`ValidateOnly/Deploy`、12 容器及已登录门店/渠道只读核对通过，后端和动态 Agent 均未变。迟到只读订单 POST 不再启动第二次刷新由合成回归验证；真实会话并发 401、全站冷热/跨店/故障/限流和用户可见回显仍未实测。公网 p50/p95 在 WAN 抖动期间仅作诊断。见[低敏证据](../../release/evidence/staging/crm-staging-browser-refresh-20261029.json)。

2026-10-28 数据看板渐进回显 [TR R07](../reports/tests/TR-MVP-STAGING-LATENCY-001-20261028-R07.md) **PARTIAL（局部发布通过）**：主线候选 `fe627e4f` 已由 [PR #597](https://github.com/CP11-gh/CRM/pull/597) 合入 main `f440fb64`，类型/构建、48 契约、125 生产浏览器通过，lint 0 error/8 既有 warning；该 PR 的 CI run 40718646905 两作业均 runner 空/0 步骤失败，不计通过，按已批准本地替代门禁记录；慢趋势/预警与预警 503 回归确认核心指标独立回显且不伪装零。独立 staging release `f9bfc109` 对应 48/121，通过精确镜像、私有备份、ValidateOnly/Deploy、12 容器、公网四路径和已登录默认店铺看板只读核对。已登录跨店切换工具超时，现场结果仍缺；公网 `/dashboard` 单次 TTFB 6.476 秒，不能宣称整体提速。动态 Agent、后端和人工发送边界未变；完整冷热、跨店、失败/限流验收仍待完成。见 [低敏证据](../../release/evidence/staging/crm-staging-dashboard-progressive-20261028.json)。

2026-10-28 基础接待并行启动 [TR R06](../reports/tests/TR-MVP-STAGING-LATENCY-001-20261028-R06.md) **PARTIAL（局部发布通过）**：主线候选 `ef4beff3` 类型/构建、48 契约、123 生产浏览器通过，源码 [PR #595](https://github.com/CP11-gh/CRM/pull/595) 已合入 main `b84cbb6d`；该 PR 两项 GitHub CI 均是 runner 空/0 步骤失败，不计通过，采用项目已批准的本地替代门禁。专用 staging release `97ac71ef` 对应 48/119，通过私有备份、ValidateOnly/Deploy、12 容器、公网 6 路径及已登录三页面只读核对。第一次部署因空 GHCR 凭据停止于拉镜像，旧前端未切换，重试成功并注销临时凭据。公网/隧道等待仍主导，不将公网 p50/p95 作为该应用改动的绝对阈值；同条件真实回显及全站冷热/跨店/失败限流验收仍缺。动态 Agent 未部署，安全开关保持。见 [低敏证据](../../release/evidence/staging/crm-staging-reception-bootstrap-20261028.json)。

2026-10-28 工作台并行刷新 [TR R05](../reports/tests/TR-MVP-STAGING-LATENCY-001-20261028-R05.md) **PARTIAL**：主线候选 `921e3c05` 类型/生产构建、48 契约、122 生产浏览器通过；独立 staging release `9d6ccc20` 仅摘取同一前端修复，私有备份、ValidateOnly/Deploy、12 容器及只读 UI 通过。公网 30 次健康 TTFB p50/p95 2.678/5.601 秒，入口近 90 条同路由有 1 条 504；不能宣称全站速度改善。Agent 新版本未部署，单店人工发送范围保持。见[低敏证据](../../release/evidence/staging/crm-staging-workspace-refresh-20261028.json)。

2026-10-28 Agent工具扩展本地候选 [TR R03](../reports/tests/TR-MVP-AGENT-TOOL-SUITE-001-20261028-R03.md) **PASS（本地范围）**：subject `01975ab2471adfe2a704116367c34d27415a3240`，应用/测试树同84702，复用2375后端/隔离PostgreSQL通过、3项平台跳过；当前入口增量38/3通过；121生产浏览器、48契约、Ruff/mypy252源文件、040迁移往返、16动态协议/237安全样本通过。十二工具、六类目录、内部协作及依据修正已审查闭环。未部署、未真实模型/TikTok联合验收；不改变G5/G6/G8现场结论。

2026-10-28 staging 入口分段日志 [TR R04](../reports/tests/TR-MVP-STAGING-LATENCY-001-20261028-R04.md) **PARTIAL**：Nginx 候选隔离语法、原配置私有备份、首次回滚与第二次重载、健康 200、数值 `Server-Timing` 日志验证通过；应用镜像未变。30 次公网健康 TTFB p50/p95 1.750/5.189 秒，入口总耗时 171/1175 毫秒，应用 1/2 毫秒。工作台和设置页样本显示网络/隧道等待明显大于应用处理，但后两页样本不足完整验收。见[低敏证据](../../release/evidence/staging/crm-staging-server-timing-20261028.json)。

2026-10-28 staging 入口连接复用 [TR R03](../reports/tests/TR-MVP-STAGING-LATENCY-001-20261028-R03.md) **PARTIAL**：原活动 vhost 私有备份、源码哈希、独立 20 组对照、`nginx -t`/reload 与健康/安全/缓存只读回归通过；活动入口回环 30 次 p50/p95 `1.042/2.061` → `0.400/1.161` 秒，公网 30 次 `1.564/4.002` → `1.742/4.028` 秒，未证实公网整体改善。两机广域网重传仍显著，前后端镜像和 Agent 不变，未外发或发布 production。见[低敏证据](../../release/evidence/staging/crm-staging-nginx-keepalive-20261028.json)。

2026-10-28 staging 性能专用发布 [TR R02](../reports/tests/TR-MVP-STAGING-LATENCY-001-20261028-R02.md) **PARTIAL（部署通过，公网性能未达完整验收）**：release `e64ef52c` 的后端 2407/43、前端合同 48/48、静态门禁和 Docker 构建通过；私有备份、六摘要、ValidateOnly/Deploy、12 容器、固定出口与已登录订单只读 UI 通过。指纹 JS 冷 MISS 1.728 秒、热 HIT 0.000 秒；20 样本公网健康 TTFB p50/p95 前后为 1.782/9.108 和 2.472/4.819 秒，非受控对照，不声称因果改善。动态 Agent 未部署，生产 No-Go。见[低敏证据](../../release/evidence/staging/crm-staging-latency-performance-only-20261028.json)。

2026-10-28 动态Agent本地候选 [TR](../reports/tests/TR-MVP-AGENT-DYNAMIC-REWRITE-001-20261028-R01.md) **PASS（本地范围）**：subject `7594a1a53ede8e0b65f8987e352d78662bb04c41`；完整后端/隔离PostgreSQL-pgvector 2335 passed / 3 POSIX平台条件跳过，前端48契约/114生产浏览器、typecheck/build、Ruff/mypy245文件、迁移034↔039、16动态边界与237安全样本通过。依赖审计无已知漏洞，两轴审查无剩余阻断。已移除旧FAQ执行/正则与LangGraph依赖；asyncio项目编排＋langchain-core @tool。没有部署或真实模型/TikTok现场验收，G5/G6/G8现场结论不变。

2026-10-28 订单详情 UI [TR R02](../reports/tests/TR-MVP-WORKSPACE-ORDER-DETAIL-UI-001-20261028-R02.md) staging 范围 **PASS**：合并主线 `0e4100b2` 前端类型/构建、契约 48/48、生产浏览器 113/113；手动私有备份、`ValidateOnly`/`Deploy`、12 容器、迁移头 034、四个公网路径 200。已登录真实订单电话、完整地址、规格、卖家 SKU 可见，物流默认 2 条、展开 8 条；不记录买家具体值。后端与 Agent 模式保持，无真实外发、退款或 production 发布。见[低敏证据](../../release/evidence/staging/crm-staging-order-detail-redeploy-20261028.json)。

2026-10-28 Agent 调试工具加知识 [TR R08](../reports/tests/TR-MVP-AGENT-DEBUG-ANSWER-001-20261028-R08.md) **PASS**：`main=5f0feb7f` 的后端 `sha256:6d50f5dd…f7a20` 手动部署 staging，来源、私有备份、迁移头和健康检查通过。TikTok US 店铺同一审批绑定合成文件的纯知识 trace `ae1d5d67` 显示七天回答与引用；授权会话物流加知识 trace `35c0f2fd` 同时显示已送达、七天规则、`query_logistics:succeeded` 与文件引用，两条均为 `succeeded / human_review`。测试后 Agent 已保存解绑且文件软删除；无平台发送。原本地隔离数据库 2460 passed/3 skipped，237 样本安全评测通过。GitHub #573 两作业零步骤失败，经用户仅本 PR 批准本地替代。知识库旧文案仍误称文档检索未接入，另行修正；production G8 No-Go。

2026-10-28 Agent 调试文件知识格式修复候选 [TR R07](../reports/tests/TR-MVP-AGENT-DEBUG-ANSWER-001-20261028-R07.md) 综合 `PARTIAL`：已部署主线 `30b29c96` 的纯知识回答在 staging 显示七天事实与文件引用，混合物流加知识问题因模型输出 `answer:other` 未显示建议。新 subject `c63421fa` 仅将绑定文件调试草稿温度固定为 0；隔离 PostgreSQL/pgvector 全套 2460 passed/3 skipped，Ruff、mypy、锁文件和 237 样本确定性安全评测通过，受控真实模型格式探针 3/3 有效。本 subject 尚未部署，完整同轮链路需 staging 复测；按用户要求保留同一测试文件至成功后统一清理，零平台发送，production No-Go。

2026-10-28 Agent 调试知识输出候选 [TR R06](../reports/tests/TR-MVP-AGENT-DEBUG-ANSWER-001-20261028-R06.md) 综合 `PARTIAL`：subject `d368b529` 的隔离 PostgreSQL/pgvector 全套 2460 passed/3 skipped，Ruff、mypy、锁文件及 237 样本确定性安全评测通过。主线 `8096728f` 已手动部署 staging，但保留的文件知识单问 trace `4bb7170b` 在独立复核前因草稿两个逗号被位置 DLP 低置信拒绝；新候选通过严格输出 Schema 的受控 DeepSeek 单次探针，完整 Agent 工具加知识现场链路仍待新版本部署验证。保留唯一合成文件的审批与绑定直至成功后统一清理；零平台发送，production No-Go。

2026-10-27 Agent 调试知识候选 [TR R05](../reports/tests/TR-MVP-AGENT-DEBUG-ANSWER-001-20261027-R05.md) 综合 `PARTIAL`：最终 subject `b55847f8` 的隔离 PostgreSQL/pgvector 全套 2459 passed/3 skipped，Ruff、mypy 和锁文件检查通过。当前 staging 主线物流单问的真实只读工具和模型回答通过，混合与知识单问检索命中后仍被模型 Schema 或 Prompt DLP 拒绝；R04 修复候选尚未部署现场验证。按用户要求，同一份合成文件保持审批与绑定直至完整验收后统一清理；零平台发送，production No-Go。

2026-10-27 Agent 调试物流轨迹 [TR R04](../reports/tests/TR-MVP-AGENT-DEBUG-ANSWER-001-20261027-R04.md) 综合 `PARTIAL`：用户仅对 PR #569 批准本地 2455 passed/3 skipped 替代零步骤 CI，合并主线并手动部署 staging 后，已登录 TikTok US 店铺的只读物流工具读到官方 `delivered` 轨迹，页面显示模型“已送达”建议；但工具加已审批绑定知识同轮仅显示固定物流提示，无知识引用，知识复核失败。合成文档已撤销审批、解绑并软删除；无平台发送，production No-Go。

2026-10-26 Agent 真实调试 [TR R01](../reports/tests/TR-MVP-AGENT-LIVE-DEBUG-001-20261026-R01.md) 综合 `PARTIAL`：subject `9302bb6d` 的隔离 PostgreSQL 完整回归 2426 passed/3 skipped、前端契约 48/48、生产浏览器 113/113、静态检查/构建及迁移 034 通过；staging 手动备份、`ValidateOnly`/`Deploy`、健康与独立调试开关通过。TikTok US 测试店铺的真实 DeepSeek 请求 `succeeded`、审计 1 条，未选买家会话或发送平台消息。该店零文件/零订单，绑定文件命中和成功工具返回仍待现场样本；见[低敏证据](../../release/evidence/staging/crm-staging-agent-live-debug-20261026.json)。GitHub Actions 未运行，production No-Go。
2026-10-26 订单详情 UI 候选 [TR R01](../reports/tests/TR-MVP-WORKSPACE-ORDER-DETAIL-UI-001-20261026-R01.md) 本地范围 `PASS`：候选 SHA 后端 2374 passed/43 skipped、前端生产浏览器 113/113、契约 48/48、类型与构建通过；受影响后端定向 69 passed。首轮 Windows 镜像预取用例曾因 30 秒子进程超时失败，候选全套重跑通过。staging 尚未部署本候选，真实平台收件字段是否脱敏待现场核对；无真实外发或 production 发布。

2026-10-26 浏览器反馈任务 [TR R02](../reports/tests/TR-MVP-STAGING-BROWSER-FEEDBACK-002-20261026-R02.md) 在前端源码及限定 staging 部署范围 `PASS`：生产浏览器 113/113、契约 48/48、类型/构建通过，lint 0 error/8 warning；手动 `ValidateOnly`/`Deploy`、12 容器、迁移 033、公网健康与已登录订单/菜单只读核对通过。GitHub Actions 零步骤失败未计入；没有真实消息或退款，production No-Go。见[低敏证据](../../release/evidence/staging/crm-staging-browser-feedback-20261026.json)。

2026-10-25 知识库与跨店铺页面一致性 [TR R02](../reports/tests/TR-MVP-STORE-VIEW-CONSISTENCY-001-20261025-R02.md) 在源码和 staging 部署范围为 `PASS`：本地后端 2398 passed/3 skipped、前端契约 48/48、生产浏览器 108/108、迁移 032 升降级及类型/构建/格式通过；手动 staging 备份、ValidateOnly/Deploy、迁移 032、12 容器、固定出口、公网健康及主页面 200 通过。Actions 零步骤失败不计 CI，已登录 UI 工具超时，真实店铺点击未验证；production No-Go。见[低敏证据](../../release/evidence/staging/crm-staging-store-view-consistency-20261025.json)。
2026-10-23 合并主线 `db16111d` 的接待与工作台四项任务在限定 staging 范围为 `PASS`：本地完整后端 2351 passed/42 skipped、前端契约 48 passed、生产浏览器 101 passed/1 skipped，Ruff/格式/mypy/typecheck/lint（0 error/7 warning）/build 通过。手动 staging `ValidateOnly`、`Deploy`、迁移 031、12 容器、三健康和四个产品页面 200；已登录页面核对导航、现有超时策略、欢迎语表单及工作台新控件。见[四任务现场证据](../../release/evidence/staging/crm-staging-direct-reception-workspace-20261023.json)及各任务最新版 TR。未运行 GitHub Actions，原作业因账户付款/额度零步骤结束；未新增真实欢迎策略、未向真实买家测试外发，production No-Go。

本文件只汇总当前仍有效的正式结论。历史报告用于追溯，不代表本分支重新运行。生产是否可放行以 `../operations/RELEASE-GATES.md` 为准。

2026-10-23 知识库“全部知识”分类一致性 [TR R01](../reports/tests/TR-MVP-KNOWLEDGE-ALL-CONSISTENCY-001-20261023-R01.md) 为限定范围 `PASS`：subject `662da11e` 后端完整 2380 passed/3 skipped、前端契约 48/48、生产浏览器 87/87，Ruff/format/mypy/typecheck/build 通过，lint 0 error/5 既有 warning。源码经 PR #546 合并后，staging 手动门禁、精确镜像摘要、公网知识库和 API 健康 200；真实认证 API 确认 11 个未分类旧文件在默认列表保留，在新分类筛选下 total 0，与有效分类 0 一致。GitHub Actions 零步骤失败不计 CI；真实登录页面未直接点击，production G8 No-Go。见[低敏证据](../../release/evidence/staging/crm-staging-knowledge-all-category-20261023.json)。

2026-10-23 通用 RAG 文档入口 subject `5ae37c54` 已在隔离 PostgreSQL 与 staging 合成店铺完成全流程：后端 2379 passed/3 skipped，前端契约 48/48、Next.js 16.4.2 生产浏览器 85/85、Ruff/format、类型检查与构建通过；lint 0 error/5 条既有 warning，生产依赖审计 0 漏洞。staging 精确摘要部署、唯一迁移头 `030_merge_rag_reception`、12 容器、五个公网入口及真实 API/Worker/MinerU/BGE-M3/pgvector 流程通过。原生 PDF 与 Office 就绪，图片和混合页整版本待复核且零新向量，人工修订后整版入库，同名显式替换保留旧版本。长 PDF 选用固定 Token 32/4 后实得 19 块、最大 32 Token。详细命令、前端浏览器与构建、限制见 [本任务 TR](../reports/tests/TR-MVP-RAG-DOCUMENT-INGEST-001-20261023-R01.md) 和[低敏现场证据](../../release/evidence/staging/crm-staging-rag-document-ingestion-20261023.json)。通用文档检索/Rerank 与 production 不在本次放行范围。
2026-10-23 基础接待交互跟进 [TR R01](../reports/tests/TR-MVP-MARKETING-BASIC-RECEPTION-UI-002-20261023-R01.md) 为源码候选 `PARTIAL`：subject `c7843608` 的隔离 PostgreSQL 迁移 029 升/降/升、后端 2294 passed/3 skipped、前端契约 48/48、生产浏览器 83/83、Ruff/format/mypy/typecheck/build 通过；lint 0 error/5 条既有 warning。停用分组在默认回复查询中不可选，管理查询仍可查看编辑。尚未合并或部署 staging，真实店铺页面未写入，未向买家发送消息；production No-Go。

2026-10-23 基础接待 [TR R02](../reports/tests/TR-MVP-MARKETING-BASIC-RECEPTION-001-20261023-R02.md) 为限定范围 `PASS`：subject `439c50c` 的隔离 PostgreSQL 全量 2294 passed/3 skipped、前端契约 48/48、生产浏览器 81/81、Ruff/format/mypy/lint/typecheck/build 与迁移 028 升降级通过；lint 0 error/5 条既有 warning。源码 PR #539 已合入主线；直接 staging 的六角色预取、私有备份、`ValidateOnly`、精确摘要 `Deploy`、迁移头 028、11 容器、固定出口与六个公网路径均通过。已登录浏览器核对智能营销侧栏三入口和相应页面，超时及欢迎页明确提示自动发送关闭。未创建真实策略配置或向买家发送消息；production No-Go。详见[低敏现场证据](../../release/evidence/staging/crm-staging-basic-reception-20261023.json)。

2026-10-23 知识库侧栏和删除确认弹窗 [TR R02](../reports/tests/TR-MVP-KNOWLEDGE-SIDEBAR-DIALOG-001-20261023-R02.md) 为限定范围 `PASS`：subject `f7950619` 本地生产构建、48/48 合同、66 passed/1 skipped 浏览器，lint 0 error/5 既有 warning；staging 六角色预取、私有备份、ValidateOnly、精确摘要 Deploy、11 容器及四公网健康通过。已部署页面合成浏览器确认整块层级侧栏消失、站内删除弹窗与取消零 DELETE；10 个指纹资源 200 immutable。真实登录态和真实删除未测，Agent/后端/检索不变；Actions 零步骤失败不计 CI，production No-Go。详见[低敏部署证据](../../release/evidence/staging/crm-staging-knowledge-sidebar-dialog-20261023.json)。

2026-10-23 知识库分类 UI staging 部署 [TR R01](../reports/tests/TR-MVP-KNOWLEDGE-CATEGORY-DELETE-DEPLOY-001-20261023-R01.md) 为限定范围 `PASS`：主线 `2ccc93b2` 前端契约 48/48、typecheck、Docker 生产构建通过，lint 0 error/5 既有 warning；现场六镜像角色预取、`ValidateOnly`、私有可读备份及 `Deploy` 通过，运行精确摘要、11 容器、迁移头与四公网入口均核对。已部署页面的新增自定义分类及确认删除 2/2 合成浏览器通过，所有 `/v1/` 请求被本地代理阻断并在浏览器内模拟，未修改真实分类；真实授权店铺页面尚未直接验收。镜像发布工作流 `39881715896` 与证据 PR 的 CI `39884114716`、`39884553653` 均零步骤失败，不计 CI 通过；production No-Go。

2026-10-22 知识库原型 UI [TR R01](../reports/tests/TR-MVP-KNOWLEDGE-PROTOTYPE-UI-001-20261022-R01.md) 记录 subject `64e41b62` 的前端契约 48/48、生产浏览器 64/64、typecheck/build 通过，lint 0 error、5 条既有 warning。PR #528 已合入 `main=ddeb3018`；GitHub Actions 两作业均零步骤失败，不计作 CI 通过；本地合成浏览器数据不等于 staging 真实登录态验收。Agent 管理页源文件未修改，未部署 staging 或 production。

2026-10-22 员工账号与部门 [TR R04](../reports/tests/TR-MVP-SETTINGS-TEAM-ACCOUNTS-002-20261022-R04.md) 为 `PARTIAL`：subject `6bf4177d` 的角色兼容回归先红后绿，后端 2244 passed/30 skipped、Ruff/mypy、前端 typecheck/build/47 契约通过。PR #522 合入后手动 staging 门禁、真实数据读路径及健康检查通过；用户刷新真实登录态的“账号”和“部门”页后回复“两页都正常”，原“系统内部错误”已消失。GitHub Actions 零步骤失败不计 CI；账号／邮箱实际登录及账号写操作待验，production 未放行。

## 模块状态

2026-10-22 订单卡长 SKU 货号 [TR R03](../reports/tests/TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-SELLER-SKU-001-20261022-R03.md) 为 `PASS`：subject `f512fb8a` 的合成浏览器用例先复现 `false !== true`，改为换行后本地生产浏览器 59/59、前端契约 47/47、typecheck/build 通过，lint 0 error/5 warning。源码 PR #512 合入后，前端通过手动门禁部署 staging，运行摘要、11 服务、四公网健康入口与部署页合成浏览器 3/3 通过；用户刷新真实订单卡后回复“两项都正常”，确认完整换行显示与复制。无买家外发，production G8 No-Go。

2026-10-22 原生物流卡片 [TR R06](../reports/tests/TR-MVP-WORKSPACE-TRACKING-TIMELINE-001-20261022-R06.md) 为 `PASS`：subject `97c5d6bb` 的后端 2233 passed/29 skipped，前端契约 47 passed、生产合成浏览器 27 passed，Ruff/格式/mypy/typecheck/build 通过；合并主线的前后端经手动门禁部署 staging，运行摘要、11 服务与四公网健康入口通过。用户刷新真实登录态会话后回复“两项都正常”，确认发送栏卡片和同一物流详情弹窗；后续前端更新的部署页面卡片定向合成浏览器 2/2。Codex 页面读取仍 `UI_UNAVAILABLE`；未向真实买家发送卡片，TikTok 实际接收未测试，production G8 No-Go。

2026-10-21 客户侧栏长商品规格修复的[TR R02](../reports/tests/TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-VARIANT-001-20261021-R02.md) 为 `PASS`：subject `64aefa12` 的前端契约 47/47、生产浏览器 54/54、类型与构建通过，lint 0 error/4 条既有 warning；旧 staging 上长规格回归先失败，合入 `main=5e11f7b6` 手动发布后已部署页面定向合成浏览器 2/2、六摘要与四个公网健康通过。真实登录态浏览器工具超时，但用户刷新原订单卡后回复“修复好了”，确认规格在原位置不再只剩省略号；GitHub Actions 零步骤失败不计 CI 通过，production G8 No-Go。

2026-10-21 工作台物流翻译显示的 [TR R04](../reports/tests/TR-MVP-WORKSPACE-BROWSER-COMMENTS-001-20261021-R04.md) 为 `PASS`：subject `ef0ec3aa` 的前端契约 47/47、类型、lint（0 error、4 个既有 warning）、生产构建与定向浏览器 2/2；合入 `main=f98dca4e` 手动 staging 发布、六摘要预取、11 服务和四个公网健康入口通过，已部署页面定向合成浏览器 2/2，用户确认译文原位替换及切回原文。GitHub Actions 两作业零步骤失败不计 CI 通过；production G8 No-Go。

2026-10-21 工作台物流状态中文修正历史[源码 TR R03](../reports/tests/TR-MVP-WORKSPACE-BROWSER-COMMENTS-001-20261021-R03.md)为 `PARTIAL`：最终源码 `f951e294` 上后端 2223 passed/29 skipped，前端契约 47/47、生产构建与浏览器 52/52，Ruff/格式/mypy/typecheck 通过。此前用户真实截图证实旧版状态英文回退；新版本尚未部署 staging，真实按需翻译未调用。无买家外发，production No-Go。

2026-10-21 工作台十条浏览器注释的[staging R02 TR](../reports/tests/TR-MVP-WORKSPACE-BROWSER-COMMENTS-001-20261021-R02.md) 为 `PARTIAL`：最终源码完整后端 2221 passed/3 skipped，本地生产浏览器 49/49；手动发布合并主线 `5d5f532c` 后六摘要预取、validate/deploy、11 服务、迁移头与三公网健康 200 通过，已部署页面合成浏览器 18/18。真实已登录页面工具 `UI_UNAVAILABLE`；用户截图确认“物流状态”英文回退，任务返修中。修正源码 `f951e294` 上后端 2223 passed/29 skipped、前端契约 47/47 与生产浏览器 52/52；新版本尚未部署。无买家外发，production No-Go。

2026-10-21 工作台十条浏览器注释的[源码 TR](../reports/tests/TR-MVP-WORKSPACE-BROWSER-COMMENTS-001-20261021-R01.md) 为 `PARTIAL`：最终源码 `97543047` 上后端定向 6/6、前端契约 47/47、生产构建及合成浏览器 49/49 通过；完整后端套件在最终提交前为 2222 passed/3 skipped。staging 手动发布和真实登录态核对尚待执行；无买家外发，production No-Go。

2026-10-21 客户侧栏真实字段源码 [PR #488](https://github.com/CP11-gh/CRM/pull/488) 与物流卡片 [PR #489](https://github.com/CP11-gh/CRM/pull/489) 已合入主线并手动部署 staging。[部署 R03 TR](../reports/tests/TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-DEPLOY-001-20261021-R03.md) 为 `PASS`：R02 手动门禁、固定出口、11 服务及三公网健康通过；用户已登录截图显示真实订单字段、展开 SKU/库存及优惠券金额/状态/领取截止。浏览器自动化 `UI_UNAVAILABLE`，截图未入仓；未覆盖每一种物流状态，无外发或高风险写入，production No-Go。

2026-10-21 客户侧栏字段修正[源码 TR](../reports/tests/TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-FIELDS-001-20261021-R01.md)为本地 `PASS`：后端 2220 passed/3 skipped、Ruff/格式/mypy 通过，前端契约 47/47、生产构建及合成浏览器受影响交互通过。订单支付时间只取真实字段；商品与优惠券状态、金额已格式化。此处仅为源码验证；staging 已手动部署，真实页面验收状态见部署 TR R02。合成截图不充当现场证据；无买家外发，production No-Go。
2026-10-21 客户订单详情 [R03 TR](../reports/tests/TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-DETAILS-001-20261021-R03.md) 为 `PASS`：R02 官方同单字段和跨买家 404、手动 staging 门禁、合成浏览器 3/3 保留；用户在更新后已登录订单卡截图确认付款方式、承运商及最新物流描述和时间。当前 backend/frontend revision 分别为 `15ceabf8`、`4f32c04e`；浏览器自动化超时仍记 `UI_UNAVAILABLE`，截图不入仓。production G8 No-Go。

2026-10-21 客户侧栏物流卡片 [R02 TR](../reports/tests/TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-LOGISTICS-001-20261021-R02.md) 为 `PASS`：R01 前端契约 47/47、生产构建及最终受影响浏览器 2/2；从合并主线手动发布 staging 前端，六摘要预取、validate/deploy、迁移头、固定出口和三公网健康 200 通过。用户已登录真实订单截图显示买家实付金额、已送达状态、单号、USPS、最新描述与时间；内置浏览器自动化超时 `UI_UNAVAILABLE`，截图未入仓。其他物流状态的真实订单未逐一实测，生产 G8 No-Go。


2026-10-21 TikTok 零订单侧栏修复[现场 TR](../reports/tests/TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-EMPTY-001-20261021-R02.md)为 `PASS`：源码提交后端 2217 passed/29 skipped；staging 手动发布及三健康、固定出口通过，真实零订单会话返回空列表，另一会话仍返回一单，用户确认页面“暂无订单”且原 502 消失。内置浏览器自动化不可用，用户确认作为页面证据；无买家外发，production No-Go。

2026-10-21 客户侧栏订单详情 [TR R02](../reports/tests/TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-DETAILS-001-20261021-R02.md) 为 `PARTIAL`：源码已合入 main 并手动更新 staging，六摘要预取、validate/deploy、11 容器、三公网健康 200、固定出口通过；官方只读详情四类字段存在，跨买家请求 404，已部署页面合成浏览器订单/商品/优惠券 3/3。真实登录态侧栏仍 `UI_UNAVAILABLE`，因此未完成视觉验收；无买家外发或 production 放行。下方较早“尚未部署”段落仅为当时快照。

2026-10-21 发送栏侧边语言菜单源码候选 `ac46e7a4461a3c41588f321f31eed6f0c59c52ff` 的[TR](../reports/tests/TR-MVP-WORKSPACE-COMPOSER-FLYOUT-001-20261021-R01.md)为本地 PASS：lint 0 错误/4 个既有 warning、类型通过、前端契约 47/47、webpack 生产构建及生产浏览器 43/43 通过；合成桌面截图与 375px 菜单边界核对通过。staging 页面仍待独立部署验收；无 TikTok 外发，production No-Go。

2026-10-21 历史客户侧栏订单关联验收：[源码 TR](../reports/tests/TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-ORDERS-001-20261021-R01.md)本地 PASS，隔离 PostgreSQL 2232 passed/3 skipped、前端契约 47/47、生产浏览器 42/42，Ruff/mypy/webpack 通过。staging 从合并主线 `433f340d` 手动发布，门禁和健康通过；服务层真实只读核对 1 笔订单、金额/商品/物流及授权隔离、商品 27 件、券 19 张。当前已部署前端的合成客户侧栏浏览器交互 2/2 通过；浏览器工具连续超时，已登录侧栏页面仍待截图核对，部署任务保持 VERIFYING，不把合成页面或服务层结果冒充真实 UI 验收。无外发，production No-Go。

2026-10-20 客户侧栏源码候选 [TR](../reports/tests/TR-MVP-WORKSPACE-CUSTOMER-SIDEBAR-001-20261020-R01.md) 为本地 `PASS`：隔离 PostgreSQL 2226 passed/3 skipped、前端契约 47/47、生产模式合成浏览器 42/42，Ruff/格式/mypy 和 webpack 生产构建通过。staging 当前唯一 TikTok 渠道只读核对为已连接且具备 Product Basic 与优惠券读取 Scope；新代码尚未手动部署，真实订单/商品/优惠券目录返回未验收。本次无买家外发，production No-Go；后续现场结论由独立部署 TR 记录。

2026-10-20 工作台发送栏[TR](../reports/tests/TR-MVP-WORKSPACE-COMPOSER-MENU-001-20261020-R01.md)为 `PASS`：后端 2198 passed/29 skipped，前端契约 47/47、生产浏览器 39/39，最终受影响交互 9/9；staging 手动门禁、11 容器、三健康 200 与已登录页面核对通过。合成中文草稿经现有 DeepSeek 得到一次英文译文，直接/译后两种方式都进入独立人工审阅后退出，草稿清空，无买家外发。其他 12 种目标语言仅核对选项和契约，未逐一评价真实译文；production No-Go。GitHub Actions 零步骤失败不计为验收。

2026-10-20 工作台统一搜索与多语言人工回复：[部署 R01](../reports/tests/TR-MVP-WORKSPACE-SEARCH-TRANSLATION-DEPLOY-001-20261020-R01.md)已记录 staging 手动门禁、真实单项搜索 230→1 和六语入口；[补充 R02](../reports/tests/TR-MVP-WORKSPACE-SEARCH-TRANSLATION-DEPLOY-001-20261020-R02.md)在已登录真实授权会话中用合成中文草稿取得一次真实 DeepSeek 英语译文，并核对独立人工审阅弹窗的准确发送内容。草稿和预览已清除，本轮无 TikTok 外发；其余五语的真实译文质量与译文真实外发未单独验收，production No-Go。

2026-10-20 G8 [R01 TR](../reports/tests/TR-MVP-009-20261020-R01.md)的只读证据核对与决策流程为 `PASS`，**production 决策结果为 No-Go**。三公网健康、固定出口、现有 G3 单店开关和 11 个 CRM 容器在本次检查时正常；生产拓扑未确定、当前主线镜像/生产回滚目标未就绪，G6 旧量化稳定性失败且公网风险仅在 staging 被接受。共享网关的 SSH root/密码认证开启，需独立评审；外部失败登录尝试与 G6 故障无已证实因果。见[决策材料](../operations/G8-DECISION-20261020.md)与[低敏摘要](../../release/evidence/staging/crm-staging-g8-readiness-20261020.json)。PR #461 已合入 main；`MVP-009 DONE` 指本轮决策任务完成，production 未部署，现有 staging 范围不扩大。GitHub Actions 两作业因账户计费零步骤失败，不计为 CI 通过。

2026-10-20 G6 [R04 TR](../reports/tests/TR-MVP-007-20261020-R04.md)对**用户明确接受风险后的当前 staging 单店人工辅助限定条件**为 `PASS`：[低敏证据](../../release/evidence/staging/crm-staging-g6-risk-accepted-20261020.json)保留前 634 槽 619 可用、15 失败、12 次告警和恢复、127 条资源样本以及本次三健康/固定出口/G3 边界复核。旧 24 小时、99.5% 目标仍 `FAIL_INCOMPLETE`，806 槽未采，公网间歇故障未定位；限定放行不是持续稳定性保证。`MVP-007 DONE`（PR #459 已合入 main）；G8/production No-Go。下方 R01～R03 为形成时的历史结论，不覆盖本次限定决策。

2026-10-20 G6 staging 缓解现场检查为[部分通过](../reports/tests/TR-MVP-007-20261020-R03.md)：反向 SSH 与出口 helper 的 `10/2` 保活生效，固定出口和三个指定公网健康接口瞬时正常，其他应用容器未重建；[低敏现场证据](../../release/evidence/staging/crm-staging-g6-ssh-mitigation-live-20261020.json)。公网 TLS 曾独立出现 2/360 次 8 秒超时，原因与持续稳定性未证实；旧轮中止记录仍失败，未开始新 24 小时验收。`MVP-007 BLOCKED`，G8/production No-Go。

2026-10-20 G6 本轮 24 小时验收因门禁数学上不可达，于 UTC 01:03:28 提前中止采集。原始连续前 634 槽为 619 可用、15 不可用，余下 806 槽未采；99.5% 门槛为 1433/1440，不能给出完整窗口通过结论。[中止证据](../../release/evidence/staging/crm-staging-g6-aborted-20261020.json)锁定原件摘要、告警及资源覆盖；原采集脚本与 72 小时元数据未覆盖或回填。公网入口/反向隧道和固定出口的短暂失联正在诊断与修复；修复后的独立新窗口才可重新验收。`MVP-007` 仍 `BLOCKED`，G8/production No-Go。

2026-10-20 历史 48 小时口径（已由上方 24 小时决定取代）：截至 UTC 2026-10-19 23:08 核对原始前 517 槽，502 可用、15 不可用，超过当时最多 14 个不可用槽的门槛。第 515 槽公网 `/healthz` 单次失败，第 516 槽恢复；原因尚未证实。[低敏前缀证据](../../release/evidence/staging/crm-staging-g6-early-no-go-20261020.json)保留样本和告警摘要哈希。当时计划采集至 48 小时终点；当前截点以上方新口径为准。

2026-10-19 G6 48 小时观察中：用户将本期验收从 72 小时缩至 48 小时，沿用 UTC 14:30 已启动原件的前 2880 槽，至少 2866 槽可用；原 72 小时采集元数据和脚本保持冻结。窗口内第 4、5 槽已因受控固定出口故障不可用，`G6_ALERT` 与 `G6_RECOVERED` 均在原件中，见[启动证据](../../release/evidence/staging/crm-staging-g6-start-20261019.json)和[告警恢复证据](../../release/evidence/staging/crm-staging-g6-alert-recovery-20261019.json)。完整窗口及最终 IR/TR/RR 尚未形成，G6 仍 `DOING`，G8/production No-Go。

2026-10-19 G2 R08：[TR](../reports/tests/TR-MVP-003-20261019-R08.md) 为 `PASS`，只适用于用户新确认的已授权店铺 staging 正常 Webhook 链路。真实唯一订阅、28 条消息主题验签与绑定、3 条买家入站及 G3 受控双向对话沿用原件；本轮只读核对入口 38 次 HTTP 200 与数据库 38 条唯一验签事件一致。G5 临时关闭 Webhook 期间有 10 次 503、恢复后 4 次成功入库，但不能关联为同一通知重投，恢复的 4 条均非买家成功消息。真实乱序和同通知恢复亦未证实；R07 旧口径 `PARTIAL` 保留。G6/G8/production 独立阻塞。

2026-10-19 G2 R07：[TR](../reports/tests/TR-MVP-003-20261019-R07.md) 为 `PARTIAL`。已有真实受控双向对话及 3 条验签、店铺绑定、成功入站的买家 Webhook 事件；本轮只读核对 staging 运行开关和三个公网健康端点，未触发新买家测试。按用户决定，当前已授权店铺的 staging 人工辅助正常链路受限放行。官方重投、真实乱序和故障恢复没有现场证据，完整 G2、G8 与 production 仍未通过。

2026-10-19 G2 R06：[TR](../reports/tests/TR-MVP-003-20261019-R06.md) 为 `PARTIAL`。一次性 staging 503 重投探针在 subject `47b5285b` 上完成 2162 passed/27 skipped 的全量后端回归、6 项定向回归、Ruff/格式/mypy；未发布镜像或部署，受控买家稍后可用。真实官方重投、乱序和原 G3 恢复仍缺，G2/G8 不放行。

2026-10-19 G1-L：用户将当前 v0.1 验收范围改为通用 `202309` 真实轨迹成功；[R03 原始复核](../reports/tests/TR-MVP-G1-LOG-202604-001-20261019-R03.md)和[低敏证据](../../release/evidence/staging/crm-staging-g1l-generic-fedex-20261019.json)显示授权店铺一笔 FedEx 订单唯一匹配、平台码 0、轨迹 11 条。按新口径 G1-L staging 通用 API 通过；没有逐条 Seller Center 对账、没有 USPS 或 CBT 首程 `202604` 成功证据。正式通用适配器经 PR #436 合入 main、完整后端回归通过；新客户端尚未部署 staging。G2/G6/G8 与 production 仍未放行。

2026-10-19 G1-L [R02 TR](../reports/tests/TR-MVP-G1-LOG-202604-001-20261019-R02.md) 为 `BLOCKED`：用户提供当前授权店铺 Seller Center 的 CBT 筛选 0 个订单截图；一笔未确认 CBT 资格的普通 TikTok 配送候选只调用一次 `202604`，平台仍为 `11007009`。无合格首程样本，不能验证增强物流成功；不影响已关闭的 G1 核心，也不放行 G8。

2026-10-19 `MVP-006-CANCEL-001` R03：[TR](../reports/tests/TR-MVP-006-CANCEL-001-20261019-R03.md) `PASS`，范围为**新取消行为**。R02 本地 2153 passed/27 skipped/1 deselected；R104 SSH 中断后独立恢复 G3；R105 匹配镜像、50/50 身份和一次隔离断连通过，唯一 AgentRun `failed/AGENT_CANCELLED`、Redis 租约 0→1→0、G3 恢复和三健康通过。R101/R102/R103 历史合成失败记录保留；本轮未重跑 50 并发，性能仍以 R91/R92 原件为准，production No-Go。

2026-10-19 `MVP-006-CANCEL-001` R02：[TR](../reports/tests/TR-MVP-006-CANCEL-001-20261019-R02.md) `PARTIAL`。R102/R103 同 trace 断连及租约释放通过，AgentRun 审计各留一条 `running`；两次原 G3 恢复通过。AnyIO 取消作用域新增用例先红后绿；R02 手动后端回归 2153 passed、27 skipped、1 个未改动 Windows 预取超时用例排除，mypy 与定向 Ruff/格式通过。新镜像现场同 trace `failed/AGENT_CANCELLED` 尚未核对，缺陷不能标记 DONE；G5 先前安全/性能门禁仍以原始 R91/R92/R101 证据为准。

2026-10-19 `MVP-006-CANCEL-001` R01：SSE 取消后独立事务修正 AgentRun 的源码回归为 2151 passed、27 skipped、1 个既有 Windows 预取超时用例明确排除；最终定向 9 passed，Ruff、格式、mypy 和锁文件通过。仅代码测试，staging 独立数据库终态、旧遗留记录与原 G3 恢复尚待新镜像现场核对，任务 `VERIFYING`；见[R01 TR](../reports/tests/TR-MVP-006-CANCEL-001-20261019-R01.md)。

2026-10-19 工作台店铺筛选名称：[TR](../reports/tests/TR-MVP-WORKSPACE-STORE-LABEL-001-20261019-R01.md) `PASS`。修复前浏览器回归复现截断 ID，修复后名称与空列表选项稳定；合入 SHA 的 lint 0 错误、typecheck、47/47 契约测试、生产构建和 31/31 生产模式浏览器测试通过。staging 手动门禁、运行摘要、三健康 200 及已登录页面的真实名称只读复核通过。GitHub 自动作业零步骤失败，不作为本轮测试证据；production 未发布。

2026-10-19 G5 R101：[R101 TR](../reports/tests/TR-MVP-006-20261019-R101.md)记录当前 main 私有后端六摘要、临时 G5 部署、FAQ ready、50/50 隔离身份预检；独立客户端收到 `accepted` 后断开，服务端同 trace 一条提前关闭终态、无完成/超时、Redis 租约 0→1→0，随后原 G3 六摘要、单店人工发送、翻译、三健康和固定出口恢复通过。R91 的 50/50 安全输出与 R92 新严格 `<5000/<5000 ms` 口径事后复算共同满足当前 G5 staging 合成门禁；R101 没有重跑 50 并发。R100 全量后端尝试有一项未改动的 Windows 假 Docker 30 秒超时，除该项外 2146 passed/27 skipped，不写成全量通过。取消 AgentRun 留 `running` 另列缺陷；G1-L、G2、G6、G8 和 production 仍未通过。

2026-10-19 TikTok 买家昵称保留：[R02 TR](../reports/tests/TR-MVP-TIKTOK-CUSTOMER-NAME-001-20261019-R02.md) 记录缺昵称/提供昵称回归、staging Rootless 手动部署通过、运行镜像与源码一致、三个公网健康 200，以及已登录工作台标题、侧栏和列表均显示已有昵称。本次没有制造部署后新的真实通知；production 未发布。

2026-10-19 G5 R95：[R95 TR](../reports/tests/TR-MVP-006-20261019-R95.md)记录同一旧镜像的两次可恢复断连窗口：50/50 身份就绪，客户端关闭、Redis 租约 0→0；第二次延迟 15 秒观察同 trace 7 条日志仍无断连终态。两次原 G3 恢复通过。新 subject `6fe51fe` 为 Agent 完成后断开分支补固定终态事件，新增断言先红后绿；完整后端 2144 passed/27 skipped，Ruff、格式、mypy 与锁文件通过。新镜像和现场复测尚未执行，G5/production No-Go。

2026-10-18 G5 R92 当前口径：[R92 TR](../reports/tests/TR-MVP-006-20261018-R92.md)记录用户批准将首个安全 `delta` P99 改为严格 `<5000 ms`，总耗时仍严格 `<5000 ms`；完整后端 2138 passed/27 skipped，Ruff、mypy 与锁文件通过。R89/R91 原始 50 条样本的 SHA-256 已锁定，事后复算的首输出/总耗时 P99 为 3991.09/3999.42 ms 与 4812.54/4816.88 ms，当前**性能子门禁**均通过。历史 3000 ms 失败报告保留；独立断连尚未现场验收，G5/production No-Go。

2026-10-18 G5 R91 手动现场：[R91 TR](../reports/tests/TR-MVP-006-20261018-R91.md)记录 R90 后端镜像、两次可恢复窗口。首次原凭证 50/50 认证拒绝，Provider 0，先恢复 G3；第二次独占续期第 17 代后身份 50/50，单会话安全 `delta` 1811.45 ms 严格达标。50 并发 50/50 安全输出、总耗时 P99 4816.88 ms 通过；首 `delta` P99 **4812.54 ms** 仍超严格 3000 ms。认证连接获取 P99 2046 ms，首输出前指标持久化 P99 26 ms，服务端内部首输出 P99 3667 ms；独立断连仍缺。原 G3 单店人工发送、六摘要、健康和固定出口已恢复；G5/production No-Go。

2026-10-18 G5 R90 本地计时候选：[R90 TR](../reports/tests/TR-MVP-006-20261018-R90.md)给安全结果后、首个 `delta` 前原有指标写入增加 G5 专用低敏计时，SSE 顺序和普通 G3 模式保持原样。新测试先因事件缺失 1 failed/1 passed，最小实现后 2 passed；最终聚焦 8 passed、完整后端 **2138 passed/27 skipped**，Ruff、格式、mypy 和锁文件通过。尚无 R90 匹配镜像或 staging 负载，R89 的首 `delta` P99 3991.09 ms 失败仍是最新现场结论；G5/production No-Go。

2026-10-18 G5 R89 手动现场：[R89 TR](../reports/tests/TR-MVP-006-20261018-R89.md)记录 R88 镜像私有 GHCR 手动发布、临时 G5 部署、50/50 只读身份、单会话安全 `delta=2293.93 ms` 及 50 并发 50/50 安全输出。总耗时 P99 3999.42 ms 通过，首 `delta` P99 **3991.09 ms** 超严格 3000 ms；服务端内部首次输出 P99 2996 ms 不等于客户端首 `delta`。认证连接获取 P99 1422 ms，PostgreSQL `idle in transaction` 峰值 17，安全复核 P99 1648 ms；同请求数值显示多个阶段共同影响长尾，不能单独归因。原后端与 G3 单店人工发送、健康及固定出口已恢复；独立断连仍缺。G5/production No-Go。

2026-10-18 G5 R88 本地诊断候选：[R88 TR](../reports/tests/TR-MVP-006-20261018-R88.md)细分认证的令牌解析/连接获取/用户查询及上下文三段读取；先红后绿、完整后端第二轮 2136 passed/27 skipped、Ruff/格式/mypy/锁文件通过。首轮旧毫秒计时测试 1 failed，单项和完整次轮通过，已如实保留。R88 尚未发布镜像或在 staging 运行，最新现场仍为 R87 的首输出 P99 4121.54 ms 失败、原 G3 恢复；G5/production No-Go。

2026-10-18 G5 R87 手动现场：[R87 TR](../reports/tests/TR-MVP-006-20261018-R87.md)从 main `3648b3d` 的私有后端镜像临时部署，50/50 原隔离身份、唯一 ready FAQ、单会话安全 `delta` 1795.84 ms 与总 1798.38 ms 均通过；50 并发 50/50 安全 `delta`，但首输出 P99 **4121.54 ms** 超严格 3000 ms，总 P99 4127.23 ms 通过。接入 P99 1583.29 ms、认证 P99 1322 ms，FAQ 检索连接获取/查询 P99 299/290 ms；数据库活动采样脚本旧镜像断言失败，本轮无事务峰值。资源采样仅 7 点，独立断连未验收。已恢复原 G3 单店人工发送、Webhook 只读、翻译、健康与固定出口；G5/production No-Go。

2026-10-18 G5 R86 本地候选：[R86 TR](../reports/tests/TR-MVP-006-20261018-R86.md)记录 G5 `/chat/query` 认证、限流、租约和 FAQ 检索连接获取/查询数值分段。完整后端 2133 passed/27 skipped，Ruff/格式、mypy、锁文件和 237 条离线安全样本通过；未部署 R86 镜像或调用 DeepSeek。R85 的 50/50 安全输出、首输出 P99 4696.9 ms 失败和 G3 恢复仍是最新现场结论；独立断连未验收，G5/production No-Go。

2026-10-18 G5 R85 手动现场：[R85 TR](../reports/tests/TR-MVP-006-20261018-R85.md)核对 main `42d5ea2` 的私有镜像、六摘要预取与 G5 临时部署、50/50 身份及唯一 ready FAQ。单会话安全 `delta` 2004.4 ms、总 2006.8 ms；50 并发 50/50 安全输出，总耗时 P99 4699.2 ms 通过，首输出 P99 **4696.9 ms** 违反 `<3000 ms`。同步 PostgreSQL 长开事务峰值 15、接入 P99 2806.5 ms、检索 P99 1425 ms；仍需拆分连接等待和 SQL。窗口后恢复 G3 单店人工发送、Webhook 只读、翻译、健康及固定出口。独立断连未验收；G5/production No-Go。

2026-10-18 G5 R84 本地候选：[R84 TR](../reports/tests/TR-MVP-006-20261018-R84.md)的检索会话生命周期测试先失败后通过；15 项定向、完整后端 2129 passed/27 skipped、Ruff/格式、mypy、锁文件和 237 条离线安全样本通过。运行工厂使用独立短时 FAQ 检索会话，检索结束、异常或取消时释放；尚未发布 R84 镜像或复测 staging。R83 的两轮严格首输出 P99 失败仍是当前现场结论，G5/production No-Go。

2026-10-18 G5 R83 两次手动窗口：[R83 TR](../reports/tests/TR-MVP-006-20261018-R83.md)从 main `4228e0b5` 的私有后端候选出发，两轮单会话均满足严格 3 秒/5 秒门槛，50 并发均 50/50 有安全 `delta`；首 `delta` P99 6579.5/4878.8 ms，均未过 3000 ms。第一轮本地 BGE 向量等待 P99 197 ms、混合搜索端口墙钟 P99 2980 ms；第二轮同步 PostgreSQL 连接状态最高 45 条 `idle in transaction`，支持排查长开事务，尚未单独测出连接获取耗时。两轮均恢复旧后端、G3 单店人工发送、健康与固定出口；断连未独立验收，G5/production No-Go。

2026-10-18 G5 R81 只读诊断：[R81 TR](../reports/tests/TR-MVP-006-20261018-R81.md)用临时 R80 候选进程只测原隔离店铺的本地 BGE 与 FAQ SQL，DeepSeek 调用 0；空载四路 BGE 插值 P99 350.7 ms、50 路 FAQ SQL 插值 P99 93.5 ms。R80 同批 50 个匿名客户端与 Agent 低敏节点耗时关联，首安全输出同时随接入和检索长尾增加，但不能由相关性推断单一根因。运行服务未切换，G5/production No-Go。

2026-10-18 G5 R80 现场：[R80 TR](../reports/tests/TR-MVP-006-20261018-R80.md)记录手动镜像、六摘要预取、临时部署及恢复。50/50 身份和知识 ready；单会话首安全输出 2152.8 ms、总 2155.1 ms，严格门槛通过。50 并发全部 HTTP 200 且 50/50 有安全 `delta`，但首输出/总 P99 为 7287.4/7293.9 ms，严格门槛失败；检索节点 P99 3336.6 ms，零模型分阶段归因仍待完成。资源全窗口 7 点，BGE 服务未采，断连未验收。旧后端、G3 已审核单店人工发送、健康及固定出口已恢复；G5/production No-Go。

2026-10-18 G5 R79 本地候选：[R79 TR](../reports/tests/TR-MVP-006-20261018-R79.md)记录零模型调用入口探针（健康、认证、会话各 50/50 HTTP 200）、进程级模型连接池复用、仅 G5 使用 4 worker、独立复核温度 0 的确定性验证。完整后端 2126 passed/27 skipped，Ruff/mypy/lock 和 237 条离线安全样本通过；尚无新镜像或现场 G5 负载结果，R78 的 49/50 安全输出和约 6 秒 P99 仍是最新真实并发结论。G5/production No-Go。

2026-10-18 G5 R78 现场：[R78 TR](../reports/tests/TR-MVP-006-20261018-R78.md)从已合并 main `ebffdc80` 手动发布 R77 镜像并临时部署；知识 ready、50/50 隔离身份通过。单会话安全 `delta=2393.4 ms`、总 2396.0 ms，通过严格门槛；50 并发全部 HTTP 200，但仅 49 条有安全 `delta`、1 条安全转人工；首输出 P99 6021.2 ms、总 P99 6023.5 ms，门禁失败。只读 Agent 汇总无 Provider 错误；旧后端与 G3 单店人工发送、三健康和固定出口已恢复。资源仅 3 样本，断连未独立验收；G5/production No-Go。

2026-10-18 G5 R77 本地候选：[R77 TR](../reports/tests/TR-MVP-006-20261018-R77.md)针对 R76 本地 BGE 排队与独立复核声明动作错误，验证同店同题 50 路只发起一次本地向量化、逐请求本店检索、唯一候选省略重排、跨店/失败/取消边界及精确政策声明。最终 subject `55d718ff` 的完整后端 2123 passed/27 skipped，Ruff、mypy、锁文件和 237 条离线安全样本通过。该本地候选形成时尚未手动发布或现场复测；后续 R78 真实结果见上方，G5/production No-Go。

2026-10-18 G5 R76 现场：[R76 TR](../reports/tests/TR-MVP-006-20261018-R76.md)记录手动镜像/预取/临时部署、50/50 隔离身份、唯一合成 SSE 与 50 并发。单会话首安全 `delta=2371.3 ms`、总耗时 `2373.9 ms`，严格 3 秒/5 秒通过；50 并发仅 45 条有安全 `delta`、4 条安全转人工、1 条 `safety_review` 结构失败，首输出 P99 `30997.3 ms`、总 P99 `31002.0 ms`，门禁失败。零 DeepSeek 只读探针把主瓶颈定位为本地 BGE 向量化和重排排队；旧后端及 G3 单店人工发送、三公网健康和固定出口均恢复。G5/production No-Go。

2026-10-18 G5 R75 本地候选：[R75 TR](../reports/tests/TR-MVP-006-20261018-R75.md)记录当前店铺审批通用政策 FAQ 原文与分类并行、独立结构化复核及本地声明/DLP/发送门禁。精确资格、跨店/旧版、空或错误声明、取消等相关 214 项通过，完整后端 `2118 passed, 27 skipped`，Ruff、mypy、锁文件与 237 条离线安全样本通过。尚未做本版 DeepSeek SSE 或 50 并发；R74 真实首安全输出 5174.6 ms、总 5476.1 ms 仍是最近现场证据。G5/production No-Go。

2026-10-18 G5 R74 现场：[R74 TR](../reports/tests/TR-MVP-006-20261018-R74.md)记录 R73 并行路径从 main 手动发布、六摘要与临时部署。首次公网 504 经网关失效反向 SSH 隧道诊断和精确恢复，原 G3 门禁通过；重试部署、FAQ ready 和 50/50 身份预检通过。唯一合成 SSE HTTP 200、有安全 `delta`，但首输出 5174.6 ms、总耗时 5476.1 ms，严格 3 秒/5 秒均失败，50 并发与资源/断连采样未启动。最终恢复旧后端及 G3 单店人工发送，三公网健康和固定出口通过。并行检索的三次串行模型调用比 R72 两次组合路径更慢，G5/production No-Go。

2026-10-18 G5 R73 本地源码候选：运行工厂重新选择已存在的分类与店铺 FAQ 检索并行路径；单节点 FAQ Prompt 澄清内容级 `needs_human` 与员工必审发送的区别，并同步注册版本及 SHA-256。两条新增契约先按预期失败再通过；FAQ/工具/拒判/检索异常/取消等相关 121 项通过，完整后端 `2103 passed, 27 skipped`，Ruff lint/format、mypy 183 个源码文件与锁文件检查通过。现有 R68 并行路径单会话曾测得 4550.4 ms，不能由本地结果推断 R73 达到严格 3 秒门槛；新镜像、staging 与 50 并发尚未执行，G5/production No-Go。

2026-10-18 G5 R72 现场：[R72 TR](../reports/tests/TR-MVP-006-20261018-R72.md)记录组合 Prompt v1.0.1 后端手动发布、临时部署、FAQ ready、50/50 身份预检及唯一合成 SSE。HTTP 200 且有安全 `delta=3743.8 ms`，总耗时 3889.4 ms；严格首输出 `<3000 ms` 未通过，50 并发、资源与断连采样未启动。旧后端、G3 单店人工发送、三健康和固定出口恢复通过。R73 并行分类/店铺 FAQ 检索为本地候选，不能由确定性测试推定真实延迟。G5/production No-Go。

2026-10-18 `MVP-TIKTOK-STORE-SEND-001` staging 已审核单店人工普通文本范围：[R01 TR](../reports/tests/TR-MVP-TIKTOK-STORE-SEND-001-20261018-R01.md)记录 PR #348/#350 的店铺/单会话互斥与失败关闭、手动 validate/deploy、同店铺 180 个现有会话 `send_mode=real` 的只读汇总、两个已登录真实会话的现场模式，以及 337 项定向测试通过；Ruff lint/format 和 mypy 通过。原受控单会话真实外发与买家回复仍由 `MVP-004` R04 独立证明，本轮未向其他真实买家发送。G5 R70 之后已恢复 G3 单店模式；production 未发布。

2026-10-18 G5 R71 本地候选：[R71 TR](../reports/tests/TR-MVP-006-20261018-R71.md)记录组合 FAQ Prompt 对 `needs_human` 与员工确认发送语义的有界修复，契约先红后绿；完整后端 2101 passed/27 skipped，Ruff、格式、mypy 与锁文件检查通过。尚无新镜像或真实 DeepSeek SSE 复测；R70 的无安全 `delta` 仍是最新现场结论，50 并发未启动，G5/production No-Go。

2026-10-18 G5 R70 最新现场：[R70 TR](../reports/tests/TR-MVP-006-20261018-R70.md)记录从 main `86f3dae` 手动发布并临时部署 R69 组合 FAQ 后端；FAQ v3 ready、第十三代短期令牌、50/50 身份会话通过。唯一合成 SSE HTTP 200、总耗时 3155.2 ms，但无安全 `delta`；只读 Agent 摘要为组合 Prompt 已运行、分类成功、`faq_draft_needs_human`，独立复核仍执行。严格首输出门槛失败，50 并发未启动。按私有快照恢复原后端 `sha256:8913c09c…83a958`、当前前端 `sha256:1addb6c8…2db795`、检索与 G3 单店人工发送，三健康与固定出口通过。G5/production No-Go。

2026-10-18 G5 R69 源码候选：现有非工具 FAQ 命中路径改为一次严格结构化请求同时取得意图与草稿，随后仍执行本地引用/店铺/DLP 校验和独立安全复核。新增组合结构、Prompt 注册、Provider 路由和拒判/低置信度/工具/无知识/错引用/跨店/独立复核否决/异常/取消的确定性验证；本分支最终完整后端 `2101 passed, 27 skipped`，Ruff lint/format、mypy 和锁文件检查通过。尚未发布该候选镜像或在 staging 复测，最新真实现场仍是 R68 的首次安全 `delta=4550.4 ms`，50 并发未启动；G5/production No-Go。

2026-10-18 G5 R68 最新现场：[R68 TR](../reports/tests/TR-MVP-006-20261018-R68.md)记录从 main `04f0fbe` 手动发布 R67 并行检索后端、六摘要预取与临时 G5 部署，FAQ v3 ready、第十二代令牌及 50/50 身份会话通过。唯一合成 SSE HTTP 200、安全 `delta=4550.4 ms`、总耗时 4555.3 ms，严格首输出 <3000 ms 失败；分类/检索/草稿/独立安全复核为 1286/321/1504/1486 ms。50 并发及资源采样未启动。首次恢复被旧镜像构建输入门禁拒绝，随后从旧镜像对应的历史受审 checkout 按私有快照恢复原后端与 G3 店铺限定人工发送，三健康及固定出口通过。G5 与 production No-Go。

2026-10-18 G5 R67 源码：[R67 TR](../reports/tests/TR-MVP-006-20261018-R67.md)记录分类与当前店铺 FAQ 检索并行、拒判/低置信度/取消时清理任务、FAQ 检索异常失败关闭的先红后绿测试。更新到 main `6394282` 后完整后端 2083 passed/27 skipped，Ruff lint/format 与 mypy 通过。此轮仅本地源码验证，尚无 R67 镜像、staging 部署或 DeepSeek 现场结果；最近真实单会话仍为 R66 的安全 `delta=3635.8 ms`，50 并发未启动。G5 与 production No-Go。

2026-10-18 G5 R66 最新现场：[R66 TR](../reports/tests/TR-MVP-006-20261018-R66.md)记录从 main `ea8011b` 手动发布并临时部署 R65 计时后端。FAQ ready、第十一代隔离令牌和 50/50 身份会话只读预检通过；唯一合成 SSE HTTP 200、安全 `delta=3635.8 ms`、总耗时 3638.1 ms，严格首输出 <3000 ms 失败。Agent 分类/检索/FAQ 草稿/独立安全复核为 1185/392/1108/660 ms。50 并发未启动；旧后端与 G3 限定会话、健康及固定出口已恢复。G5 与 production No-Go。

2026-10-18 G5 R65 源码：[R65 TR](../reports/tests/TR-MVP-006-20261018-R65.md)记录五个固定 Agent 节点耗时的先红后绿验证，提交后完整后端 2069 passed/27 skipped、Ruff/mypy 通过；仅成功运行的低敏摘要新增白名单毫秒数，原路由、安全复核与 3 秒/5 秒门槛未改变。尚未发布或部署 R65 镜像，也未复测真实模型。R64 仍是最新现场：安全 `delta` 7829.7 ms，50 并发未启动，原 G3 模式已恢复。G5 与 production No-Go。

2026-10-18 G5 R64 最新现场：[R64 TR](../reports/tests/TR-MVP-006-20261018-R64.md)记录本机 Docker Desktop 登录 GHCR 后手动发布不可变后端，staging 临时 G5 部署、FAQ 就绪、第十代隔离令牌与 50/50 身份会话预检通过。唯一合成 SSE HTTP 200 并产生安全 `delta`，但首 `delta` 7829.7 ms、总耗时 7837.6 ms，未满足严格 3000/5000 ms 门槛；50 并发与资源采样未启动。原后端及 G3 限定会话人工发送已恢复，三健康与固定出口通过。G5 与 production No-Go。

2026-10-18 G5 R63 源码：[R63 TR](../reports/tests/TR-MVP-006-20261018-R63.md)记录固定转人工原因的先红后绿测试、提交后完整后端 2069 passed/27 skipped，以及 Ruff/mypy 通过。它只增强白名单诊断，不改变 Agent 动作或安全阈值；尚未发布或部署 R63 镜像，也未运行新 DeepSeek 单会话。[R62 现场](../reports/tests/TR-MVP-006-20261018-R62.md)仍是最新真实结果：无安全 `delta`、50 并发未启动、旧 G3 模式已恢复。G5 与 production No-Go。

2026-10-18 G5 R62 最新现场：[R62 TR](../reports/tests/TR-MVP-006-20261018-R62.md)记录 R61 后端手动临时部署、唯一 FAQ 就绪、第九代 50 枚隔离短期令牌续期及 50/50 身份会话预检通过。唯一合成 SSE HTTP 200 并正常结束，但没有安全 `delta`；Agent `transfer_human`、最终置信度 0，故 `performance_gate_passed=false`，50 并发未启动。旧后端和 G3 限定会话已恢复，三健康及固定出口通过。下一步先用固定低敏原因定位转人工，G5 与 production No-Go。

2026-10-18 G5 R61 源码候选：[R61 TR](../reports/tests/TR-MVP-006-20261018-R61.md)记录五条业务声明不变量固定分类及 FAQ 政策 Prompt `v1.6.2` 的先红后绿测试。定向 119 passed、完整后端 2064 passed/27 skipped，Ruff lint/format 与 mypy 通过；尚未发布镜像、部署或调用 DeepSeek。[R60 现场](../reports/tests/TR-MVP-006-20261018-R60.md)仍是最新真实结果：无安全 `delta`、9.613 秒、50 并发未运行，旧 G3 模式已恢复。G5 与 production No-Go。

2026-10-18 G5 R60 手动现场：[R60 TR](../reports/tests/TR-MVP-006-20261018-R60.md)证实新 FAQ JSON Schema 镜像发布、六摘要预取与临时部署、`knowledge_ready` 和 50/50 身份预检通过。唯一合成 SSE HTTP 200，但 `faq_draft / invalid_schema / business_claims:value_error`，无安全 `delta`，总耗时 9.613 秒；50 并发未运行。原后端与 G3 限定会话模式已恢复，三健康和固定出口通过。现有低敏类别无法定位具体声明不变量；G5 与 production No-Go。

2026-10-18 G5 R59 源码已合并：[R59 TR](../reports/tests/TR-MVP-006-20261018-R59.md)记录 FAQ 草稿使用 Responses JSON Schema 后的完整后端 2057 passed/27 skipped、Ruff lint/format、mypy 通过，独立审查无阻断；[PR #333](https://github.com/CP11-gh/CRM/pull/333) 已合入 main。两次单请求合成探针确认现用 DeepSeek 模型返回符合最小及完整 FAQ Schema 的结构；它们不等于实际 SSE 验收。GitHub CI 因账户计费在零步骤失败，没有作为测试证据。当前仍以 [R58 现场失败](../reports/tests/TR-MVP-006-20261018-R58.md)为准：无安全 `delta`、总耗时 8.135 秒、50 并发未运行；原 G3 模式已恢复。G5 与 production No-Go。

2026-10-18 G5 R57 源码已合并：[R57 TR](../reports/tests/TR-MVP-006-20261018-R57.md)记录 FAQ 安全复核五个结构化字段及低敏诊断路径的确定性修复。新增测试先红后绿，相关 98 passed、全量后端 2051 passed/27 skipped，Ruff lint/format 与 mypy 通过。本轮尚未发布镜像、部署 staging、调用 DeepSeek 或执行 50 并发；R56 仍是最新现场失败，G5 与 production No-Go。

2026-10-18 G5 R56 最新现场：[R56 TR](../reports/tests/TR-MVP-006-20261018-R56.md)记录六摘要预取、临时 G5 部署、FAQ v3 可检索、50 枚隔离令牌续期及 50/50 身份会话预检通过。唯一合成 SSE 为 HTTP 200，却在独立 `safety_review` 节点出现 `invalid_schema / unknown:missing`，公开 `50003`、无安全 `delta`、总耗时 6806.5 ms；50 并发没有启动。原后端与 G3 限定会话模式已恢复，三健康和固定出口通过。G5 与 production No-Go。

2026-10-18 G5 R54 源码候选：针对 [R53 单会话诊断](../reports/tests/TR-MVP-006-20261017-R53.md) 的 `business_claims:model_type`，FAQ Prompt `faq-answer-v1.6.1` 明列必需字段及声明对象结构；FAQ 顶层字段进入低敏 Schema 路径白名单。新增测试先红后绿，相关 169 passed，全量后端 2049 passed/3 skipped、2 项依赖弃用警告，Ruff lint/format 与 mypy 通过。本轮尚未发布新镜像、部署 staging 或调用 DeepSeek，G5 单会话和 50 并发仍未通过，production No-Go。

2026-10-17 G5 R53 获批手动诊断窗口：[R53 TR](../reports/tests/TR-MVP-006-20261017-R53.md)记录六摘要预取、G5 临时部署、现有凭证 50/50 只读预检通过；唯一合成 SSE HTTP 200，accepted 1047.6 ms，却在 FAQ 草稿 `invalid_schema` 后以公开 `50003` 结束，安全 `delta` 为空。只读白名单诊断为 `business_claims:model_type` 和 `unknown:missing`，后者仍不能定位具体字段。单会话失败，50 并发未启动；旧后端与 G3 限定会话模式已恢复，三健康与固定出口通过。G5 和 production No-Go。

2026-10-17 G5 R52 手动镜像证据：从 main `19437e64` 发布的诊断后端 OCI index `sha256:d85e1767…819f7` 已核对 linux/amd64、revision、12 层压缩大小及按摘要拉回，见[低敏证据](../../release/evidence/staging/crm-staging-g5-r52-manual-backend-image-20261017.json)。镜像尚未部署，R50 的单会话失败与 G5 No-Go 结论不变。

2026-10-17 G5 R51 本地诊断源码：[R51 TR](../reports/tests/TR-MVP-006-20261017-R51.md)记录先红后绿的白名单 Schema 明细传递验证；完整后端 2047 passed/3 skipped，Ruff、格式、mypy 通过。仅在 `invalid_schema` 最多记录八组固定字段路径与错误类型，未发布镜像、切换 staging 或调用 DeepSeek；R50 的实际失败字段仍未知，安全 `delta` 和 50 并发仍未通过。G5 与 production No-Go。

2026-10-17 G5 R50 两次获批手动窗口：[R50 TR](../reports/tests/TR-MVP-006-20261017-R50.md)核对 OCI index 六摘要预取、临时 G5 部署与恢复。第一次 50/50 预检通过后，单会话因客户端默认 localhost Origin 被 staging CORS 拒绝；第二次显式设置 staging Origin，50/50 通过、SSE HTTP 200，但 FAQ 草稿 `invalid_schema` 导致公开 `50003`、无安全 `delta`，性能门禁失败。两次均未执行 50 并发或资源采样；旧后端与 G3 限定会话模式已恢复，三健康 200、固定出口通过。G5 与 production 未通过。

2026-10-17 G5 R49 镜像发布：已从 main `ba020c1ff` 手动发布 R48 诊断后端候选，并按不可变摘要拉回核对 `linux/amd64`、OCI revision、12 层压缩合计 110,933,216 字节；见[低敏镜像证据](../../release/evidence/staging/crm-staging-g5-r49-manual-backend-image-20261017.json)。尚未部署 staging、复测合成单会话或运行 50 并发；G5 与 production 仍未通过。

2026-10-17 G5 R48 已合入源码：[PR #315](https://github.com/CP11-gh/CRM/pull/315) 将 subject `a927156a` 合入 main `e0d3fc3`。运行记录只在 `LLM_OUTPUT_INVALID` 时追加白名单模型节点和固定输出失败子类，未知诊断不入库；公开错误、DLP、评分和发送开关未变。本地后端回归 2045 passed、27 skipped，Ruff 与 mypy 通过；见 [R48 TR](../reports/tests/TR-MVP-006-20261017-R48.md)。尚未发布镜像、部署或在 staging 复现故障，G5 与 production 仍未通过。

2026-10-17 G5 R47：获批手动窗口已从 main `d29d5e0a` 完成 G5 部署、唯一隔离 FAQ 版本 3 更新及本地 BGE 向量化、第六份 50 枚短期凭证续期，50/50 不同授权用户只读预检通过。唯一合成 SSE HTTP 200，但公开码 `50003`、内部码 `LLM_OUTPUT_INVALID`、无安全 `delta`，性能门禁失败；没有启动 50 并发或资源采样。恢复原后端与 G3 限定会话人工发送后，LLM/SSE 关闭、限流 10、三公网健康 200 和固定出口通过。现有持久记录无法定位模型输出失败节点或子类；见 [R47 TR](../reports/tests/TR-MVP-006-20261017-R47.md)。G5 与 production 仍未通过。

2026-10-17 G5 R45/R46：R45 获批手动窗口的 50/50 只读预检通过；唯一合成 SSE HTTP 200，但 `first_delta_ms=null`、总耗时约 7.83 秒，性能门禁失败，50 并发未启动。恢复旧后端、G3 限定会话发送与翻译后三健康 200、固定出口通过；见 [R45 TR](../reports/tests/TR-MVP-006-20261017-R45.md)。本地安全判定复现原隔离 FAQ 答案的逗号与来源标签导致 Prompt 不放行；R46 subject `c8d68a1f7815c299093b64722b76fd7ba33ace81` 的隔离 PostgreSQL 全量回归为 2064 passed、3 skipped，Ruff、mypy 与 PowerShell AST 通过；本地 Prompt 安全判定放行新载荷，不能替代新的 staging 单会话、50 并发及资源/断连证据。G5 与 production 仍未通过。

2026-10-17 G5 R41 合并后只读预检：PR #304 已合入 main `a0788e77`。GitHub 比较确认 R40 镜像提交是 main 的祖先（ahead 3、behind 0），但 `src/backend` 树 SHA 不一致；手动门禁返回非零并在任何写入前停止。Dockerfile blob 一致。现有 SSH 密钥被 staging 拒绝，运行容器未检查；未写测试数据、调用 BGE/DeepSeek 或执行并发。见[低敏预检证据](../../release/evidence/staging/crm-staging-g5-r41-ancestor-preflight-20261017.json)。R40 镜像不能用于本次夹具替换，G5 与 production 仍未通过。

2026-10-17 G5 R41 源码候选：手动 `ReconcileFixture` 从当前 main 的受审源码运行，运行镜像来自较早提交时必须在写入前证明祖先关系及后端树、Dockerfile 完全一致，并继续核对不可变运行摘要与 OCI revision。先红后绿相关 49 项；最新 main 基线完整后端 `2006 passed, 27 skipped, 2 warnings`，Ruff、mypy 和 PowerShell AST 通过。当前 main 的后端树已变化，R40 旧镜像只读预检应失败关闭；尚未更新 staging 数据或运行 G5 容量测试，见 [R41 TR](../reports/tests/TR-MVP-006-20261017-R41.md)。

2026-10-17 G5 R40：从 main `7d4a72d7` 本地构建 linux/amd64 后端，并从 GHCR 远端核对不可变索引摘要 `sha256:8a418e6c…796221`、OCI revision、12 个压缩层 110,929,110 字节；[发布证据](../../release/evidence/staging/crm-staging-g5-r40-manual-backend-image-20261017.json)。镜像发布通过不代表 staging 部署或 G5 容量通过；现场内容更新、BGE、DeepSeek 与 50 并发均未执行。

2026-10-17 G5 R39 源码候选：旧版隔离提问的精确识别、店铺/50 会话/唯一 FAQ 拒绝条件、版本 2 旧切片失效及手动确认值已做红绿测试；内容工具与向量化 35 passed。完整后端及隔离 PostgreSQL 回归 `2019 passed, 3 skipped, 2 warnings`，Ruff lint/format、183 个源文件 mypy、4 个 PowerShell AST 与 `git diff --check` 通过。此为代码与测试证据；没有执行 staging 数据更新、向量化、DeepSeek 单会话或 50 并发，G5/production 仍未通过。

2026-10-17 G5 R38：获批手动 staging 窗口的六摘要预取、修复版 G5 validate/deploy、第四份短期测试凭证签发及公网 50/50 只读预检通过。唯一合成 SSE 为 HTTP 200、协议完成，却无安全 `delta`，`first_delta_ms=null`、性能门禁 false；只读 Agent 追踪为 `insufficient_context`、`transfer_human`、检索候选 0。旧后端、Webhook 只读与工作台翻译已恢复，三健康 200、LLM/SSE 关闭、限流 10。没有 50 并发，G5/production 继续未通过。见 [R38 TR](../reports/tests/TR-MVP-006-20261017-R38.md)。

2026-10-17 G5 R37：已授权的手动窗口完成六摘要预取和 G5 validate，迁移容器因 backend 未收到仓库外已有的内部检索令牌而失败；没有签发第四份凭证或发起合成 SSE/DeepSeek。旧后端、TikTok Webhook 只读和工作台翻译按门禁恢复，三健康 200。修复仅在 G5 backend 注入令牌并于部署前要求与检索服务一致且长度至少 32；本地完整后端 `1973 passed, 27 skipped`，subject 后 staging 门禁 `145 passed`，Ruff 和 PowerShell AST 通过。修复后的现场部署及单会话尚未执行，G5/production 继续未通过。见 [R37 TR](../reports/tests/TR-MVP-006-20261017-R37.md)。

2026-10-17 G5 R34：续期工具改为原 R05 批次连续编号文件、逐份验签与 50 用户/会话映射校验；红灯后修复，定向 `26 passed`，后端全量 `1962 passed, 27 skipped`，全量 Ruff、183 文件 mypy 及两份 PowerShell AST 通过。仅是本地源码门禁，[R34 TR](../reports/tests/TR-MVP-006-20261017-R34.md) 未签发新令牌、发布镜像或在 staging 复测；G5/production 继续未通过。

2026-10-17 G5 R33：[staging 空闲采样](../reports/tests/TR-MVP-006-20261017-R33.md)在 Linux/Rootless 下读取 3 组 backend/worker/agent-worker 资源与 backend TCP 白名单指标，服务器与入库副本哈希一致。未施加 SSE 负载，不能作为 50 并发容量证据；第三份凭证的 50/50 枚令牌已过期。G5/production 继续未通过。

2026-10-17 G5 R32：获批的手动单会话 SSE 在 `accepted` 后返回 `50003`，没有安全 `delta`，随后原 TikTok 只读加工作台翻译模式已通过 validate/deploy 与三个公网健康检查恢复。G5 backend 缺少 Agent 必需的本地检索开关；修复 subject `4eee102` 的定向 14 项、完整 staging 门禁文件 142 项及全量后端 `1959 passed, 27 skipped`，Ruff/PowerShell AST 均通过。修复尚未在 staging 复测；G5/production 未通过。见 [R32 TR](../reports/tests/TR-MVP-006-20261017-R32.md)。

2026-10-17 G5 R31：只读资源/TCP 队列采样器与格式修复主线整合后的 `9712c5a8` 本地全量后端 pytest `1955 passed, 27 skipped`、Ruff lint/format 与 mypy 通过；前端 47 项契约、lint/typecheck/build 通过。PR #281 的 GitHub Actions 作业均在首步前失败，不能作为代码测试结论；用户决定 G5 改用 GitHub 凭据和 staging 手动路径。格式基线已由 PR #283 修复，采样器仍待合并，尚未在 Linux staging 运行；单会话安全 `delta`、真实 50 并发、资源峰值与恢复仍无现场结论，G5/production 未通过。见 [R31 TR](../reports/tests/TR-MVP-006-20261017-R31.md)。

2026-10-17 `TEST-CI-FORMAT-001`：锁定 Ruff 0.16.3 对三个既有 G5 测试文件作纯排版修复；全量 Ruff lint/format 通过，三文件 AST 一致、定向 43 passed，见 [TR](../reports/tests/TR-TEST-CI-FORMAT-001-20261017-R01.md)。PR #283 已经按手动等价验证 squash 合入 main `2da8e172`；GitHub Actions 作业因账户计费在首步前失败，未被记为通过。

2026-10-17 G5 R29：用户精确授权的单次凭证续期返回 50 枚短期令牌、数据库写入和 Provider 调用均为 0；独立只读 `ContentCheck` 为 50/50 会话、凭证 renewed、知识 ready，第三份私有文件权限 `600`。见 [R29 TR](../reports/tests/TR-MVP-006-20261017-R29.md)。未运行 `/auth/me` 端到端预检、单会话 SSE 或真实 50 并发，G5/production 未通过。

2026-10-17 G5 R28：获批的第二次、也是修复后唯一一次本地 BGE 向量化成功；独立 `ContentCheck` 为 `knowledge_ready=true`、50/50 会话、原凭证，SQL 检索门禁为 1 个合格片段，DeepSeek 0，三健康 200，常驻 Embedding/LLM/TikTok 写入仍关闭。见 [R28 TR](../reports/tests/TR-MVP-006-20261017-R28.md)。短期凭证、单会话及 50 并发仍未验收，G5/production 未通过。

2026-10-17 G5 R26–R27：获批单次向量化因单文件挂载不满足旧源码挂载安全门禁而失败；只读对账 50/50、FAQ pending、chunk 0、原凭证。修复恢复完整受审源码只读挂载，相关测试 51 passed，未二次运行。见 [R26 TR](../reports/tests/TR-MVP-006-20261017-R26.md)与[R27 TR](../reports/tests/TR-MVP-006-20261017-R27.md)。G5/production 未通过。

2026-10-17 G5 R24 现场内容准备：一次获批 `ContentPrepare` 写入原隔离店铺 50 条合成提问和 1 条内部审阅级 FAQ；写前/写后只读对账均为 50/50 会话，写后 `fixture_state=prepared`、凭证仍为原状态，Provider 调用 0。三项公网健康仍为 200。`EMBEDDING_ENABLED=false` 使 FAQ 尚未向量化，`knowledge_ready=false`；见 [R24 TR](../reports/tests/TR-MVP-006-20261017-R24.md)。凭证续期、SSE、DeepSeek 和 50 并发未执行，G5/production 仍未通过。

2026-10-17 G5 R23 手动 staging：从 main `7b7acc35` 发布的后端 `sha256:477d571d…cb293` 经六角色预取、validate/deploy 和独立核对运行；前端/检索不变，迁移头、三个公网健康 200、固定出口、TikTok 只读与工作台翻译通过，G5 SSE 关闭且限流 10。零调用内容检查仍为原 50/50 会话、知识未准备、凭证原状态，Provider/数据库写入 0。首次 tar 解包路径因下层门禁要求 Git checkout 而在切换前失败，改用同一 SHA 的干净浅克隆后通过。见 [R23 TR](../reports/tests/TR-MVP-006-20261017-R23.md)。未写入合成数据、续期、调用 DeepSeek 或运行 50 并发；G5/production 未通过。

2026-10-17 G5 R22 手动夹具源码：从受审源码与运行镜像精确核对后，手动内容入口可分别只读检查、准备 50 条合成问题和内部审阅 FAQ、续期私有凭证；续期后只读对账与异常文件名拒绝经回归覆盖。完整后端 `1929 passed, 27 skipped`，定向 `36 passed`，Ruff、格式、mypy、PowerShell AST 与独立审查通过。见 [R22 TR](../reports/tests/TR-MVP-006-20261017-R22.md)。未发布新镜像或在 staging 执行本入口，G5/production 未通过。

2026-10-16 G5 R21 手动恢复源码：新增 `RestoreReadAndTranslation`，在结束 SSE 窗口后通过原 Rootless 门禁同时恢复 TikTok 只读与工作台翻译，并核对通用模型/SSE 关闭及限流 10。本地相关门禁完整回归 `151 passed`、格式后定向 `22 passed`、Ruff/格式及 PowerShell AST 通过，独立代码审查无严重或重要问题。见 [R21 TR](../reports/tests/TR-MVP-006-20261016-R21.md)。未执行 staging G5 窗口或恢复演练，G5/production 仍未通过。

2026-10-16 G5 R20 手动只读现场：新版界面配套后端 `sha256:deef65ee…babbe8` 运行时，受审源码 `f56b998` 的归档校验和手动 `CheckOnly` 通过；原批次 50/50 会话匹配，`fixture_state=original`、`knowledge_ready=false`，Provider 调用与数据库写入均为 0。容器默认工作目录导致第一次安全路径校验拒绝；显式设置受审目录后只读检查通过，持久入口待修。见 [R20 TR](../reports/tests/TR-MVP-006-20261016-R20.md) 与 [低敏证据](../../release/evidence/staging/crm-staging-g5-manual-content-check-20261016.json)。未准备内容、续期凭证、执行 SSE 或恢复演练；G5 与 production 仍未通过。

2026-10-16 `MVP-CONV-UI-001` R04 现场 `f56b998`：staging 后端新摘要、前端已验证摘要运行健康，门禁迁移及三项公开健康 200；已登录工作台显示 179 个真实 TikTok 会话，买家左侧白色、客服右侧蓝色。分别对一条英文买家和客服消息按需调用 DeepSeek 后，原文下方显示中文；回复输入与发送按钮禁用。真实译质需坐席核对，真实发信和 production 仍关闭。见 [R04 TR](../reports/tests/TR-MVP-CONV-UI-001-20261016-R04.md) 与 [低敏门禁证据](../../release/evidence/staging/crm-staging-conv-ui-translation-20261016.json)。

2026-10-16 `MVP-CONV-UI-001` R03 翻译 Prompt 候选 `81f9963`：staging 的 `14ec836` 已显示 179 个真实 TikTok 会话、双侧气泡、原文与按需翻译入口，三项公开健康为 200；真实消息首次两次 DeepSeek 翻译因 `LLM_OUTPUT_INVALID` 失败。合成探针定位旧提示词未说明输出字段；R03 明确四字段后同模型合成句返回可校验中文，受影响后端 602 passed、Ruff 与格式通过。R03 镜像尚未部署，真实译文待现场复测，见 [R03 TR](../reports/tests/TR-MVP-CONV-UI-001-20261016-R03.md)。真实发信与 production 关闭。

2026-10-16 `MVP-CONV-UI-001` R02 前端依赖候选 `7ec8062`：官方 npm 生产依赖审计 0 vulnerabilities，Next.js `16.3.8`、`sharp` `0.35.5`、`source-map-js` `1.2.2`；前端契约 45 passed、本地生产构建浏览器 26 passed，lint 0 错误/2 条原有警告、typecheck/build 通过。R01 的双语 UI/后端测试证据仍有效；新镜像及真实 staging 页面尚未验收，见 [R02 TR](../reports/tests/TR-MVP-CONV-UI-001-20261016-R02.md)。

2026-10-16 `MVP-CONV-UI-001` 候选 `93b8476`：后端翻译/门禁相关 150 passed，前端契约 45 passed，本地生产构建合成浏览器 26 passed；Ruff、格式、mypy、lint、typecheck、build 通过。合成浏览器确认买家左侧、卖家右侧、按需中文译文与平台发信 0 次。尚未发布后端/前端镜像、部署 staging 或对真实消息调用 DeepSeek；现场 UI/译文待验，见 [R01 TR](../reports/tests/TR-MVP-CONV-UI-001-20261016-R01.md)。真实消息写与 production 仍关闭。

2026-10-16 `MVP-CONV-SYNC-001` staging 只读现场：授权 TikTok 会话 179 个、可见消息 2018 条，工作台接口 6 页返回 179 个不重复会话；截图目标平台 29 条原始历史中的 25 条可见消息全部在工作台详情。R02 前端 45 契约测试、24 浏览器回归通过，1 项缓存配置测试跳过，类型检查与构建通过；PR #250 双 CI 合入。用户授权的手动 staging validate/deploy 使用固定源码包和不可变摘要均通过；新版前端运行且三个健康接口 200。浏览器现场显示真实会话总数 179、列表由 30 条加载至 60 条、目标历史及角色标签；回复输入与发送按钮禁用。真实消息写关闭，G2/G3 未通过；完整范围见 [R03 TR](../reports/tests/TR-MVP-CONV-SYNC-001-20261016-R03.md)，production No-Go。

2026-10-16 G5 R16 源码：subject `c3439013` 新增原隔离店铺的合成 FAQ/问题和短期凭证续期精确门禁；最终完整后端 `1892 passed, 27 skipped`，隔离 PostgreSQL 4 passed，Ruff、格式、mypy、工作流 PowerShell AST 通过；[PR #251](https://github.com/CP11-gh/CRM/pull/251) 前后端 CI #38890253045 均通过并 squash 合入 main `5d6c0298`，见[R16 TR](../reports/tests/TR-MVP-006-20261016-R16.md)。未在 staging 写入内容、轮换凭证、发布镜像或调用模型；R14 的限流 10 仍是最近明确现场值。G5、production No-Go。

2026-10-16 G5 R14：用户授权的精确邮箱修复 [#38878859064](https://github.com/CP11-gh/CRM/actions/runs/38878859064) 更新原 50 用户、轮换 50 令牌并保留旧 manifest，`provision` skipped、Provider 0。紧接的只读[预检 #38878976347](https://github.com/CP11-gh/CRM/actions/runs/38878976347) 为 50/50 身份及会话可用、失败类别为空；生效单 IP 限流 10 小于 50，工作流按门禁失败关闭，未发送 SSE 负载。[R14 TR](../reports/tests/TR-MVP-006-20261016-R14.md)及[低敏证据](../../release/evidence/staging/crm-staging-g5-fixture-repair-20261016.json)已记录。G5、production No-Go。

2026-10-16 G5 R13：PR #245 双 CI 通过并合入 main `26a4e8e`；[staging 只读对账 #38877932619](https://github.com/CP11-gh/CRM/actions/runs/38877932619) 核对源码、运行摘要、数据库目标和原私有 manifest，报告 50 个匹配账号、Provider 0、数据库写入 0。`reconcile_email`、`provision`、50 身份预检均未执行。原认证失败和生效限流 10 尚未解除；[R13 TR](../reports/tests/TR-MVP-006-20261016-R13.md)及[低敏证据](../../release/evidence/staging/crm-staging-g5-reconcile-check-38877932619.json)。G5、production No-Go。

2026-10-16 G5 R12 源码候选：完整后端 1858 passed/3 skipped；隔离 PostgreSQL 夹具 3 passed，定向 16 passed；Ruff、格式、mypy 与工作流八段 PowerShell AST 通过。`@example.invalid` 在真实 `/auth/me` 路径触发 `ValidationError`/500 的本地复现已转为测试；新夹具改用有效邮箱格式。只读 `reconcile_check` 与需要精确确认的 `reconcile_email` 已分离，后者只针对 R05 原 50 账号、独占新私有凭证文件，保留原 manifest。尚未合入 main、未运行 staging 只读对账或写入；50 身份、限流与真实负载仍未通过，G5、production No-Go。

2026-10-16 G5 R11：[固定窗日志回查 #38866573949](https://github.com/CP11-gh/CRM/actions/runs/38866573949) 从 main `fafbac740` 成功执行，但只输出 `matched_events=0`、Provider 0；不能据此确认 HTTP 500 的异常类型。原夹具邮箱 `@example.invalid` 被当前 `EmailStr` 本地复现拒绝，属于待现场核实的原因；[R11 TR](../reports/tests/TR-MVP-006-20261016-R11.md)与[低敏证据](../../release/evidence/staging/crm-staging-g5-auth-log-recheck-38866573949.json)已记录。50 身份与会话、限流 50、安全输出及真实 50 并发仍未通过，G5、production No-Go。

2026-10-16 G5 R10：[固定窗只读探针 #38864445483](https://github.com/CP11-gh/CRM/actions/runs/38864445483)在报告计数类型检查处失败，未产生异常类型结论；[低敏失败证据](../../release/evidence/staging/crm-staging-g5-auth-log-probe-38864445483.json)。修复 subject 9b478fb 聚焦 3 passed、七段 AST 与本机模拟 JSON 校验通过，PR #243 双 CI 通过并合入 main `fafbac740`；现场回查结果见 R11。G5、production No-Go。

2026-10-16 G5 R09：[获批单令牌只读诊断 #38862950177](https://github.com/CP11-gh/CRM/actions/runs/38862950177) 在 main 1626622 返回本地有效的令牌与一致的运行签名配置，但 /auth/me 为 HTTP 500 / API 50001；没有运行 50 身份预检、provision 或模型。[低敏证据](../../release/evidence/staging/crm-staging-g5-auth-status-38862950177.json)。固定日志窗只读探针 subject 47aae95 本地 1851 passed/20 skipped、Ruff/格式/mypy 和工作流语法通过；现场异常类型待核对。G5、production No-Go。

2026-10-16 G5 R08：一次获批的 [只读诊断 #38861412442](https://github.com/CP11-gh/CRM/actions/runs/38861412442) 在 main fbe1b81 上报告首枚令牌 valid、运行密钥和算法匹配、一次 /auth/me 状态 other、Provider 0；旧类别无法细分响应。[低敏证据](../../release/evidence/staging/crm-staging-g5-auth-diagnostic-38861412442.json)已保留。获批的状态/白名单 API 错误码细分在 subject f15bb3a 的定向 15 passed、完整后端 1849 passed/20 skipped、Ruff/格式/mypy 通过；最终 PR CI 和第二次现场只读诊断待核对。50 身份认证和限流 50 尚未通过，G5、production No-Go。

2026-10-16 G5 R07：PR #239 双 CI 通过并合入 main `7e12314`；[staging 只读预检 #38858709981](https://github.com/CP11-gh/CRM/actions/runs/38858709981) 返回 50 次 `auth_rejected`、运行限流 10、Token 有效期 120 分钟、Provider 0，按门禁失败关闭。第一枚令牌的签名、算法、必需声明、过期及签发配置与运行配置匹配诊断已在 subject `fe65b93` 实现，最终定向 11 passed、Ruff/格式/mypy 通过；本地完整后端 1842 passed/20 skipped 属前一源码提交，最终 CI 待核对，见 [R07 TR](../reports/tests/TR-MVP-006-20261016-R07.md)；现场诊断尚未运行。G5、G6 与 production 未通过。

2026-10-16 G5 R06 只读预检源码候选：subject `8493fc8` 增加 staging Runner 50 身份/会话 GET、运行限流和 Token 有效期核对；审查发现低于 50 限流仍可能误报成功，已增加失败门禁。最终聚焦 39 passed、五段 PowerShell AST 通过，完整后端 1837 passed/20 skipped 的执行范围见 [R06 TR](../reports/tests/TR-MVP-006-20261016-R06.md)。PR #239 最终 CI 与现场运行尚待复核；真实 50 并发与 production 仍未通过。

2026-10-16 G5 R05 现场夹具：一次获批的 [staging 工作流 #38852775454](https://github.com/CP11-gh/CRM/actions/runs/38852775454)在 main `a202c755` 核对源码、运行镜像和数据库目标后成功创建 50 个隔离 CRM 账号及 50 个会话，Provider 0，私有凭证 manifest 保留在仓库外，见 [R05 TR](../reports/tests/TR-MVP-006-20261016-R05.md)。R01 逐一认证/会话预检尚未运行，真实限流、知识命中、安全输出及 50 并发尚无现场证据；G5、G6 与 production 未通过。

2026-10-16 G5 R04 现场只读前置检查：PR #234 前后端 CI 通过并合入 main `814590f`；一次获批的 [工作流 #38847788672](https://github.com/CP11-gh/CRM/actions/runs/38847788672)在 staging 成功核对源码、运行后端、数据库指纹和私有路径，返回 ready、Provider 0、业务写入 0，`provision` skipped，见 [R04 TR](../reports/tests/TR-MVP-006-20261016-R04.md)。尚未创建 50 个账号或运行 R01 账号认证预检；G5、G6 与 production 未通过。

2026-10-16 G5 R03 Runner 入口源码：subject `feaaf5e` 增加 main/运行镜像/数据库指纹核对、只读 `check_only` 与单独确认的 `provision`。独立审查发现并修复无 Git 镜像的私有路径校验问题；最终源码聚焦 15 passed，前一源码提交的本地完整后端 1835 passed/20 skipped、隔离 PostgreSQL 1852 passed/3 skipped，Ruff/格式/Linux mypy 通过，最终完整回归待 PR CI，见 [R03 TR](../reports/tests/TR-MVP-006-20261016-R03.md)。此处尚未把代码合入 main 或运行现场检查；G5 仍未通过，production No-Go。

2026-10-16 G5 R02 源码准备：用户确认只提交隔离 staging 账号工具、测试和清理方案，subject `dae1083`。最小 `workspace.view`、50 独立会话、数据库指纹、Linux 私有凭证、提交结果未知时保留 manifest 均经确定性测试；完整后端 1827 passed/20 skipped，隔离 PostgreSQL 新增测试 1 passed，Ruff/格式/Windows 与 Linux mypy 通过，PR #232 前后端 CI 通过并合入 main `4440440`；隔离 PostgreSQL 全量 1844 passed/3 skipped，见 [R02 TR](../reports/tests/TR-MVP-006-20261016-R02.md)。本轮没有在 staging 创建账号、运行只读预检或调用模型。合成店铺没有可检索的已审批 FAQ，安全 `delta` 和 50 并发仍未验证；G5 未通过，production No-Go。

2026-10-16 G5 R01 源码准备：从 main `beb24b7` 的 subject `9ca964b` 增加零模型调用只读凭证预检。定向 36 passed，完整后端 1820 passed/19 skipped，Ruff、格式及 mypy 通过；[PR #230](https://github.com/CP11-gh/CRM/pull/230) 双 CI 通过并合入 main `b66ecd0`，低敏报告只含计数和固定失败类别，见 [R01 TR](../reports/tests/TR-MVP-006-20261016-R01.md)。尚无仓库外 50 个受控账号的现场凭证池，因此未运行真实预检、50 并发或 DeepSeek 负载；G5 未通过，production No-Go。

2026-10-16 G4 R56：用户在精确付费范围说明后要求继续，[完整 live #38832517813](https://github.com/CP11-gh/CRM/actions/runs/38832517813) 从 main `54594dc4` 和 R55 staging 后端 `sha256:1045d683…eec363` 执行。冻结 34 条 DeepSeek 合成样本加 2 条本地故障注入，终态 36/36、危险逃逸 0、合法误拦 0、Provider 故障 0，报告 `passed=true`；R52 的售后与多语言两条失败均经受控政策修复通过。原样低敏报告、SHA-256、调用/延迟/费用估算及外推边界见 [R56 TR](../reports/tests/TR-MVP-005-20261016-R56.md)。[PR #228](https://github.com/CP11-gh/CRM/pull/228) 前后端 CI 通过并合入 main `7ed1bfe`。G4 冻结合成质量门禁通过；真实买家闭环、50 客户端 SSE、五日稳定性和 production 仍按独立门禁验收。

2026-10-15 G4 R55 staging：用户单独授权的[六摘要预取 #38710281674](https://github.com/CP11-gh/CRM/actions/runs/38710281674)、[validate #38712087142](https://github.com/CP11-gh/CRM/actions/runs/38712087142)、[deploy #38712441191](https://github.com/CP11-gh/CRM/actions/runs/38712441191) 与零调用 [prepare #38713090896](https://github.com/CP11-gh/CRM/actions/runs/38713090896) 均从 main `86ac3dd` 成功。staging 后端已切到 `sha256:1045d683…eec363`，前端/检索不变；迁移头、三健康、固定出口与 Webhook 只读通过。prepare 核对冻结 36 条及 Provider 调用 0，原样证据与哈希见 [R55 TR](../reports/tests/TR-MVP-005-20261015-R55.md)；[PR #226](https://github.com/CP11-gh/CRM/pull/226) 前后端 CI 通过并合入 main `cf362c4`。尚未运行新版付费 `live`；R52 仍是最新真实质量失败，G4 `PARTIAL`、production No-Go。

2026-10-15 G4 R54 单镜像发布：用户在精确范围后批准继续；从 main `6e41632` 仅运行一次[后端发布 #38708209437](https://github.com/CP11-gh/CRM/actions/runs/38708209437)，生成 `ghcr.io/cp11-gh/crm-backend@sha256:1045d683…eec363`。原样[镜像证据](../../release/evidence/staging/crm-staging-g4-r54-image-38708209437.json)确认 `linux/amd64` manifest `PASS`、压缩层 110,072,185 字节、最大层 33,257,532 字节；原始/入库哈希一致；[PR #224](https://github.com/CP11-gh/CRM/pull/224) 前后端 CI 通过并合入 main `eda95db`，见 [R54 TR](../reports/tests/TR-MVP-005-20261015-R54.md)。本轮未部署 staging 或调用 DeepSeek；R52 仍是最新真实质量，G4 `PARTIAL`、production No-Go。

2026-10-15 G4 R53 源码候选：从 main `5ac6da6` 的 subject `1d15123` 将内部政策诊断码从模型修复请求移出，改用固定白名单自然语言要求，Prompt 升至 `real-model-eval-v1.2.13` 并保留严格 `reason_code` 枚举。先红后绿，subject 上六个相关文件 92 passed；定向 Ruff 和格式通过，本地 mypy 长时间无输出后中断；[PR #222](https://github.com/CP11-gh/CRM/pull/222) 前后端 CI（含后端类型检查）通过并合入 main `39f18d6`。见 [R53 TR](../reports/tests/TR-MVP-005-20261015-R53.md)。尚未发布镜像、部署或调用 DeepSeek；下方 R52 仍是最新现场，G4 `PARTIAL`、production No-Go。

2026-10-15 G4 R52：当前 main `1937336` 的零调用 [prepare #38702143931](https://github.com/CP11-gh/CRM/actions/runs/38702143931) 锁定 staging 后端 `sha256:8e8dcd81…7d5a`、冻结 36 条及 Provider 0 调用；用户单次授权的[完整 live #38702433875](https://github.com/CP11-gh/CRM/actions/runs/38702433875)取得 34/36（94.44%）、危险逃逸 0、合法误拦 0、Provider 故障 2，机器 `passed=false`。售后及多语言政策两条首稿均缺审核步骤，修复稿均在严格 `reason_code / literal_error` Schema 校验处失败关闭。原样证据与哈希见 [R52 TR](../reports/tests/TR-MVP-005-20261015-R52.md)。本次付费授权已用完；G4 `PARTIAL`、production No-Go。

2026-10-15 G4 R51：经单独授权，从 main `9eb3ef4` 完成[六摘要预取 #38696165478](https://github.com/CP11-gh/CRM/actions/runs/38696165478)、[validate #38698770092](https://github.com/CP11-gh/CRM/actions/runs/38698770092)、[deploy #38699231261](https://github.com/CP11-gh/CRM/actions/runs/38699231261)。staging 后端已切到 `sha256:8e8dcd81…7d5a`，前端和检索不变；迁移头、三健康、固定出口与 Webhook 只读通过。零调用 [prepare #38699921968](https://github.com/CP11-gh/CRM/actions/runs/38699921968) 核对运行摘要和冻结 36 条，Provider 0 调用；原样证据及哈希见 [R51 TR](../reports/tests/TR-MVP-005-20261015-R51.md)。尚未运行新版付费 `live`；R48 的 35/36、Provider 故障 1、机器 `passed=false` 仍是最新真实质量，G4 `PARTIAL`、production No-Go。

2026-10-15 G4 R50：用户单独授权的[后端镜像发布 #38694723923](https://github.com/CP11-gh/CRM/actions/runs/38694723923) 从 main `6b63fd7` 成功；候选不可变摘要 `sha256:8e8dcd81…7d5a`、`linux/amd64` manifest `PASS`、压缩层 110,070,651 字节，原样证据及 SHA-256 见 [R50 TR](../reports/tests/TR-MVP-005-20261015-R50.md)。本轮尚未部署 staging 或调用 DeepSeek；R48 仍是最新真实质量，G4 `PARTIAL`、production No-Go。本次镜像授权已用完。

2026-10-15 G4 R49：按用户批准的有界设计，Prompt `real-model-eval-v1.2.12` 给一次性政策修复列出七个合法 `reason_code`、有证据 FAQ 的 `human_review+policy_grounded` 映射及诊断码隔离。新增契约先红后绿，五个相关评测文件 79 passed，定向 Ruff、格式、mypy 及 [PR #214](https://github.com/CP11-gh/CRM/pull/214) 前后端 CI 通过，见 [R49 TR](../reports/tests/TR-MVP-005-20261015-R49.md)。本轮没有发布镜像、部署 staging 或调用 DeepSeek；下方 R48 仍是最新真实质量，G4 `PARTIAL`、production No-Go。

2026-10-15 G4 R48：用户单次授权的[完整 staging live #38690748057](https://github.com/CP11-gh/CRM/actions/runs/38690748057)完成 34 条合成模型样本及 2 条本地故障注入，35/36（97.22%）、危险逃逸 0、合法误拦 0、Provider 故障 1。唯一失败 `multilingual-open-001` 的修复稿在严格 `reason_code / literal_error` Schema 校验处失败关闭；最终质量门禁 `passed=false`。原样报告哈希和逐项诊断见 [R48 TR](../reports/tests/TR-MVP-005-20261015-R48.md)。R41 的批量超时本轮未重现，但根因未证实；G4 `PARTIAL`、production No-Go。本次付费授权已用完。

2026-10-15 G4 R47：用户授权的一次 [staging 单样本 canary #38688630576](https://github.com/CP11-gh/CRM/actions/runs/38688630576) 从 main `5add1e7` 和已运行后端不可变摘要执行。固定低敏报告显示一次 SDK 调用、请求与响应头钩子均触发、请求至响应头 `101-500ms`、总耗时 `501-2000ms`、`result=completed`，见 [R47 TR](../reports/tests/TR-MVP-005-20261015-R47.md)。这证明该时刻单样本真实请求完成，不能解释 R41 的 34 次超时；完整 34+2 质量复测尚未进行，G4 `PARTIAL`、production No-Go。本次付费授权已用完。

2026-10-15 G4 R46：[PR #207](https://github.com/CP11-gh/CRM/pull/207) 将现有 live 已获批的五项计价配置原值传给 canary/check_only 一次性容器进程，前后端 CI 通过。[零调用复核 #38683585950](https://github.com/CP11-gh/CRM/actions/runs/38683585950) 的[低敏报告](../reports/tests/TR-MVP-005-20261015-R46.md)为 `ready/none`、Provider 0 调用、请求钩子 false，确认 R45 的配置加载阻断已解除。尚未重试付费 canary；R41 真实生成超时仍未定位。G4 `PARTIAL`、production No-Go。

2026-10-15 G4 R45：用户获批的 [canary #38678589702](https://github.com/CP11-gh/CRM/actions/runs/38678589702) 在安全报告生成前以 `CANARY_SETUP_FAILED` 结束，请求是否发出无法证明且授权未重用。[PR #204](https://github.com/CP11-gh/CRM/pull/204) 增加零调用分类，最终双 CI 通过；[staging check_only #38681595434](https://github.com/CP11-gh/CRM/actions/runs/38681595434) 的[低敏报告](../reports/tests/TR-MVP-005-20261015-R45.md)为 `settings_validation`、Provider 0 调用、请求钩子 false。现有 canary 步骤缺 live 使用的五项获批计价配置，当时待修复与零调用复核；R41 生成超时未解决。G4 `PARTIAL`、production No-Go。

2026-10-15 G4 R44：[PR #201](https://github.com/CP11-gh/CRM/pull/201) 的单样本诊断代码已合入 main `19e603f`，完整后端 1799 passed/19 skipped，双 CI 通过。[零调用 prepare #38673009877](https://github.com/CP11-gh/CRM/actions/runs/38673009877) 核对运行后端摘要、冻结 36 条且 Provider 调用 0；原样证据与哈希见 [R44 TR](../reports/tests/TR-MVP-005-20261015-R44.md)。当时付费 `canary` 未运行，R41 真实生成超时根因未定。G4 `PARTIAL`、production No-Go。

2026-10-15 G4 R43：获准的[请求路径探针 #38669010532](https://github.com/CP11-gh/CRM/actions/runs/38669010532)从 Runner 与运行中 backend 各发送一次无凭据、无有效模型参数的固定 POST，均在 `101-500ms` 总耗时分档收到 4xx；DNS/TCP/TLS 与首字节阶段均为 `0-100ms`。原样证据和 SHA-256 见 [R43 TR](../reports/tests/TR-MVP-005-20261015-R43.md)。这只说明探针时刻该路径可快速拒绝无效请求，不能验证真实生成；R41 的 34 次超时仍未定位。G4 `PARTIAL`、production No-Go。

2026-10-15 G4 R41/R42：一次获批的 [R41 live #38662963980](https://github.com/CP11-gh/CRM/actions/runs/38662963980) 中 34 条真实模型样本全部 `LLM_TIMEOUT`，仅 2 条本地故障注入通过；不能据此判断 Prompt 质量。[R42 只读探针 #38665764165](https://github.com/CP11-gh/CRM/actions/runs/38665764165) 显示 Runner 和运行后端均收到无凭据 HTTPS 4xx，容器 DNS/TCP/TLS 通过，证明当时基础传输通畅，但未重现模型生成超时。原样证据与哈希见 [R41 TR](../reports/tests/TR-MVP-005-20261015-R41.md)、[R42 TR](../reports/tests/TR-MVP-005-20261015-R42.md)。本次付费 live 授权已用完，G4 `PARTIAL`、production No-Go。

2026-10-14 G4 R40 staging：获批的[六摘要预取 #38550506209](https://github.com/CP11-gh/CRM/actions/runs/38550506209)、[validate #38551198566](https://github.com/CP11-gh/CRM/actions/runs/38551198566)、[deploy #38551532509](https://github.com/CP11-gh/CRM/actions/runs/38551532509) 均从 main `2d164767` 通过；后端运行摘要为 `sha256:ee48ee38…335daa`，迁移头、三健康、固定出口与 Webhook 只读通过。零调用 [prepare #38552161363](https://github.com/CP11-gh/CRM/actions/runs/38552161363) 在 Runner 核对新摘要及冻结 36 条；四份原始证据与哈希见 [R40 TR](../reports/tests/TR-MVP-005-20261014-R40.md)。R37 live 仍是最新模型质量结果：35/36、Provider 故障 1、机器 `passed=false`。G4 `PARTIAL`、production No-Go。

2026-10-14 G4 R39 单次获批后端镜像发布：[工作流 #38548833793](https://github.com/CP11-gh/CRM/actions/runs/38548833793) 从 main `3d8e0d5` 发布 `ghcr.io/cp11-gh/crm-backend@sha256:ee48ee38…35daa`，linux/amd64 manifest `PASS`，压缩层 110,072,001 字节；原样证据及 SHA-256 见 [R39 TR](../reports/tests/TR-MVP-005-20261014-R39.md)。未部署 staging、未调用 DeepSeek；R37 35/36、Provider 故障 1、机器 `passed=false` 仍为真实质量结果，G4 `PARTIAL`、production No-Go。

2026-10-14 G4 R38 低敏诊断源码候选：subject `ae3fa29` 将后续结构失败分为 `invalid_json`/`invalid_schema`，仅 Schema 失败最多记录八组白名单字段路径与错误类型；未知值映射固定枚举，不存原文。受影响测试 102 passed，完整后端在最终类型标注整理前 1782 passed/19 skipped，整理后 mypy 172 源文件通过，PR CI 待验，详见 [R38 TR](../reports/tests/TR-MVP-005-20261014-R38.md)。未发布镜像或部署，R37 的 35/36、Provider 故障 1、机器 `passed=false` 仍为现场事实；G4 `PARTIAL`、production No-Go。

2026-10-14 G4 R37 单次获批真实复测：main `1aa1dee` 的 [prepare #38542493623](https://github.com/CP11-gh/CRM/actions/runs/38542493623) 对运行后端 `sha256:61c00d69…95e1881` 锁定 36 条冻结样本且 Provider 0 调用；[live #38542949502](https://github.com/CP11-gh/CRM/actions/runs/38542949502) 调用 34 条合成样本加 2 条本地故障注入，35/36、危险逃逸 0、合法误拦 0、Provider 故障 1，机器 `passed=false`。多语言政策首稿缺审核组 1，修复调用 `LLM_OUTPUT_INVALID / invalid_structure` 后安全转人工；该类别尚不能细分 JSON 与 Schema 问题。配置估算 USD 0.027265（非账单），本次授权已用完。两份原始低敏证据及哈希见 [R37 TR](../reports/tests/TR-MVP-005-20261014-R37.md)。G4 `PARTIAL`、production No-Go。

2026-10-14 G4 R36 staging：用户另行授权的 [六角色预取 #38536657630](https://github.com/CP11-gh/CRM/actions/runs/38536657630)、[validate #38538873665](https://github.com/CP11-gh/CRM/actions/runs/38538873665)、[deploy #38539305810](https://github.com/CP11-gh/CRM/actions/runs/38539305810) 均从 main `401b0e5` 通过；后端切到 `sha256:61c00d69…95e1881`，前端/检索不变，迁移头、三健康和固定出口通过，Webhook 只读。[prepare #38540054971](https://github.com/CP11-gh/CRM/actions/runs/38540054971) 独立核对运行中后端摘要、冻结 36 条且 Provider 调用 0。四份原始低敏证据及哈希见 [R36 TR](../reports/tests/TR-MVP-005-20261014-R36.md)。未运行新版 `live`；R33 的 35/36、Provider 故障 1、机器 `passed=false` 仍是最新真实质量结果。G4 `PARTIAL`、production No-Go。

2026-10-14 G4 R35 镜像发布：用户精确授权的 [publish-backend-image #38534500772](https://github.com/CP11-gh/CRM/actions/runs/38534500772) 从 main `b6c05fc` 发布单个私有后端候选，摘要 `sha256:61c00d69…95e1881`；[原样低敏证据](../../release/evidence/staging/crm-staging-g4-r35-image-38534500772.json) 确认 linux/amd64 manifest `PASS`、压缩层 110,068,396 字节、最大层 33,257,734 字节，见 [R35 TR](../reports/tests/TR-MVP-005-20261014-R35.md)。尚未部署 staging 或再次调用 DeepSeek；G4 `PARTIAL`、production No-Go。

2026-10-14 G4 R34 源码候选：从 main `6727cd8` 增加低敏 Provider 错误码与固定输出失败类别，subject `beb002f` 本地完整后端 1780 passed/3 skipped/2 warnings，Ruff 和工作流 YAML/PowerShell 语法通过；本地 mypy 无响应；PR #181 前后端 CI（含 mypy）通过并合入 main `53c22e4`。未发布镜像、部署 staging 或调用 DeepSeek；最近现场仍是 [R33 live](../reports/tests/TR-MVP-005-20261014-R33.md) 的 35/36、Provider 故障 1、机器 `passed=false`。详见 [R34 TR](../reports/tests/TR-MVP-005-20261014-R34.md)。G4 `PARTIAL`、production No-Go。

2026-10-14 G4 R33 现场：[prepare #38527631807](https://github.com/CP11-gh/CRM/actions/runs/38527631807) 在 main `d262f440` 和 R31 后端 `sha256:1c3a8e83…fc21f0` 上锁定冻结 36 条，Provider 0 调用；用户单次授权的 [live #38528027351](https://github.com/CP11-gh/CRM/actions/runs/38528027351) 为 35/36=97.22%，危险逃逸 0、合法误拦 0、Provider 故障 1，机器 `passed=false`。否定说明已通过；多语言政策首稿缺审核步骤，第二次调用记为 `provider_failed` 并转人工，仍是唯一失败；工作流日志另有一条未绑定样本的 `deepseek_output_invalid`。配置估算 USD 0.027232（非账单）。见 [R33 TR](../reports/tests/TR-MVP-005-20261014-R33.md)。G4 `PARTIAL`、production No-Go，本次付费授权已用完。

2026-10-14 G4 R32 staging 部署：经单独授权，从 main `3d6859a` 依序完成[六摘要预取 #38517947272](https://github.com/CP11-gh/CRM/actions/runs/38517947272)、[validate #38519678056](https://github.com/CP11-gh/CRM/actions/runs/38519678056)、[deploy #38520023020](https://github.com/CP11-gh/CRM/actions/runs/38520023020)。运行后端为 R31 `sha256:1c3a8e83…fc21f0`；前端/检索不变，迁移头已应用，三健康 200，固定出口 `38.55.145.52`，Webhook 仍只读。公网只读复核三个健康端点也各为 200。详见 [R32 TR](../reports/tests/TR-MVP-005-20261014-R32.md)。本版尚未运行 `prepare/live`；R30 两条逐项失败仍待复核，G4 `PARTIAL`、production No-Go。

2026-10-14 G4 R31 镜像发布：用户本次授权的 [publish-backend-image #38516990486](https://github.com/CP11-gh/CRM/actions/runs/38516990486) 从 main `e48ab395` 生成单个私有 `crm-backend`；[机器证据](../../release/evidence/staging/crm-staging-g4-r31-image-38516990486.json) 记录不可变摘要 `sha256:1c3a8e83…fc21f0`、linux/amd64 manifest `PASS`、压缩总量 110,069,185 字节和最大层 33,258,817 字节。尚未部署 staging 或调用 DeepSeek；R30 仍是最新 live，G4 `PARTIAL`。

2026-10-14 G4 R31 本地候选：Prompt `real-model-eval-v1.2.11` 对页面否定展示和证据充足的多语言政策修复增加明确约束。subject `fb7a58f` 的定向请求契约 34 passed；完整后端 1778 passed、19 skipped、2 warnings，Ruff、格式和 mypy 通过，见 [R31 TR](../reports/tests/TR-MVP-005-20261014-R31.md)。该源码验证阶段未发布镜像、部署 staging 或调用 DeepSeek；下方 R30 仍是最新现场，G4 `PARTIAL`、production No-Go。

2026-10-14 G4 最新现场：staging 后端 `sha256:a38855fa…5f5da5` 的 [live #38509348666](https://github.com/CP11-gh/CRM/actions/runs/38509348666) 在 main `012df0b` 上完成；36 条冻结集含 34 条 DeepSeek 样本与 2 条本地注入，终态 34/36=94.44%，危险逃逸、合法误拦和 Provider 故障均为 0，机器 `passed=true`，配置估算 USD 0.026979（非账单）。条件政策第二稿通过；否定说明缺必需组 0、多语言政策第二稿转人工且缺组 0、1。两条逐项失败未闭环，完整 G4 保持 `PARTIAL`、production No-Go；见 [R30 TR](../reports/tests/TR-MVP-005-20261014-R30.md)。

2026-10-14 R27 历史现场：main `60bf105` 的诊断后端[ live #38496772348](https://github.com/CP11-gh/CRM/actions/runs/38496772348) 为 33/36、合法误拦 1、机器 `passed=false`；当时条件政策第二稿被 DLP 拒绝、多语言政策第二稿由模型转人工、否定说明缺必需组 0，见 [R27 TR](../reports/tests/TR-MVP-005-20261014-R27.md)。该结论已被上方 R30 新现场取代。

2026-10-14 G4 R28 本地候选：`v1.2.10` 仅强化第二次 DLP 再生成的分隔符约束，不改 DLP、冻结评分或安全开关。定向先红后绿，最终 `57 passed`；完整后端 `1777 passed, 19 skipped, 2 warnings`，Ruff 全量/格式与 mypy 通过，见 [R28 TR](../reports/tests/TR-MVP-005-20261014-R28.md)。源码经 PR #165/#167 合入 main `c7f464c`，一次获批的[后端镜像发布](../../release/evidence/staging/crm-staging-g4-r28-image-38504855995.json)已验证摘要与层大小。

2026-10-14 G4 R29 staging：六摘要预取、validate、deploy 和零调用 prepare 均通过，见 [R29 TR](../reports/tests/TR-MVP-005-20261014-R29.md)。后端运行 `sha256:a38855fa…5f5da5`，迁移头已应用、三健康与固定出口通过，Webhook 保持只读；prepare 锁定 36 条样本、Provider 调用 0。后续 live 结果见上方 R30，G4 `PARTIAL`。

2026-10-13 最新 G4 现场：main `cd36685` 的 `v1.2.9` 后端已在 staging 通过六角色预取、validate/deploy、三健康与固定出口；[prepare](../../release/evidence/ai/crm-staging-g4-r24-prepare-38411143806.json) 确认 36 条冻结集且 Provider 0 调用。[live #38413001338](https://github.com/CP11-gh/CRM/actions/runs/38413001338) 终态 33/36=91.67%，危险逃逸 0、合法误拦 1、Provider 故障 0；三次疑似分隔符再生成成功恢复两次，条件政策仍安全转人工。否定缺项与多语言修复无草稿仍失败；机器 `passed=false`，G4 和 production 未放行。配置估算 USD 0.027002，非账单。见 [R25 TR](../reports/tests/TR-MVP-005-20261013-R25.md)。源码确定性验证见 [R24 TR](../reports/tests/TR-MVP-005-20261013-R24.md)。

2026-10-13 上一轮 G4 现场：离线政策证据指代修复 subject `dbb65f5` 经 [PR #152](https://github.com/CP11-gh/CRM/pull/152) 合入 main `6c6a82d`，后端 `sha256:4ab4d7ce…73c50` 已在 staging 通过六摘要预取、validate/deploy、三健康与固定出口；[prepare](../../release/evidence/ai/crm-staging-g4-r22-prepare-38398089685.json) 0 调用。[live #38398552906](../../release/evidence/ai/crm-staging-g4-r22-live-38398552906.json) 首轮 32/34，终态 31/36=86.11%，危险逃逸 0、合法误拦 2、Provider 失败 0，配置估算 USD 0.024512（非账单）。政策指代样本通过；三条分隔符疑似、一条否定缺项、一条多语言修复无草稿仍失败，机器报告 `passed=false`，G4 与 production 未放行。见 [R23 TR](../reports/tests/TR-MVP-005-20261013-R23.md)。

2026-10-13 上一轮 G4 现场：main `7690960` 的 Prompt `v1.2.8` 后端已部署 staging，[prepare](../../release/evidence/ai/crm-staging-g4-v128-prepare-38388814954.json) 0 调用；[live #38389129411](https://github.com/CP11-gh/CRM/actions/runs/38389129411) 首轮 32/34，终态 30/36=83.33%，危险逃逸 0、合法误拦 3、Provider 失败 0、配置估算 USD 0.024482（非账单）。[低敏报告](../../release/evidence/ai/crm-staging-g4-v128-live-38389129411.json)显示三条 `LOCATION_SEPARATORS`、一条否定缺项、一条政策证据不足、一条修复无合格草稿。G4 与 production 仍未通过。

Prompt `real-model-eval-v1.2.8` 的源码测试先红后绿，完整后端 `1765 passed, 19 skipped, 2 warnings`，mypy、Ruff/格式通过，最终 subject 的受影响测试 `51 passed`。后续现场发布、部署和 live 结果见 [R21 TR](../reports/tests/TR-MVP-005-20261013-R21.md)；模型是否按短句指令稳定输出仍需后续验证。

2026-10-13 G4 诊断候选后端镜像 `sha256:bb38fa09…e7d80` 已发布，但首次六角色预取 #38363713490 在第 1/6 项后端原生 `docker pull` 挂起后受控取消；没有部署。修复候选 `f78350e12b85840e8f5ddc1036c2792caf702339` 把三种受审仓库的全部缺失摘要改用已验证的 OCI 分块续传。本机完整回归 `1758 passed, 19 skipped, 2 warnings`，Ruff/格式、标准 mypy、PowerShell 解析通过。PR #146 已合入 main；新预取 #38369618427 的六摘要通过，第 1 项由 OCI 分块导入，validate #38371623054 与 deploy #38372083732 均通过，运行后端 `sha256:bb38fa09…e7d80`，三健康 200、固定出口匹配、Webhook 只读。G4 质量仍独立验收，production No-Go。

| 主题 | 已有结论 | 尚缺内容 |
|---|---|---|
| M00 基础设施 | Split-ingress Rootless staging 已通过真实 DNS/TLS、两台主机部署、迁移头、容器/公网健康、隧道恢复和公司负载零变化验收；内部运行凭据已轮换，外部四项凭据已安全注入；PostgreSQL/MinIO 备份已在隔离目标恢复；2026-09-30 六摘要预取、候选部署、上一版实际切回和候选切返均通过，见 `TR-MVP-008-20260930-R01`。2026-10-08 代理配置改用持久源码后正式部署和再次重启通过，见 `TR-MVP-STAGING-PROXY-PERSIST-001-20261008-R01` | 外部平台实际接受验证和 production 放行；MinIO 原业务桶为空，真实业务对象恢复尚无样本；G6 连续五日仍未验证 |
| M01 管理端/工作台 | 认证、权限、看板、会话、知识、团队、Agent 和人工消息主流程有自动化覆盖；本机生产构建浏览器 22/22、前端契约 41/41；新缓存修复已仅部署 staging，公网精确 HTML `no-store`、指纹 JS `immutable` | 带身份 staging 全按钮浏览器复验及真实 TikTok 业务验收 |
| M02 数据与任务 | PostgreSQL/pgvector、Redis、Worker、幂等、审计和店铺隔离有模块/综合测试 | 真实负载、长稳和灾难恢复 |
| M03 平台集成 | TikTok 首次 OAuth、Scope、Token 生命周期、六项非物流只读和跨店失败关闭有 staging 真实证据；2026-10-09 最新 job `connected`、临时密文清空、匹配成功审计 1 条，按用户新口径 G1 核心通过；Webhook、普通消息和 `unknown` 对账已有确定性检查 | G1-L 通用 `202309` 轨迹按用户新口径已通过；CBT 增强 `202604` 待适用订单，不再阻断 G8；G2 真实订阅/投递、G3 人工消息和对账未完成；G4 逐项闭环、G5/G6 门禁仍缺；同一 callback 现场重放未验但不再阻断 G1 核心 |
| M04 AI 与 RAG | Provider、DLP、结构化声明、知识审批、工具边界及 BGE 已覆盖；[R56 live](../reports/tests/TR-MVP-005-20261016-R56.md) 为 36/36、危险逃逸 0、合法误拦 0、Provider 故障 0，机器 `passed=true` | G4 冻结合成质量通过；真实买家闭环、50 客户端 SSE、实际独立解决率与五日稳定性另验；公开自动回复/营销未放行 |

2026-10-12 真实 `v1.2.4` 复测中上一轮西语英译与一条否定说明恢复，英文条件政策的必需内容也恢复；`negation-open-002` 缺冻结组 0，`condition-open-002` 仍命中未引用禁用词。原始报告只保留组/词序号及布尔提示，不能还原模型草稿。本机 `v1.2.4` 源码完整测试 `1718 passed, 19 skipped, 2 warnings`，Ruff、格式、mypy 和工作流静态解析通过；这是已被下一段 `v1.2.5` 现场结果取代的历史快照。

`v1.2.5` 已随 PR #129 合入 main，先红后绿与完整后端回归 `1719 passed, 19 skipped, 2 warnings`、Ruff/格式/mypy 为源码验证。2026-10-13 已分别获批发布、部署及一次 live，见 [R11 TR](../reports/tests/TR-MVP-005-20261013-R11.md)；现场为 34/36，否定说明恢复、条件政策仍失败且弃购样本新失败。模型正文未留存，不以本地或旧版结果代替本次现场事实。

`v1.2.6` 的 Prompt 契约新增两类通用输出前检查，测试先红后绿；完整后端 `1720 passed, 19 skipped, 2 warnings`，Ruff、格式和 mypy 通过，见 [R12 TR](../reports/tests/TR-MVP-005-20261013-R12.md)。现已分别获批发布、部署和一次真实模型复测，见 [R13 TR](../reports/tests/TR-MVP-005-20261013-R13.md)：弃购样本通过，条件政策仍失败，售后样本新失败。两条逐项失败继续阻断 G4。

`v1.2.7` 源码已由 [PR #137](https://github.com/CP11-gh/CRM/pull/137) 合入 main：售后与条件政策 Prompt 收敛为正向流程，聚焦契约先红后绿，完整后端 `1720 passed, 19 skipped, 2 warnings`，Ruff、格式、mypy 和 PR 双 CI 通过，见 [R14 TR](../reports/tests/TR-MVP-005-20261013-R14.md)。此后分别获批的镜像发布、staging 部署与一次真实模型复测见 [R15 TR](../reports/tests/TR-MVP-005-20261013-R15.md)：售后本轮恢复，条件政策仍失败，多语言样本新增缺项；G4 保持部分通过。

2026-10-08 渠道页状态修复仅更新了 staging 前端：PR #96 的前后端 CI 通过，单镜像发布、六角色预取、预检和部署通过；现场前端摘要、11 容器、迁移头与三个公网健康接口已核对，随后公网五路径仍为 200，见 [低敏证据](../../release/evidence/staging/crm-staging-frontend-only-rollout-20261008.json)。内置浏览器页面读取超时且用户无法刷新，先前“有成功提示”的回答已撤回；带身份提示和新的真实 OAuth callback 仍待验，不能据此关闭 G1。

2026-10-09 Edge 保留的新 callback 为 303，最新 job `connected`，因此上次 TikTok 授权页的“连接失败”不是本次最新任务的结果。新标签页打开旧 Network 项未产生第二次 callback GET，重放仍未验收。增强物流对五笔不同的 TikTok 配送订单均返回平台业务码 `11007009`；已确认固定出口、所需 Scope 和 `shop_cipher`，但 CBT 首程适用订单及平台开通状态未知。后端 TikTok 只读聚焦测试本次 26 passed。见 [低敏诊断证据](../../release/evidence/staging/crm-staging-g1-live-diagnostics-20261009.json)，G1 未签署。

2026-10-09 后续用户将 G1 本阶段验收限定为首次真实授权完成、Scope/Token 生命周期、非物流只读和隔离，现场二次 callback GET 不再阻断；增强物流 `202604` 独立留在 G1-L，最终 G8 前仍须通过。只读复核最新 job 为 `connected`、完成且无错误、临时密文字段为空、匹配成功审计 1 条、渠道 connected；因此按**新口径**，G1 核心范围在 staging 通过。G2 启动前的当时预检显示 Partner Center 订阅数 0、staging 真实只读与 Webhook 开关均为 false；后续部署状态见下段，真实投递仍未验证。见 [低敏关闭与预检证据](../../release/evidence/staging/crm-staging-g1-core-closure-20261009.json)；production 和 G8 未放行。

2026-10-09 G2 候选分支完成签名先验、重复通知正文校验、未绑定店铺失败关闭、乱序消息会话排序保护及受限 staging 开关的本机预检。另备仅发布当前 main 后端镜像的工作流。TikTok 平台定向测试 33 passed；完整后端 `1696 passed, 3 skipped, 2 warnings`；staging 门禁测试 `151 passed, 3 skipped`；Ruff 检查/格式和 mypy 通过。公网 `/v1/webhooks/tiktok` 的无签名 GET 为 405、ready 为 200、TLS 校验结果 0。当前主机 SSH 公钥被 staging 拒绝，浏览器工具未提供已登录 Partner Center 会话；本次没有新订阅查询、配置切换或真实事件投递。见 [低敏预检证据](../../release/evidence/staging/crm-staging-g2-preflight-20261009.json)。本机通过仅证明代码/配置契约，G2 仍待现场验收。

2026-10-09 后续 G2 预备代码由 PR #101 合入 main `81ed505bf85e70ecf09c11594ad4479be262a346`；单个 backend 镜像发布、六角色不可变摘要预取、staging 显式 G2 模式 validate/deploy 均通过。部署证据显示受审后端摘要、迁移头、三个公网健康 200、固定出口及只读/Webhook 开关；独立公网复核 ready/渠道页为 200、无签名 Webhook GET 为 405、TLS 校验为 0。新只读订阅诊断候选 `c46f3d4b1016cd6fa004450c5202207b121f682a` 的后端测试 `1698 passed, 3 skipped, 2 warnings`，Ruff、mypy、工作流 PowerShell 解析及 PR #102 后端/前端 CI 通过；该候选尚未合入或运行。订阅现状和官方真实投递仍未验，G2 未通过。见 [后端发布与部署部分证据](../../release/evidence/staging/crm-staging-g2-backend-rollout-20261009.json)。

2026-10-09 PR #102 此后合入 main `4707e531845f4c016081341c17032e12e6fb408a`，只读运行 `37879307329` 核对当时订阅数 0、预期地址匹配数 0，无外部写入，见[写入前订阅读取证据](../../release/evidence/staging/crm-staging-g2-subscription-read-20261009.json)。一次性 `NEW_MESSAGE` 注册候选 `4bb25c9ee6e12caf1a956598658b6ca2bd800877` 的正确项目入口 `uv run pytest -q` 结果 `1704 passed, 18 skipped, 2 warnings`；六项定向测试、Ruff、mypy 170 文件、YAML 与两个 PowerShell run 块解析通过。第一次显式指定测试目录因未载入项目配置导致 14 个 `_support` 导入在收集阶段失败，已用规定入口重跑通过。该段测试与执行前状态均为历史快照；最新订阅状态见下段。

2026-10-09 PR #103 合入 main `253a6cf0f563aae85b15ea7447a3589f203484b1` 后，用户精确授权的一次 workflow `37881350331` 对固定 `NEW_MESSAGE`/staging 地址执行一次 PUT，HTTP 200，写后 GET 确认订阅数 1、地址匹配数 1。独立只读 workflow `37881477237` 再次确认订阅数 1、主题仅 `NEW_MESSAGE`、预期地址匹配数 1、其他地址数 0；两个 artifact 的 SHA-256 见[低敏证据](../../release/evidence/staging/crm-staging-g2-subscription-confirmed-20261009.json)。尚无官方真实事件进入、处理、重试、乱序、审计或恢复切换的现场证据，G2 保持未通过。

2026-10-09 只读事件观测候选分支 `feature/mvp003-g2-event-observer` 的 6 项聚焦测试通过；Ruff 检查/格式、脚本 mypy 和两个工作流 PowerShell run 块语法解析通过。脚本在任何 SELECT 前设置数据库只读事务，输出固定数量字段；工作流将核对 main SHA 与已运行 backend 摘要。尚未合入或在 staging 运行，不能据此推断真实事件已投递。

2026-10-09 PR #105 后端/前端 CI 通过并合入 main `8e1d3cf74ef0cbec2e6c172d620f4cdba66878fe`。只读 staging 工作流 `37883016283` 核对运行中 backend 摘要、只读事务和唯一已连接渠道后成功上传低敏基线：订阅确认时间之后的 `NEW_MESSAGE` 事件 0、签名有效事件 0、处理成功 0、TikTok 入站消息累计 0、未绑定事件 0。artifact SHA-256 见[基线证据](../../release/evidence/staging/crm-staging-g2-event-baseline-20261009.json)。没有可据此判为真实投递的事件，G2 未通过。

2026-10-09 06:17Z main 745d79f6cacfdb0b1356d2c73aa86928667d7193 的 staging 只读工作流 37892709909 再次成功：运行后端摘要匹配，订阅窗口内 NEW_MESSAGE 事件 0、签名有效 0、入站消息 0、未绑定事件 0。artifact ID/SHA-256 见[低敏复核](../../release/evidence/staging/crm-staging-g2-no-trigger-20261009.json)。用户报告买家侧电脑和手机均无商家聊天入口、无受控测试买家既有会话；此项是用户报告，不是机器对平台入口原因的证明。真实投递、重试、乱序仍未验，G2 不通过。

2026-10-09 G3 顺序例外的离线复核：基线 main `0f80d3f804b425b8aca53e1f8b34939e52b6e89d`，在 Windows 工作树 `src/backend` 执行 `uv run pytest -q -c pyproject.toml ../tests/backend/platform/test_tiktok_write.py ../tests/backend/domain/test_phase3_domain.py ../tests/backend/agent/test_tool_executor.py`，结果 55 passed、1 Starlette/httpx 弃用 warning。检查覆盖 TikTok 单次普通文本请求和签名、固定出口失败不直连、未确认不发送、超时及不完整响应进入 `unknown`、旧未知消息阻断后续真实写、管理员对账记录。以上仅为确定性离线检查；未启用 staging 真实写，未使用受控平台会话，未发送外部消息，不能判定 G3 通过。

2026-10-10 G3 中断后安全补丁已由 main `6e975148650bfd8e6cb0b7980b86554345caf5d0` 发布为单个 backend 私有镜像；六角色预取、G2 模式预检和 staging 部署通过，迁移头、固定出口、三个公网健康端点和运行后端摘要均核对成功，见 [TR R02](../reports/tests/TR-MVP-004-20261010-R02.md)与[低敏证据](../../release/evidence/staging/crm-staging-g3-backend-rollout-20261010.json)。真实消息写仍关闭，`NEW_MESSAGE`/入站消息仍为零，G3 真实发送、`unknown` 对账及恢复未验证。

2026-10-09 G3 安全补丁（PR #109 已合入 main）：隔离 PostgreSQL 红测证明，旧 `processing` 出站消息与 `running` 工具调用存在时，新幂等键原先仍可触发一次平台发送；修复后，同店铺真实 TikTok 发送在提交新的 `processing` 前使用店铺行锁串行化，并同时阻断 `processing` 和 `unknown`。同一回归转绿；全新 `postgres-test` 数据库由项目脚本迁移并完成后端完整回归 `1726 passed, 3 skipped, 2 warnings`，随后只停止并移除该测试容器。`ruff check`、`ruff format --check` 和 `mypy app scripts` 均通过。未发布镜像、未部署 staging、未启用真实写；遗留 `processing` 的人工恢复流程和受控会话真实发送仍待验，G3 不通过。

## BGE 正式基线

- 质量：Dense Recall@20 = 100%，Rerank Recall@5 = 100%，MRR = 1，nDCG = 1，引用合法率 = 100%，无答案拒判率 = 100%。
- 接受阈值：Dense 相似度 `0.52`。
- RTX 4060 8GB 单实例容量：50 并发零失败；Embedding P99 = 375.22 ms；Reranker P99 = 1966.59 ms；显存峰值 = 3697 MB；冷启动 = 24.256 s。
- 机器证据：`release/evidence/retrieval/bge-quality-threshold-052-20260821.json`、`bge-capacity-gpu-gate-20260821.json`、`bge-gpu-runtime-20260821.json`。

这些结果固定模型、硬件、数据集与当时配置，不自动外推到其他模型 Revision、GPU、并发模型或生产网络。

## 当前未关闭风险

- `MVP-READONLY-LOG-001` 的源码门禁见 `TR-MVP-READONLY-LOG-001-20260928-R01`；staging 现有后端上的六项非物流真实只读重测见 `TR-MVP-G1-NONLOG-001-20260928-R01`。后者只证明这六项路径成功，不覆盖增强物流、重复回调或 G1 签署；真实 Token 自然刷新另见 `release/evidence/staging/crm-staging-g1-natural-token-refresh-20261008.json`。日志部署与增强物流的单独记录仍在 PR #56 草稿中。

- G4 R56 的一次真实模型冻结综合集为 36/36，历史逐项失败已闭环；仍缺实际买家闭环、端到端 SSE 首 Token、本期 G6 连续 48 小时稳定性及实际 AI 独立解决率证据。低敏报告不保存模型原文；后续任何候选仍须保留严格判分和冻结集。
- 用户已确认真实 TikTok US 店铺授权后自动返回 CRM；仍未完成整个店铺端到端验收，不能确认 production Scope、投递和消息行为。
- `MVP-OAUTH-REAUTH-001` 的一次真实 staging 重新授权任务终态、临时材料清除、审计匹配及 job 查询原用户边界已核对，详见 `TR-MVP-OAUTH-REAUTH-001-20260928-R01`；重复状态轮询与确定性测试不等于同一真实 callback 重放，G1 仍未签署。
- TikTok Partner Center 与 DeepSeek 外部四项凭据已安全注入 staging；DeepSeek 已通过本次 34 条合成请求确认接受，TikTok 各真实能力按对应 G1/G2/G3 证据判断；未获放行的能力继续失败关闭。
- 本期 G6 连续 48 小时至少 99.5% 稳定性正在采集，尚未到验收终点；50 客户端 SSE 的当前受限结论以 `RELEASE-GATES.md` 的 G5 行为准。
- 隔离备份恢复子项见 `TR-MVP-008-RESTORE-001-20260929-R01`；兼容上一版实际镜像回滚及候选切返见 `TR-MVP-008-20260930-R01`。活动 MinIO 业务桶为空，字节级恢复仅用隔离合成对象验证；两项均不证明 production 活动卷可直接覆盖或 G8 最终联合签署。

## 管理端本机交互回归

`MVP-UI-CACHE-001` 的 subject `7617647965278198b2712b678007bc3ad6fbbe98` 在本机生产构建服务、合成 API 响应上完成 22/22 浏览器测试、0 跳过；三个 HTML 路由返回 `no-store`，带指纹 JS 仍为 `immutable`，无店铺营销页显示创建店铺引导。前端契约 41/41、类型检查、构建与 lint（0 error、既有 2 warning）通过。修复前生产构建的 `/login` 为 `s-maxage=31536000`。这是本机候选结论，staging 实际部署与入口缓存另验，见 `TR-MVP-UI-CACHE-001-20260924-R01`。

候选 `8c13a9f1df0e71e3c3e7bb7916a1f1422b5a1820` 在本机 Chrome、合成 `/v1/` 响应上完成 20/20 浏览器用例，开发服务和 production build 两次均通过；前端契约 41/41，lint 0 error/2 条既有 warning，typecheck、build 与生产依赖 audit 通过。PR #43 的前后端 CI 均通过，已 squash 合入 main `c9e49b88f54807f37b72c4c93ad1d66e554acc7d`。覆盖无店铺加载、过期 URL 店铺范围、表单与 OAuth 前置反馈、Agent 日志和会话筛选旧请求竞态。详见 `TR-MVP-UI-001-20260923-R01`。这不替代真实 staging、TikTok 店铺授权或 production 验收；含开发依赖的既有 `js-yaml` 高危项仍待独立处理。

## 管理端 staging 镜像部署冒烟

2026-09-24 首次三新摘要部署 `35949846192` 因新检索镜像下载停滞而在容器切换前取消，失败事实保留于 `release/evidence/staging/crm-staging-html-cache-rollout-attempt-20260924.json`。用户随后仅对**本次 staging** 重新授权复用旧检索摘要；混合摘要预检 `35953530870` 和部署 `35953792293` 通过，新 backend/frontend 实际运行，旧检索镜像依赖锁偏差如实保留。PR #49 的 staging vhost 关闭继承代理缓存，PR #50 的入口脚本接受唯一合法首页 307；两者已合并。公网无 query 的 `/login`、`/marketing`、`/knowledge`、`/settings/stores` 均 200/no-store，指纹 JS 200/immutable，三条健康 200，双机最终入口脚本通过；公司 system Docker 和其他 vhost 摘要不变。详见 `TR-MVP-UI-CACHE-DEPLOY-001-20260924-R01` 与终态机器证据。带身份 staging 全按钮和真实 TikTok 仍未执行，production 不变。

`main=58263b1...` 的新 backend/frontend 摘要已由 staging 工作流 `35849490309` 部署并经现场 inspect 确认；旧检索镜像只按本次明确授权保留，依赖锁偏差见 `TR-MVP-UI-DEPLOY-001-20260923-R01`。入口、迁移头、固定出口和三个公网健康端点通过，`/login`、渠道、知识、营销公开路由及 Next 静态 JavaScript 返回 200。此为部署冒烟，不等于带身份的逐按钮浏览器回归、真实店铺授权或 production 验收。

## 域名契约迁移验证

候选 `10428b4501fd470a5a671676edcdc00e75180844` 已将 staging/production 固定域名统一为 `staging.overselfx.com` / `www.overselfx.com`。完整后端回归为 `1538 passed, 12 skipped, 3 warnings`，Ruff、格式、mypy、锁文件和旧域名扫描通过。该候选当时只证明仓库内契约一致；后续 staging DNS/TLS 与部署结论见下节，Partner Center 与真实 OAuth/Webhook 仍未执行。

## Split-ingress staging 部署验证

最终候选 subject `c0f1e6f0a5c575190b71541be3f67b3163780d61` 已将域名契约落地为真实 staging；它与已部署运行配置 `98460796...` 的受审运行资产零差异。PR #25 CI 为 `1559 passed, 12 skipped, 3 warnings`，前端 40/40 测试及 production build 通过；staging-only deploy `35561109568` 完成不可变镜像、迁移头和三个公网健康端点验证。真实隧道恢复、端口隔离、Nginx/TLS 与公司系统 Docker 零变化详见 `TR-MVP-STAGING-001-20260919-R01`。该结论只关闭 staging 基础设施 AC-01～AC-10，不替代 G1～G6 真实业务与稳定性验收。

## Staging 内部凭据轮换验证

候选 subject `83da7cc67a5e799d1d3aa9a6fb50253abbe523f8` 记录 2026-09-21 真实轮换终态。PostgreSQL、MinIO、JWT、检索令牌已轮换，TikTok 凭据加密主密钥已生成；独立审计从成功恢复副本读取旧值，确认 PostgreSQL/MinIO/检索旧值拒绝、新值接受，四个应用容器取得新配置，全部真实能力开关保持 false。三个公网 HTTPS 健康端点为 200，响应和轮换后日志未命中凭据；系统 Docker、边缘 Nginx 和隧道边界未变。历史结果见 `TR-MVP-001-20260921-R01` 与 `release/evidence/staging/crm-staging-credential-rotation-20260921.json`；当时外部凭据缺失，R01 为 `PARTIAL`。

## Staging 外部凭据安全注入验证

候选 subject `4ffb888a6af59a25333d6c984273fd1a89abff09` 绑定 2026-09-23 现场注入事实。TikTok App Key、Service ID、App Secret 与 DeepSeek API Key 已由受限 SSH 通道注入 staging，四个应用容器按职责取得字段，真实能力开关全部 false；Mock 专用 `TIKTOK_WEBHOOK_SECRET` 保持空。三个公网 HTTPS 健康端点均 200，日志/响应未命中四项值，出口仍为 `38.55.145.52`，系统 Docker 清单未变。一次性工具首次在预变更阶段因 cwd 权限失败，旧状态经独立复核，修正后成功。局部后端回归 201 passed、1 warning；不是全量回归，也未调用真实 TikTok/DeepSeek。R02 `TR-MVP-001-20260923-R02` 结论 `PASS` 只适用于 MVP-001 注入范围；G0 恢复/回滚、G1/G2/G4 和 production 仍待独立验收。

## TikTok 固定出口 staging 验证

候选 subject `746c10cacf7b2e1e827317e9759e203dc0cc9551` 的 PR #37 CI 后端/前端均通过；proxy 刷新修复的门禁测试为 `103 passed, 2 skipped`。真实 staging deploy `35806983990` 观测配置/实际出口均为 `38.55.145.52`、迁移头应用、三个公网端点 200。只停止出口 helper 后验证器非零，恢复后再次观测固定 IP；两台服务器的入口、GitLab 和其他站点保护基线未发生业务漂移。当前运行的 backend/frontend 镜像与候选构建输入零差异，旧检索镜像有依赖差异；两项仅限 staging 的用户授权及 GHCR 下载阻断均见 `TR-MVP-EGRESS-001-20260923-R02` 和机器证据。该结论不覆盖真实 TikTok 店铺、DeepSeek、恢复演练或 production。

## 本次根目录迁移验证口径

本次将产品代码恢复到源提交 `77d9f8f` 并提升到仓库根，验证范围为 Git 历史、目录结构、活动路径引用、JSON 可解析和首版 Rootless Staging 关键资产。按用户要求不执行完整后端回归、前端安装/构建或真实平台门禁，且历史测试结果不得被描述为本分支重新运行结果。
