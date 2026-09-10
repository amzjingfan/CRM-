"""验证检索模型启动时对全部六个运行文件执行完整性校验。"""

import hashlib
import json
from pathlib import Path

import pytest

from app.retrieval_model_service.engine import RetrievalEngineError, TransformersBgeEngine

REQUIRED_MODEL_FILES = (
    "bge-m3/config.json",
    "bge-m3/pytorch_model.bin",
    "bge-m3/tokenizer.json",
    "bge-reranker-large/config.json",
    "bge-reranker-large/model.safetensors",
    "bge-reranker-large/tokenizer.json",
)
MODEL_MANIFEST = Path(__file__).resolve().parents[2] / "deploy" / "models" / "model-manifest.json"
EXPECTED_MANIFEST_MODELS = {
    "BAAI/bge-m3": {
        "revision": "5617a9f61b028005a4858fdac845db406aefb181",
        "local_path": "deploy/models/bge-m3",
        "weight_file": "pytorch_model.bin",
        "runtime_files": {
            "config.json": (687, "26159e7ad065073448460117eb24b7a4572f6f4e78eadff65dc0a11c052449fa"),
            "pytorch_model.bin": (
                2271145830,
                "b5e0ce3470abf5ef3831aa1bd5553b486803e83251590ab7ff35a117cf6aad38",
            ),
            "tokenizer.json": (
                17098108,
                "21106b6d7dab2952c1d496fb21d5dc9db75c28ed361a05f5020bbba27810dd08",
            ),
        },
    },
    "BAAI/bge-reranker-large": {
        "revision": "55611d7bca2a7133960a6d3b71e083071bbfc312",
        "local_path": "deploy/models/bge-reranker-large",
        "weight_file": "model.safetensors",
        "runtime_files": {
            "config.json": (801, "25dda0319f57e9de243c32eb7ecefa0768271afac6b5d8a94ba7f779198ab102"),
            "model.safetensors": (
                2239618772,
                "c5ae4e262c60ed2fb507ec587358285377ec36ee0a2e6da029f0534272b06d36",
            ),
            "tokenizer.json": (
                17098107,
                "9eb652ac4e40cc093272bbbe0f55d521cf67570060227109b5cdc20945a4489e",
            ),
        },
    },
}


def _write_test_assets(root: Path) -> dict[str, str]:
    """写入不含真实模型的确定性文件，并返回人工可复核的相对路径哈希。"""
    expected_hashes: dict[str, str] = {}
    for relative_path in REQUIRED_MODEL_FILES:
        content = f"test:{relative_path}".encode()
        asset_path = root / relative_path
        asset_path.parent.mkdir(parents=True, exist_ok=True)
        asset_path.write_bytes(content)
        expected_hashes[relative_path] = hashlib.sha256(content).hexdigest()
    return expected_hashes


def test_verify_assets_accepts_only_when_all_six_trusted_hashes_match(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """删除任一六文件哈希校验都会让受篡改的运行资产绕过启动门禁。"""
    expected_hashes = _write_test_assets(tmp_path)
    monkeypatch.setattr(TransformersBgeEngine, "_EXPECTED_ASSET_HASHES", expected_hashes, raising=False)
    engine = TransformersBgeEngine(
        embedding_path=tmp_path / "bge-m3",
        reranker_path=tmp_path / "bge-reranker-large",
        device="cpu",
        use_fp16=False,
        embedding_batch_size=1,
        reranker_batch_size=1,
        embedding_max_length=16,
        reranker_max_length=16,
        verify_hashes=True,
    )

    engine._verify_assets()

    for relative_path in REQUIRED_MODEL_FILES:
        asset_path = tmp_path / relative_path
        original_content = asset_path.read_bytes()
        asset_path.write_bytes(original_content + b":tampered")
        with pytest.raises(RetrievalEngineError, match="MODEL_ASSET_HASH_MISMATCH"):
            engine._verify_assets()
        asset_path.write_bytes(original_content)


def test_runtime_hash_authority_matches_the_versioned_model_manifest() -> None:
    """路径、大小、Revision 或摘要漂移会让服务器预检和容器启动得到不同结论。"""
    manifest = json.loads(MODEL_MANIFEST.read_text(encoding="utf-8"))
    assert len(manifest["models"]) == len(EXPECTED_MANIFEST_MODELS)

    manifest_hashes: dict[str, str] = {}
    for model in manifest["models"]:
        expected_model = EXPECTED_MANIFEST_MODELS[model["model_id"]]
        assert model["revision"] == expected_model["revision"]
        assert model["local_path"] == expected_model["local_path"]
        runtime_files = model["runtime_files"]
        assert len(runtime_files) == 3
        assert len({runtime_file["path"] for runtime_file in runtime_files}) == 3
        actual_runtime_files = {
            runtime_file["path"]: (runtime_file["size_bytes"], runtime_file["sha256"]) for runtime_file in runtime_files
        }
        assert actual_runtime_files == expected_model["runtime_files"]
        weight_size, weight_sha256 = actual_runtime_files[model["weight_file"]]
        assert model["weight_file"] == expected_model["weight_file"]
        assert model["weight_size_bytes"] == weight_size
        assert model["weight_sha256"] == weight_sha256
        model_dir = model["local_path"].removeprefix("deploy/models/")
        manifest_hashes.update(
            {f"{model_dir}/{path}": sha256 for path, (_size, sha256) in actual_runtime_files.items()}
        )

    assert set(manifest_hashes) == set(REQUIRED_MODEL_FILES)
    assert manifest_hashes == TransformersBgeEngine._EXPECTED_ASSET_HASHES
    assert TransformersBgeEngine.embedding_model == "BAAI/bge-m3"
    assert TransformersBgeEngine.embedding_revision == EXPECTED_MANIFEST_MODELS["BAAI/bge-m3"]["revision"]
    assert TransformersBgeEngine.reranker_model == "BAAI/bge-reranker-large"
    assert TransformersBgeEngine.reranker_revision == EXPECTED_MANIFEST_MODELS["BAAI/bge-reranker-large"]["revision"]
