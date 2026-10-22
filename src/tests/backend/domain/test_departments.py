"""部门组织归属与既有店铺权限相互独立。"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.shared.exceptions.errors import AppError
from app.users.department_schemas import DepartmentCreate


def test_department_management_routes_are_registered() -> None:
    """部门和成员管理有明确独立接口。"""
    paths = TestClient(app).get("/openapi.json").json()["paths"]
    assert "/v1/settings/departments" in paths
    assert "/v1/settings/departments/{department_id}" in paths
    assert "/v1/settings/departments/{department_id}/members" in paths
    assert "/v1/settings/departments/{department_id}/members/{member_id}" in paths


@pytest.mark.asyncio
async def test_department_outside_actor_store_scope_is_not_visible(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.users import department_service

    department_id = uuid.uuid4()
    session = SimpleNamespace(
        get=AsyncMock(return_value=Mock(id=department_id)),
        scalars=AsyncMock(return_value=Mock(all=Mock(return_value=[uuid.uuid4()]))),
    )
    monkeypatch.setattr(department_service, "allowed_store_ids", AsyncMock(return_value={uuid.uuid4()}))

    with pytest.raises(AppError) as error:
        await department_service._visible_department(session, Mock(), department_id)  # type: ignore[arg-type]
    assert error.value.status_code == 404


def test_department_name_cannot_be_only_whitespace() -> None:
    with pytest.raises(ValueError, match="部门名称不能为空"):
        DepartmentCreate(name="   ", store_ids=[uuid.uuid4()])


@pytest.mark.asyncio
async def test_removing_department_member_never_changes_rbac_assignments(monkeypatch: pytest.MonkeyPatch) -> None:
    """移除部门只删除组织关系，不撤销账号角色或店铺权限。"""
    from app.users import department_service

    department_id = uuid.uuid4()
    member_id = uuid.uuid4()
    actor = SimpleNamespace(id=uuid.uuid4())
    session = SimpleNamespace(execute=AsyncMock(return_value=Mock(rowcount=1)), add=Mock(), commit=AsyncMock())
    monkeypatch.setattr(department_service, "_visible_department", AsyncMock(return_value=(Mock(), [uuid.uuid4()])))

    await department_service.remove_member(session, actor, department_id, member_id)  # type: ignore[arg-type]

    statements = [str(call.args[0]) for call in session.execute.call_args_list]
    assert any("department_members" in statement for statement in statements)
    assert all("user_roles" not in statement for statement in statements)
    session.commit.assert_awaited_once()
