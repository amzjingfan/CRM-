"""G5 合成 FAQ 准备与凭证续期的现场门禁。"""

import importlib
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest


def tool():  # type: ignore[no-untyped-def]
    return importlib.import_module("scripts.prepare_sse_staging_content")


def test_content_tool_rejects_non_staging_and_unexpected_private_batch(tmp_path: Path) -> None:
    source = tmp_path / "g5-38852775454-2.json"
    output = tmp_path / "g5-38852775454-3.json"
    source.write_text("private", encoding="utf-8")

    with pytest.raises(ValueError, match="staging"):
        tool().validate_content_paths("production", source, output, writable=False)
    with pytest.raises(ValueError, match="batch"):
        tool().validate_content_paths("staging", tmp_path / "other.json", output, writable=False)
    with pytest.raises(ValueError, match="batch"):
        tool().validate_content_paths("staging", source, tmp_path / "other.json", writable=False)


def test_content_tool_never_overwrites_an_existing_renewed_pool(tmp_path: Path) -> None:
    source = tmp_path / "g5-38852775454-2.json"
    output = tmp_path / "g5-38852775454-3.json"
    source.write_text("private", encoding="utf-8")
    output.write_text("keep", encoding="utf-8")

    with pytest.raises(ValueError, match="exists"):
        tool().validate_content_paths("staging", source, output, writable=True)
    assert output.read_text(encoding="utf-8") == "keep"


def test_private_mount_uses_runner_file_ownership_even_when_container_runs_as_root() -> None:
    parent = SimpleNamespace(st_uid=1004, st_mode=stat.S_IFDIR | 0o700)
    source = SimpleNamespace(st_uid=1004, st_mode=stat.S_IFREG | 0o600, st_size=8000)

    assert tool().private_source_metadata_is_safe(parent, source)
    assert not tool().private_source_metadata_is_safe(parent, SimpleNamespace(**{**vars(source), "st_uid": 0}))
    assert not tool().private_source_metadata_is_safe(
        parent, SimpleNamespace(**{**vars(source), "st_mode": stat.S_IFREG | 0o644})
    )
