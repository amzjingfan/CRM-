"""TikTok OAuth 凭证的认证加密封装。"""

import base64
import hashlib

from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes

ENCRYPTED_PREFIX = "encrypted:v1:"
NONCE_BYTES = 12


def encrypt_credential(value: str, master_key: str, context: str) -> str:
    """AES-256-GCM 加密凭证，并用店铺与凭证类型绑定密文。"""
    key = hashlib.sha256(master_key.encode()).digest()
    cipher = AES.new(key, AES.MODE_GCM, nonce=get_random_bytes(NONCE_BYTES), mac_len=16)
    cipher.update(context.encode())
    ciphertext, tag = cipher.encrypt_and_digest(value.encode())
    payload = bytes(cipher.nonce) + tag + ciphertext
    encoded = base64.urlsafe_b64encode(payload).decode()
    return f"{ENCRYPTED_PREFIX}{encoded}"


def decrypt_credential(value: str, master_key: str, context: str) -> str:
    """验证并解密 OAuth 凭证；上下文不匹配或密文被篡改时必须失败。"""
    if not value.startswith(ENCRYPTED_PREFIX):
        raise ValueError("凭证不是受支持的加密格式")
    payload = base64.urlsafe_b64decode(value.removeprefix(ENCRYPTED_PREFIX).encode())
    if len(payload) <= NONCE_BYTES + 16:
        raise ValueError("凭证密文长度无效")
    nonce = payload[:NONCE_BYTES]
    tag = payload[NONCE_BYTES : NONCE_BYTES + 16]
    ciphertext = payload[NONCE_BYTES + 16 :]
    key = hashlib.sha256(master_key.encode()).digest()
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce, mac_len=16)
    cipher.update(context.encode())
    return cipher.decrypt_and_verify(ciphertext, tag).decode()
