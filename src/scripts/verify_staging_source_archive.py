"""校验 Git 归档与 staging 解包内容一致，忽略宿主机 UID/GID 等元数据。"""

from __future__ import annotations

import argparse
import hashlib
import os
import stat
import sys
import tarfile
from pathlib import Path, PurePosixPath
from typing import IO


def _digest(stream: IO[bytes]) -> str:
    hasher = hashlib.sha256()
    while chunk := stream.read(1024 * 1024):
        hasher.update(chunk)
    return hasher.hexdigest()


def verify(archive: Path, source: Path, expected_sha256: str) -> None:
    if len(expected_sha256) != 64 or any(character not in "0123456789abcdef" for character in expected_sha256):
        raise ValueError("digest")
    if not source.is_dir() or archive.is_symlink() or not archive.is_file():
        raise ValueError("path")
    with archive.open("rb") as handle:
        if _digest(handle) != expected_sha256:
            raise ValueError("digest")

    expected_files: set[str] = set()
    with tarfile.open(archive, "r:") as bundle:
        seen: set[str] = set()
        for member in bundle:
            name = member.name.rstrip("/")
            relative = PurePosixPath(name)
            if not name or name.startswith("/") or "\\" in name or any(part in (".", "..") for part in relative.parts):
                raise ValueError("member")
            if name in seen:
                raise ValueError("duplicate")
            seen.add(name)
            target = source.joinpath(*relative.parts)
            if member.isdir():
                if not target.is_dir() or target.is_symlink():
                    raise ValueError("directory")
                continue
            if not member.isfile() or not target.is_file() or target.is_symlink():
                raise ValueError("file")
            archived = bundle.extractfile(member)
            if archived is None:
                raise ValueError("file")
            with archived, target.open("rb") as actual:
                if _digest(archived) != _digest(actual):
                    raise ValueError("content")
            expected_files.add(relative.as_posix())

    actual_files: set[str] = set()
    for root, directories, files in os.walk(source, followlinks=False):
        current = Path(root)
        if current == source and ".git" in directories:
            directories.remove(".git")
        for directory in directories:
            if (current / directory).is_symlink():
                raise ValueError("directory")
        for filename in files:
            path = current / filename
            if not stat.S_ISREG(path.lstat().st_mode):
                raise ValueError("file")
            actual_files.add(path.relative_to(source).as_posix())
    if actual_files != expected_files:
        raise ValueError("file set")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify one reviewed staging source archive")
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    arguments = parser.parse_args()
    try:
        verify(arguments.archive, arguments.source, arguments.sha256)
    except (OSError, ValueError, tarfile.TarError):
        print("staging source archive verification failed", file=sys.stderr)
        return 1
    print("staging source archive verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
