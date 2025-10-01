"""キー検証/ハッシュ計算のテスト"""

from infra.compute import (
    DEFAULT_MAX_STORAGE_KEY_LENGTH,
    SHA256_HEX_LENGTH,
    hash_text_sha256,
    is_safe_storage_key,
    sanitize_storage_key,
)


def test_is_safe_storage_key() -> None:
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


def test_sanitize_storage_key() -> None:
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


def test_hash_text_sha256() -> None:
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
