"""MinIO FAQ 导入文件存储封装。"""

import asyncio
import io

from minio import Minio

from app.shared.config.settings import get_settings


def _client() -> Minio:
    """使用类型化配置创建客户端，调用方不得记录访问密钥。"""
    settings = get_settings()
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


def _put(object_key: str, content: bytes, content_type: str) -> None:
    settings = get_settings()
    client = _client()
    if not client.bucket_exists(settings.minio_bucket):
        client.make_bucket(settings.minio_bucket)
    client.put_object(settings.minio_bucket, object_key, io.BytesIO(content), len(content), content_type=content_type)


async def put_import_file(object_key: str, content: bytes, content_type: str) -> None:
    """在线程中执行同步 MinIO SDK，避免阻塞 FastAPI 事件循环。"""
    await asyncio.to_thread(_put, object_key, content, content_type)


def get_import_file(object_key: str, *, max_bytes: int | None = None) -> bytes:
    """由独立任务进程读取对象，并确保连接及时释放。"""
    settings = get_settings()
    response = _client().get_object(settings.minio_bucket, object_key)
    try:
        content = response.read(max_bytes + 1) if max_bytes is not None else response.read()
        if max_bytes is not None and len(content) > max_bytes:
            raise ValueError("FILE_SIZE_INVALID")
        return content
    finally:
        response.close()
        response.release_conn()
