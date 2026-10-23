"""基础接待文本配置服务；启用策略只改变本地配置，不触发发送。"""

import hashlib
import json
import uuid
from collections.abc import Iterable

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import AuditLog
from app.auth.store_access import allowed_store_ids
from app.reception.models import (
    ReceptionGroup,
    ReceptionMutation,
    ReceptionPolicy,
    ReceptionPolicyStore,
    ReceptionReply,
)
from app.reception.repository import (
    find_group,
    find_mutation,
    find_policy,
    find_reply,
    group_has_replies,
    group_reply_counts,
    shortcut_exists,
)
from app.reception.repository import (
    list_groups as query_groups,
)
from app.reception.repository import (
    list_policies as query_policies,
)
from app.reception.repository import (
    list_replies as query_replies,
)
from app.reception.schemas import (
    GroupCreate,
    GroupPage,
    GroupUpdate,
    GroupView,
    PolicyCreate,
    PolicyPage,
    PolicyUpdate,
    PolicyView,
    ReplyCreate,
    ReplyPage,
    ReplyUpdate,
    ReplyView,
)
from app.shared.database.base import Permission, Role, User, role_permissions, user_roles
from app.shared.exceptions.errors import AppError, ErrorCode


async def _ensure_stores(session: AsyncSession, user: User, store_ids: Iterable[uuid.UUID]) -> None:
    allowed = await allowed_store_ids(session, user)
    if not set(store_ids) <= allowed:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "资源不存在", 404)


async def _ensure_permission(session: AsyncSession, user: User, store_ids: Iterable[uuid.UUID], code: str) -> None:
    """权限与店铺角色分配同时核对，防止跨店角色的权限被混用。"""
    store_set = set(store_ids)
    if not store_set:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "资源不存在", 404)
    permitted = await _permission_store_ids(session, user, code)
    if not store_set <= permitted:
        raise AppError(ErrorCode.PERMISSION_DENIED, "没有执行该操作的权限", 403)


async def _permission_store_ids(session: AsyncSession, user: User, code: str) -> set[uuid.UUID]:
    allowed = await allowed_store_ids(session, user)
    rows = (
        await session.execute(
            select(Role.code, Permission.code, user_roles.c.store_id)
            .join(user_roles, user_roles.c.role_id == Role.id)
            .outerjoin(role_permissions, role_permissions.c.role_id == Role.id)
            .outerjoin(Permission, Permission.id == role_permissions.c.permission_id)
            .where(user_roles.c.user_id == user.id)
        )
    ).all()
    system_admin = any(role == "admin" and assigned_store is None for role, _, assigned_store in rows)
    if system_admin:
        return allowed
    return {
        store_id
        for store_id in allowed
        if any(permission == code and assigned_store in (None, store_id) for _, permission, assigned_store in rows)
    }


def _group_permission(scope: str, write: bool) -> str:
    return (
        "marketing.manage" if scope == "team" and write else "workspace.view" if scope == "team" else "workspace.reply"
    )


async def visible_group(
    session: AsyncSession,
    user: User,
    item_id: uuid.UUID,
    permission: str | None = None,
    write: bool = False,
) -> ReceptionGroup:
    group = await find_group(session, item_id, await allowed_store_ids(session, user))
    if group is None or (group.scope == "personal" and group.owner_user_id != user.id):
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "分组不存在", 404)
    await _ensure_permission(session, user, [group.store_id], permission or _group_permission(group.scope, write))
    return group


async def visible_reply(session: AsyncSession, user: User, item_id: uuid.UUID, write: bool = False) -> ReceptionReply:
    reply = await find_reply(session, item_id, await allowed_store_ids(session, user))
    if reply is None or (reply.scope == "personal" and reply.owner_user_id != user.id):
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "快捷回复不存在", 404)
    await _ensure_permission(session, user, [reply.store_id], _group_permission(reply.scope, write))
    return reply


async def visible_policy(session: AsyncSession, user: User, item_id: uuid.UUID, write: bool = False) -> ReceptionPolicy:
    policy = await find_policy(session, item_id, await allowed_store_ids(session, user))
    if policy is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "策略不存在", 404)
    # 多店策略任一关联店铺无权访问时，整条资源隐藏，不能泄露其他店铺配置。
    await _ensure_stores(session, user, policy.store_ids)
    await _ensure_permission(session, user, policy.store_ids, "marketing.manage" if write else "marketing.view")
    return policy


async def list_groups(
    session: AsyncSession,
    user: User,
    store_id: uuid.UUID,
    scope: str,
    page: int,
    page_size: int,
) -> GroupPage:
    await _ensure_stores(session, user, [store_id])
    await _ensure_permission(session, user, [store_id], _group_permission(scope, False))
    rows, total = await query_groups(
        session, store_id, scope, user.id if scope == "personal" else None, page, page_size
    )
    counts = await group_reply_counts(session, [row.id for row in rows])
    return GroupPage(
        items=[GroupView.model_validate(row).model_copy(update={"reply_count": counts.get(row.id, 0)}) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


async def list_replies(
    session: AsyncSession,
    user: User,
    store_id: uuid.UUID,
    scope: str,
    group_id: uuid.UUID | None,
    q: str | None,
    page: int,
    page_size: int,
    shortcut: str | None = None,
    include_disabled: bool = False,
) -> ReplyPage:
    await _ensure_stores(session, user, [store_id])
    await _ensure_permission(session, user, [store_id], _group_permission(scope, False))
    if group_id:
        group = await visible_group(session, user, group_id)
        if group.store_id != store_id or group.scope != scope:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "分组不存在", 404)
    rows, total = await query_replies(
        session,
        store_id,
        scope,
        user.id if scope == "personal" else None,
        group_id,
        q,
        page,
        page_size,
        shortcut=shortcut.lower() if shortcut else None,
        include_disabled=include_disabled,
    )
    return ReplyPage(items=[ReplyView.model_validate(row) for row in rows], total=total, page=page, page_size=page_size)


async def list_policies(
    session: AsyncSession,
    user: User,
    store_id: uuid.UUID | None,
    kind: str,
    page: int,
    page_size: int,
) -> PolicyPage:
    if store_id is not None:
        await _ensure_stores(session, user, [store_id])
        await _ensure_permission(session, user, [store_id], "marketing.view")
    permitted = await _permission_store_ids(session, user, "marketing.view")
    rows, total = await query_policies(session, store_id, kind, permitted, page, page_size)
    return PolicyPage(
        items=[PolicyView.model_validate(row) for row in rows], total=total, page=page, page_size=page_size
    )


def _request_hash(operation: str, payload: dict[str, object]) -> str:
    canonical = json.dumps({"operation": operation, "payload": payload}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


async def _replay(
    session: AsyncSession,
    user: User,
    key_hash: str,
    request_hash: str,
    permission: str,
) -> dict[str, object] | None:
    mutation = await find_mutation(session, user.id, key_hash)
    if mutation is None:
        return None
    if mutation.request_hash != request_hash:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "幂等键已用于其他配置请求", 409)
    store_ids = [uuid.UUID(value) for value in mutation.store_ids]
    await _ensure_stores(session, user, store_ids)
    await _ensure_permission(session, user, store_ids, mutation.permission)
    return mutation.response_body


async def _commit(
    session: AsyncSession,
    user: User,
    *,
    key_hash: str,
    request_hash: str,
    response_body: dict[str, object],
    store_ids: Iterable[uuid.UUID],
    permission: str,
    action: str,
    resource_type: str,
    resource_id: uuid.UUID,
) -> dict[str, object]:
    stores = sorted(set(store_ids))
    for store_id in stores:
        # 审计只记资源与动作，不保存快捷回复和策略正文。
        session.add(
            AuditLog(
                store_id=store_id,
                actor_type="user",
                actor_id=user.id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                after_data={"delivery_enabled": False},
                result="succeeded",
            )
        )
    session.add(
        ReceptionMutation(
            actor_id=user.id,
            key_hash=key_hash,
            request_hash=request_hash,
            permission=permission,
            response_body=response_body,
            store_ids=[str(value) for value in stores],
        )
    )
    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        replay = await _replay(session, user, key_hash, request_hash, permission)
        if replay is not None:
            return replay
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "配置冲突或快捷键重复", 409) from error
    return response_body


def _key_and_hash(key: str, operation: str, payload: dict[str, object]) -> tuple[str, str]:
    return hashlib.sha256(key.encode()).hexdigest(), _request_hash(operation, payload)


async def create_group(session: AsyncSession, user: User, payload: GroupCreate, key: str) -> GroupView:
    key_hash, request_hash = _key_and_hash(key, "groups:create", payload.model_dump(mode="json"))
    permission = _group_permission(payload.scope, True)
    replay = await _replay(session, user, key_hash, request_hash, permission)
    if replay is not None:
        return GroupView.model_validate(replay)
    await _ensure_stores(session, user, [payload.store_id])
    await _ensure_permission(session, user, [payload.store_id], permission)
    group = ReceptionGroup(
        id=uuid.uuid4(), **payload.model_dump(), owner_user_id=user.id if payload.scope == "personal" else None
    )
    session.add(group)
    body = GroupView.model_validate(group).model_dump(mode="json")
    saved = await _commit(
        session,
        user,
        key_hash=key_hash,
        request_hash=request_hash,
        response_body=body,
        store_ids=[group.store_id],
        permission=permission,
        action="reception.group.create",
        resource_type="reception_group",
        resource_id=group.id,
    )
    return GroupView.model_validate(saved)


async def update_group(
    session: AsyncSession,
    user: User,
    item_id: uuid.UUID,
    payload: GroupUpdate,
    key: str,
) -> GroupView:
    key_hash, request_hash = _key_and_hash(
        key, f"groups:{item_id}:patch", payload.model_dump(mode="json", exclude_unset=True)
    )
    replay = await _replay(session, user, key_hash, request_hash, "workspace.reply")
    if replay is not None:
        return GroupView.model_validate(replay)
    group = await visible_group(session, user, item_id, write=True)
    permission = _group_permission(group.scope, True)
    await _ensure_permission(session, user, [group.store_id], permission)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is None:
            raise AppError(ErrorCode.VALIDATION_ERROR, "字段不能为空", 422)
        setattr(group, field, value)
    body = GroupView.model_validate(group).model_dump(mode="json")
    saved = await _commit(
        session,
        user,
        key_hash=key_hash,
        request_hash=request_hash,
        response_body=body,
        store_ids=[group.store_id],
        permission=permission,
        action="reception.group.update",
        resource_type="reception_group",
        resource_id=group.id,
    )
    return GroupView.model_validate(saved)


async def delete_group(session: AsyncSession, user: User, item_id: uuid.UUID, key: str) -> None:
    key_hash, request_hash = _key_and_hash(key, f"groups:{item_id}:delete", {})
    if await _replay(session, user, key_hash, request_hash, "workspace.reply") is not None:
        return
    group = await visible_group(session, user, item_id, write=True)
    permission = _group_permission(group.scope, True)
    await _ensure_permission(session, user, [group.store_id], permission)
    if await group_has_replies(session, group.id):
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "请先移除分组内快捷回复", 409)
    await session.delete(group)
    await _commit(
        session,
        user,
        key_hash=key_hash,
        request_hash=request_hash,
        response_body={"deleted": True},
        store_ids=[group.store_id],
        permission=permission,
        action="reception.group.delete",
        resource_type="reception_group",
        resource_id=group.id,
    )


async def _validate_reply_group(
    session: AsyncSession,
    user: User,
    group_id: uuid.UUID,
    store_id: uuid.UUID,
    scope: str,
) -> None:
    group = await visible_group(session, user, group_id, permission=_group_permission(scope, True))
    if group.store_id != store_id or group.scope != scope:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "分组不存在", 404)


async def create_reply(session: AsyncSession, user: User, payload: ReplyCreate, key: str) -> ReplyView:
    key_hash, request_hash = _key_and_hash(key, "replies:create", payload.model_dump(mode="json"))
    permission = _group_permission(payload.scope, True)
    replay = await _replay(session, user, key_hash, request_hash, permission)
    if replay is not None:
        return ReplyView.model_validate(replay)
    await _ensure_stores(session, user, [payload.store_id])
    await _ensure_permission(session, user, [payload.store_id], permission)
    await _validate_reply_group(session, user, payload.group_id, payload.store_id, payload.scope)
    owner_id = user.id if payload.scope == "personal" else None
    if await shortcut_exists(session, payload.store_id, payload.scope, owner_id, payload.shortcut):
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "快捷键已存在", 409)
    reply = ReceptionReply(id=uuid.uuid4(), **payload.model_dump(), owner_user_id=owner_id)
    session.add(reply)
    body = ReplyView.model_validate(reply).model_dump(mode="json")
    saved = await _commit(
        session,
        user,
        key_hash=key_hash,
        request_hash=request_hash,
        response_body=body,
        store_ids=[reply.store_id],
        permission=permission,
        action="reception.reply.create",
        resource_type="reception_reply",
        resource_id=reply.id,
    )
    return ReplyView.model_validate(saved)


async def update_reply(
    session: AsyncSession,
    user: User,
    item_id: uuid.UUID,
    payload: ReplyUpdate,
    key: str,
) -> ReplyView:
    key_hash, request_hash = _key_and_hash(
        key, f"replies:{item_id}:patch", payload.model_dump(mode="json", exclude_unset=True)
    )
    replay = await _replay(session, user, key_hash, request_hash, "workspace.reply")
    if replay is not None:
        return ReplyView.model_validate(replay)
    reply = await visible_reply(session, user, item_id, write=True)
    permission = _group_permission(reply.scope, True)
    changes = payload.model_dump(exclude_unset=True)
    if "group_id" in changes:
        if changes["group_id"] is None:
            raise AppError(ErrorCode.VALIDATION_ERROR, "分组不能为空", 422)
        await _validate_reply_group(session, user, changes["group_id"], reply.store_id, reply.scope)
    if any(value is None and field != "site_code" for field, value in changes.items()):
        raise AppError(ErrorCode.VALIDATION_ERROR, "字段不能为空", 422)
    if "shortcut" in changes and await shortcut_exists(
        session, reply.store_id, reply.scope, reply.owner_user_id, changes["shortcut"], reply.id
    ):
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "快捷键已存在", 409)
    for field, value in changes.items():
        setattr(reply, field, value)
    body = ReplyView.model_validate(reply).model_dump(mode="json")
    saved = await _commit(
        session,
        user,
        key_hash=key_hash,
        request_hash=request_hash,
        response_body=body,
        store_ids=[reply.store_id],
        permission=permission,
        action="reception.reply.update",
        resource_type="reception_reply",
        resource_id=reply.id,
    )
    return ReplyView.model_validate(saved)


async def delete_reply(session: AsyncSession, user: User, item_id: uuid.UUID, key: str) -> None:
    key_hash, request_hash = _key_and_hash(key, f"replies:{item_id}:delete", {})
    if await _replay(session, user, key_hash, request_hash, "workspace.reply") is not None:
        return
    reply = await visible_reply(session, user, item_id, write=True)
    permission = _group_permission(reply.scope, True)
    await session.delete(reply)
    await _commit(
        session,
        user,
        key_hash=key_hash,
        request_hash=request_hash,
        response_body={"deleted": True},
        store_ids=[reply.store_id],
        permission=permission,
        action="reception.reply.delete",
        resource_type="reception_reply",
        resource_id=reply.id,
    )


async def create_policy(session: AsyncSession, user: User, payload: PolicyCreate, key: str) -> PolicyView:
    key_hash, request_hash = _key_and_hash(key, "policies:create", payload.model_dump(mode="json"))
    replay = await _replay(session, user, key_hash, request_hash, "marketing.manage")
    if replay is not None:
        return PolicyView.model_validate(replay)
    await _ensure_stores(session, user, payload.store_ids)
    await _ensure_permission(session, user, payload.store_ids, "marketing.manage")
    await _ensure_permission(session, user, payload.store_ids, "marketing.view")
    attributes = payload.model_dump(exclude={"store_ids"})
    attributes["schedule"] = payload.schedule.model_dump(mode="json") if payload.schedule else None
    policy = ReceptionPolicy(
        id=uuid.uuid4(),
        created_by=user.id,
        **attributes,
        stores=[ReceptionPolicyStore(store_id=value) for value in payload.store_ids],
    )
    session.add(policy)
    body = PolicyView.model_validate(policy).model_dump(mode="json")
    saved = await _commit(
        session,
        user,
        key_hash=key_hash,
        request_hash=request_hash,
        response_body=body,
        store_ids=policy.store_ids,
        permission="marketing.manage",
        action="reception.policy.create",
        resource_type="reception_policy",
        resource_id=policy.id,
    )
    return PolicyView.model_validate(saved)


async def update_policy(
    session: AsyncSession,
    user: User,
    item_id: uuid.UUID,
    payload: PolicyUpdate,
    key: str,
) -> PolicyView:
    key_hash, request_hash = _key_and_hash(
        key, f"policies:{item_id}:patch", payload.model_dump(mode="json", exclude_unset=True)
    )
    replay = await _replay(session, user, key_hash, request_hash, "marketing.manage")
    if replay is not None:
        return PolicyView.model_validate(replay)
    policy = await visible_policy(session, user, item_id, write=True)
    old_stores = set(policy.store_ids)
    changes = payload.model_dump(exclude_unset=True)
    merged: dict[str, object] = {
        "kind": policy.kind,
        "name": policy.name,
        "content": policy.content,
        "timeout_minutes": policy.timeout_minutes,
        "valid_from": policy.valid_from,
        "valid_to": policy.valid_to,
        "schedule": policy.schedule,
        "enabled": policy.enabled,
        "sort_order": policy.sort_order,
        "store_ids": policy.store_ids,
    } | changes
    try:
        validated = PolicyCreate.model_validate(merged)
    except ValidationError as error:
        raise AppError(ErrorCode.VALIDATION_ERROR, "策略配置无效", 422) from error
    await _ensure_stores(session, user, validated.store_ids)
    await _ensure_permission(session, user, validated.store_ids, "marketing.manage")
    await _ensure_permission(session, user, validated.store_ids, "marketing.view")
    for field, value in changes.items():
        if field == "store_ids":
            policy.stores = [ReceptionPolicyStore(store_id=store_id) for store_id in validated.store_ids]
        elif field == "schedule":
            policy.schedule = validated.schedule.model_dump(mode="json") if validated.schedule else None
        else:
            setattr(policy, field, value)
    body = PolicyView.model_validate(policy).model_dump(mode="json")
    saved = await _commit(
        session,
        user,
        key_hash=key_hash,
        request_hash=request_hash,
        response_body=body,
        store_ids=old_stores | set(validated.store_ids),
        permission="marketing.manage",
        action="reception.policy.update",
        resource_type="reception_policy",
        resource_id=policy.id,
    )
    return PolicyView.model_validate(saved)


async def delete_policy(session: AsyncSession, user: User, item_id: uuid.UUID, key: str) -> None:
    key_hash, request_hash = _key_and_hash(key, f"policies:{item_id}:delete", {})
    if await _replay(session, user, key_hash, request_hash, "marketing.manage") is not None:
        return
    policy = await visible_policy(session, user, item_id, write=True)
    store_ids = policy.store_ids
    await session.delete(policy)
    await _commit(
        session,
        user,
        key_hash=key_hash,
        request_hash=request_hash,
        response_body={"deleted": True},
        store_ids=store_ids,
        permission="marketing.manage",
        action="reception.policy.delete",
        resource_type="reception_policy",
        resource_id=policy.id,
    )
