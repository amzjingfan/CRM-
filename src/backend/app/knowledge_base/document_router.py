"""店铺隔离的通用 RAG 文件导入、整版复核和配置接口。"""

import uuid
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from pydantic import ValidationError

from app.auth.dependencies import get_current_user, require_csrf, require_idempotency_key, require_permission
from app.knowledge_base.document_api_schemas import (
    DocumentFileDetail,
    DocumentFilePage,
    DocumentImportAccepted,
    DocumentUnitReview,
    DocumentVersionDetail,
)
from app.knowledge_base.document_schemas import DocumentIndexConfig
from app.knowledge_base.document_service import (
    MAX_DOCUMENT_BYTES,
    DocumentUploadError,
    accept_document_import,
    get_document_file,
    get_document_settings,
    get_document_source,
    get_document_version,
    list_document_files,
    retry_document_version,
    review_document_unit,
    save_document_settings,
)
from app.shared.config.settings import get_settings
from app.shared.database.base import User
from app.shared.database.session import DbSession
from app.shared.exceptions.errors import AppError, ErrorCode
from app.shared.schemas.responses import ApiResponse

router = APIRouter(prefix="/knowledge", tags=["知识库文件"])
WRITE_GUARDS = [
    Depends(require_csrf),
    Depends(require_permission("knowledge.manage")),
]


@router.get(
    "/files",
    response_model=ApiResponse[DocumentFilePage],
    dependencies=[Depends(require_permission("knowledge.view"))],
)
async def document_files(
    store_id: uuid.UUID,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
    category_id: uuid.UUID | None = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    categorized_only: bool = False,
) -> ApiResponse[DocumentFilePage]:
    return ApiResponse(
        data=await list_document_files(session, user, store_id, category_id, search, page, page_size, categorized_only)
    )


@router.get(
    "/files/{file_id}",
    response_model=ApiResponse[DocumentFileDetail],
    dependencies=[Depends(require_permission("knowledge.view"))],
)
async def document_file(
    file_id: uuid.UUID, session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> ApiResponse[DocumentFileDetail]:
    return ApiResponse(data=await get_document_file(session, user, file_id))


@router.get(
    "/files/{file_id}/versions/{version_number}",
    response_model=ApiResponse[DocumentVersionDetail],
    dependencies=[Depends(require_permission("knowledge.view"))],
)
async def document_version(
    file_id: uuid.UUID,
    version_number: int,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[DocumentVersionDetail]:
    return ApiResponse(data=await get_document_version(session, user, file_id, version_number))


@router.get(
    "/files/{file_id}/versions/{version_number}/source",
    dependencies=[Depends(require_permission("knowledge.view"))],
)
async def document_source(
    file_id: uuid.UUID,
    version_number: int,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
) -> Response:
    content, media_type, filename = await get_document_source(session, user, file_id, version_number)
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post(
    "/files/imports",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ApiResponse[DocumentImportAccepted],
    dependencies=WRITE_GUARDS,
)
async def import_document_file(
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
    store_id: Annotated[uuid.UUID, Form()],
    file: Annotated[UploadFile, File()],
    config_json: Annotated[str, Form(max_length=4096)],
    category_id: Annotated[uuid.UUID | None, Form()] = None,
    replace_file_id: Annotated[uuid.UUID | None, Form()] = None,
) -> ApiResponse[DocumentImportAccepted]:
    """有界读取 multipart，配置随文件版本冻结，同名变化须显式指定替换目标。"""
    limit = min(get_settings().knowledge_file_import_max_bytes, MAX_DOCUMENT_BYTES)
    try:
        content = await file.read(limit + 1)
    finally:
        await file.close()
    if len(content) > limit:
        raise AppError(ErrorCode.VALIDATION_ERROR, "FILE_SIZE_INVALID", 413)
    try:
        config = DocumentIndexConfig.model_validate_json(config_json)
    except ValidationError as exc:
        raise AppError(ErrorCode.VALIDATION_ERROR, "导入配置无效", 422) from exc
    try:
        version = await accept_document_import(
            session,
            user,
            store_id,
            category_id,
            file.filename or "",
            file.content_type or "application/octet-stream",
            content,
            config,
            replace_file_id,
            idempotency_key,
        )
    except DocumentUploadError as exc:
        raise AppError(ErrorCode.VALIDATION_ERROR, exc.code, 422) from exc
    return ApiResponse(
        data=DocumentImportAccepted(
            file_id=version.file_id,
            version_id=version.id,
            version_number=version.version_number,
            status=version.status,
        )
    )


@router.post(
    "/files/{file_id}/versions/{version_number}/units/{unit_index}/review",
    response_model=ApiResponse[DocumentVersionDetail],
    dependencies=WRITE_GUARDS,
)
async def review_document_file_unit(
    file_id: uuid.UUID,
    version_number: int,
    unit_index: int,
    payload: DocumentUnitReview,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
) -> ApiResponse[DocumentVersionDetail]:
    return ApiResponse(
        data=await review_document_unit(session, user, file_id, version_number, unit_index, payload, idempotency_key)
    )


@router.post(
    "/files/{file_id}/versions/{version_number}/retry",
    response_model=ApiResponse[DocumentVersionDetail],
    dependencies=WRITE_GUARDS,
)
async def retry_document_file_version(
    file_id: uuid.UUID,
    version_number: int,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
) -> ApiResponse[DocumentVersionDetail]:
    return ApiResponse(data=await retry_document_version(session, user, file_id, version_number, idempotency_key))


@router.get(
    "/file-settings",
    response_model=ApiResponse[DocumentIndexConfig],
    dependencies=[Depends(require_permission("knowledge.view"))],
)
async def document_settings(
    store_id: uuid.UUID, session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> ApiResponse[DocumentIndexConfig]:
    return ApiResponse(data=await get_document_settings(session, user, store_id))


@router.put(
    "/file-settings",
    response_model=ApiResponse[DocumentIndexConfig],
    dependencies=WRITE_GUARDS,
)
async def update_document_settings(
    store_id: uuid.UUID,
    config: DocumentIndexConfig,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
) -> ApiResponse[DocumentIndexConfig]:
    return ApiResponse(
        data=await save_document_settings(session, user, store_id, config, idempotency_key=idempotency_key)
    )
