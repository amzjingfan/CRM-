# 测试证据目录

本目录保存测试工程师生成的低敏聚合证据。不得写入客户原文、FAQ 完整正文、模型完整向量、API Key 或内部服务 Token。

正式测试结论以 `测试工程师/` 下的 Markdown 报告为准，JSON 文件仅用于复现指标和审计计算过程。

2026-08-21 BGE 生产门禁证据：

- `bge-quality-threshold-052-20260821.json`：真实 BGE 质量、拒判和阈值校准结果。
- `bge-capacity-gpu-gate-20260821.json`：RTX 4060 批量与 50 并发结果。
- `bge-gpu-runtime-20260821.json`：GPU 设备、进程冷启动、显存峰值和日志 OOM 汇总。
- `bge-production-gate-20260821.json`：首次质量校准及 GPU 容量基线，保留追溯。
- `bge-capacity-gate-20260821.json`：误用基础 Compose 后形成的 CPU 对照轮次，`valid_for_gpu_gate=false`，不得用于 GPU 性能结论。
