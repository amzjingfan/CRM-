"""隔离 MinerU 镜像的一次性本地解析入口；队列消费由索引阶段接入。"""

import argparse
import asyncio
import json
import logging
import os
import sys
import tempfile
import uuid
from dataclasses import asdict
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from app.knowledge_base.document_parser import (
    MINERU_VERSION,
    DocumentParseError,
    ParsedUnit,
    parse_document,
)
from app.knowledge_base.document_service import MAX_DOCUMENT_BYTES
from app.knowledge_base.storage import get_import_file

MAX_RESULT_BYTES = 100 * 1024 * 1024
PARSE_TIMEOUT_SECONDS = 600
logger = logging.getLogger(__name__)


def verify_runtime() -> bool:
    """部署前对照精确锁定的解析器版本。"""
    try:
        return version("mineru") == MINERU_VERSION
    except PackageNotFoundError:
        return False


def parse_to_file(source: Path, output: Path, suffix: str, mode: str) -> int:
    """只把结构化结果写入调用方指定的私有输出路径，标准输出不含正文。"""
    units = parse_document(source, suffix, mode)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(json.dumps([asdict(unit) for unit in units], ensure_ascii=False), encoding="utf-8")
        os.chmod(temporary, 0o600)
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return len(units)


async def _run_parser_subprocess(source: Path, output: Path, suffix: str, mode: str) -> None:
    """超时后杀掉解析子进程，避免线程超时后继续占用 CPU/内存。"""
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "app.knowledge_base.document_parser_worker",
        "--input",
        str(source),
        "--output",
        str(output),
        "--suffix",
        suffix,
        "--mode",
        mode,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        await asyncio.wait_for(process.communicate(), timeout=PARSE_TIMEOUT_SECONDS)
    except TimeoutError as exc:
        process.kill()
        await process.wait()
        raise DocumentParseError("PARSER_TIMEOUT") from exc
    if process.returncode != 0:
        raise DocumentParseError("PARSER_EXECUTION_FAILED")


class LocalDocumentParser:
    """从私有 MinIO 读有界字节，在临时目录执行独立 MinerU 子进程。"""

    async def parse(self, object_key: str, suffix: str, mode: str) -> list[ParsedUnit]:
        try:
            source = await asyncio.to_thread(get_import_file, object_key, max_bytes=MAX_DOCUMENT_BYTES)
        except ValueError as exc:
            raise DocumentParseError("FILE_SIZE_INVALID") from exc
        except Exception as exc:
            raise DocumentParseError("PARSER_SOURCE_UNAVAILABLE") from exc
        with tempfile.TemporaryDirectory(prefix="rag-document-") as directory:
            root = Path(directory)
            source_path = root / f"source{suffix}"
            source_path.write_bytes(source)
            os.chmod(source_path, 0o600)
            output = root / "parsed.json"
            await _run_parser_subprocess(source_path, output, suffix, mode)
            if not output.is_file() or output.stat().st_size > MAX_RESULT_BYTES:
                raise DocumentParseError("PARSER_RESULT_TOO_LARGE")
            try:
                payload = json.loads(output.read_text(encoding="utf-8"))
                if not isinstance(payload, list) or not payload:
                    raise ValueError("empty parse result")
                return [ParsedUnit(**item) for item in payload]
            except (TypeError, ValueError, KeyError) as exc:
                raise DocumentParseError("PARSER_RESULT_INVALID") from exc


async def run_queue_worker() -> None:
    """一个解析镜像只运行一个消费循环，所有外部能力均为内部私有端点。"""
    from app.agent.retrieval_models import LocalRetrievalModelClient
    from app.knowledge_base.document_chunking import BgeM3Tokenizer
    from app.knowledge_base.document_indexer import process_document_version
    from app.shared.config.settings import get_settings
    from app.shared.database.session import session_factory
    from app.shared.logging.setup import configure_logging

    settings = get_settings()
    configure_logging(settings.log_level)
    if not verify_runtime() or not settings.embedding_enabled or settings.retrieval_model_service_token is None:
        raise RuntimeError("DOCUMENT_WORKER_CONFIGURATION_INVALID")
    if os.getenv("MINERU_MODEL_SOURCE") != "local" or os.getenv("HF_HUB_OFFLINE") != "1":
        raise RuntimeError("DOCUMENT_WORKER_OFFLINE_MODE_REQUIRED")
    tokenizer = BgeM3Tokenizer(settings.bge_m3_model_path / "tokenizer.json")
    model_client = LocalRetrievalModelClient(
        base_url=settings.retrieval_model_service_url,
        token=settings.retrieval_model_service_token.get_secret_value(),
        timeout_seconds=settings.embedding_timeout_seconds,
    )
    parser = LocalDocumentParser()
    worker_id = f"document-{uuid.uuid4()}"
    try:
        while True:
            processed = False
            try:
                async with session_factory() as session:
                    processed = await process_document_version(
                        session, parser, model_client, tokenizer, worker_id=worker_id
                    )
            except Exception:
                logger.exception("文档 Worker 周期失败", extra={"event": "document_worker_cycle_failed"})
            await asyncio.sleep(0 if processed else settings.jobs_poll_seconds)
    finally:
        await model_client.aclose()


def main() -> int:
    parser = argparse.ArgumentParser(description="受控文档解析镜像的本地入口")
    parser.add_argument("--version-check", action="store_true")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--suffix")
    parser.add_argument("--mode", choices=["auto", "flash", "basic"], default="auto")
    args = parser.parse_args()
    if not verify_runtime():
        print("PARSER_VERSION_MISMATCH", file=sys.stderr)
        return 2
    if args.version_check:
        print(MINERU_VERSION)
        return 0
    if args.input is None and args.output is None and args.suffix is None:
        asyncio.run(run_queue_worker())
        return 0
    if args.input is None or args.output is None or args.suffix is None:
        parser.error("--input, --output and --suffix are required")
    try:
        parse_to_file(args.input, args.output, args.suffix, args.mode)
    except DocumentParseError as exc:
        print(exc.code, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
