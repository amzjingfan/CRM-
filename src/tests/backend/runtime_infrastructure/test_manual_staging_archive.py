"""手动 staging 源码包只按内容和安全路径核对，不依赖归档 UID/GID。"""

import hashlib
import subprocess
import sys
import tarfile
from pathlib import Path

from _support import SOURCE_ROOT

SCRIPT = SOURCE_ROOT / "scripts" / "verify_staging_source_archive.py"


def make_archive(tmp_path: Path) -> tuple[Path, Path, str]:
    source = tmp_path / "source"
    source.mkdir()
    (source / "src").mkdir()
    (source / "src" / "gate.ps1").write_text("safe script\n", encoding="utf-8")
    archive = tmp_path / "source.tar"
    with tarfile.open(archive, "w") as bundle:
        bundle.add(source / "src", arcname="src")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    return archive, source, digest


def verify(archive: Path, source: Path, digest: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--archive", str(archive), "--source", str(source), "--sha256", digest],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=15,
    )


def test_accepts_exact_extracted_content_despite_metadata_differences(tmp_path: Path) -> None:
    archive, source, digest = make_archive(tmp_path)
    assert verify(archive, source, digest).returncode == 0


def test_rejects_changed_extracted_content(tmp_path: Path) -> None:
    archive, source, digest = make_archive(tmp_path)
    (source / "src" / "gate.ps1").write_text("changed\n", encoding="utf-8")
    assert verify(archive, source, digest).returncode != 0


def test_rejects_untracked_extra_source_file(tmp_path: Path) -> None:
    archive, source, digest = make_archive(tmp_path)
    (source / "src" / "extra.txt").write_text("extra", encoding="utf-8")
    assert verify(archive, source, digest).returncode != 0


def test_rejects_wrong_archive_digest(tmp_path: Path) -> None:
    archive, source, _ = make_archive(tmp_path)
    assert verify(archive, source, "0" * 64).returncode != 0
