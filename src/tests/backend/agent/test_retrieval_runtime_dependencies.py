"""锁定本地 BGE 推理运行时的安全版本与离线加载边界。"""

import tomllib

from _support import BACKEND_ROOT


def test_retrieval_model_extra_uses_reviewed_security_baseline() -> None:
    """防止已处置的 Torch/Transformers 漏洞版本被意外重新引入。"""
    project_file = BACKEND_ROOT / "pyproject.toml"
    project = tomllib.loads(project_file.read_text(encoding="utf-8"))

    dependencies = set(project["project"]["optional-dependencies"]["retrieval-model"])

    assert "torch>=2.13,<2.14" in dependencies
    assert "transformers>=5.10.4,<5.11" in dependencies


def test_model_engine_keeps_offline_untrusted_code_disabled() -> None:
    """模型运行面只能读取受校验的本地资产，禁止执行仓库自定义代码。"""
    engine_file = BACKEND_ROOT / "app" / "retrieval_model_service" / "engine.py"
    source = engine_file.read_text(encoding="utf-8")

    assert source.count("local_files_only=True") == 4
    assert source.count("trust_remote_code=False") == 4
    assert "trust_remote_code=True" not in source
    assert "torch.jit.script" not in source
    assert "Trainer" not in source
