"""管理员账号变更不泄露密码，也不能留下旧会话。"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.audit.models import AuditLog
from app.auth.security import hash_password, verify_password
from app.shared.database.base import User
from app.users import service as team_service


@pytest.mark.asyncio
async def test_admin_password_reset_bumps_auth_version_and_audits_without_secret() -> None:
    """密码重置后所有旧令牌版本失效，审计只记录动作。"""
    actor = User(id=uuid.uuid4(), email="admin@example.com", name="管理员")
    member = User(
        id=uuid.uuid4(),
        login_name="agent_1",
        email=None,
        name="客服一",
        password_hash=hash_password("PreviousPass123!"),
        auth_version=0,
    )
    session = SimpleNamespace(get=AsyncMock(return_value=member), add=Mock(), commit=AsyncMock())

    await team_service.change_member_password(session, actor, member.id, "NewPassword123!")  # type: ignore[arg-type]

    assert verify_password("NewPassword123!", member.password_hash)
    assert member.auth_version == 1
    audits = [call.args[0] for call in session.add.call_args_list if isinstance(call.args[0], AuditLog)]
    assert len(audits) == 1
    assert audits[0].action == "team.member.password_change"
    assert audits[0].after_data == {"password_changed": True}
