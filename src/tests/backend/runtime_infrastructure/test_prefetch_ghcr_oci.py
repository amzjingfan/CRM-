"""Offline checks for resumable, digest-checked GHCR layer transfer."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import threading
from pathlib import Path

import pytest
from _support import SOURCE_ROOT

SCRIPT = SOURCE_ROOT / "scripts" / "prefetch_ghcr_oci.py"
spec = importlib.util.spec_from_file_location("prefetch_ghcr_oci", SCRIPT)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FakeRegistry:
    def __init__(self, data: bytes, *, corrupt: bool = False) -> None:
        self.data = data
        self.corrupt = corrupt
        self.calls: list[tuple[int, int]] = []
        self.lock = threading.Lock()

    def get(self, _path: str, *, byte_range: tuple[int, int] | None = None) -> bytes:
        if byte_range is None:
            return self.data
        with self.lock:
            self.calls.append(byte_range)
        start, end = byte_range
        result = self.data[start : end + 1]
        if self.corrupt and start == module.RANGE_SIZE:
            return b"x" + result[1:]
        return result


def descriptor(data: bytes) -> dict[str, object]:
    return {"digest": "sha256:" + hashlib.sha256(data).hexdigest(), "size": len(data)}


def test_resumes_existing_ranges_and_verifies_complete_digest(tmp_path: Path) -> None:
    content = b"a" * module.RANGE_SIZE + b"b" * module.RANGE_SIZE + b"tail"
    item = descriptor(content)
    digest = str(item["digest"]).removeprefix("sha256:")
    part_dir = tmp_path / "parts" / digest
    part_dir.mkdir(parents=True)
    (part_dir / "000000.part").write_bytes(content[: module.RANGE_SIZE])
    registry = FakeRegistry(content)

    result = module.download_blob(registry, tmp_path, item, workers=2)

    assert result.read_bytes() == content
    assert sorted(registry.calls) == [
        (module.RANGE_SIZE, 2 * module.RANGE_SIZE - 1),
        (2 * module.RANGE_SIZE, len(content) - 1),
    ]
    module.download_blob(registry, tmp_path, item, workers=2)
    assert len(registry.calls) == 2


def test_rejects_corrupted_complete_blob(tmp_path: Path) -> None:
    content = b"a" * module.RANGE_SIZE + b"b" * 7
    registry = FakeRegistry(content, corrupt=True)
    with pytest.raises(ValueError, match="SHA-256 verification failed"):
        module.download_blob(registry, tmp_path, descriptor(content), workers=2)
    assert not (tmp_path / "blobs" / "sha256" / hashlib.sha256(content).hexdigest()).exists()


def test_small_config_is_downloaded_whole_and_digest_checked(tmp_path: Path) -> None:
    content = b"config-bytes"
    registry = FakeRegistry(content)
    result = module.download_blob(registry, tmp_path, descriptor(content), workers=2)
    assert result.read_bytes() == content
    assert registry.calls == []


def test_oci_wrapper_retains_original_index_digest(tmp_path: Path) -> None:
    digest = "sha256:" + "a" * 64
    image = f"{module.IMAGE_PREFIX}{digest}"
    module.write_layout(
        tmp_path,
        image,
        {"mediaType": "application/vnd.oci.image.index.v1+json", "digest": digest, "size": 856},
    )
    wrapper = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    assert wrapper["manifests"][0]["digest"] == digest
    assert wrapper["manifests"][0]["annotations"]["io.containerd.image.name"] == image
    assert wrapper["manifests"][0]["annotations"]["org.opencontainers.image.ref.name"] == f"@{digest}"


def test_range_request_rejects_full_body_response(monkeypatch: pytest.MonkeyPatch) -> None:
    class FullResponse:
        status_code = 200
        headers = {"Content-Length": "4"}
        content = b"data"

        def raise_for_status(self) -> None:
            return None

    registry = module.Registry.__new__(module.Registry)
    registry._token = lambda force=False: "test-only-token"
    monkeypatch.setattr(module, "RETRIES", 1)
    monkeypatch.setattr(module.requests, "get", lambda *_args, **_kwargs: FullResponse())
    with pytest.raises(RuntimeError, match="failed after 1 attempts"):
        registry.get("blobs/sha256:" + "a" * 64, byte_range=(0, 3))
