"""Resume an immutable GHCR image through checked HTTP ranges, then import OCI."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import os
import re
import subprocess
import tarfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import requests

REPOSITORY = "cp11-gh/crm-retrieval-model-service"
IMAGE_PREFIX = f"ghcr.io/{REPOSITORY}@"
ALLOWED_REPOSITORIES = frozenset(
    {
        "cp11-gh/crm-backend",
        "cp11-gh/crm-frontend",
        REPOSITORY,
    }
)
ACCEPT = ", ".join(
    (
        "application/vnd.oci.image.index.v1+json",
        "application/vnd.oci.image.manifest.v1+json",
        "application/vnd.docker.distribution.manifest.list.v2+json",
        "application/vnd.docker.distribution.manifest.v2+json",
    )
)
RANGE_SIZE = 1024 * 1024
RETRIES = 8


def checked_digest(value: str) -> str:
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
        raise ValueError("Expected an immutable lowercase SHA-256 digest")
    return value.removeprefix("sha256:")


def checked_image_reference(image: str) -> tuple[str, str]:
    match = re.fullmatch(r"ghcr\.io/(cp11-gh/[a-z-]+)@(sha256:[0-9a-f]{64})", image)
    if match is None or match.group(1) not in ALLOWED_REPOSITORIES:
        raise ValueError("Only reviewed GHCR repositories and immutable SHA-256 digests are allowed")
    return match.group(1), match.group(2)


def file_matches(path: Path, digest: str, size: int) -> bool:
    if not path.is_file() or path.stat().st_size != size:
        return False
    actual = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            actual.update(block)
    return actual.hexdigest() == checked_digest(digest)


class Registry:
    def __init__(self, docker_config: Path, repository: str) -> None:
        if repository not in ALLOWED_REPOSITORIES:
            raise ValueError("Only reviewed GHCR repositories are allowed")
        with docker_config.open(encoding="utf-8") as source:
            encoded = json.load(source)["auths"]["ghcr.io"]["auth"]
        username, password = base64.b64decode(encoded).decode("utf-8").split(":", 1)
        if not username or not password:
            raise ValueError("GHCR Docker credentials are unavailable")
        self._auth = (username, password)
        self._repository = repository
        self._bearer = ""
        self._expires_at = 0.0
        self._lock = threading.Lock()

    def _token(self, force: bool = False) -> str:
        with self._lock:
            if force or time.monotonic() >= self._expires_at:
                response = requests.get(
                    "https://ghcr.io/token",
                    params={
                        "scope": f"repository:{self._repository}:pull",
                        "service": "ghcr.io",
                    },
                    auth=self._auth,
                    timeout=(15, 45),
                )
                response.raise_for_status()
                payload = response.json()
                self._bearer = payload["token"]
                self._expires_at = time.monotonic() + min(max(int(payload.get("expires_in", 300)) - 30, 30), 120)
            return self._bearer

    def get(self, path: str, *, byte_range: tuple[int, int] | None = None) -> bytes:
        for attempt in range(RETRIES):
            headers = {
                "Authorization": f"Bearer {self._token()}",
                "Accept": ACCEPT,
                "Accept-Encoding": "identity",
            }
            if byte_range is not None:
                headers["Range"] = f"bytes={byte_range[0]}-{byte_range[1]}"
            try:
                response = requests.get(
                    f"https://ghcr.io/v2/{self._repository}/{path}",
                    headers=headers,
                    timeout=(15, 120),
                )
                if response.status_code == 401:
                    self._token(force=True)
                    continue
                response.raise_for_status()
                if byte_range is not None:
                    start, end = byte_range
                    expected_prefix = f"bytes {start}-{end}/"
                    if (
                        response.status_code != 206
                        or not response.headers.get("Content-Range", "").startswith(expected_prefix)
                        or len(response.content) != end - start + 1
                    ):
                        raise ValueError("GHCR returned an invalid byte range")
                return response.content
            except (requests.RequestException, ValueError) as error:
                if attempt == RETRIES - 1:
                    raise RuntimeError(
                        f"GHCR request failed after {RETRIES} attempts ({type(error).__name__})"
                    ) from None
                time.sleep(min(2**attempt, 20))
        raise RuntimeError("GHCR request retries exhausted")


def save_checked_bytes(path: Path, data: bytes, digest: str, size: int) -> None:
    if len(data) != size or hashlib.sha256(data).hexdigest() != checked_digest(digest):
        raise ValueError("GHCR descriptor bytes do not match the immutable digest")
    if path.exists():
        if not file_matches(path, digest, size):
            raise ValueError(f"Existing cache blob differs from {digest}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    with temporary.open("xb") as target:
        target.write(data)
    temporary.replace(path)


def fetch_manifest(registry: Registry, root: Path, digest: str, size: int | None) -> dict[str, Any]:
    data = registry.get(f"manifests/{digest}")
    if size is not None and len(data) != size:
        raise ValueError("GHCR manifest descriptor size mismatch")
    path = root / "blobs" / "sha256" / checked_digest(digest)
    save_checked_bytes(path, data, digest, len(data))
    return json.loads(data)


def download_blob(registry: Registry, root: Path, descriptor: dict[str, Any], workers: int) -> Path:
    digest = str(descriptor["digest"])
    size = int(descriptor["size"])
    if size <= 0:
        raise ValueError("GHCR blob descriptor size must be positive")
    hex_digest = checked_digest(digest)
    final = root / "blobs" / "sha256" / hex_digest
    if final.exists():
        if not file_matches(final, digest, size):
            raise ValueError(f"Existing cache blob differs from {digest}")
        print(f"Verified cached blob {hex_digest[:12]} ({size} bytes)", flush=True)
        return final
    if size <= RANGE_SIZE:
        save_checked_bytes(final, registry.get(f"blobs/{digest}"), digest, size)
        print(f"Verified complete blob {hex_digest[:12]} ({size} bytes)", flush=True)
        return final
    parts = root / "parts" / hex_digest
    parts.mkdir(parents=True, exist_ok=True)
    count = math.ceil(size / RANGE_SIZE)

    def fetch_part(index: int) -> Path:
        start = index * RANGE_SIZE
        end = min(start + RANGE_SIZE, size) - 1
        part = parts / f"{index:06d}.part"
        if part.exists() and part.stat().st_size == end - start + 1:
            return part
        if part.exists():
            raise ValueError(f"Existing range part has the wrong size: {index}")
        data = registry.get(f"blobs/{digest}", byte_range=(start, end))
        temporary = parts / f"{index:06d}.tmp-{os.getpid()}-{threading.get_ident()}"
        with temporary.open("xb") as target:
            target.write(data)
        temporary.replace(part)
        return part

    missing = [index for index in range(count) if not (parts / f"{index:06d}.part").exists()]
    print(
        f"Fetching blob {hex_digest[:12]}: {size} bytes, {count - len(missing)}/{count} ranges cached",
        flush=True,
    )
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(fetch_part, index) for index in missing]
        for completed_count, completed in enumerate(as_completed(futures), start=1):
            completed.result()
            if completed_count % 16 == 0 or completed_count == len(futures):
                print(
                    f"Blob {hex_digest[:12]}: {count - len(missing) + completed_count}/{count} ranges cached",
                    flush=True,
                )
    final.parent.mkdir(parents=True, exist_ok=True)
    temporary_final = final.with_name(final.name + f".tmp-{os.getpid()}")
    actual = hashlib.sha256()
    written = 0
    try:
        with temporary_final.open("xb") as target:
            for index in range(count):
                part = parts / f"{index:06d}.part"
                expected = min(RANGE_SIZE, size - index * RANGE_SIZE)
                if part.stat().st_size != expected:
                    raise ValueError(f"GHCR range part has the wrong size: {index}")
                with part.open("rb") as source:
                    data = source.read()
                actual.update(data)
                target.write(data)
                written += len(data)
        if written != size or actual.hexdigest() != hex_digest:
            raise ValueError(f"GHCR blob SHA-256 verification failed: {digest}")
    except Exception:
        temporary_final.unlink(missing_ok=True)
        raise
    temporary_final.replace(final)
    print(f"Verified complete blob {hex_digest[:12]} ({size} bytes)", flush=True)
    return final


def write_layout(root: Path, image: str, descriptor: dict[str, Any]) -> None:
    repository, _ = checked_image_reference(image)
    (root / "oci-layout").write_text('{"imageLayoutVersion":"1.0.0"}', encoding="ascii")
    wrapper = {
        "schemaVersion": 2,
        "mediaType": "application/vnd.oci.image.index.v1+json",
        "manifests": [
            {
                **descriptor,
                "annotations": {
                    "containerd.io/distribution.source.ghcr.io": repository,
                    "io.containerd.image.name": image,
                    "org.opencontainers.image.ref.name": f"@{descriptor['digest']}",
                },
            }
        ],
    }
    (root / "index.json").write_text(json.dumps(wrapper, separators=(",", ":")), encoding="utf-8")


def import_layout(root: Path, image: str, digests: list[str], ctr_socket: str) -> None:
    repository, _ = checked_image_reference(image)
    command = [
        "/usr/bin/ctr",
        "--address",
        ctr_socket,
        "--namespace",
        "moby",
        "images",
        "import",
        "--local",
        "--digests",
        "--platform",
        "linux/amd64",
        "--base-name",
        f"ghcr.io/{repository}",
        "-",
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    if process.stdin is None:
        raise RuntimeError("Unable to open OCI import stream")
    try:
        with tarfile.open(fileobj=process.stdin, mode="w|") as archive:
            for relative in ("oci-layout", "index.json"):
                archive.add(root / relative, arcname=relative, recursive=False)
            for digest in sorted(set(digests)):
                hex_digest = checked_digest(digest)
                relative = f"blobs/sha256/{hex_digest}"
                archive.add(root / relative, arcname=relative, recursive=False)
    finally:
        process.stdin.close()
    if process.wait() != 0:
        raise RuntimeError("Rootless containerd OCI import failed")
    inspected = subprocess.run(
        ["docker", "image", "inspect", "--format", "{{json .RepoDigests}}", image],
        check=True,
        capture_output=True,
        text=True,
    )
    if image not in json.loads(inspected.stdout):
        raise RuntimeError("Rootless Docker did not retain the exact requested RepoDigest")


def prefetch(image: str, docker_config: Path, root: Path, ctr_socket: str, workers: int) -> None:
    repository, digest = checked_image_reference(image)
    if workers < 1 or workers > 16:
        raise ValueError("Range worker count must be between 1 and 16")
    if ctr_socket != "/run/user/1004/docker/containerd/containerd.sock":
        raise ValueError("OCI import requires the crmdeploy Rootless containerd socket")
    if os.geteuid() != 1004:
        raise ValueError("OCI import must run as crmdeploy UID 1004")
    if os.environ.get("DOCKER_HOST") != "unix:///run/user/1004/docker.sock":
        raise ValueError("OCI import requires the crmdeploy Rootless Docker socket")
    os.umask(0o077)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if root.is_symlink() or root.stat().st_uid != 1004:
        raise ValueError("OCI cache root must be owned by crmdeploy and not be a symlink")
    registry = Registry(docker_config, repository)
    index = fetch_manifest(registry, root, digest, None)
    if index.get("mediaType") != "application/vnd.oci.image.index.v1+json":
        raise ValueError("Expected the reviewed OCI image index")
    choices = [
        descriptor
        for descriptor in index.get("manifests", [])
        if descriptor.get("platform", {}).get("os") == "linux"
        and descriptor.get("platform", {}).get("architecture") == "amd64"
    ]
    if len(choices) != 1:
        raise ValueError("Expected one linux/amd64 image manifest")
    platform_descriptor = choices[0]
    manifest = fetch_manifest(registry, root, platform_descriptor["digest"], int(platform_descriptor["size"]))
    blobs = [manifest["config"], *manifest["layers"]]
    if len(blobs) < 2:
        raise ValueError("Image manifest contains no layers")
    for descriptor in blobs:
        download_blob(registry, root, descriptor, workers)
    index_bytes = (root / "blobs" / "sha256" / checked_digest(digest)).stat().st_size
    write_layout(
        root,
        image,
        {
            "mediaType": index["mediaType"],
            "digest": digest,
            "size": index_bytes,
        },
    )
    print("All requested OCI content verified; importing into Rootless Docker", flush=True)
    import_layout(
        root,
        image,
        [digest, platform_descriptor["digest"], *(item["digest"] for item in blobs)],
        ctr_socket,
    )
    print(f"Exact Rootless Docker RepoDigest verified: {image}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--docker-config", required=True, type=Path)
    parser.add_argument("--cache-dir", required=True, type=Path)
    parser.add_argument("--ctr-socket", required=True)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    prefetch(args.image, args.docker_config, args.cache_dir, args.ctr_socket, args.workers)


if __name__ == "__main__":
    main()
