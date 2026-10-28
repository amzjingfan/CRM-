# Agent Tool Suite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成已批准 12 项业务工具及六类目录 UI，本地验收后等待部署批准。
**Architecture:** agents/tools 统一元数据和原生工具包装；业务执行复用工作台与官方只读客户端，内部协作独立持久化。管理 API 输出目录，前端无需维护工具清单。
**Tech Stack:** Python、FastAPI、Pydantic、SQLAlchemy/PostgreSQL、langchain-core @tool、Next.js/TypeScript。
**Spec:** docs/superpowers/specs/2026-10-28-agent-tool-suite-design.md

## Global Constraints

- 12 工具、6 分类、3 操作标签；保留四项人工确认提议，不发送平台消息。
- 仅本地隔离数据；不部署、不读私有密钥，不修改根 main 或其他活动 worktree。
- 服务端绑定店铺/客户/会话，模型仅引用本轮候选；知识仅显式绑定获批文件。
- 测试全部位于 src/tests，临时输出在 src/tests/.artifacts。

## Review Focus

- 多订单无选择时必须返回候选，不默认最新。
- store 切换中的迟到请求不能污染目录与协作记录。
- scope 不足不得伪装成零售后/零物流。
- 相同内部写入重试/并发只产生一条记录；不转交或外发。
- 大型物流分页的事实只能来自实际送入模型的页；冻结会话以外消息不可读取。

### Task 1: 统一目录、Schema 与分类 API

Files: agents/tools/metadata.py、access.py、catalog.py；management/schemas.py、router.py。
Interfaces: tool_catalog(session,user,store_id) -> ToolCatalogView；TOOL_METADATA；build_agent_tools(..., business_executor=None)。
- [ ] 添加 test_agent_tool_suite.py：12 个工具均有唯一类别/权限，模型可用参数不含店铺客户 ID，未知工具拒绝。
- [ ] 运行 pytest 指定测试，确认缺失目录导致失败；实现元数据和当前店铺可用性 API。
- [ ] 运行目录、配置 API 和旧工具回归，提交。

### Task 2: 十项只读能力与可信选择

Files: agents/tools/business.py、arguments.py、product_facts.py；integrations/tiktok_read.py；runtime/execution.py、worker.py；management/debug.py、runtime/formal.py。
Interfaces: AgentBusinessExecutor.invoke(name,arguments) -> dict[str,object]；候选引用只在同执行器有效。
- [ ] 测试多订单澄清、选单、伪造引用、商品、优惠、售后 scope、历史快照、完整物流分页及工具+知识组合。
- [ ] 观察失败后实现受控执行，替换预取最新订单行为；扩展原生循环的结构化事实依据。
- [ ] 运行受影响后端测试及 TikTok 只读客户端契约测试，提交。

### Task 3: 两项内部写入及可读记录

Files: agents/tools/collaboration.py、models.py；migrations/versions/040_agent_collaboration.py；shared/database/models.py；management/router.py。
Interfaces: save_collaboration(session,snapshot,run_id,kind,content)；list_collaboration(session,user,conversation_id)。
- [ ] PostgreSQL 测试同店授权、跨客户拒绝、重复/并发幂等、审计和会话状态不变。
- [ ] 实现一张内部协作记录表及可回滚迁移，按模型调用生成实际记录；API 只读展示。
- [ ] 迁移039→040→039→040及数据库测试，提交。

### Task 4: 分类卡片与协作记录 UI

Files: frontend/components/AgentToolCatalog.tsx；app/agents/page.tsx、agent-prototype.css；lib/api.ts。
- [ ] 浏览器测试六类显示、搜索/筛选/绑定、知识跳转、权限说明、跨店迟到请求和协作记录。
- [ ] 删除前端固定工具数组，接入后端目录；无新依赖，沿用现有 SVG 图标和样式。
- [ ] lint/typecheck/contract/build，生产浏览器回归与截图检查，提交。

### Task 5: 全量验证、审查、文档与交付

- [ ] 在最终 subject 提交运行适用后端/数据库/前端、AI安全/动态协议评测及迁移检查。
- [ ] 更新 PRODUCT/API/AI/SYSTEM、任务、IR/TR/RR、索引和恢复状态；两轴审查并修复发现。
- [ ] 复核授权 origin/main，创建 PR；仅 Actions 零步骤不可用时按持续授权采用完整本地证据。不得部署。

## Execution ledger

- 2026-10-28：BASE_SHA=9d6a9182ec7e9e29712e670654b757f8c767ef5d，分支 feature/agent-tool-suite-20261028；复用同仓库干净隔离工作树；根 checkout 未知文件保留。
- 目录变更前基线：既有工具目录/循环测试 7 passed。
- Ruling: 用户已确认分类并要求实施，本计划直接执行，不重复请求设计批准；不扩大为欢迎语/超时回复工具。

- 本地中间验证：原生完整目录5项、订单/商品/完整物流/售后业务与参数测试、HTML与明示分页、官方客户端契约和真实数据库协作/权限/冻结历史测试已运行；前端48契约和开发模式分类/会话/跨店浏览器用例已运行。最终 subject 的完整回归、生产构建、迁移往返和两轴审查仍待执行，不能据此标记 DONE。
- Ruling: 商品与优惠仅需店铺授权，不强制关联买家；订单/售后/客户/会话/内部写入继续要求授权会话。共用工作台店铺目录服务，避免为调试创建合成买家。
- Ruling: 候选引用按父运行和资源生成稳定不透明值；分页/不同对象的结构化事实分别保留，避免多Agent汇总混淆或覆盖。显示前重新读角色权限，撤权清空回答与派生记忆事实。
- 公开文档 UI 在本机不可读取（UI_UNAVAILABLE）；以本机官方 OAS和可读取的官方docv2搜索结果核对端点。没有访问真实模型、TikTok 或 staging。

- 本次提交前验证：新增业务/目录/商品事实与真实数据库协作19 passed；Agent开发模式浏览器6 passed，48前端契约通过。下一步固定subject并完成全量验证与两轴审查，仍未部署。

- 独立审查委派：父任务MVP-AGENT-TOOL-SUITE-001，两个只读轴standards/spec，允许读取本任务工作树，交付固定SHA的发现。首轮898bf637发现历史运单号、候选澄清依据、售后状态门禁与包裹摘要分页，均补回归修正；另补多订单记忆按scope及临时引用排除、生产浏览器保存响应同步。完整首次后端2368 passed/3 skipped，旧迁移头断言1 fail已更新为040并保留祖先校验；首次浏览器120 pass/1保存请求同步race，定向修正6 pass。最终完整复测仍待运行，不以这些中间结果替代最终验收。

- 二轮审查残余：10包裹和10条长描述同时出现仍超16000字符。改为DLP后实际序列化大小9000/4000双预算与精确offset续读；同一回归覆盖80包裹及10包裹+长描述+JSON转义字符。D5中间完整后端2375 passed/3 skipped，不能替代此最终变化的复测。
