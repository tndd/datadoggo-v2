"""データ変換ユーティリティ (圧縮/ハッシュ)"""

import hashlib

import zstandard as zstd

SHA256_HEX_LENGTH = 64


# ==================== 圧縮/解凍 ====================


def compress_bytes_to_zstd(
    payload: bytes,
    *,
    level: int = 3,
) -> bytes:
    """バイト列をZstandardで圧縮する"""

    compressor = zstd.ZstdCompressor(level=level)
    return compressor.compress(payload)


def decompress_zstd_to_bytes(payload: bytes) -> bytes:
    """Zstandard圧縮済みのバイト列を展開する"""

    decompressor = zstd.ZstdDecompressor()
    return decompressor.decompress(payload)


def compress_text_to_zstd(
    content: str,
    *,
    level: int = 3,
    encoding: str = "utf-8",
) -> bytes:
    """テキストを指定エンコーディングでエンコードしてZstandard圧縮する"""

    return compress_bytes_to_zstd(content.encode(encoding), level=level)


def decompress_zstd_to_text(
    payload: bytes,
    *,
    encoding: str = "utf-8",
) -> str:
    """Zstandard圧縮済みデータを展開しテキストに復元する"""

    return decompress_zstd_to_bytes(payload).decode(encoding)


# ==================== ハッシュ計算 ====================


def hash_text_sha256(value: str) -> str:
    """任意の文字列をSHA256でハッシュ化した16進文字列を返す"""

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


# ==================== テスト ====================


class TestMod:
    def test_compress_and_decompress_bytes(self) -> None:
        """
        docs:
            目的: バイナリ圧縮/展開ユーティリティが無劣化で往復することを確認する。
            検証観点:
                - compress_bytes_to_zstd の出力が元サイズより小さくなることがある。
                - decompress_zstd_to_bytes が元データを復元できる。
        """

        payload = b"A" * 1024
        compressed = compress_bytes_to_zstd(payload)
        assert len(compressed) < len(payload)

        decompressed = decompress_zstd_to_bytes(compressed)
        assert decompressed == payload

    def test_compress_and_decompress_text(self) -> None:
        """
        docs:
            目的: テキストの圧縮/展開ヘルパーのエンコード処理を確認する。
            検証観点:
                - compress_text_to_zstd がバイト列を返す。
                - decompress_zstd_to_text で元テキストが復元される。
        """

        text = "圧縮対象のテキストデータ"
        compressed = compress_text_to_zstd(text, level=5)
        assert isinstance(compressed, bytes)

        restored = decompress_zstd_to_text(compressed)
        assert restored == text

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
