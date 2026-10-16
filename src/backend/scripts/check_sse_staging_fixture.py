"""G5 staging Runner 零模型调用、只读数据库预检。"""

import argparse
import asyncio
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.config.settings import get_settings
from app.shared.database.base import Permission
from app.shared.database.session import session_factory
from app.stores.models import Store
from scripts.prepare_sse_staging_fixture import validate_database_target


class ReadinessError(Exception):
    def __init__(self, stage: str) -> None:
        self.stage = stage
        super().__init__(stage)


async def check_readiness(session: AsyncSession, app_env: str) -> dict[str, str | bool | int]:
    """只查权限和历史 G5 夹具，防止未知提交后的盲目重跑。"""
    if app_env != "staging":
        raise ReadinessError("config")
    try:
        permission = await session.scalar(select(Permission.id).where(Permission.code == "workspace.view"))
        if permission is None:
            raise ReadinessError("permission_missing")
        existing = await session.scalar(select(Store.id).where(Store.code.like("g5-%")).limit(1))
        if existing is not None:
            raise ReadinessError("existing_fixture")
    except ReadinessError:
        raise
    except Exception as exc:
        raise ReadinessError("database_read") from exc
    return {"mode": "check_only", "ready": True, "provider_calls": 0}


def safe_report(error: ReadinessError) -> dict[str, str | bool | int]:
    """诊断只给固定阶段，不回显 DSN、异常或对象标识。"""
    return {"mode": "check_only", "ready": False, "failure_stage": error.stage, "provider_calls": 0}


async def run_check(expected_database_sha256: str) -> dict[str, str | bool | int]:
    try:
        settings = get_settings()
        validate_database_target(settings.database_url, expected_database_sha256)
    except Exception as exc:
        raise ReadinessError("config") from exc
    try:
        async with session_factory() as session:
            return await check_readiness(session, settings.app_env)
    except ReadinessError:
        raise
    except Exception as exc:
        raise ReadinessError("database_read") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only staging G5 fixture preflight")
    parser.add_argument("--expected-database-sha256", required=True)
    args = parser.parse_args()
    try:
        report = asyncio.run(run_check(args.expected_database_sha256))
    except ReadinessError as exc:
        print(json.dumps(safe_report(exc), sort_keys=True))
        raise SystemExit(1) from None
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
