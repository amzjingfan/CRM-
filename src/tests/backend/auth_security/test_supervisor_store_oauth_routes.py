"""主管可发起和确认 TikTok 授权，普通客服不能越权。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, require_csrf
from app.integrations.oauth_router import router
from app.shared.database.session import get_db_session
from app.shared.exceptions.errors import AppError
from app.stores.router import router as stores_router


@pytest.mark.parametrize(
    "role_code,permission_code,expected",
    [
        ("supervisor", "settings.store_authorize", 200),
        ("agent", "workspace.reply", 403),
    ],
)
def test_new_store_oauth_route_checks_authorization_permission(
    monkeypatch: pytest.MonkeyPatch, role_code: str, permission_code: str, expected: int
) -> None:
    app = FastAPI()
    app.include_router(router, prefix="/v1")

    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, error: AppError) -> JSONResponse:
        return JSONResponse(status_code=error.status_code, content={"code": error.code})

    role = SimpleNamespace(code=role_code, permissions=[SimpleNamespace(code=permission_code)])
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(roles=[role])
    app.dependency_overrides[get_db_session] = lambda: SimpleNamespace()
    app.dependency_overrides[require_csrf] = lambda: None
    start = AsyncMock(return_value={"authorization_url": "https://example.invalid", "expires_in": 600})
    monkeypatch.setattr("app.integrations.oauth_router.start_new_tiktok_store_oauth", start)
    with TestClient(app) as client:
        response = client.post("/v1/settings/stores/tiktok/oauth/start")
    assert response.status_code == expected
    if expected == 200:
        start.assert_awaited_once()
    else:
        start.assert_not_awaited()


@pytest.mark.parametrize(
    "role_code,permission_code,expected",
    [("supervisor", "settings.store_authorize", 200), ("agent", "workspace.reply", 403)],
)
def test_channel_authorization_list_checks_scoped_permission(
    monkeypatch: pytest.MonkeyPatch, role_code: str, permission_code: str, expected: int
) -> None:
    app = FastAPI()
    app.include_router(stores_router, prefix="/v1")

    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, error: AppError) -> JSONResponse:
        return JSONResponse(status_code=error.status_code, content={"code": error.code})

    role = SimpleNamespace(code=role_code, permissions=[SimpleNamespace(code=permission_code)])
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(roles=[role])
    app.dependency_overrides[get_db_session] = lambda: SimpleNamespace()
    get_channels = AsyncMock(return_value=[])
    monkeypatch.setattr("app.stores.router.get_channels", get_channels)
    with TestClient(app) as client:
        response = client.get("/v1/settings/channels")
    assert response.status_code == expected
    if expected == 200:
        get_channels.assert_awaited_once()
    else:
        get_channels.assert_not_awaited()
