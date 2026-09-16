"""仓库工程根布局契约。"""

from pathlib import Path


def repository_root(start: Path) -> Path:
    """从普通 checkout 或 linked worktree 中定位 Git 仓库根。"""
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
    raise AssertionError("Git repository root was not found")


REPOSITORY_ROOT = repository_root(Path(__file__).resolve())
SOURCE_ROOT = REPOSITORY_ROOT / "src"


def test_engineering_assets_live_under_src() -> None:
    """工程与运行资产必须只从单一 src 工程根提供。"""
    required = (
        "backend",
        "frontend",
        "tests",
        "scripts",
        "deploy",
        "docker",
        "compose",
        "config/.env.example",
    )
    assert all((SOURCE_ROOT / path).exists() for path in required)
    forbidden = (
        "backend",
        "frontend",
        "tests",
        "scripts",
        "deploy",
        "Dockerfile.backend",
        "docker-compose.yml",
    )
    assert all(not (REPOSITORY_ROOT / path).exists() for path in forbidden)
    assert not (SOURCE_ROOT / "deploy/cloudflared/config.example.yml").exists()
