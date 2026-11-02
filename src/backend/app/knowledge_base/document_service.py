"""通用文档上传的文件边界和后续服务入口。"""

import asyncio
import hashlib
import io
import json
import ntpath
import unicodedata
import uuid
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import PurePosixPath

from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import AuditLog
from app.auth.store_access import allowed_store_ids, ensure_store_access
from app.knowledge_base.document_api_schemas import (
    DocumentFileDetail,
    DocumentFilePage,
    DocumentFileSummary,
    DocumentUnitReview,
    DocumentUnitView,
    DocumentVersionApproval,
    DocumentVersionDetail,
    DocumentVersionSummary,
)
from app.knowledge_base.document_models import (
    KnowledgeFile,
    KnowledgeFileChunk,
    KnowledgeFileImportReceipt,
    KnowledgeFileSettings,
    KnowledgeFileUnit,
    KnowledgeFileVersion,
)
from app.knowledge_base.document_schemas import DocumentIndexConfig
from app.knowledge_base.models import KnowledgeCategory
from app.knowledge_base.schemas import KnowledgeCustomerScope, KnowledgePublicationApproval, KnowledgeStatementType
from app.knowledge_base.storage import get_import_file, put_import_file
from app.shared.config.settings import get_settings
from app.shared.database.base import User
from app.shared.exceptions.errors import AppError, ErrorCode

MAX_DOCUMENT_BYTES = 20 * 1024 * 1024
MAX_ARCHIVE_EXPANDED_BYTES = 100 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 5000

TEXT_SUFFIXES = {".txt", ".md", ".csv", ".tsv"}
OFFICE_MEMBERS = {
    ".docx": "word/document.xml",
    ".pptx": "ppt/presentation.xml",
    ".xlsx": "xl/workbook.xml",
}
LEGACY_OFFICE_SUFFIXES = {".doc", ".ppt", ".xls"}
MEDIA_TYPES: dict[str, set[str]] = {
    ".pdf": {"application/pdf"},
    ".png": {"image/png"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".doc": {"application/msword"},
    ".ppt": {"application/vnd.ms-powerpoint"},
    ".xls": {"application/vnd.ms-excel"},
    ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    ".pptx": {"application/vnd.openxmlformats-officedocument.presentationml.presentation"},
    ".xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    ".txt": {"text/plain"},
    ".md": {"text/markdown", "text/plain"},
    ".csv": {"text/csv", "text/plain"},
    ".tsv": {"text/tab-separated-values", "text/plain"},
}


class DocumentUploadError(ValueError):
    """稳定错误码；不把文件正文或底层解析异常回显给浏览器。"""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ValidatedDocumentUpload:
    filename: str
    name_key: str
    suffix: str
    media_type: str


def _validate_office_archive(content: bytes, required_member: str) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            members = archive.infolist()
            if len(members) > MAX_ARCHIVE_MEMBERS:
                raise DocumentUploadError("ARCHIVE_TOO_MANY_MEMBERS")
            names = {item.filename.lower() for item in members}
            if "[content_types].xml" not in names or required_member not in names:
                raise DocumentUploadError("OFFICE_FORMAT_INVALID")
            if any("vbaproject" in name or name.endswith(".exe") for name in names):
                raise DocumentUploadError("OFFICE_MACRO_REJECTED")
            if sum(item.file_size for item in members) > MAX_ARCHIVE_EXPANDED_BYTES:
                raise DocumentUploadError("ARCHIVE_EXPANDED_TOO_LARGE")
            for item in members:
                path = PurePosixPath(item.filename)
                if path.is_absolute() or ".." in path.parts or item.flag_bits & 1:
                    raise DocumentUploadError("ARCHIVE_MEMBER_UNSAFE")
    except (zipfile.BadZipFile, OSError) as exc:
        raise DocumentUploadError("OFFICE_FORMAT_INVALID") from exc


def validate_document_upload(
    filename: str, media_type: str, content: bytes, *, max_bytes: int = MAX_DOCUMENT_BYTES
) -> ValidatedDocumentUpload:
    """先校验格式与有界输入，后续存储键只由服务端 UUID 生成。"""
    safe_name = unicodedata.normalize("NFC", ntpath.basename(filename)).strip()
    if not safe_name or len(safe_name) > 255 or any(ord(char) < 32 for char in safe_name):
        raise DocumentUploadError("FILENAME_INVALID")
    suffix = PurePosixPath(safe_name).suffix.lower()
    if suffix not in MEDIA_TYPES or safe_name.startswith("."):
        raise DocumentUploadError("FILE_TYPE_UNSUPPORTED")
    if not content or max_bytes <= 0 or len(content) > min(max_bytes, MAX_DOCUMENT_BYTES):
        raise DocumentUploadError("FILE_SIZE_INVALID")
    if media_type and media_type != "application/octet-stream" and media_type not in MEDIA_TYPES[suffix]:
        raise DocumentUploadError("MEDIA_TYPE_MISMATCH")

    if suffix == ".pdf" and not content.startswith(b"%PDF-"):
        raise DocumentUploadError("FILE_SIGNATURE_INVALID")
    if suffix == ".png" and not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise DocumentUploadError("FILE_SIGNATURE_INVALID")
    if suffix in {".jpg", ".jpeg"} and not content.startswith(b"\xff\xd8\xff"):
        raise DocumentUploadError("FILE_SIGNATURE_INVALID")
    if suffix in OFFICE_MEMBERS:
        _validate_office_archive(content, OFFICE_MEMBERS[suffix])
    if suffix in LEGACY_OFFICE_SUFFIXES and not content.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        raise DocumentUploadError("FILE_SIGNATURE_INVALID")
    if suffix in TEXT_SUFFIXES:
        try:
            decoded = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise DocumentUploadError("TEXT_ENCODING_INVALID") from exc
        if "\x00" in decoded:
            raise DocumentUploadError("TEXT_ENCODING_INVALID")
    return ValidatedDocumentUpload(
        filename=safe_name,
        name_key=safe_name.casefold(),
        suffix=suffix,
        media_type=media_type
        if media_type and media_type != "application/octet-stream"
        else "application/octet-stream",
    )


def _request_fingerprint(
    store_id: uuid.UUID,
    category_id: uuid.UUID | None,
    name_key: str,
    file_sha256: str,
    config: DocumentIndexConfig,
    replace_file_id: uuid.UUID | None,
) -> str:
    """同一幂等键只能代表一份完全相同的受理意图。"""
    payload = {
        "store_id": str(store_id),
        "category_id": str(category_id) if category_id else None,
        "name_key": name_key,
        "file_sha256": file_sha256,
        "config": config.model_dump(),
        "replace_file_id": str(replace_file_id) if replace_file_id else None,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _receipt(
    store_id: uuid.UUID, user_id: uuid.UUID, version_id: uuid.UUID, key_hash: str, fingerprint: str
) -> KnowledgeFileImportReceipt:
    return KnowledgeFileImportReceipt(
        store_id=store_id,
        created_by=user_id,
        version_id=version_id,
        idempotency_key_hash=key_hash,
        request_fingerprint=fingerprint,
    )


async def _return_existing_with_receipt(
    session: AsyncSession,
    version: KnowledgeFileVersion,
    store_id: uuid.UUID,
    user_id: uuid.UUID,
    key_hash: str,
    fingerprint: str,
) -> KnowledgeFileVersion:
    """重复文件也留下幂等键记录，防止该键日后用于其他内容。"""
    session.add(_receipt(store_id, user_id, version.id, key_hash, fingerprint))
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "幂等键并发冲突", 409) from exc
    return version


async def accept_document_import(
    session: AsyncSession,
    user: User,
    store_id: uuid.UUID,
    category_id: uuid.UUID | None,
    filename: str,
    media_type: str,
    content: bytes,
    config: DocumentIndexConfig,
    replace_file_id: uuid.UUID | None,
    idempotency_key: str,
) -> KnowledgeFileVersion:
    """受理当前店铺的一个完整文件版本；同名变化必须显式替换。"""
    await ensure_store_access(session, user, store_id)
    upload = validate_document_upload(
        filename, media_type, content, max_bytes=get_settings().knowledge_file_import_max_bytes
    )
    if not 8 <= len(idempotency_key) <= 200:
        raise AppError(ErrorCode.VALIDATION_ERROR, "幂等键无效", 422)
    if category_id is not None:
        category = await session.scalar(
            select(KnowledgeCategory.id).where(
                KnowledgeCategory.id == category_id,
                KnowledgeCategory.store_id == store_id,
                KnowledgeCategory.status == "active",
            )
        )
        if category is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "分类不存在", 404)

    file_sha256 = hashlib.sha256(content).hexdigest()
    key_hash = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
    fingerprint = _request_fingerprint(store_id, category_id, upload.name_key, file_sha256, config, replace_file_id)
    prior_key = await session.scalar(
        select(KnowledgeFileImportReceipt).where(
            KnowledgeFileImportReceipt.store_id == store_id,
            KnowledgeFileImportReceipt.created_by == user.id,
            KnowledgeFileImportReceipt.idempotency_key_hash == key_hash,
        )
    )
    if prior_key is not None:
        if prior_key.request_fingerprint != fingerprint:
            raise AppError(ErrorCode.RESOURCE_CONFLICT, "幂等键已用于其他文件", 409)
        prior_version = await session.get(KnowledgeFileVersion, prior_key.version_id)
        if prior_version is None or prior_version.store_id != store_id:
            raise AppError(ErrorCode.RESOURCE_CONFLICT, "原导入版本不可用", 409)
        return prior_version

    existing_file = await session.scalar(
        select(KnowledgeFile)
        .where(
            KnowledgeFile.store_id == store_id,
            KnowledgeFile.filename_key == upload.name_key,
            KnowledgeFile.deleted_at.is_(None),
        )
        .with_for_update()
    )
    if existing_file is not None and existing_file.archived_at is not None:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "归档文件请先恢复，再替换", 409)
    if existing_file is not None and category_id != existing_file.category_id:
        raise AppError(ErrorCode.VALIDATION_ERROR, "文件分类与现有文件不一致", 422)
    if replace_file_id is not None:
        if existing_file is None or existing_file.id != replace_file_id:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "要替换的文件不存在", 404)
    elif existing_file is not None:
        duplicate = await session.scalar(
            select(KnowledgeFileVersion)
            .where(
                KnowledgeFileVersion.file_id == existing_file.id,
                KnowledgeFileVersion.file_sha256 == file_sha256,
                KnowledgeFileVersion.config_json == config.model_dump(),
            )
            .order_by(KnowledgeFileVersion.version_number.desc())
            .limit(1)
        )
        if duplicate is not None:
            return await _return_existing_with_receipt(session, duplicate, store_id, user.id, key_hash, fingerprint)
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "同名文件已存在，请明确选择替换旧文件", 409)

    document_file = existing_file or KnowledgeFile(
        id=uuid.uuid4(),
        store_id=store_id,
        category_id=category_id,
        original_filename=upload.filename,
        filename_key=upload.name_key,
    )
    latest_version = None
    if existing_file is not None:
        latest_version = await session.scalar(
            select(KnowledgeFileVersion)
            .where(KnowledgeFileVersion.file_id == existing_file.id)
            .order_by(KnowledgeFileVersion.version_number.desc())
            .limit(1)
        )
        if (
            latest_version is not None
            and latest_version.file_sha256 == file_sha256
            and latest_version.config_json == config.model_dump()
        ):
            return await _return_existing_with_receipt(
                session, latest_version, store_id, user.id, key_hash, fingerprint
            )
    version_number = 1 if latest_version is None else latest_version.version_number + 1
    version_id = uuid.uuid4()
    object_key = f"knowledge-files/{store_id}/{document_file.id}/{version_id}{upload.suffix}"
    await put_import_file(object_key, content, upload.media_type)
    version = KnowledgeFileVersion(
        id=version_id,
        store_id=store_id,
        file_id=document_file.id,
        version_number=version_number,
        source_object_key=object_key,
        file_sha256=file_sha256,
        media_type=upload.media_type,
        config_json=config.model_dump(),
        status="queued",
        cleaning_version="clean-v1",
        retry_count=0,
        created_by=user.id,
    )
    try:
        if existing_file is None:
            session.add(document_file)
            await session.flush()
        session.add(version)
        await session.flush()
        session.add(_receipt(store_id, user.id, version.id, key_hash, fingerprint))
        session.add(
            AuditLog(
                store_id=store_id,
                actor_type="user",
                actor_id=user.id,
                action="knowledge.file_import",
                resource_type="knowledge_file_version",
                resource_id=version.id,
                request_id=key_hash,
                after_data={
                    "version_number": version.version_number,
                    "file_sha256": file_sha256,
                    "config_sha256": hashlib.sha256(
                        json.dumps(config.model_dump(), sort_keys=True).encode("utf-8")
                    ).hexdigest(),
                    "replaces_file": replace_file_id is not None,
                },
                result="succeeded",
            )
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        # 对象键随机，冲突时该私有对象成为可定期清理的孤儿对象。
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "文件或幂等键并发冲突", 409) from exc
    await session.refresh(version)
    return version


async def get_document_settings(session: AsyncSession, user: User, store_id: uuid.UUID) -> DocumentIndexConfig:
    """读取当前店铺未来导入的默认配置。"""
    await ensure_store_access(session, user, store_id)
    settings = await session.get(KnowledgeFileSettings, store_id)
    if settings is None:
        return DocumentIndexConfig()
    return DocumentIndexConfig.model_validate(
        {
            "strategy": settings.strategy,
            "chunk_size": settings.chunk_size,
            "overlap": settings.overlap,
            "parser_mode": settings.parser_mode,
            "embedding_model": settings.embedding_model,
        }
    )


async def save_document_settings(
    session: AsyncSession,
    user: User,
    store_id: uuid.UUID,
    config: DocumentIndexConfig,
    *,
    idempotency_key: str,
) -> DocumentIndexConfig:
    """只更新未来任务的店铺默认值；已有版本始终使用冻结快照。"""
    await ensure_store_access(session, user, store_id)
    settings = await session.scalar(
        select(KnowledgeFileSettings).where(KnowledgeFileSettings.store_id == store_id).with_for_update()
    )
    request_id = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
    prior = await session.scalar(
        select(AuditLog).where(
            AuditLog.store_id == store_id,
            AuditLog.action == "knowledge.file_settings_update",
            AuditLog.request_id == request_id,
        )
    )
    config_hash = hashlib.sha256(json.dumps(config.model_dump(), sort_keys=True).encode("utf-8")).hexdigest()
    if prior is not None:
        if prior.after_data is None or prior.after_data.get("config_sha256") != config_hash:
            raise AppError(ErrorCode.RESOURCE_CONFLICT, "幂等键已用于其他配置", 409)
        return config
    before = (
        {field: getattr(settings, field) for field in config.model_fields}
        if settings is not None
        else DocumentIndexConfig().model_dump()
    )
    if settings is None:
        settings = KnowledgeFileSettings(store_id=store_id, updated_by=user.id)
        session.add(settings)
    for field, value in config.model_dump().items():
        setattr(settings, field, value)
    settings.updated_by = user.id
    session.add(
        AuditLog(
            store_id=store_id,
            actor_type="user",
            actor_id=user.id,
            action="knowledge.file_settings_update",
            resource_type="knowledge_file_settings",
            resource_id=store_id,
            request_id=request_id,
            before_data={"config_sha256": hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest()},
            after_data={"config_sha256": config_hash},
            result="succeeded",
        )
    )
    await session.commit()
    return config


async def _scoped_file(session: AsyncSession, user: User, file_id: uuid.UUID) -> KnowledgeFile:
    stores = await allowed_store_ids(session, user)
    file = await session.scalar(
        select(KnowledgeFile).where(
            KnowledgeFile.id == file_id,
            KnowledgeFile.store_id.in_(stores),
            KnowledgeFile.deleted_at.is_(None),
        )
    )
    if file is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "文件不存在", 404)
    return file


async def _scoped_version(
    session: AsyncSession, user: User, file_id: uuid.UUID, version_number: int, *, lock: bool = False
) -> tuple[KnowledgeFile, KnowledgeFileVersion]:
    file = await _scoped_file(session, user, file_id)
    query = select(KnowledgeFileVersion).where(
        KnowledgeFileVersion.file_id == file.id,
        KnowledgeFileVersion.store_id == file.store_id,
        KnowledgeFileVersion.version_number == version_number,
    )
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    version = await session.scalar(query)
    if version is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "文件版本不存在", 404)
    return file, version


async def _version_summary(
    session: AsyncSession, file: KnowledgeFile, version: KnowledgeFileVersion, chunk_count: int | None = None
) -> DocumentVersionSummary:
    count = chunk_count
    if count is None:
        count = await session.scalar(
            select(func.count(KnowledgeFileChunk.id)).where(KnowledgeFileChunk.version_id == version.id)
        )
    return DocumentVersionSummary(
        id=version.id,
        version_number=version.version_number,
        status=version.status,
        error_code=version.error_code,
        retry_count=version.retry_count,
        created_at=version.created_at,
        completed_at=version.completed_at,
        is_active=file.active_version_number == version.version_number,
        chunk_count=count or 0,
        approval_status=getattr(version, "publication_approval", "draft"),
        statement_type=getattr(version, "statement_type", "unknown"),
        customer_scope=getattr(version, "customer_scope", "none"),
    )


async def approve_document_version(
    session: AsyncSession,
    user: User,
    file_id: uuid.UUID,
    version_number: int,
    payload: DocumentVersionApproval,
    idempotency_key: str,
) -> DocumentVersionDetail:
    """人工确认文件用途；客户回复须显式审批，不能由内部建议自动提升。"""
    file, version = await _scoped_version(session, user, file_id, version_number, lock=True)
    if file.deleted_at is not None or file.archived_at is not None or file.active_version_number != version_number:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "只能审批当前有效且未归档的文件版本", 409)
    if version.status != "ready":
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "文件版本尚未索引就绪", 409)
    if payload.statement_type == KnowledgeStatementType.UNKNOWN:
        raise AppError(ErrorCode.VALIDATION_ERROR, "审批时必须确认知识语义类型", 422)
    if payload.purpose == "public_reply" and (
        payload.statement_type == KnowledgeStatementType.TECHNICAL_ARTIFACT
        or payload.customer_scope != KnowledgeCustomerScope.GENERIC
    ):
        raise AppError(ErrorCode.VALIDATION_ERROR, "客户回复只能使用已确认通用范围的业务知识", 422)
    if payload.customer_scope == KnowledgeCustomerScope.SPECIFIC_CUSTOMER:
        raise AppError(ErrorCode.VALIDATION_ERROR, "客户实例事实不能用于通用知识检索", 422)
    if (
        payload.statement_type == KnowledgeStatementType.TECHNICAL_ARTIFACT
        and payload.customer_scope != KnowledgeCustomerScope.NONE
    ):
        raise AppError(ErrorCode.VALIDATION_ERROR, "技术资产不能绑定客户范围", 422)
    request_id = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
    prior = await session.scalar(
        select(AuditLog).where(
            AuditLog.store_id == file.store_id,
            AuditLog.action == "knowledge.file_version_approve",
            AuditLog.resource_id == version.id,
            AuditLog.request_id == request_id,
        )
    )
    expected = {
        "statement_type": payload.statement_type.value,
        "customer_scope": payload.customer_scope.value,
        "purpose": payload.purpose,
    }
    if prior is not None:
        prior_values = dict(prior.after_data or {})
        prior_values.setdefault("purpose", "internal_review")
        if prior.after_data is None or any(prior_values.get(key) != value for key, value in expected.items()):
            raise AppError(ErrorCode.RESOURCE_CONFLICT, "幂等键已用于其他审批", 409)
        await session.rollback()
        return await get_document_version(session, user, file_id, version_number)
    if version.publication_approval != KnowledgePublicationApproval.DRAFT:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "当前版本已审批；如需变更请上传替换版本", 409)
    version.statement_type = payload.statement_type.value
    version.customer_scope = payload.customer_scope.value
    version.publication_approval = (
        KnowledgePublicationApproval.APPROVED_FOR_PUBLIC_REPLY.value
        if payload.purpose == "public_reply"
        else KnowledgePublicationApproval.APPROVED_FOR_INTERNAL_REVIEW.value
    )
    version.approved_by = user.id
    version.approved_at = datetime.now(UTC)
    session.add(
        AuditLog(
            store_id=file.store_id,
            actor_type="user",
            actor_id=user.id,
            action="knowledge.file_version_approve",
            resource_type="knowledge_file_version",
            resource_id=version.id,
            request_id=request_id,
            before_data={"publication_approval": "draft"},
            after_data={**expected, "publication_approval": version.publication_approval},
            result="succeeded",
        )
    )
    await session.commit()
    return await get_document_version(session, user, file_id, version_number)


async def revoke_document_version(
    session: AsyncSession, user: User, file_id: uuid.UUID, version_number: int, idempotency_key: str
) -> DocumentVersionDetail:
    """撤销内部建议授权，下一次检索立即失效。"""
    file, version = await _scoped_version(session, user, file_id, version_number, lock=True)
    request_id = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
    prior = await session.scalar(
        select(AuditLog).where(
            AuditLog.store_id == file.store_id,
            AuditLog.action == "knowledge.file_version_revoke",
            AuditLog.resource_id == version.id,
            AuditLog.request_id == request_id,
        )
    )
    if prior is not None:
        await session.rollback()
        return await get_document_version(session, user, file_id, version_number)
    if version.publication_approval == KnowledgePublicationApproval.DRAFT:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "当前文件版本尚未审批", 409)
    before = {"publication_approval": version.publication_approval}
    version.publication_approval = KnowledgePublicationApproval.DRAFT.value
    version.approved_by = None
    version.approved_at = None
    session.add(
        AuditLog(
            store_id=file.store_id,
            actor_type="user",
            actor_id=user.id,
            action="knowledge.file_version_revoke",
            resource_type="knowledge_file_version",
            resource_id=version.id,
            request_id=request_id,
            before_data=before,
            after_data={"publication_approval": "draft"},
            result="succeeded",
        )
    )
    await session.commit()
    return await get_document_version(session, user, file_id, version_number)


async def _chunk_counts(session: AsyncSession, version_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not version_ids:
        return {}
    rows = await session.execute(
        select(KnowledgeFileChunk.version_id, func.count(KnowledgeFileChunk.id))
        .where(KnowledgeFileChunk.version_id.in_(version_ids))
        .group_by(KnowledgeFileChunk.version_id)
    )
    return {row[0]: row[1] for row in rows}


def _validated_locator(value: dict[str, object]) -> dict[str, int]:
    if any(not isinstance(item, int) or isinstance(item, bool) for item in value.values()):
        raise AppError(ErrorCode.INTERNAL_ERROR, "文件来源定位信息无效", 500)
    return {key: item for key, item in value.items() if isinstance(item, int)}


async def _file_summary(
    session: AsyncSession, file: KnowledgeFile, latest: KnowledgeFileVersion, chunk_count: int | None = None
) -> DocumentFileSummary:
    return DocumentFileSummary(
        id=file.id,
        store_id=file.store_id,
        category_id=file.category_id,
        filename=file.original_filename,
        active_version_number=file.active_version_number,
        archived_at=file.archived_at,
        latest_version=await _version_summary(session, file, latest, chunk_count),
    )


async def list_document_files(
    session: AsyncSession,
    user: User,
    store_id: uuid.UUID,
    category_id: uuid.UUID | None,
    search: str | None,
    page: int,
    page_size: int,
    categorized_only: bool = False,
) -> DocumentFilePage:
    await ensure_store_access(session, user, store_id)
    query = select(KnowledgeFile).where(KnowledgeFile.store_id == store_id, KnowledgeFile.deleted_at.is_(None))
    if category_id is not None:
        query = query.where(KnowledgeFile.category_id == category_id)
    if categorized_only:
        visible_categories = select(KnowledgeCategory.id).where(
            KnowledgeCategory.store_id == store_id,
            KnowledgeCategory.status == "active",
        )
        query = query.where(KnowledgeFile.category_id.in_(visible_categories))
    if search:
        query = query.where(KnowledgeFile.original_filename.ilike(f"%{search}%"))
    total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
    files = (
        await session.scalars(
            query.order_by(KnowledgeFile.created_at.desc(), KnowledgeFile.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    if not files:
        return DocumentFilePage(items=[], total=total, page=page, page_size=page_size)
    latest_numbers = (
        select(
            KnowledgeFileVersion.file_id,
            func.max(KnowledgeFileVersion.version_number).label("latest_number"),
        )
        .where(KnowledgeFileVersion.file_id.in_([file.id for file in files]))
        .group_by(KnowledgeFileVersion.file_id)
        .subquery()
    )
    versions = (
        await session.scalars(
            select(KnowledgeFileVersion).join(
                latest_numbers,
                and_(
                    KnowledgeFileVersion.file_id == latest_numbers.c.file_id,
                    KnowledgeFileVersion.version_number == latest_numbers.c.latest_number,
                ),
            )
        )
    ).all()
    latest_by_file = {version.file_id: version for version in versions}
    chunk_counts = await _chunk_counts(session, [version.id for version in latest_by_file.values()])
    items: list[DocumentFileSummary] = []
    for file in files:
        latest = latest_by_file.get(file.id)
        if latest is not None:
            items.append(await _file_summary(session, file, latest, chunk_counts.get(latest.id, 0)))
    return DocumentFilePage(items=items, total=total, page=page, page_size=page_size)


async def get_document_file(session: AsyncSession, user: User, file_id: uuid.UUID) -> DocumentFileDetail:
    file = await _scoped_file(session, user, file_id)
    versions = (
        await session.scalars(
            select(KnowledgeFileVersion)
            .where(KnowledgeFileVersion.file_id == file.id)
            .order_by(KnowledgeFileVersion.version_number.desc())
        )
    ).all()
    if not versions:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "文件版本不存在", 404)
    counts = await _chunk_counts(session, [version.id for version in versions])
    summary = await _file_summary(session, file, versions[0], counts.get(versions[0].id, 0))
    return DocumentFileDetail(
        **summary.model_dump(),
        versions=[await _version_summary(session, file, version, counts.get(version.id, 0)) for version in versions],
    )


async def change_document_file(
    session: AsyncSession,
    user: User,
    file_id: uuid.UUID,
    action: str,
    idempotency_key: str,
    category_id: uuid.UUID | None = None,
) -> DocumentFileDetail | None:
    """对逻辑文件执行店铺隔离的元数据操作；历史版本和原文件保持不变。"""
    if action not in {"category_update", "archive", "restore", "delete"}:
        raise ValueError("unsupported file action")
    request_id = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
    stores = await allowed_store_ids(session, user)
    file = await session.scalar(
        select(KnowledgeFile).where(KnowledgeFile.id == file_id, KnowledgeFile.store_id.in_(stores)).with_for_update()
    )
    if file is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "文件不存在", 404)
    audit_action = f"knowledge.file_{action}"
    prior = await session.scalar(
        select(AuditLog).where(
            AuditLog.store_id == file.store_id,
            AuditLog.action == audit_action,
            AuditLog.resource_id == file.id,
            AuditLog.request_id == request_id,
        )
    )
    if prior is not None:
        if action == "category_update" and prior.after_data != {"category_id": str(category_id)}:
            raise AppError(ErrorCode.RESOURCE_CONFLICT, "幂等键已用于其他分类", 409)
        await session.commit()
        return None if action == "delete" else await get_document_file(session, user, file_id)
    if file.deleted_at is not None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "文件不存在", 404)
    before: dict[str, object]
    after: dict[str, object]
    if action == "category_update":
        if category_id is None:
            raise AppError(ErrorCode.VALIDATION_ERROR, "请选择归属分类", 422)
        category = await session.scalar(
            select(KnowledgeCategory.id).where(
                KnowledgeCategory.id == category_id,
                KnowledgeCategory.store_id == file.store_id,
                KnowledgeCategory.status == "active",
            )
        )
        if category is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "分类不存在", 404)
        before = {"category_id": str(file.category_id) if file.category_id else None}
        after = {"category_id": str(category_id)}
        file.category_id = category_id
    else:
        if action in {"archive", "delete"}:
            processing = await session.scalar(
                select(KnowledgeFileVersion.id)
                .where(
                    KnowledgeFileVersion.file_id == file.id,
                    KnowledgeFileVersion.status.in_(["queued", "parsing", "indexing"]),
                )
                .limit(1)
            )
            if processing is not None:
                raise AppError(ErrorCode.RESOURCE_CONFLICT, "文件正在处理，请完成后再操作", 409)
        before = {"archived": file.archived_at is not None, "deleted": file.deleted_at is not None}
        now = datetime.now(UTC)
        if action == "archive":
            file.archived_at = file.archived_at or now
        elif action == "restore":
            file.archived_at = None
        else:
            file.deleted_at = now
            file.archived_at = file.archived_at or now
        after = {"archived": file.archived_at is not None, "deleted": file.deleted_at is not None}
    session.add(
        AuditLog(
            store_id=file.store_id,
            actor_type="user",
            actor_id=user.id,
            action=audit_action,
            resource_type="knowledge_file",
            resource_id=file.id,
            request_id=request_id,
            before_data=before,
            after_data=after,
            result="succeeded",
        )
    )
    await session.commit()
    return None if action == "delete" else await get_document_file(session, user, file_id)


async def get_document_version(
    session: AsyncSession, user: User, file_id: uuid.UUID, version_number: int
) -> DocumentVersionDetail:
    file, version = await _scoped_version(session, user, file_id, version_number)
    units = (
        await session.scalars(
            select(KnowledgeFileUnit)
            .where(KnowledgeFileUnit.version_id == version.id)
            .order_by(KnowledgeFileUnit.unit_index)
        )
    ).all()
    summary = await _version_summary(session, file, version)
    return DocumentVersionDetail(
        **summary.model_dump(),
        file_id=file.id,
        filename=file.original_filename,
        file_sha256=version.file_sha256,
        config=DocumentIndexConfig.model_validate(version.config_json),
        parser_version=version.parser_version,
        cleaning_version=version.cleaning_version,
        units=[
            DocumentUnitView(
                unit_index=unit.unit_index,
                unit_kind=unit.unit_kind,
                source_locator=_validated_locator(unit.source_locator),
                raw_text=unit.raw_text,
                cleaned_text=unit.cleaned_text,
                issue_codes=unit.issue_codes,
                needs_review=unit.needs_review,
                parse_mode=unit.parse_mode,
                reviewed_by=unit.reviewed_by,
                reviewed_at=unit.reviewed_at,
            )
            for unit in units
        ],
    )


async def get_document_source(
    session: AsyncSession, user: User, file_id: uuid.UUID, version_number: int
) -> tuple[bytes, str, str]:
    """只对有权限的店铺成员读取原件，供人工核对 OCR 与表格。"""
    file, version = await _scoped_version(session, user, file_id, version_number)
    try:
        content = await asyncio.to_thread(get_import_file, version.source_object_key, max_bytes=MAX_DOCUMENT_BYTES)
    except Exception as exc:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "原文件暂时无法读取", 503) from exc
    return content, version.media_type, file.original_filename


async def review_document_unit(
    session: AsyncSession,
    user: User,
    file_id: uuid.UUID,
    version_number: int,
    unit_index: int,
    payload: DocumentUnitReview,
    idempotency_key: str,
) -> DocumentVersionDetail:
    # 延迟导入以避免通用解析器引用上传限制时形成模块循环。
    from app.knowledge_base.document_cleaning import clean_unit
    from app.knowledge_base.document_parser import ParsedUnit

    file, version = await _scoped_version(session, user, file_id, version_number, lock=True)
    if file.archived_at is not None:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "归档文件请先恢复，再复核", 409)
    request_id = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
    text_hash = hashlib.sha256(payload.corrected_text.encode("utf-8")).hexdigest()
    prior = await session.scalar(
        select(AuditLog).where(
            AuditLog.store_id == file.store_id,
            AuditLog.action == "knowledge.file_unit_review",
            AuditLog.resource_id == version.id,
            AuditLog.request_id == request_id,
        )
    )
    if prior is not None:
        if (
            prior.after_data is None
            or prior.after_data.get("text_sha256") != text_hash
            or prior.after_data.get("unit_index") != unit_index
        ):
            raise AppError(ErrorCode.RESOURCE_CONFLICT, "幂等键已用于其他复核", 409)
        await session.rollback()
        return await get_document_version(session, user, file_id, version_number)
    if version.status != "review_required":
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "当前版本不在待复核状态", 409)
    unit = await session.scalar(
        select(KnowledgeFileUnit)
        .where(KnowledgeFileUnit.version_id == version.id, KnowledgeFileUnit.unit_index == unit_index)
        .with_for_update()
    )
    if unit is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "复核单元不存在", 404)
    if not unit.needs_review:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "该单元已经完成复核", 409)
    config = DocumentIndexConfig.model_validate(version.config_json)
    block_type = "table" if config.strategy == "table_rows" else "text"
    corrected = clean_unit(
        ParsedUnit(
            index=unit.unit_index,
            kind=unit.unit_kind,
            locator=_validated_locator(unit.source_locator),
            blocks=[{"type": block_type, "content": payload.corrected_text}],
            parse_mode=unit.parse_mode,
            ocr_derived=False,
            parser_version=version.parser_version or "unknown",
        )
    )
    if corrected.needs_review:
        raise AppError(ErrorCode.VALIDATION_ERROR, "修订内容仍无法可靠识别，请补全后重试", 422)
    prior_issues = unit.issue_codes.copy()
    unit.cleaned_text = corrected.cleaned_text
    unit.blocks_json = corrected.blocks
    unit.issue_codes = []
    unit.needs_review = False
    unit.reviewed_by = user.id
    unit.reviewed_at = datetime.now(UTC)
    remaining = await session.scalar(
        select(func.count(KnowledgeFileUnit.id)).where(
            KnowledgeFileUnit.version_id == version.id,
            KnowledgeFileUnit.needs_review.is_(True),
            KnowledgeFileUnit.id != unit.id,
        )
    )
    if not remaining:
        version.status = "queued"
        version.error_code = None
        version.lease_owner = None
        version.lease_until = None
    session.add(
        AuditLog(
            store_id=file.store_id,
            actor_type="user",
            actor_id=user.id,
            action="knowledge.file_unit_review",
            resource_type="knowledge_file_version",
            resource_id=version.id,
            request_id=request_id,
            before_data={"unit_index": unit_index, "issue_codes": prior_issues},
            after_data={
                "unit_index": unit_index,
                "text_sha256": text_hash,
                "remaining_review_units": remaining or 0,
            },
            result="succeeded",
        )
    )
    await session.commit()
    return await get_document_version(session, user, file_id, version_number)


RETRYABLE_CODES = {
    "PARSER_EXECUTION_FAILED",
    "PARSER_UNAVAILABLE",
    "PARSER_TIMEOUT",
    "PARSER_SOURCE_UNAVAILABLE",
    "EMBEDDING_OUTPUT_INVALID",
    "EMBEDDING_REVISION_MISMATCH",
    "DOCUMENT_PROCESSING_FAILED",
    "DOCUMENT_LEASE_LOST",
}


async def retry_document_version(
    session: AsyncSession,
    user: User,
    file_id: uuid.UUID,
    version_number: int,
    idempotency_key: str,
) -> DocumentVersionDetail:
    file, version = await _scoped_version(session, user, file_id, version_number, lock=True)
    if file.archived_at is not None:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "归档文件请先恢复，再重试", 409)
    request_id = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
    prior = await session.scalar(
        select(AuditLog).where(
            AuditLog.store_id == file.store_id,
            AuditLog.action == "knowledge.file_version_retry",
            AuditLog.resource_id == version.id,
            AuditLog.request_id == request_id,
        )
    )
    if prior is not None:
        await session.rollback()
        return await get_document_version(session, user, file_id, version_number)
    if version.status not in {"failed_retryable", "failed_final"} or version.error_code not in RETRYABLE_CODES:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "当前失败原因不能直接重试", 409)
    before = version.status
    version.status = "queued"
    version.error_code = None
    version.retry_count = 0
    version.lease_owner = None
    version.lease_until = None
    version.completed_at = None
    session.add(
        AuditLog(
            store_id=file.store_id,
            actor_type="user",
            actor_id=user.id,
            action="knowledge.file_version_retry",
            resource_type="knowledge_file_version",
            resource_id=version.id,
            request_id=request_id,
            before_data={"status": before},
            after_data={"status": "queued"},
            result="succeeded",
        )
    )
    await session.commit()
    return await get_document_version(session, user, file_id, version_number)
