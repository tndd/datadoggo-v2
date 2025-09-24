import hashlib
from datetime import datetime
from pathlib import Path

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
