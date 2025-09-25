import hashlib
from datetime import datetime
from pathlib import Path

import zstandard as zstd

SAFE_STORAGE_KEY_ALLOWED_CHARS = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
)
DEFAULT_MAX_STORAGE_KEY_LENGTH = 128
SHA256_HEX_LENGTH = 64


def generate_timestamp() -> str:
    """現在時刻からタイムスタンプ文字列を生成する (YYYYMMDD_HHMMSS)"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def generate_timestamped_filename(
    prefix: str = "out",
    suffix: str = "",
    extension: str = "txt",
    output_dir: str = "mock",
) -> str:
    """タイムスタンプ付きファイルパスを生成する"""
    timestamp = generate_timestamp()
    filename_parts = [prefix, timestamp]

    if suffix:
        filename_parts.append(suffix)

    filename = "_".join(filename_parts) + f".{extension}"
    return str(Path(output_dir) / filename)


def generate_timestamped_key(
    prefix: str = "content",
    suffix: str = "",
    extension: str = "html.zst",
) -> str:
    """タイムスタンプ付きオブジェクトキーを生成する"""
    timestamp = generate_timestamp()
    key_parts = [prefix, timestamp]

    if suffix:
        key_parts.append(suffix)

    return "_".join(key_parts) + f".{extension}"


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


class Tests:
    def test_generate_timestamp(self) -> None:
        """
        docs:
            目的: タイムスタンプ生成の正常性を確認する。
            検証観点:
                - YYYYMMDD_HHMMSS形式で生成される。
                - 15文字の長さである。
        """
        timestamp = generate_timestamp()
        TIMESTAMP_LENGTH = 15  # YYYYMMDD_HHMMSS
        assert len(timestamp) == TIMESTAMP_LENGTH
        assert "_" in timestamp
        # 基本的な日付形式チェック
        assert timestamp[:8].isdigit()  # YYYYMMDD
        assert timestamp[9:].isdigit()  # HHMMSS

    def test_generate_timestamped_filename(self) -> None:
        """
        docs:
            目的: タイムスタンプ付きファイル名生成の正常性を確認する。
            検証観点:
                - プレフィックス、サフィックス、拡張子が正しく反映される。
                - ディレクトリパスが正しく結合される。
        """
        # デフォルト
        filename = generate_timestamped_filename()
        assert filename.startswith("mock/out_")
        assert filename.endswith(".txt")

        # カスタム設定
        filename = generate_timestamped_filename(
            prefix="test", suffix="data", extension="html", output_dir="output"
        )
        assert filename.startswith("output/test_")
        assert "data" in filename
        assert filename.endswith(".html")

    def test_generate_timestamped_key(self) -> None:
        """
        docs:
            目的: タイムスタンプ付きオブジェクトキー生成の正常性を確認する。
            検証観点:
                - プレフィックス、サフィックス、拡張子が正しく反映される。
                - パス区切り文字が含まれない。
        """
        # デフォルト
        key = generate_timestamped_key()
        assert key.startswith("content_")
        assert key.endswith(".html.zst")
        assert "/" not in key

        # カスタム設定
        key = generate_timestamped_key(
            prefix="scrape", suffix="page", extension="json.gz"
        )
        assert key.startswith("scrape_")
        assert "page" in key
        assert key.endswith(".json.gz")

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
