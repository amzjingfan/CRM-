"""通用文档配置和文件边界的确定性测试。"""

import io
import zipfile

import pytest
from pydantic import ValidationError

from app.knowledge_base.document_schemas import DocumentIndexConfig
from app.knowledge_base.document_service import DocumentUploadError, validate_document_upload


def _office_file(member: str, *, macro: bool = False) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr(member, "<document />")
        if macro:
            archive.writestr("word/vbaProject.bin", b"macro")
    return buffer.getvalue()


def test_index_defaults_and_real_size_boundaries() -> None:
    assert DocumentIndexConfig().model_dump() == {
        "strategy": "recursive",
        "chunk_size": 500,
        "overlap": 50,
        "parser_mode": "auto",
        "embedding_model": "BAAI/bge-m3",
    }
    chars = DocumentIndexConfig(strategy="fixed_char")
    assert (chars.chunk_size, chars.overlap) == (1000, 100)
    custom = DocumentIndexConfig(strategy="fixed_token", chunk_size=320, overlap=24)
    assert (custom.chunk_size, custom.overlap) == (320, 24)
    with pytest.raises(ValidationError):
        DocumentIndexConfig(chunk_size=50, overlap=50)
    with pytest.raises(ValidationError):
        DocumentIndexConfig(strategy="unknown")


def test_upload_sniffs_pdf_image_office_and_text() -> None:
    assert validate_document_upload("guide.pdf", "application/pdf", b"%PDF-1.7\nhello").suffix == ".pdf"
    assert validate_document_upload("photo.png", "image/png", b"\x89PNG\r\n\x1a\nrest").suffix == ".png"
    assert (
        validate_document_upload("report.docx", "application/octet-stream", _office_file("word/document.xml")).suffix
        == ".docx"
    )
    assert validate_document_upload("notes.md", "text/markdown", "退货期限 7 天".encode()).suffix == ".md"


@pytest.mark.parametrize(
    ("name", "media_type", "payload"),
    [
        ("fake.pdf", "application/pdf", b"not a pdf"),
        ("macro.docx", "application/octet-stream", _office_file("word/document.xml", macro=True)),
        ("nested.exe", "application/octet-stream", b"MZ"),
        ("empty.txt", "text/plain", b""),
        ("bad.txt", "text/plain", b"\xff\xfe"),
        ("mismatch.png", "application/pdf", b"\x89PNG\r\n\x1a\nrest"),
    ],
)
def test_upload_rejects_invalid_or_unsafe_content(name: str, media_type: str, payload: bytes) -> None:
    with pytest.raises(DocumentUploadError):
        validate_document_upload(name, media_type, payload)


def test_upload_normalizes_display_name_without_using_it_as_object_key() -> None:
    accepted = validate_document_upload("C:\\incoming\\帮助.PDF", "application/pdf", b"%PDF-1.7\nhello")
    assert accepted.filename == "帮助.PDF"
    assert accepted.name_key == "帮助.pdf"


def test_upload_limit_can_be_tightened_but_not_raised_by_runtime_configuration() -> None:
    payload = b"%PDF-1.7\nhello"
    with pytest.raises(DocumentUploadError):
        validate_document_upload("guide.pdf", "application/pdf", payload, max_bytes=8)
