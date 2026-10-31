from pathlib import Path


def find_repository_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
    raise AssertionError("Git repository root was not found")


REPOSITORY_ROOT = find_repository_root(Path(__file__).resolve())
SOURCE_ROOT = REPOSITORY_ROOT / "src"
BACKEND_ROOT = SOURCE_ROOT / "backend"
TESTS_ROOT = SOURCE_ROOT / "tests"


def require_isolated_postgres_url(value: str | None) -> str:
    """测试库允许独立回环端口，但禁止使用业务账号、业务库或远程主机。"""
    from sqlalchemy.engine import make_url

    assert value is not None
    target = make_url(value)
    assert not target.query
    assert target.drivername == "postgresql+asyncpg"
    assert target.host in {"localhost", "127.0.0.1"}
    assert target.username == "crm_test" and target.password == "crm_test"
    assert target.database == "crm_test" or (
        target.database is not None and target.database.startswith("crm_template_") and "_test_" in target.database
    )
    return value
