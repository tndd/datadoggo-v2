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
