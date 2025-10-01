"""Zstandard圧縮/解凍のテスト"""

from infra.compression import (
    compress_bytes_to_zstd,
    compress_text_to_zstd,
    decompress_zstd_to_bytes,
    decompress_zstd_to_text,
)


def test_compress_and_decompress_bytes() -> None:
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


def test_compress_and_decompress_text() -> None:
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
