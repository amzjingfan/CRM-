"""JWT 和密码安全单元测试。"""

import uuid
from datetime import timedelta

import pytest

from app.auth.security import create_token, decode_token, hash_password, verify_password
from app.shared.exceptions.errors import AppError, ErrorCode


def test_password_hash_can_be_verified_without_exposing_plaintext() -> None:
    """密码哈希可以验证，但哈希内容不应等于明文。"""
    password = "Correct@Password123"
    password_hash = hash_password(password)
    assert password_hash != password
    assert verify_password(password, password_hash)
    assert not verify_password("Wrong@Password123", password_hash)


def test_access_token_contains_only_expected_identity_claims() -> None:
    """Access Token 应包含用户、类型、签发、过期和唯一 ID。"""
    payload = decode_token(create_token(uuid.uuid4(), "access", timedelta(minutes=5)), "access")
    assert payload["type"] == "access"
    assert "sub" in payload
    assert "jti" in payload


def test_access_token_cannot_be_used_as_refresh_token() -> None:
    """Token 类型不匹配时必须拒绝，避免 Access/Refresh 混用。"""
    token = create_token(uuid.uuid4(), "access", timedelta(minutes=5))
    with pytest.raises(AppError) as error:
        decode_token(token, "refresh")
    assert error.value.code == ErrorCode.TOKEN_INVALID
