"""解析 Worker 从私有对象读取并运行有超时的隔离子进程。"""

import json
from pathlib import Path
from typing import Any

import pytest

from app.knowledge_base import document_parser_worker


@pytest.mark.asyncio
async def test_local_parser_bounds_private_source_and_reads_structured_result(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, int]] = []

    def fake_get(object_key: str, *, max_bytes: int) -> bytes:
        calls.append((object_key, max_bytes))
        return b"%PDF-1.7\nsynthetic"

    async def fake_subprocess(source: Path, output: Path, suffix: str, mode: str) -> None:
        assert source.read_bytes().startswith(b"%PDF-")
        assert (suffix, mode) == (".pdf", "auto")
        payload: list[dict[str, Any]] = [
            {
                "index": 0,
                "kind": "page",
                "locator": {"page": 1},
                "blocks": [{"type": "text", "content": [{"type": "text", "content": "测试"}]}],
                "parse_mode": "txt",
                "ocr_derived": False,
                "parser_version": "4.0.12",
            }
        ]
        output.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(document_parser_worker, "get_import_file", fake_get)
    monkeypatch.setattr(document_parser_worker, "_run_parser_subprocess", fake_subprocess)
    parser = document_parser_worker.LocalDocumentParser()
    units = await parser.parse("private/key", ".pdf", "auto")
    assert calls == [("private/key", 20 * 1024 * 1024)]
    assert len(units) == 1 and units[0].locator == {"page": 1}
