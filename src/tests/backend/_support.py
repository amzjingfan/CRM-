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
