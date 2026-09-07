"""FAQ CSV/XLSX 异步导入处理器。"""

import csv
import io
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge_base.models import KnowledgeCategory, KnowledgeDocument, KnowledgeImportJob
from app.knowledge_base.service import content_hash
from app.knowledge_base.storage import get_import_file
from app.shared.config.settings import get_settings

REQUIRED_COLUMNS = {"question", "answer"}
OPTIONAL_COLUMNS = {"category_code", "tags", "source", "status", "entry_id"}


def _csv_rows(content: bytes) -> list[dict[str, Any]]:
    """使用带 BOM 兼容的 UTF-8 解码 CSV。"""
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    return [dict(row) for row in reader]


def _xlsx_rows(content: bytes) -> list[dict[str, Any]]:
    """以只读模式解析首个工作表，控制大文件内存占用。"""
    workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    try:
        sheet = workbook.active
        values: Iterable[tuple[Any, ...]] = sheet.iter_rows(values_only=True)
        headers = [str(value).strip() if value is not None else "" for value in next(iter(values), ())]
        return [dict(zip(headers, row, strict=False)) for row in values]
    finally:
        workbook.close()


def parse_import(content: bytes, content_type: str) -> list[dict[str, Any]]:
    """解析受支持文件，并在入库前验证表头和行数上限。"""
    rows = _csv_rows(content) if content_type == "text/csv" else _xlsx_rows(content)
    headers = set(rows[0]) if rows else set()
    if not REQUIRED_COLUMNS.issubset(headers):
        raise ValueError("MISSING_REQUIRED_COLUMNS")
    if headers - REQUIRED_COLUMNS - OPTIONAL_COLUMNS:
        # 多余列可能含客户隐私，拒绝而不是静默落库。
        raise ValueError("UNSUPPORTED_COLUMNS")
    if len(rows) > get_settings().knowledge_import_max_rows:
        raise ValueError("TOO_MANY_ROWS")
    return rows


def _clean_text(value: Any, limit: int) -> str:
    text = str(value or "").strip()
    if not text or len(text) > limit:
        raise ValueError("INVALID_REQUIRED_TEXT")
    return text


async def _import_row(session: AsyncSession, job: KnowledgeImportJob, row: dict[str, Any]) -> None:
    """导入单行 FAQ；每行在独立保存点中执行，失败不会回滚其他成功行。"""
    question = _clean_text(row.get("question"), 4000)
    answer = _clean_text(row.get("answer"), 20_000)
    category_id: uuid.UUID | None = None
    category_code = str(row.get("category_code") or "").strip()
    if category_code:
        category_id = await session.scalar(
            select(KnowledgeCategory.id).where(
                KnowledgeCategory.store_id == job.store_id,
                KnowledgeCategory.code == category_code,
                KnowledgeCategory.status == "active",
            )
        )
        if category_id is None:
            raise ValueError("CATEGORY_NOT_FOUND")
    tags = [item.strip() for item in str(row.get("tags") or "").split(",") if item.strip()][:30]
    status = str(row.get("status") or "draft").strip()
    if status not in {"draft", "published"}:
        raise ValueError("INVALID_STATUS")
    if status == "published":
        # 批量文件不能替代 knowledge.manage 操作者逐版本审批。
        raise ValueError("PUBLISH_REQUIRES_APPROVAL")
    source = str(row.get("source") or "").strip()[:200] or None
    document = KnowledgeDocument(
        store_id=job.store_id,
        category_id=category_id,
        title=question[:500],
        question=question,
        answer=answer,
        source=source,
        tags=tags,
        status="draft",
        vectorization_status="pending",
        content_hash=content_hash(question, answer),
        published_at=None,
    )
    entry_id = str(row.get("entry_id") or "").strip()
    if entry_id:
        try:
            document.id = uuid.UUID(entry_id)
        except ValueError as exc:
            raise ValueError("INVALID_ENTRY_ID") from exc
    session.add(document)
    await session.flush()


async def process_import_job(session: AsyncSession) -> bool:
    """认领并处理一个导入任务；行错误仅记录行号和错误码。"""
    job = await session.scalar(
        select(KnowledgeImportJob)
        .where(KnowledgeImportJob.status == "pending")
        .order_by(KnowledgeImportJob.created_at, KnowledgeImportJob.id)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if job is None:
        return False
    job.status = "processing"
    job.started_at = datetime.now(UTC)
    await session.commit()
    try:
        rows = parse_import(get_import_file(job.object_key), job.content_type)
    except (OSError, UnicodeError, ValueError) as exc:
        job.status = "failed"
        job.error_summary = [{"row": 0, "code": str(exc)[:100]}]
        job.completed_at = datetime.now(UTC)
        await session.commit()
        return True
    job.total_rows = len(rows)
    errors: list[dict[str, object]] = []
    for row_number, row in enumerate(rows, start=2):
        try:
            async with session.begin_nested():
                await _import_row(session, job, row)
            job.succeeded_rows += 1
        except (ValueError, TypeError):
            job.failed_rows += 1
            if len(errors) < 100:
                errors.append({"row": row_number, "code": "INVALID_ROW"})
    job.error_summary = errors
    job.status = "succeeded" if job.failed_rows == 0 else "partially_succeeded"
    if job.succeeded_rows == 0 and job.failed_rows:
        job.status = "failed"
    job.completed_at = datetime.now(UTC)
    await session.commit()
    return True
