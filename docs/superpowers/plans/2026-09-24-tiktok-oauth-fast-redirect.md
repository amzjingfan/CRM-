# TikTok OAuth 快速回跳实施计划

基线 `7adb26927a717b3fca04056e779bd09bd05d9c75`；分支 `fix/mvp002-oauth-redirect-20260924`；仅 staging。设计见同日 `specs/2026-09-24-tiktok-oauth-fast-redirect-design.md`。

1. 在集中测试目录先写失败的 callback/重复回调、worker 成功/失败/崩溃、状态查询权限和前端进度测试。
2. 增加可回滚的短期任务表及 ORM；实现 Redis state 只读校验、加密任务创建、现有 worker 处理、受限状态接口和前端进度反馈。不改 TikTok 平台签名、真实读取或消息写入契约。
3. 运行后端相关单测/集成、迁移升降级、前端测试/构建、lint/typecheck、安全检查；同步 API/SYSTEM、任务、IR/TR/RR 和索引。
4. `MVP-OAUTH-REDIRECT-001` 经审查与 CI 合并短期分支；另以 `MVP-OAUTH-REDIRECT-DEPLOY-001` 单独部署 staging，验证迁移、健康、回调响应时延、重放拒绝及 OAuth 真实回跳。卖家类型门禁若未解除，只能记录实测受阻，不宣称回跳现场通过。
5. 回跳真实通过后再执行 `MVP-002` G1 只读门禁：Scope、Token 生命周期、仅聚合输出的店铺/订单/物流/会话读取及隔离；所有写入能力保持关闭。production 不在本次授权内。
