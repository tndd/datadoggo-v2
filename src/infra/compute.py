"""キー検証/ハッシュ計算ユーティリティ"""

import hashlib

SAFE_STORAGE_KEY_ALLOWED_CHARS = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
)
DEFAULT_MAX_STORAGE_KEY_LENGTH = 128
SHA256_HEX_LENGTH = 64


def is_safe_storage_key(
    value: str,
    *,
    max_length: int = DEFAULT_MAX_STORAGE_KEY_LENGTH,
) -> bool:
    """ファイルシステムで安全に扱えるキーかを判定する"""

    if not value or len(value) > max_length:
        return False

    return all(char in SAFE_STORAGE_KEY_ALLOWED_CHARS for char in value)


def sanitize_storage_key(
    value: str,
    *,
    max_length: int = DEFAULT_MAX_STORAGE_KEY_LENGTH,
) -> str:
    """ストレージキーを安全な形式に正規化する"""

    normalized = value.strip()
    if is_safe_storage_key(normalized, max_length=max_length):
        return normalized

    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def hash_text_sha256(value: str) -> str:
    """任意の文字列をSHA256でハッシュ化した16進文字列を返す"""

    return hashlib.sha256(value.encode("utf-8")).hexdigest()
