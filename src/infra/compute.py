"""ハッシュ計算ユーティリティ"""

import hashlib

SHA256_HEX_LENGTH = 64


def hash_text_sha256(value: str) -> str:
    """任意の文字列をSHA256でハッシュ化した16進文字列を返す"""

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class TestMod:
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
