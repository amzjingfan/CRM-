"""店铺授权列表只返回当前用户可见的 TikTok 店铺。"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.shared.database.session import get_db_session
from app.shared.exceptions.errors import AppError
from app.stores import service
from app.stores.router import router


@pytest.mark.asyncio
async def test_store_authorizations_keep_store_scope_and_hide_local_revocations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    allowed_id = uuid.uuid4()
    revoked_id = uuid.uuid4()
    foreign_id = uuid.uuid4()
    stores = [SimpleNamespace(id=store_id) for store_id in (allowed_id, revoked_id, foreign_id)]
    channels = [
        SimpleNamespace(store_id=allowed_id, platform="tiktok", status="connected", authorization_status=None),
        SimpleNamespace(store_id=revoked_id, platform="tiktok", status="disconnected", authorization_status="revoked"),
        SimpleNamespace(store_id=foreign_id, platform="tiktok", status="connected", authorization_status=None),
    ]
    allowed = {allowed_id, revoked_id}
    allowed_store_ids = AsyncMock(return_value=allowed)
    list_stores = AsyncMock(return_value=stores)
    list_channels = AsyncMock(return_value=channels)
    monkeypatch.setattr(service, "allowed_store_ids", allowed_store_ids)
    monkeypatch.setattr(service, "list_stores", list_stores)
    monkeypatch.setattr(service, "list_channels", list_channels)

    rows = await service.get_store_authorizations(SimpleNamespace(), SimpleNamespace())

    assert [(store.id, channel.store_id) for store, channel in rows] == [(allowed_id, allowed_id)]
    assert allowed_store_ids.await_count == 1
    assert allowed_store_ids.call_args.args[2] == "settings.store_authorize"
    list_stores.assert_awaited_once_with(allowed_store_ids.call_args.args[0], allowed)
    list_channels.assert_awaited_once_with(allowed_store_ids.call_args.args[0], allowed)


def test_store_authorizations_require_store_authorize_permission() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/v1")

    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, error: AppError) -> JSONResponse:
        return JSONResponse(status_code=error.status_code, content={"code": error.code})

    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(roles=[])
    app.dependency_overrides[get_db_session] = lambda: SimpleNamespace()
    with TestClient(app) as client:
        response = client.get("/v1/settings/store-authorizations")
    assert response.status_code == 403


def test_supervisor_with_store_authorize_permission_can_load_store_authorizations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = FastAPI()
    app.include_router(router, prefix="/v1")

    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, error: AppError) -> JSONResponse:
        return JSONResponse(status_code=error.status_code, content={"code": error.code})

    role = SimpleNamespace(code="supervisor", permissions=[SimpleNamespace(code="settings.store_authorize")])
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(roles=[role])
    app.dependency_overrides[get_db_session] = lambda: SimpleNamespace()
    monkeypatch.setattr("app.stores.router.get_store_authorizations", AsyncMock(return_value=[]))
    with TestClient(app) as client:
        response = client.get("/v1/settings/store-authorizations")
    assert response.status_code == 200
    assert response.json()["data"] == []


@pytest.mark.asyncio
async def test_channel_list_uses_store_authorization_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    store_id = uuid.uuid4()
    allowed_store_ids = AsyncMock(return_value={store_id})
    list_channels = AsyncMock(return_value=[])
    monkeypatch.setattr(service, "allowed_store_ids", allowed_store_ids)
    monkeypatch.setattr(service, "list_channels", list_channels)

    assert await service.get_channels(SimpleNamespace(), SimpleNamespace()) == []

    assert allowed_store_ids.call_args.args[2] == "settings.store_authorize"
    list_channels.assert_awaited_once_with(allowed_store_ids.call_args.args[0], {store_id})
