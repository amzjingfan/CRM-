"""真实会话回填命令的环境边界。"""

import uuid

import pytest

import scripts.sync_tiktok_conversations as sync_script
from app.shared.config.settings import Settings
from app.shared.exceptions.errors import AppError


@pytest.mark.asyncio
async def test_backfill_command_refuses_non_staging_before_database_access(monkeypatch: pytest.MonkeyPatch) -> None:
    """误在非 staging 环境执行时必须在读取渠道或平台前拒绝。"""
    monkeypatch.setattr(
        sync_script,
        "get_settings",
        lambda: Settings(_env_file=None),  # type: ignore[call-arg]
    )
    with pytest.raises(AppError):
        await sync_script.sync_channel(uuid.uuid4(), uuid.uuid4())
