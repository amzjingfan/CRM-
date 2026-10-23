"""文档 Worker 从 MinIO 读取时实行服务端大小上限。"""

from types import SimpleNamespace

import pytest

from app.knowledge_base import storage


def test_bounded_source_read_rejects_oversize_and_releases_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        closed = False
        released = False

        def read(self, amount: int) -> bytes:
            assert amount == 9
            return b"x" * 9

        def close(self) -> None:
            self.closed = True

        def release_conn(self) -> None:
            self.released = True

    response = Response()
    monkeypatch.setattr(storage, "_client", lambda: SimpleNamespace(get_object=lambda *_args: response))
    monkeypatch.setattr(storage, "get_settings", lambda: SimpleNamespace(minio_bucket="test"))
    with pytest.raises(ValueError, match="FILE_SIZE_INVALID"):
        storage.get_import_file("private/key", max_bytes=8)
    assert response.closed and response.released
