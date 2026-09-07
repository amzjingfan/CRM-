"""FAQ 知识库管理 HTTP 接口。"""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status

from app.auth.dependencies import get_current_user, require_csrf, require_idempotency_key, require_permission
from app.knowledge_base.schemas import (
    CategoryCreate,
    CategoryUpdate,
    CategoryView,
    ImportAccepted,
    ImportJobView,
    KnowledgeEntryCreate,
    KnowledgeEntryUpdate,
    KnowledgeEntryView,
    KnowledgePage,
    KnowledgeVectorizationStatus,
)
from app.knowledge_base.service import (
    accept_import,
    create_category,
    create_entry,
    delete_category,
    delete_entry,
    get_categories,
    get_entries,
    get_entry,
    get_import_job,
    get_vectorization_status,
    retry_entry_vectorization,
    set_entry_status,
    update_category,
    update_entry,
)
from app.shared.database.base import User
from app.shared.database.session import DbSession
from app.shared.schemas.responses import ApiResponse

router = APIRouter(
    prefix="/knowledge",
    tags=["知识库"],
)


@router.get("/categories", response_model=ApiResponse[list[CategoryView]])
async def categories(
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
    store_id: uuid.UUID | None = None,
) -> ApiResponse[list[CategoryView]]:
    """查询授权店铺 FAQ 分类。"""
    return ApiResponse(
        data=[CategoryView.model_validate(item) for item in await get_categories(session, user, store_id)]
    )


@router.post(
    "/categories",
    description="需要 knowledge.manage 权限；按 store_id 隔离；重复请求必须复用 Idempotency-Key。",
    response_model=ApiResponse[CategoryView],
    dependencies=[
        Depends(require_csrf),
        Depends(require_permission("knowledge.manage")),
        Depends(require_idempotency_key),
    ],
)
async def add_category(
    payload: CategoryCreate, session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> ApiResponse[CategoryView]:
    """创建 C 层 FAQ 分类。"""
    return ApiResponse(data=CategoryView.model_validate(await create_category(session, user, payload)))


@router.patch(
    "/categories/{category_id}",
    description=(
        "需要 knowledge.manage 权限；只能更新用户可访问店铺内的分类；"
        "父分类必须属于同一 store_id 且不能形成循环；重复请求必须复用 Idempotency-Key。"
    ),
    response_model=ApiResponse[CategoryView],
    dependencies=[
        Depends(require_csrf),
        Depends(require_permission("knowledge.manage")),
        Depends(require_idempotency_key),
    ],
)
async def edit_category(
    category_id: uuid.UUID,
    payload: CategoryUpdate,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[CategoryView]:
    """更新 FAQ 分类。"""
    return ApiResponse(data=CategoryView.model_validate(await update_category(session, user, category_id, payload)))


@router.delete(
    "/categories/{category_id}",
    description=(
        "需要 knowledge.manage 权限；只能删除用户可访问店铺内且没有子分类或 FAQ 的分类；"
        "跨店铺资源返回 40401；重复请求必须复用 Idempotency-Key。"
    ),
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[
        Depends(require_csrf),
        Depends(require_permission("knowledge.manage")),
        Depends(require_idempotency_key),
    ],
)
async def remove_category(
    category_id: uuid.UUID, session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> Response:
    """删除空分类。"""
    await delete_category(session, user, category_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/entries",
    response_model=ApiResponse[KnowledgePage],
    dependencies=[Depends(require_permission("knowledge.view"))],
)
async def entries(
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
    store_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    layer: Annotated[Literal["A", "B", "C", "D"] | None, Query()] = None,
    entry_status: Annotated[Literal["draft", "published", "archived"] | None, Query(alias="status")] = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse[KnowledgePage]:
    """分页查询 FAQ。"""
    return ApiResponse(
        data=await get_entries(session, user, store_id, category_id, layer, entry_status, search, page, page_size)
    )


@router.get(
    "/vectorization/status",
    description=(
        "需要 knowledge.view 权限；按 store_id 汇总已发布 FAQ 的 BGE-M3 向量化状态；"
        "响应不包含模型本机路径、内部令牌或知识正文。"
    ),
    response_model=ApiResponse[KnowledgeVectorizationStatus],
    dependencies=[Depends(require_permission("knowledge.view"))],
)
async def vectorization_status(
    store_id: uuid.UUID,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[KnowledgeVectorizationStatus]:
    """查询单个授权店铺的本地 BGE 向量化队列状态。"""
    return ApiResponse(data=await get_vectorization_status(session, user, store_id))


@router.post(
    "/entries",
    description=(
        "需要 knowledge.manage 权限；创建草稿按 store_id 隔离；statement_type 和 customer_scope "
        "缺省时分别为 unknown 和 none，但 unknown 不能发布；重复请求必须复用 Idempotency-Key。"
    ),
    response_model=ApiResponse[KnowledgeEntryView],
    dependencies=[
        Depends(require_csrf),
        Depends(require_permission("knowledge.manage")),
        Depends(require_idempotency_key),
    ],
)
async def add_entry(
    payload: KnowledgeEntryCreate, session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> ApiResponse[KnowledgeEntryView]:
    """创建 FAQ 草稿。"""
    return ApiResponse(data=KnowledgeEntryView.model_validate(await create_entry(session, user, payload)))


@router.get(
    "/entries/{entry_id}",
    response_model=ApiResponse[KnowledgeEntryView],
    dependencies=[Depends(require_permission("knowledge.view"))],
)
async def entry_detail(
    entry_id: uuid.UUID, session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> ApiResponse[KnowledgeEntryView]:
    """获取单个 FAQ，并执行资源级店铺隔离。"""
    return ApiResponse(data=KnowledgeEntryView.model_validate(await get_entry(session, user, entry_id)))


@router.patch(
    "/entries/{entry_id}",
    description=(
        "需要 knowledge.manage 权限；FAQ 按资源所属 store_id 隔离；"
        "正文或语义类型变化会递增版本、撤销审批并回到 draft + pending；"
        "重复请求必须复用 Idempotency-Key。"
    ),
    response_model=ApiResponse[KnowledgeEntryView],
    dependencies=[
        Depends(require_csrf),
        Depends(require_permission("knowledge.manage")),
        Depends(require_idempotency_key),
    ],
)
async def edit_entry(
    entry_id: uuid.UUID,
    payload: KnowledgeEntryUpdate,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[KnowledgeEntryView]:
    """更新 FAQ 并按内容变化失效旧向量。"""
    return ApiResponse(data=KnowledgeEntryView.model_validate(await update_entry(session, user, entry_id, payload)))


@router.delete(
    "/entries/{entry_id}",
    description=(
        "需要 knowledge.manage 权限；FAQ 按资源所属 store_id 隔离并执行软删除；"
        "跨店铺资源返回 40401；重复请求必须复用 Idempotency-Key。"
    ),
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[
        Depends(require_csrf),
        Depends(require_permission("knowledge.manage")),
        Depends(require_idempotency_key),
    ],
)
async def remove_entry(
    entry_id: uuid.UUID, session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> Response:
    """软删除 FAQ。"""
    await delete_entry(session, user, entry_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/entries/{entry_id}/publish",
    description=(
        "需要 knowledge.manage 权限；FAQ 按资源所属 store_id 隔离；"
        "发布即由当前操作人批准该精确版本仅供内部 AI 复核，unknown 禁止发布；"
        "异步向量 ready 前不能检索，FAQ 不获得自动回复权限；重复请求必须复用 Idempotency-Key。"
    ),
    response_model=ApiResponse[KnowledgeEntryView],
    dependencies=[
        Depends(require_csrf),
        Depends(require_permission("knowledge.manage")),
        Depends(require_idempotency_key),
    ],
)
async def publish_entry(
    entry_id: uuid.UUID, session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> ApiResponse[KnowledgeEntryView]:
    """发布 FAQ，但在向量完成前仍不能正式检索。"""
    return ApiResponse(
        data=KnowledgeEntryView.model_validate(await set_entry_status(session, user, entry_id, "published"))
    )


@router.post(
    "/entries/{entry_id}/archive",
    description=(
        "需要 knowledge.manage 权限；FAQ 按资源所属 store_id 隔离；"
        "归档后立即退出正式检索；重复请求必须复用 Idempotency-Key。"
    ),
    response_model=ApiResponse[KnowledgeEntryView],
    dependencies=[
        Depends(require_csrf),
        Depends(require_permission("knowledge.manage")),
        Depends(require_idempotency_key),
    ],
)
async def archive_entry(
    entry_id: uuid.UUID, session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> ApiResponse[KnowledgeEntryView]:
    """归档 FAQ 并立即退出正式检索。"""
    return ApiResponse(
        data=KnowledgeEntryView.model_validate(await set_entry_status(session, user, entry_id, "archived"))
    )


@router.post(
    "/entries/{entry_id}/vectorization/retry",
    description=(
        "需要 knowledge.manage 权限；仅允许把授权店铺内 published + failed 的 FAQ 放回 pending；"
        "重复请求必须复用 Idempotency-Key，跨店铺资源统一返回 40401。"
    ),
    response_model=ApiResponse[KnowledgeEntryView],
    dependencies=[
        Depends(require_csrf),
        Depends(require_permission("knowledge.manage")),
        Depends(require_idempotency_key),
    ],
)
async def retry_vectorization(
    entry_id: uuid.UUID,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[KnowledgeEntryView]:
    """人工重试失败的 BGE-M3 向量化任务。"""
    document = await retry_entry_vectorization(session, user, entry_id)
    return ApiResponse(data=KnowledgeEntryView.model_validate(document))


@router.post(
    "/imports",
    description="需要 knowledge.manage 权限；文件进入异步任务，按 store_id 隔离；重复提交必须复用 Idempotency-Key。",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ApiResponse[ImportAccepted],
    dependencies=[
        Depends(require_csrf),
        Depends(require_permission("knowledge.manage")),
        Depends(require_idempotency_key),
    ],
)
async def import_entries(
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
    store_id: Annotated[uuid.UUID, Form()],
    file: Annotated[UploadFile, File()],
) -> ApiResponse[ImportAccepted]:
    """受理不超过 10 MiB 的 CSV/XLSX，并交给独立 Worker。"""
    content = await file.read()
    job = await accept_import(
        session,
        user,
        store_id,
        file.filename or "knowledge-import",
        file.content_type or "application/octet-stream",
        content,
    )
    return ApiResponse(data=ImportAccepted(job_id=job.id, status="pending"))


@router.get(
    "/imports/{job_id}",
    response_model=ApiResponse[ImportJobView],
    dependencies=[Depends(require_permission("knowledge.view"))],
)
async def import_status(
    job_id: uuid.UUID, session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> ApiResponse[ImportJobView]:
    """查询异步导入进度。"""
    return ApiResponse(data=ImportJobView.model_validate(await get_import_job(session, user, job_id)))
