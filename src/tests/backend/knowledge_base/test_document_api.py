"""通用文件 HTTP 契约、权限声明和 multipart 边界。"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.knowledge_base import document_router
from app.main import app
from app.shared.database.session import get_db_session


def test_document_routes_expose_managed_contract() -> None:
    paths = TestClient(app).get("/openapi.json").json()["paths"]
    assert "/v1/knowledge/files" in paths
    assert "/v1/knowledge/files/imports" in paths
    assert "/v1/knowledge/files/{file_id}/versions/{version_number}" in paths
    assert "/v1/knowledge/files/{file_id}/versions/{version_number}/source" in paths
    assert "/v1/knowledge/files/{file_id}/versions/{version_number}/units/{unit_index}/review" in paths
    assert "/v1/knowledge/files/{file_id}/versions/{version_number}/retry" in paths
    assert "/v1/knowledge/file-settings" in paths
    for path in ("/v1/knowledge/entries", "/v1/knowledge/files"):
        params = paths[path]["get"]["parameters"]
        assert any(item["name"] == "categorized_only" and item["in"] == "query" for item in params)
    for path in (
        "/v1/knowledge/files/imports",
        "/v1/knowledge/files/{file_id}/versions/{version_number}/units/{unit_index}/review",
        "/v1/knowledge/files/{file_id}/versions/{version_number}/retry",
    ):
        params = paths[path]["post"]["parameters"]
        assert any(item["name"] == "Idempotency-Key" and item["in"] == "header" for item in params)


def test_upload_is_bounded_before_service_acceptance(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    async def current_user() -> SimpleNamespace:
        return SimpleNamespace(id=uuid.uuid4(), roles=[SimpleNamespace(code="admin", permissions=[])])

    async def session():  # type: ignore[no-untyped-def]
        yield object()

    accept = AsyncMock()
    monkeypatch.setattr(document_router, "accept_document_import", accept)
    monkeypatch.setattr(
        document_router,
        "get_settings",
        lambda: SimpleNamespace(knowledge_file_import_max_bytes=4),
    )
    app.dependency_overrides[get_current_user] = current_user
    app.dependency_overrides[get_db_session] = session
    try:
        response = TestClient(app).post(
            "/v1/knowledge/files/imports",
            headers={"Authorization": "Bearer test", "Idempotency-Key": "upload-boundary"},
            data={"store_id": str(uuid.uuid4()), "config_json": "{}"},
            files={"file": ("a.txt", b"12345", "text/plain")},
        )
        assert response.status_code == 413
        assert response.json()["message"] == "FILE_SIZE_INVALID"
        accept.assert_not_awaited()
    finally:
        app.dependency_overrides.clear()


def test_upload_passes_frozen_strategy_and_explicit_replacement(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    store_id, file_id, version_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    async def current_user() -> SimpleNamespace:
        return SimpleNamespace(id=uuid.uuid4(), roles=[SimpleNamespace(code="admin", permissions=[])])

    async def session():  # type: ignore[no-untyped-def]
        yield object()

    accept = AsyncMock(return_value=SimpleNamespace(file_id=file_id, id=version_id, version_number=2, status="queued"))
    monkeypatch.setattr(document_router, "accept_document_import", accept)
    app.dependency_overrides[get_current_user] = current_user
    app.dependency_overrides[get_db_session] = session
    try:
        client = TestClient(app)
        path = "/v1/knowledge/files/imports"
        form = {
            "store_id": str(store_id),
            "replace_file_id": str(file_id),
            "config_json": '{"strategy":"fixed_token","chunk_size":80,"overlap":8}',
        }
        files = {"file": ("guide.txt", b"policy text", "text/plain")}
        missing_key = client.post(path, headers={"Authorization": "Bearer test"}, data=form, files=files)
        assert missing_key.status_code == 422
        response = client.post(
            path,
            headers={"Authorization": "Bearer test", "Idempotency-Key": "replace-guide-1"},
            data=form,
            files=files,
        )
        assert response.status_code == 202
        assert response.json()["data"]["version_number"] == 2
        args = accept.await_args.args
        assert args[2] == store_id and args[8] == file_id and args[9] == "replace-guide-1"
        assert args[7].strategy == "fixed_token" and args[7].chunk_size == 80 and args[7].overlap == 8
    finally:
        app.dependency_overrides.clear()
