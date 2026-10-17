"""G5 合成内容只能写入 R05 原隔离店铺的精确 50 个会话。"""

import uuid
from types import SimpleNamespace

import pytest

from scripts import prepare_sse_staging_fixture as fixture


def content_snapshot() -> tuple[fixture.ReconciliationManifest, object, list[object], list[object], list[object]]:
    run_id = uuid.uuid4()
    store_id = uuid.uuid4()
    users = [uuid.uuid4() for _ in range(50)]
    sessions = [uuid.uuid4() for _ in range(50)]
    manifest = fixture.ReconciliationManifest(
        run_id=run_id,
        store_id=store_id,
        role_id=uuid.uuid4(),
        user_ids=tuple(users),
        conversation_ids=tuple(sessions),
    )
    code = f"g5-{run_id.hex}"
    store = SimpleNamespace(
        id=store_id,
        code=code,
        status="active",
        deleted_at=None,
        metadata_json={"purpose": "g5-staging", "run_id": str(run_id)},
    )
    user_rows = [
        SimpleNamespace(id=user_id, email=f"{code}-{index:02d}@example.com", status="active")
        for index, user_id in enumerate(users)
    ]
    conversation_rows = [
        SimpleNamespace(id=conversation_id, store_id=store_id, platform="synthetic", status="active")
        for conversation_id in sessions
    ]
    message_rows = [
        SimpleNamespace(
            id=uuid.uuid4(),
            store_id=store_id,
            conversation_id=conversation_id,
            platform="synthetic",
            external_message_id=f"{code}-{index:02d}",
            role="user",
            direction="inbound",
            content=fixture.G5_ORIGINAL_QUESTION,
            status="received",
        )
        for index, conversation_id in enumerate(sessions)
    ]
    return manifest, store, user_rows, conversation_rows, message_rows


def test_exact_repaired_fixture_is_eligible_for_synthetic_content() -> None:
    manifest, store, users, conversations, messages = content_snapshot()

    assert fixture.verify_g5_content_snapshot(manifest, store, users, conversations, messages) == "original"


@pytest.mark.parametrize("tamper", ["store", "email", "session", "message", "missing"])
def test_content_preparation_rejects_mismatched_or_partial_fixture(tamper: str) -> None:
    manifest, store, users, conversations, messages = content_snapshot()
    if tamper == "store":
        store.metadata_json = {"purpose": "ordinary-store"}
    elif tamper == "email":
        users[0].email = "person@example.com"
    elif tamper == "session":
        conversations[0].store_id = uuid.uuid4()
    elif tamper == "message":
        messages[0].content = "A real customer message"
    else:
        messages.pop()

    with pytest.raises(ValueError, match="fixture"):
        fixture.verify_g5_content_snapshot(manifest, store, users, conversations, messages)


def test_prepared_fixture_must_have_all_fifty_matching_questions() -> None:
    manifest, store, users, conversations, messages = content_snapshot()
    for message in messages:
        message.content = fixture.G5_SYNTHETIC_QUESTION

    assert fixture.verify_g5_content_snapshot(manifest, store, users, conversations, messages) == "prepared"
    messages[1].content = fixture.G5_ORIGINAL_QUESTION
    with pytest.raises(ValueError, match="fixture"):
        fixture.verify_g5_content_snapshot(manifest, store, users, conversations, messages)


def test_legacy_fixture_requires_exactly_fifty_old_questions_before_replacement() -> None:
    manifest, store, users, conversations, messages = content_snapshot()
    for message in messages:
        message.content = "What can this test assistant help with?"

    assert fixture.verify_g5_content_snapshot(manifest, store, users, conversations, messages) == "legacy_prepared"
    messages[0].content = "How do I return a real order?"
    with pytest.raises(ValueError, match="fixture"):
        fixture.verify_g5_content_snapshot(manifest, store, users, conversations, messages)
