"""员工账号标识与登录凭据的边界测试。"""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.auth import service as auth_service
from app.auth.schemas import LoginRequest
from app.auth.security import decode_token, hash_password
from app.shared.database.base import User
from app.shared.exceptions.errors import AppError, ErrorCode
from app.users import service as team_service
from app.users.schemas import TeamMemberCreate, TeamRoleAssignment


def test_login_accepts_account_or_legacy_email_field() -> None:
    """新账号可直接登录，旧调用方的 email 字段仍可用。"""
    by_account = LoginRequest.model_validate({"identifier": "agent_1", "password": "ExamplePass123!"})
    by_email = LoginRequest.model_validate({"email": "admin@example.invalid", "password": "ExamplePass123!"})
    assert by_account.identifier == "agent_1"
    assert by_email.identifier == "admin@example.invalid"


def test_create_account_accepts_unique_login_without_email() -> None:
    """新账号必须有登录名，邮箱与手机号为可选联系字段。"""
    account = TeamMemberCreate.model_validate(
        {
            "login_name": "agent_1",
            "name": "客服一",
            "temporary_password": "ExamplePass123!",
            "phone": "+8613900000000",
            "timezone": "Asia/Shanghai",
            "max_concurrent_sessions": 50,
            "assignments": [{"role": "agent", "store_id": str(uuid.uuid4())}],
        }
    )
    assert account.login_name == "agent_1"
    assert account.email is None
    assert account.max_concurrent_sessions == 50


def test_legacy_email_only_creation_remains_valid() -> None:
    account = TeamMemberCreate.model_validate(
        {
            "name": "旧版客户端账号",
            "email": "legacy@example.com",
            "temporary_password": "ExamplePass123!",
            "assignments": [{"role": "agent", "store_id": str(uuid.uuid4())}],
        }
    )
    assert account.login_name is None
    assert account.email == "legacy@example.com"

    with pytest.raises(ValueError, match="登录账号或邮箱至少填写一项"):
        TeamMemberCreate.model_validate(
            {
                "name": "无标识",
                "temporary_password": "ExamplePass123!",
                "assignments": [{"role": "agent", "store_id": str(uuid.uuid4())}],
            }
        )


@pytest.mark.asyncio
async def test_team_list_reads_existing_nonassignable_role_without_allowing_new_assignment() -> None:
    """历史或测试角色可以查看，但不能经员工写入接口授予。"""
    user_id = uuid.uuid4()
    user = User(
        id=user_id,
        name="合成测试账号",
        email=None,
        status="active",
        timezone="UTC",
        max_concurrent_sessions=50,
        created_at=datetime.now(UTC),
    )
    session = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                SimpleNamespace(all=lambda: [(user_id, "g5-synthetic-role", None)]),
                SimpleNamespace(all=lambda: []),
            ]
        )
    )

    views = await team_service._views(session, [user])  # type: ignore[arg-type]

    assert views[0].assignments[0].role == "g5-synthetic-role"
    assert views[0].model_dump(mode="json")["assignments"][0]["role"] == "g5-synthetic-role"
    with pytest.raises(ValueError):
        TeamRoleAssignment(role="g5-synthetic-role", store_id=None)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_login_name_and_email_use_the_same_password_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """选择标识符只改变查找方式，不绕过密码或禁用校验。"""
    user = User(
        id=uuid.uuid4(),
        login_name="agent_1",
        email="agent@example.invalid",
        name="客服一",
        password_hash=hash_password("ExamplePass123!"),
        status="active",
    )
    by_name = AsyncMock(return_value=user)
    by_email = AsyncMock(return_value=user)
    monkeypatch.setattr(auth_service, "find_user_by_login_name", by_name)
    monkeypatch.setattr(auth_service, "find_user_by_email", by_email)
    session = SimpleNamespace(commit=AsyncMock())

    assert await auth_service.authenticate_user(session, "AGENT_1", "ExamplePass123!") is user  # type: ignore[arg-type]
    assert await auth_service.authenticate_user(session, "agent@example.invalid", "ExamplePass123!") is user  # type: ignore[arg-type]
    by_name.assert_awaited_once_with(session, "agent_1")
    by_email.assert_awaited_once_with(session, "agent@example.invalid")
    with pytest.raises(AppError) as caught:
        await auth_service.authenticate_user(session, "agent_1", "wrong-password")  # type: ignore[arg-type]
    assert caught.value.code == ErrorCode.INVALID_CREDENTIALS


@pytest.mark.asyncio
async def test_password_version_invalidates_old_access_and_refresh_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    """改密码后旧令牌不能继续访问或换发。"""
    user = User(id=uuid.uuid4(), email="admin@example.com", name="管理员", auth_version=0, status="active")
    token_data = auth_service.issue_token_data(user)
    assert decode_token(token_data.access_token, "access")["ver"] == 0
    user.auth_version = 1
    monkeypatch.setattr(auth_service, "find_user_by_id", AsyncMock(return_value=user))
    monkeypatch.setattr(auth_service, "is_refresh_token_revoked", AsyncMock(return_value=False))
    session = Mock()
    for resolver, token in (
        (auth_service.resolve_access_user, token_data.access_token),
        (auth_service.resolve_refresh_user, token_data.refresh_token),
    ):
        with pytest.raises(AppError) as caught:
            await resolver(session, token)  # type: ignore[arg-type]
        assert caught.value.code == ErrorCode.TOKEN_INVALID
