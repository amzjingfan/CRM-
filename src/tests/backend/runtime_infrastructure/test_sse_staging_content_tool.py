"""G5 合成 FAQ 准备与凭证续期的现场门禁。"""

import importlib
import stat
import uuid
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


def tool():  # type: ignore[no-untyped-def]
    return importlib.import_module("scripts.prepare_sse_staging_content")


def test_content_tool_rejects_non_staging_and_unexpected_private_batch(tmp_path: Path) -> None:
    source = tmp_path / "g5-38852775454-2.json"
    output = tmp_path / "g5-38852775454-3.json"
    source.write_text("private", encoding="utf-8")

    with pytest.raises(ValueError, match="staging"):
        tool().validate_content_paths("production", source, output, writable=False)
    with pytest.raises(ValueError, match="batch"):
        tool().validate_content_paths("staging", tmp_path / "other.json", output, writable=False)
    with pytest.raises(ValueError, match="batch"):
        tool().validate_content_paths("staging", source, tmp_path / "other.json", writable=False)


def test_content_tool_never_overwrites_an_existing_renewed_pool(tmp_path: Path) -> None:
    source = tmp_path / "g5-38852775454-2.json"
    output = tmp_path / "g5-38852775454-3.json"
    source.write_text("private", encoding="utf-8")
    output.write_text("keep", encoding="utf-8")

    with pytest.raises(ValueError, match="exists"):
        tool().validate_content_paths("staging", source, output, writable=True)
    assert output.read_text(encoding="utf-8") == "keep"


def test_content_tool_accepts_only_next_numbered_private_pool() -> None:
    source = Path("/opt/crm-g5-credentials/g5-38852775454-2.json")
    fourth = source.with_name("g5-38852775454-4.json")
    original = {"g5-38852775454-1.json", source.name}
    prior = original | {"g5-38852775454-3.json"}

    assert tool().validate_credential_inventory(source, fourth, prior, writable=True, allow_renewed=False) == 4
    assert (
        tool().validate_credential_inventory(source, fourth, prior | {fourth.name}, writable=False, allow_renewed=True)
        == 4
    )
    with pytest.raises(ValueError, match="batch"):
        tool().validate_credential_inventory(source, fourth, original, writable=True, allow_renewed=False)
    with pytest.raises(ValueError, match="batch"):
        tool().validate_credential_inventory(
            source, fourth, prior | {"unexpected.json"}, writable=True, allow_renewed=False
        )
    with pytest.raises(ValueError, match="batch"):
        tool().validate_credential_inventory(
            source, source.with_name("g5-38852775454-04.json"), prior, writable=True, allow_renewed=False
        )


@pytest.mark.parametrize(
    ("mode", "generation", "output_exists", "document_version", "allowed"),
    [
        ("replace_content", 4, True, None, True),
        ("replace_content", 3, True, None, False),
        ("replace_content", 5, True, None, False),
        ("replace_answer_v3", 5, True, 2, True),
        ("replace_answer_v3", 4, True, 2, False),
        ("replace_answer_v3", 5, True, 3, False),
        ("vectorize_one", 3, False, 1, True),
        ("vectorize_one", 4, True, 2, True),
        ("vectorize_one", 3, True, 2, False),
        ("vectorize_one", 4, True, 1, False),
        ("vectorize_one", 5, True, 2, False),
        ("vectorize_one", 5, True, 3, True),
    ],
)
def test_content_write_modes_bind_private_batch_to_faq_version(
    mode: str, generation: int, output_exists: bool, document_version: int | None, allowed: bool
) -> None:
    if allowed:
        tool().assert_content_mode_inventory(mode, generation, output_exists, document_version)
    else:
        with pytest.raises(ValueError, match="G5 content batch"):
            tool().assert_content_mode_inventory(mode, generation, output_exists, document_version)


def test_private_mount_uses_runner_file_ownership_even_when_container_runs_as_root() -> None:
    parent = SimpleNamespace(st_uid=1004, st_mode=stat.S_IFDIR | 0o700)
    source = SimpleNamespace(st_uid=1004, st_mode=stat.S_IFREG | 0o600, st_size=8000)

    assert tool().private_source_metadata_is_safe(parent, source)
    assert not tool().private_source_metadata_is_safe(parent, SimpleNamespace(**{**vars(source), "st_uid": 0}))
    assert not tool().private_source_metadata_is_safe(
        parent, SimpleNamespace(**{**vars(source), "st_mode": stat.S_IFREG | 0o644})
    )


def legacy_replacement_target() -> tuple[object, object]:
    script = tool()
    store_id = uuid.uuid4()
    document = SimpleNamespace(
        id=uuid.uuid4(),
        store_id=store_id,
        source=script.FAQ_SOURCE,
        source_type="faq",
        tags=["g5-synthetic"],
        question=script.G5_LEGACY_QUESTION,
        answer=script.G5_LEGACY_ANSWER,
        status="published",
        vectorization_status="ready",
        document_version=1,
        deleted_at=None,
        approved_by=uuid.uuid4(),
        approved_at=object(),
        statement_type=script.KnowledgeStatementType.NON_ASSERTIVE_PROPOSITION,
        customer_scope=script.KnowledgeCustomerScope.GENERIC,
        publication_approval=script.KnowledgePublicationApproval.APPROVED_FOR_INTERNAL_REVIEW,
    )
    snapshot = script.ContentSnapshot(
        "legacy_prepared",
        SimpleNamespace(id=document.approved_by),
        [SimpleNamespace(content=script.G5_LEGACY_QUESTION) for _ in range(50)],
        document,
    )
    return SimpleNamespace(store_id=store_id, run_id=uuid.uuid4()), snapshot


@pytest.mark.parametrize(
    "damage", [None, "other_store", "extra_message", "changed_question", "wrong_version", "already_replaced"]
)
def test_replacement_accepts_only_original_ready_faq_and_fifty_legacy_messages(damage: str | None) -> None:
    script = tool()
    manifest, snapshot = legacy_replacement_target()
    if damage == "other_store":
        snapshot.document.store_id = uuid.uuid4()
    elif damage == "extra_message":
        snapshot.messages.append(SimpleNamespace(content=script.G5_LEGACY_QUESTION))
    elif damage == "changed_question":
        snapshot.document.question = "customer content"
    elif damage == "wrong_version":
        snapshot.document.document_version = 2
    elif damage == "already_replaced":
        snapshot = replace(snapshot, state="prepared")
    if damage is None:
        script.assert_replacement_target(manifest, snapshot)
    else:
        with pytest.raises(ValueError, match="G5 replacement target"):
            script.assert_replacement_target(manifest, snapshot)


@pytest.mark.asyncio
async def test_replacement_updates_only_one_faq_and_fifty_questions_without_model_calls() -> None:
    script = tool()
    manifest, snapshot = legacy_replacement_target()
    session = SimpleNamespace(add=lambda row: None, flush=AsyncMock())

    await script.replace_synthetic_content(session, manifest, snapshot)

    assert [row.content for row in snapshot.messages] == [script.G5_SYNTHETIC_QUESTION] * 50
    assert snapshot.document.question == script.G5_SYNTHETIC_QUESTION
    assert snapshot.document.answer == script.G5_SYNTHETIC_ANSWER_V2
    assert snapshot.document.document_version == 2
    assert snapshot.document.vectorization_status == "pending"
    assert snapshot.document.statement_type == script.KnowledgeStatementType.POLICY
    session.flush.assert_awaited_once()


def test_g5_third_faq_answer_preserves_policy_without_location_separators() -> None:
    script = tool()

    assert script.G5_SYNTHETIC_ANSWER_V2.count(",") == 2
    assert "," not in script.G5_SYNTHETIC_ANSWER
    assert "return request" in script.G5_SYNTHETIC_ANSWER
    assert "platform approval" in script.G5_SYNTHETIC_ANSWER
    assert "does not confirm" in script.G5_SYNTHETIC_ANSWER


@pytest.mark.parametrize("damage", [None, "other_store", "extra_message", "changed_answer", "wrong_version", "pending"])
def test_third_faq_reconciliation_requires_exact_ready_second_version(damage: str | None) -> None:
    script = tool()
    manifest, snapshot = legacy_replacement_target()
    snapshot = replace(snapshot, state="prepared")
    snapshot.document.question = script.G5_SYNTHETIC_QUESTION
    snapshot.document.answer = script.G5_SYNTHETIC_ANSWER_V2
    snapshot.document.document_version = 2
    snapshot.document.vectorization_status = "ready"
    snapshot.document.statement_type = script.KnowledgeStatementType.POLICY
    for message in snapshot.messages:
        message.content = script.G5_SYNTHETIC_QUESTION
    if damage == "other_store":
        snapshot.document.store_id = uuid.uuid4()
    elif damage == "extra_message":
        snapshot.messages.append(SimpleNamespace(content=script.G5_SYNTHETIC_QUESTION))
    elif damage == "changed_answer":
        snapshot.document.answer = "unreviewed content"
    elif damage == "wrong_version":
        snapshot.document.document_version = 3
    elif damage == "pending":
        snapshot.document.vectorization_status = "pending"
    if damage is None:
        script.assert_third_faq_target(manifest, snapshot)
    else:
        with pytest.raises(ValueError, match="G5 third FAQ target"):
            script.assert_third_faq_target(manifest, snapshot)


@pytest.mark.asyncio
async def test_third_faq_reconciliation_updates_only_one_faq_without_changing_messages() -> None:
    script = tool()
    manifest, snapshot = legacy_replacement_target()
    snapshot = replace(snapshot, state="prepared")
    snapshot.document.question = script.G5_SYNTHETIC_QUESTION
    snapshot.document.answer = script.G5_SYNTHETIC_ANSWER_V2
    snapshot.document.document_version = 2
    snapshot.document.vectorization_status = "ready"
    snapshot.document.statement_type = script.KnowledgeStatementType.POLICY
    for message in snapshot.messages:
        message.content = script.G5_SYNTHETIC_QUESTION
    before_messages = [message.content for message in snapshot.messages]
    recorded = []
    session = SimpleNamespace(add=recorded.append, flush=AsyncMock())

    await script.replace_third_faq_answer(session, manifest, snapshot)

    assert [message.content for message in snapshot.messages] == before_messages
    assert snapshot.document.answer == script.G5_SYNTHETIC_ANSWER
    assert snapshot.document.document_version == 3
    assert snapshot.document.vectorization_status == "pending"
    assert recorded[0].action == "g5.fixture.faq_v3_replace"
    session.flush.assert_awaited_once()


def test_third_faq_vector_target_requires_pending_version_three_in_same_store() -> None:
    script = tool()
    manifest, snapshot = legacy_replacement_target()
    snapshot = replace(snapshot, state="prepared_v3")
    snapshot.document.document_version = 3
    snapshot.document.vectorization_status = "pending"

    assert script.assert_single_vector_target(manifest, snapshot) == (
        snapshot.document.id,
        manifest.store_id,
        3,
    )
    snapshot.document.store_id = uuid.uuid4()
    with pytest.raises(ValueError, match="G5 vector target"):
        script.assert_single_vector_target(manifest, snapshot)
