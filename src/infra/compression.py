"""Zstandard圧縮/解凍ユーティリティ"""

import zstandard as zstd


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
