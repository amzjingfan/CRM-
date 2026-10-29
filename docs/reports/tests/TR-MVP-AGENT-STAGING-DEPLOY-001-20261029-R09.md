---
record_id: TR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R09
record_type: test
revision: R09
status: PARTIAL
task_id: MVP-AGENT-STAGING-DEPLOY-001
tested_sha: 7fce34ef954d398af29de8ef36c62978fa58f8c2
created_at: '2026-10-29T20:56:01+08:00'
updated_at: '2026-10-29T20:56:01+08:00'
supersedes: docs/reports/tests/TR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R08.md
implementation_record: docs/records/implementation/IR-MVP-AGENT-STAGING-DEPLOY-001-20261029-R09.md
requirement_ids:
- MVP-AGENT-STAGING-DEPLOY-001
acceptance_ids:
- AC-01
- AC-02
- AC-03
- AC-04
---

# 本地最终验证

10新增行为测试RED9failed/1passed→GREEN；五个相关文件独立审查者运行46passed。覆盖中英精简、UTF-16 emoji、再复核、删除隐私不回流、精简伪造事实拒绝、同稿超长、短稿不追加模型调用、缺证语言和用量累加。

最终隔离PG/pgvector、迁移041，绝对src/tests/.artifacts cache目录：2571passed/3Windows POSIX条件skip/2依赖warning。Ruff全路径check/format、mypy255、uv lock通过。动态协议16和确定性安全237通过，不能当作真实模型质量。前端树与aa/0fb相同，复用R07同树52契约/142生产浏览器、类型和构建，本次未重跑前端全套。

# 真实模型候选预检

独立进程校验aa模块源hash后，仅载入3个候选模块并修正进程内函数引用；未写运行服务源码或环境。仍使用正常权限、当前买家、DeepSeek和同一审批文件v1。最终Prompt下英文formal32.280秒、1875字、英文、唯一文档事实及1引用；缺政策英文6.857秒310字、中文6.077秒75字，均无发送。英文负例检索可能命中说明“非真实政策”的测试块，正确澄清不要求机械零引用。

# 必须保留的失败与未完成

首次收集因未显式指定pyproject而agent导入失败，修正命令后行为RED；首次全量2570pass/1根布局失败/3skip，源于相对cache目录生成5个根tests缓存，独立可恢复隔离后重跑。首候选英文formal30.962秒因模型未缩短、answer_too_long隐藏正文；补充目标计数和长度优先级后通过。aa英文物流两次首次失败随后模型重试成功；aa英文缺证兜底语言失败保持原结果。最终本subject尚未发布，需公开中英调试、工作台、字数和双语缺证复测及统一夹具清理；任务总体PARTIAL。
