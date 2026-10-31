---
record_id: TR-MVP-AGENT-TEMPLATE-UI-STAGING-001-20261031-R01
record_type: test
revision: R01
status: PASS
task_id: MVP-AGENT-TEMPLATE-UI-STAGING-001
tested_sha: d6de3be766d6656eadfe8e410dff6981c01fea4a
requirement_ids:
- MVP-AGENT-TEMPLATE-UI-STAGING-001
acceptance_ids:
- AC-01
- AC-02
- AC-03
- AC-04
created_at: '2026-10-31T08:22:48.825247+00:00'
updated_at: '2026-10-31T08:22:48.825247+00:00'
supersedes: null
implementation_record: docs/records/implementation/IR-MVP-AGENT-TEMPLATE-UI-STAGING-001-20261031-R01.md
environment: staging / rootless Docker / real authenticated public API / synthetic-only
  DeepSeek and bound-document RAG
deployed_source_sha: 6074c4b001aa37e1653db3a3a7f226dd3e2077e3
integration_base_sha: 743eb782904e39065c1a9d8779749f4af613198c
---

文档交付候选 subject 为 `d6de3be766d6656eadfe8e410dff6981c01fea4a`；该SHA仅绑定本轮发布说明与静态校验，实际构建/运行/模型测试对象单列 `deployed_source_sha=6074c4b001aa37e1653db3a3a7f226dd3e2077e3`。不能将文档候选误认为运行镜像，也不将后合入工作台源码算作部署验证。


# 本轮测试与证据

本报告只验证冻结的运行来源 `6074c4b001aa37e1653db3a3a7f226dd3e2077e3`；不把历史3145项本地结果或后合入工作台变更算作本轮现场验证。

| 验证 | 本轮结果 |
|---|---|
| 原版/候选 ValidateOnly、官方 Deploy | validated / validated / passed；完整摘要、受审源码、共享锁 |
| 备份与迁移 | env/PG/MinIO私有备份；目录可读；047→048 |
| 运行 | 12服务；3公网健康200；固定出口通过；原开关逐项一致 |
| 认证与CSRF负向 | 未登录401；不匹配CSRF403 |
| 搜索及批量配置 | 店铺搜索/空态、两店有效预览、确认后后台完成；不复制回复偏好和本店文件 |
| 实际模型与绑定文档 | 最终8项通过：冻结中文自动、英文自动、强制中文/英文、简洁/共情、坐席中文/英文；专业语气随强制语言覆盖，友好随自动覆盖 |
| 工具/引用 | 每项原始 `tool_events` 中 search_knowledge/retrieved，并引用本轮真实已索引/审批文件 |
| 原生流式 | 每项 draft 在result之前；首草稿4500～7154ms，最终6801～12045ms；不等同3秒性能门禁 |
| UI | 批量任务下拉选择及两店完成结果；未提交选店离开确认；真实模板分组、可选模板职责说明移除；同排版本/选店；两店多选后搜索XBM仍保留两店；无可见翻页；截图哈希见JSON |
| 清理 | 7 Agent/4文件软删、2模板归档；2完成审计保留；无自建买家/分类；原配置比对不变；零外发 |

# 语气结论与边界

本轮验证四种语气枚举的配置、发布冻结及运行链路，未做独立语义评分或风格盲评。简洁场景有多段编号及合成资料免责声明，不能据此断言其总字数总是少于其他语气，也不能将8项机器checks当作四语气语义效果全绿。此前本地语义评测单独引用，不冒充本轮现场结果。

# 保留的失败与复测

第一次合成审批参数把technical_artifact配成generic，服务端422正确拒绝，文件清理后改为合法none。测试脚本最初错误读取旧tool_calls字段，又把新search_knowledge的retrieved状态误认作succeeded；保留失败原件，最终严格按真实V2原始tool_events和文件引用重新核对，不改产品阈值。

完整8项矩阵有一次forced_cn的坐席翻译返回translation_unavailable；客户中文正文、检索和引用保持。对该项明确复测成功，最终8项为7矩阵项＋1重试项，不能说一次全绿或零随机失败。复测后的模板续测遇10分钟凭证过期401；没有放宽认证，按额外精确批准完成清理。两店批次已由前两轮实际确认成功，本轮不重复制造通过。

浏览器工具21～43秒单次，截图＋跳转曾超时；复读实际DOM后通过店铺选项文字完成多选，不把失败命令当成功。没有真实TikTok订单/物流只读回归、买家发送、production发布、数据库降级或恢复演练。本轮RAG是真实绑定合成文件，不是本地假工具。

正式机器结果：[发布证据](../../../release/evidence/staging/crm-staging-agent-template-ui-20261031.json)。原始响应、SSE时序与本轮脚本均保留在集中临时输出根，正式JSON记录SHA-256。

# 精确命令与集中原件

TEST_LAYOUT: centralized。下列命令从本轮隔离工作树根执行，Python为既有Python3.11运行时；所有命令脚本、原始输出、SSE逐事件和截图保留在 `src/tests/.artifacts/agent-template-ui-staging-20261031/`（已忽略，不提交构建包/凭证），正式低敏JSON登记对应SHA-256。

```text
git archive --format=tar --output <本轮临时目录>/release-source.tar 6074c4b001aa37e1653db3a3a7f226dd3e2077e3
docker buildx build --platform linux/amd64 --provenance=false --label org.opencontainers.image.revision=6074c4b001aa37e1653db3a3a7f226dd3e2077e3 --label org.opencontainers.image.source=https://github.com/CP11-gh/CRM -f <本轮干净源码>/src/docker/Dockerfile.backend --output type=oci,dest=<本轮临时目录>/backend-release.oci.tar <本轮干净源码>/src/backend
docker buildx build --platform linux/amd64 --provenance=false --label org.opencontainers.image.revision=6074c4b001aa37e1653db3a3a7f226dd3e2077e3 --label org.opencontainers.image.source=https://github.com/CP11-gh/CRM -f <本轮干净源码>/src/docker/Dockerfile.frontend.prod --output type=oci,dest=<本轮临时目录>/frontend-release.oci.tar <本轮干净源码>/src/frontend
python <本轮临时目录>/publish_oci.py backend
python <本轮临时目录>/publish_oci.py frontend
python <本轮临时目录>/remote.py <本轮临时目录>/backup.sh <本轮临时目录>/backup.log
python <本轮临时目录>/remote_authenticated_gate.py CurrentValidate
python <本轮临时目录>/remote_authenticated_gate.py CandidateValidate
python <本轮临时目录>/remote_authenticated_gate.py Deploy
python <本轮临时目录>/transfer-images.py
python <本轮临时目录>/remote.py <本轮临时目录>/import-images.sh <本轮临时目录>/import-images.log
python <本轮临时目录>/remote_authenticated_gate.py CandidateValidate
python <本轮临时目录>/remote_authenticated_gate.py Deploy
python <本轮临时目录>/run-acceptance.py
python <本轮临时目录>/run-acceptance.py forced_cn
python <本轮临时目录>/run-cleanup.py
python <本轮临时目录>/audit-owned.py
python <本轮临时目录>/evaluate-acceptance.py
git diff --check
```

`<本轮临时目录>` 固定指上述集中目录，`<本轮干净源码>` 为该目录下release-source；占位仅去除本机绝对目录，不改变实际参数。首次Deploy的TLS失败和第二次成功均留原件。浏览器使用已登录Codex页进行DOM观察/选项文字点击/搜索填写/任务下拉切换/截图，未注入fetch或提取登录凭据。
