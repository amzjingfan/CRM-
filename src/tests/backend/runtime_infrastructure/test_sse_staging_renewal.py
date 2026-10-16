"""G5 现有 50 个隔离账号的短期凭证续期。"""

import uuid

from app.auth.security import create_access_token
from scripts import prepare_sse_staging_fixture as fixture


def test_renewal_preserves_exact_manifest_and_sessions_but_replaces_all_tokens() -> None:
    user_ids = [uuid.uuid4() for _ in range(50)]
    conversation_ids = [uuid.uuid4() for _ in range(50)]
    manifest = fixture.ReconciliationManifest(
        run_id=uuid.uuid4(),
        store_id=uuid.uuid4(),
        role_id=uuid.uuid4(),
        user_ids=tuple(user_ids),
        conversation_ids=tuple(conversation_ids),
    )
    old = {
        "manifest": {
            "run_id": str(manifest.run_id),
            "store_id": str(manifest.store_id),
            "role_id": str(manifest.role_id),
            "user_ids": [str(value) for value in user_ids],
            "conversation_ids": [str(value) for value in conversation_ids],
        },
        "clients": [
            {
                "access_token": create_access_token(user_id),
                "csrf_token": f"old-csrf-{index}",
                "session_id": str(conversation_id),
            }
            for index, (user_id, conversation_id) in enumerate(zip(user_ids, conversation_ids, strict=True))
        ],
    }

    renewed = fixture.build_renewed_credentials(old, manifest)

    assert renewed["manifest"] == old["manifest"]
    assert len(renewed["clients"]) == 50
    assert [row["session_id"] for row in renewed["clients"]] == [str(value) for value in conversation_ids]
    assert all(
        new["access_token"] != previous["access_token"]
        for new, previous in zip(renewed["clients"], old["clients"], strict=True)
    )
    assert all(
        new["csrf_token"] != previous["csrf_token"]
        for new, previous in zip(renewed["clients"], old["clients"], strict=True)
    )
    assert fixture.validate_reconciliation_payload(renewed) == manifest
