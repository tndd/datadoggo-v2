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


def normalize_parallel(parallel: bool | int, item_count: int) -> int:
    """並列実行時のワーカー数を決定する"""

    if not parallel:
        return 1

    if parallel is True:
        return max(1, item_count)

    if isinstance(parallel, int):
        if parallel <= 1:
            return 1
        return min(parallel, item_count)

    return 1


class TestMod:
    def test_is_safe_storage_key(self) -> None:
        """
        docs:
            目的: is_safe_storage_key の判定ロジックを確認する。
            検証観点:
                - 許可文字のみかつ長さ内のキーがTrueになる。
                - 禁止文字や長過ぎるキーはFalseになる。
        """

        assert is_safe_storage_key("abc-123")
        assert not is_safe_storage_key("abc/123")
        assert not is_safe_storage_key("", max_length=5)
        assert not is_safe_storage_key("a" * (DEFAULT_MAX_STORAGE_KEY_LENGTH + 1))

    def test_sanitize_storage_key(self) -> None:
        """
        docs:
            目的: sanitize_storage_key の正規化挙動を確認する。
            検証観点:
                - 安全なキーは入力をそのまま返す。
                - 危険なキーはハッシュ化された値を返す。
        """

        assert sanitize_storage_key(" safe_key ") == "safe_key"
        hashed = sanitize_storage_key("https://example.com/path?id=1")
        assert len(hashed) == SHA256_HEX_LENGTH

    def test_hash_text_sha256(self) -> None:
        """
        docs:
            目的: SHA256ハッシュ生成ヘルパーの正常性を確認する。
            検証観点:
                - 同じ文字列は同じハッシュになる。
                - 異なる文字列は異なるハッシュになる。
                - 出力は64文字の16進文字列である。
        """

        value = "https://example.com/feed"
        hashed = hash_text_sha256(value)
        assert len(hashed) == SHA256_HEX_LENGTH
        assert hashed == hash_text_sha256(value)
        assert hashed != hash_text_sha256(value + "#diff")
